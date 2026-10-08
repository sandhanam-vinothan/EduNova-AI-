import os,re,json,hashlib,secrets,datetime,asyncio
from pathlib import Path
from contextlib import asynccontextmanager
import httpx,pymupdf,jwt
from rapidfuzz import fuzz
from dotenv import load_dotenv
from fastapi import FastAPI,HTTPException,Depends,UploadFile,File,Request
from fastapi.responses import FileResponse,StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import create_engine,Column,Integer,String,Text,ForeignKey,DateTime,UniqueConstraint,select
from sqlalchemy.orm import declarative_base,sessionmaker,Session
from pwdlib import PasswordHash
load_dotenv()
BASE=Path(__file__).resolve().parent; DATA=BASE/'data';DATA.mkdir(exist_ok=True)
DB=os.getenv('DATABASE_URL','sqlite:///./edunova.db');DB=DB.replace('postgresql://','postgresql+psycopg://',1) if DB.startswith('postgresql://') else DB
engine=create_engine(DB,connect_args={'check_same_thread':False} if DB.startswith('sqlite') else {},pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine);BaseModelDB=declarative_base();ph=PasswordHash.recommended();auth=HTTPBearer(auto_error=False)
SECRET=os.getenv('SESSION_SECRET','development-only-change-this');PDF=Path(os.getenv('PDF_PATH',str(DATA/'textbook.pdf')))
if not PDF.is_absolute(): PDF=BASE/PDF
class User(BaseModelDB):
 __tablename__='users';id=Column(Integer,primary_key=True);name=Column(String(120));email=Column(String(255),unique=True,index=True);password=Column(String(255))
class Record(BaseModelDB):
 __tablename__='records';id=Column(Integer,primary_key=True);user_id=Column(Integer,ForeignKey('users.id'),index=True);kind=Column(String(30),index=True);payload=Column(Text);created=Column(DateTime,default=datetime.datetime.utcnow)
class Page(BaseModelDB):
 __tablename__='pages';id=Column(Integer,primary_key=True);number=Column(Integer,unique=True);printed=Column(String(40));content=Column(Text)
class Chat(BaseModelDB):
 __tablename__='chats';id=Column(Integer,primary_key=True);user_id=Column(Integer,ForeignKey('users.id'),index=True);role=Column(String(20));content=Column(Text);created=Column(DateTime,default=datetime.datetime.utcnow)
BaseModelDB.metadata.create_all(engine)
app=FastAPI(title='EduNova AI API')
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:5173').split(',')],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
def db():
 with SessionLocal() as s:yield s
def current(credentials:HTTPAuthorizationCredentials=Depends(auth),s:Session=Depends(db)):
 try:
  if not credentials:raise ValueError()
  payload=jwt.decode(credentials.credentials,SECRET,algorithms=['HS256']);u=s.get(User,int(payload['sub']))
  if not u:raise ValueError()
  return u
 except Exception:raise HTTPException(401,'Invalid or expired session')
class Credentials(BaseModel):email:str;password:str;name:str='Student'
class Item(BaseModel):kind:str;payload:dict
class Question(BaseModel):message:str;provider:str='ollama';mode:str='simple';history:list[dict]=[];page:int|None=None
@app.get('/api/health')
def health():return {'status':'ok','pdf':PDF.exists(),'provider':'ollama-cloud'}
@app.post('/api/auth/signup')
def signup(v:Credentials,s:Session=Depends(db)):
 if len(v.password)<8 or '@' not in v.email:raise HTTPException(400,'Valid email and password of 8+ characters required')
 if s.scalar(select(User).where(User.email==v.email.lower().strip())):raise HTTPException(409,'Email already registered')
 u=User(name=v.name[:120],email=v.email.lower().strip(),password=ph.hash(v.password));s.add(u);s.commit();s.refresh(u);return issue(u)
def issue(u):return {'token':jwt.encode({'sub':str(u.id),'exp':datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=7)},SECRET,algorithm='HS256'),'user':{'id':u.id,'name':u.name,'email':u.email}}
@app.post('/api/auth/login')
def login(v:Credentials,s:Session=Depends(db)):
 u=s.scalar(select(User).where(User.email==v.email.lower().strip()))
 if not u or not ph.verify(v.password,u.password):raise HTTPException(401,'Incorrect credentials')
 return issue(u)
@app.get('/api/me')
def me(u:User=Depends(current)):return {'id':u.id,'name':u.name,'email':u.email}
@app.put('/api/me')
def update_me(v:dict,u:User=Depends(current),s:Session=Depends(db)):
 if 'name' in v:u.name=str(v['name'])[:120]
 if v.get('password'):
  if len(v['password'])<8:raise HTTPException(400,'Password too short')
  u.password=ph.hash(v['password'])
 s.add(u);s.commit();return {'ok':True}
@app.get('/api/records')
def records(kind:str|None=None,u:User=Depends(current),s:Session=Depends(db)):
 q=select(Record).where(Record.user_id==u.id)
 if kind:q=q.where(Record.kind==kind)
 return [{'id':x.id,'kind':x.kind,'payload':json.loads(x.payload),'created':x.created.isoformat()} for x in s.scalars(q.order_by(Record.id.desc()).limit(500))]
@app.post('/api/records')
def save(v:Item,u:User=Depends(current),s:Session=Depends(db)):
 if v.kind not in ('bookmark','highlight','progress','score','note'):raise HTTPException(400,'Invalid kind')
 x=Record(user_id=u.id,kind=v.kind,payload=json.dumps(v.payload));s.add(x);s.commit();return {'id':x.id}
@app.delete('/api/records/{id}')
def delete(id:int,u:User=Depends(current),s:Session=Depends(db)):
 x=s.get(Record,id)
 if not x or x.user_id!=u.id:raise HTTPException(404)
 s.delete(x);s.commit();return {'ok':True}
def index_pdf():
 if not PDF.exists():return 0
 d=pymupdf.open(PDF)
 with SessionLocal() as s:
  s.query(Page).delete()
  for i,page in enumerate(d):
   t=page.get_text(sort=True);lines=[x.strip() for x in t.splitlines() if x.strip()];printed=str(i-5) if i>=6 else ['I','II','III','IV','V','VI'][i]
   s.add(Page(number=i+1,printed=printed,content=t))
  s.commit()
 return len(d)
@app.on_event('startup')
def initialize_textbook():
 with SessionLocal() as session:
  has_pages=session.query(Page.id).first() is not None
 if PDF.exists() and not has_pages:
  index_pdf()

@app.post('/api/book/index')
def index(u:User=Depends(current)):return {'pages':index_pdf()}
@app.post('/api/book/upload')
async def upload(file:UploadFile=File(...),u:User=Depends(current)):
 if os.getenv('ENABLE_TEXTBOOK_UPLOAD','false').lower()!='true':raise HTTPException(403,'Textbook upload disabled on this deployment')
 if file.content_type!='application/pdf' and not file.filename.lower().endswith('.pdf'):raise HTTPException(400,'PDF required')
 data=await file.read(35*1024*1024+1)
 if len(data)>35*1024*1024 or not data.startswith(b'%PDF'):raise HTTPException(400,'Invalid or oversized PDF (max 35 MB)')
 PDF.parent.mkdir(parents=True,exist_ok=True);PDF.write_bytes(data)
 try:return {'pages':index_pdf()}
 except Exception as e:raise HTTPException(400,f'PDF indexing failed: {e}')
@app.get('/api/book/pdf')
def pdf():
 if not PDF.exists():raise HTTPException(404,'Upload the textbook first')
 return FileResponse(PDF,media_type='application/pdf',headers={'Cache-Control':'no-store'})
@app.get('/api/book/pages')
def pages(s:Session=Depends(db)):return {'count':s.query(Page).count(),'pdf':PDF.exists()}
@app.get('/api/book/search')
def search(q:str,s:Session=Depends(db)):
 if not q.strip():return []
 q=q.strip()[:500];results=[]
 for x in s.scalars(select(Page)):
  text=' '.join(x.content.split());pos=text.lower().find(q.lower());score=100 if pos>=0 else fuzz.partial_ratio(q.lower(),text.lower())
  if score>=65:
   if pos<0:
    words=text.split();best=max(((' '.join(words[i:i+max(8,len(q.split()))]),i) for i in range(0,len(words),max(1,len(q.split())//2))),key=lambda t:fuzz.ratio(q.lower(),t[0].lower()),default=('',0));snippet=best[0]
   else:snippet=text[max(0,pos-70):pos+len(q)+100]
   results.append({'page':x.number,'printed':x.printed,'score':round(score,1),'snippet':snippet})
 return sorted(results,key=lambda x:-x['score'])[:15]
@app.get('/api/book/chapters')
def chapters(s:Session=Depends(db)):
 out=[]
 for x in s.scalars(select(Page)):
  for line in x.content.splitlines():
   line=line.strip()
   if re.match(r'^(?:CHAPTER|Chapter|UNIT|Unit)\s*[-:]?\s*\d+',line) and len(line)<120:out.append({'title':line,'page':x.number})
 return out[:100]
@app.get('/api/chat/history')
def history(u:User=Depends(current),s:Session=Depends(db)):
 return [{'id':x.id,'role':x.role,'content':x.content,'created':x.created.isoformat()} for x in s.scalars(select(Chat).where(Chat.user_id==u.id).order_by(Chat.id.desc()).limit(100))][::-1]
async def generate(provider, messages):
    """Generate with Gemini or Ollama Cloud. Never send API keys to the frontend."""
    if provider == 'gemini':
        key = os.getenv('GEMINI_API_KEY', '').strip()
        model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash').strip()
        if not key:
            raise RuntimeError('Gemini API key is not configured')
        instructions = '\n'.join(m['content'] for m in messages if m['role'] == 'system')
        contents = [{'role': 'model' if m['role'] == 'assistant' else 'user',
                     'parts': [{'text': m['content']}]}
                    for m in messages if m['role'] in ('user', 'assistant')]
        payload = {'systemInstruction': {'parts': [{'text': instructions}]}, 'contents': contents}
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                headers={'x-goog-api-key': key}, json=payload)
            if response.status_code >= 400:
                raise RuntimeError(f'Gemini HTTP {response.status_code}')
            data = response.json()
            candidates = data.get('candidates') or []
            if not candidates:
                raise RuntimeError('Gemini returned no candidates')
            answer = ''.join(part.get('text', '') for part in candidates[0].get('content', {}).get('parts', []))
            if not answer.strip():
                raise RuntimeError('Gemini returned an empty response')
            return answer.strip()
    if provider == 'ollama':
        key = os.getenv('OLLAMA_API_KEY', '').strip()
        model = os.getenv('OLLAMA_MODEL', 'gemma4:31b').strip()
        if not key:
            raise RuntimeError('Ollama Cloud API key is not configured')
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post('https://ollama.com/api/chat',
                headers={'Authorization': f'Bearer {key}'},
                json={'model': model, 'messages': messages, 'stream': False})
            if response.status_code >= 400:
                raise RuntimeError(f'Ollama Cloud HTTP {response.status_code}')
            answer = response.json().get('message', {}).get('content', '').strip()
            if not answer:
                raise RuntimeError('Ollama Cloud returned an empty response')
            return answer
    raise RuntimeError('Unsupported AI provider')

@app.post('/api/chat')
async def chat(v:Question,u:User=Depends(current),s:Session=Depends(db)):
    if not v.message.strip():
        raise HTTPException(400,'Question required')
    if len(v.message)>12000:
        raise HTTPException(400,'Question too long')
    pages=list(s.scalars(select(Page)))
    ranked=sorted(pages,key=lambda p:fuzz.partial_ratio(v.message.lower(),p.content.lower()) if p.content else 0,reverse=True)
    if v.page:
        ranked=sorted(ranked,key=lambda p:0 if p.number==v.page else 1)
    context='\n\n'.join(f'[PDF page {p.number}; printed page {p.printed}] {p.content[:2500]}' for p in ranked[:3])
    modes={'simple':'Explain in simple language','detailed':'Explain step by step','textbook':'Give a textbook-grounded answer','2marks':'Answer concisely for 2 marks','3marks':'Answer for 3 marks','5marks':'Answer for 5 marks'}
    system=('You are EduNova AI, a Tamil Nadu Class 12 Computer Science tutor. '
            +modes.get(v.mode,modes['simple'])+'. Use textbook excerpts when relevant and cite only pages that directly support your statements. '
            'If the provided excerpts do not answer the question, still explain using general knowledge, clearly label it as a general explanation, and do not invent textbook references. '
            'For textbook mode, distinguish textbook-supported facts from supplementary knowledge.\nTEXTBOOK CONTEXT:\n'
            +(context or 'No indexed textbook is available.'))
    messages=[{'role':'system','content':system}]+[{'role':m.get('role','user'),'content':str(m.get('content',''))[:4000]} for m in v.history[-8:] if m.get('role') in ('user','assistant')]+[{'role':'user','content':v.message}]
    selected=v.provider if v.provider in ('gemini','ollama','auto') else 'auto'
    order=['gemini','ollama'] if selected=='auto' else [selected]
    errors=[]
    for provider in order:
        try:
            answer=await generate(provider,messages)
            for role,content in [('user',v.message),('assistant',answer)]:
                s.add(Chat(user_id=u.id,role=role,content=content))
            s.commit()
            return {'answer':answer,'provider':provider,'references':[{'pdf_page':p.number,'printed_page':p.printed} for p in ranked[:3]] if pages else []}
        except (httpx.HTTPError, RuntimeError, KeyError, ValueError, IndexError) as e:
            import logging
            logging.exception('AI provider %s failed',provider)
            # Only show safe status codes; no provider response body or credentials.
            errors.append(f'{provider}: {str(e) if isinstance(e,RuntimeError) else type(e).__name__}')
    raise HTTPException(503,'AI unavailable: '+', '.join(errors)+'. Check Render provider configuration and usage limits.')
@app.get('/api/practice')
def practice(s:Session=Depends(db)):
 pages=list(s.scalars(select(Page).limit(30)));out=[]
 for p in pages:
  lines=[x.strip() for x in p.content.splitlines() if 30<len(x.strip())<180]
  if lines:
   line=lines[0];out.append({'page':p.number,'question':'Which statement appears on PDF page '+str(p.number)+'?','options':[line[:115],'None of the above','All chapters are identical','The page contains no text'],'correct':0})
 return out[:20]

# Serve the compiled React application from the same Render web service.
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
DIST=BASE.parent/'frontend'/'dist'
if DIST.exists():
 app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
 @app.get('/{full_path:path}',include_in_schema=False)
 def spa(full_path:str):
  requested=(DIST/full_path).resolve()
  if full_path and requested.is_file() and DIST.resolve() in requested.parents:
   return FileResponse(requested)
  return FileResponse(DIST/'index.html')
