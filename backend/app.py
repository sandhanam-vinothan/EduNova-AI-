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

from sqlalchemy import create_engine,Column,Integer,String,Text,ForeignKey,DateTime,UniqueConstraint,select,inspect,text

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

 __tablename__='chats';id=Column(Integer,primary_key=True);user_id=Column(Integer,ForeignKey('users.id'),index=True);role=Column(String(20));content=Column(Text);model=Column(String(160),nullable=True);created=Column(DateTime,default=datetime.datetime.utcnow)

BaseModelDB.metadata.create_all(engine)
# Existing databases need the nullable column; old history remains valid.
if 'model' not in {c['name'] for c in inspect(engine).get_columns('chats')}:
 with engine.begin() as conn:conn.execute(text('ALTER TABLE chats ADD COLUMN model VARCHAR(160)'))

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

 # Some textbook chapter title headings are embedded as graphics. The searchable
 # PDF still includes its chapter number in the page footer (e.g. Chapter 2.indd).
 # Supply the missing chapter to the frontend without changing existing entries.
 if not any(re.search(r'(?i)\b(?:chapter|unit)\s*[-:]?\s*0*2\b', x['title']) for x in out):
  for p in s.scalars(select(Page).order_by(Page.number)):
   if re.search(r'(?i)\bChapter\s*0*2\s*\.indd\b', p.content or ''):
    out.append({'title':'Chapter 2 - Data Abstraction','page':p.number})
    break
 return out[:100]

@app.delete('/api/chat/history')

def clear_chat_history(u:User=Depends(current),s:Session=Depends(db)):

    from sqlalchemy import delete

    s.execute(delete(Chat).where(Chat.user_id==u.id))

    s.commit()

    return {'ok': True}



@app.get('/api/chat/history')

def history(u:User=Depends(current),s:Session=Depends(db)):

 return [{'id':x.id,'role':x.role,'content':x.content,'model':x.model,'created':x.created.isoformat()} for x in s.scalars(select(Chat).where(Chat.user_id==u.id).order_by(Chat.id.desc()).limit(100))][::-1]

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

        # Include neighboring textbook pages for a chapter revision request.
        # Keep normal chat behavior for non-revision questions.
        if 'revision notes' in v.message.lower():
            nearby=[p for p in pages if v.page<=p.number<=v.page+2]
            ranked=nearby+ [p for p in ranked if p.number not in {q.number for q in nearby}]
        else:
            ranked=sorted(ranked,key=lambda p:0 if p.number==v.page else 1)

    context='\n\n'.join(f'[PDF page {p.number}; printed page {p.printed}] {p.content[:2500]}' for p in ranked[:3])

    modes={'simple':'Explain in simple language','detailed':'Explain step by step','textbook':'Give a textbook-grounded answer','2marks':'Answer concisely for 2 marks','3marks':'Answer for 3 marks','5marks':'Answer for 5 marks'}

    system=('You are EduNova AI, a Tamil Nadu Class 12 Computer Science tutor. '

            +modes.get(v.mode,modes['simple'])+'. Use textbook excerpts when relevant and cite only pages that directly support your statements. '

            'STRICT SCOPE: Answer only questions about the Tamil Nadu Class 12 Computer Science syllabus and its related computing concepts. If the user asks about an unrelated topic (e.g. economics, geography, movies), reply with EXACTLY one short sentence: This question is outside the Class 12 Computer Science textbook. Do not give an explanation, greeting, citations, or extra lines for out-of-scope questions. If a question is relevant to computer science but the excerpts are insufficient, explain from general computer science knowledge without inventing textbook references. '

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

                s.add(Chat(user_id=u.id,role=role,content=content,model=(os.getenv('GEMINI_MODEL','gemini-2.5-flash').strip() if provider=='gemini' else os.getenv('OLLAMA_MODEL','gemma4:31b').strip()) if role=='assistant' else None))

            s.commit()

            return {'answer':answer,'provider':provider,'model':os.getenv('GEMINI_MODEL','gemini-2.5-flash').strip() if provider=='gemini' else os.getenv('OLLAMA_MODEL','gemma4:31b').strip(),'references':[{'pdf_page':p.number,'printed_page':p.printed} for p in ranked[:3]] if pages else []}

        except (httpx.HTTPError, RuntimeError, KeyError, ValueError, IndexError) as e:

            import logging

            logging.exception('AI provider %s failed',provider)

            # Only show safe status codes; no provider response body or credentials.

            errors.append(f'{provider}: {str(e) if isinstance(e,RuntimeError) else type(e).__name__}')

    raise HTTPException(503,'AI unavailable: '+', '.join(errors)+'. Check Render provider configuration and usage limits.')

def chapter_pages(s:Session, chapter:int):
    """Find the actual chapter heading and bound the content by the next heading."""
    all_pages=list(s.scalars(select(Page).order_by(Page.number)))
    if not all_pages:
        return [], 'The textbook has not been indexed yet.'
    # Require a heading near the beginning of a page, not a TOC listing or review question.
    headings=[]
    heading_pattern=re.compile(r'(?im)^\s*(?:chapter|unit)\s*[-:.]?\s*0?([1-9]|1[0-6])\b[^\n]{0,90}$')
    for p in all_pages:
        lines=p.content.splitlines()
        for i,line in enumerate(lines[:28]):
            match=heading_pattern.match(line)
            if match:
                headings.append((p.number,int(match.group(1)),line.strip()))
                break
    # TOC chapter listings typically cluster together; prefer the last occurrence
    # before the next chapter's heading, and avoid treating the TOC as chapter content.
    candidates=[(page,title) for page,num,title in headings if num==chapter]
    if not candidates:
        # Some PDF chapter headings are graphical, but the text footer contains
        # 'Chapter N.indd'. Detect a consecutive run of those indexed pages.
        footer=re.compile(r'(?i)\bChapter\s*0*'+str(chapter)+r'\s*\.indd\b')
        matches=[p for p in all_pages if footer.search(p.content or '')]
        if matches:
            # The footer is present on every page of the chapter, including
            # the first page, and remains searchable after PDF indexing.
            first=matches[0].number
            last=matches[-1].number
            chosen=[p for p in all_pages if first<=p.number<=last]
            return chosen, ('Chapter 2 - Data Abstraction' if chapter==2 else f'Chapter {chapter}')
        return [], f'Chapter {chapter} heading was not found in the indexed textbook. Check whether this chapter was indexed.'
    selected=None
    for page,title in candidates:
        next_head=next(((p,n) for p,n,_ in headings if p>page and n==chapter+1),None)
        if next_head and next_head[0]-page>=2:
            selected=(page,next_head[0],title)
    if selected is None:
        page,title=candidates[-1]
        following=[p for p,n,_ in headings if p>page and n!=chapter]
        stop=min(following) if following else all_pages[-1].number+1
        selected=(page,stop,title)
    first,last,title=selected
    chosen=[p for p in all_pages if first<=p.number<last]
    if not chosen:
        return [], f'No indexed content found for Chapter {chapter}.'
    return chosen, title

@app.get('/api/practice')
async def practice(chapter:int=1,provider:str='auto',u:User=Depends(current),s:Session=Depends(db)):
    if not 1<=chapter<=16:
        raise HTTPException(400,'Choose a chapter from 1 to 16')
    selected,title=chapter_pages(s,chapter)
    if not selected:
        return {'chapter':chapter,'questions':[],'message':title}
    # Limit the request size but sample across the entire chapter.
    stride=max(1,len(selected)//12)
    sampled=selected[::stride][:12]
    context='\n\n'.join(f'[PDF page {p.number}] {p.content[:2600]}' for p in sampled)
    if len(context.strip())<350:
        return {'chapter':chapter,'questions':[],'message':'Not enough readable chapter text to create a grounded quiz.'}
    instruction=(
        'Create exactly 5 distinct, accurate multiple-choice practice questions based ONLY on '
        f'Chapter {chapter} of a Tamil Nadu Class 12 Computer Science textbook. '
        'Use the supplied textbook excerpts as the sole source of facts. '
        'Do not use outside knowledge, invent topics, or ask which sentence appears on a page. '
        'Return ONLY a JSON object with a "questions" array. Each question must contain '
        '"question" (string), "options" (array of exactly four distinct answer strings), '
        '"correct" (zero-based integer 0 to 3), and "explanation" (one concise sentence). '
        'Make every distractor plausible but unambiguously wrong. Do not include markdown fences. '
        'If the excerpts do not support five reliable questions, return fewer questions.\n\n'
        'TEXTBOOK EXCERPTS:\n'+context
    )
    order=['gemini','ollama'] if provider=='auto' else [provider] if provider in ('gemini','ollama') else ['gemini','ollama']
    errors=[]
    for model in order:
        try:
            raw=await generate(model,[{'role':'system','content':'You generate textbook-grounded quizzes as valid JSON only.'},{'role':'user','content':instruction}])
            raw=raw.strip()
            if raw.startswith('```'):
                raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw,flags=re.I).strip()
            data=json.loads(raw)
            items=data.get('questions',[]) if isinstance(data,dict) else []
            valid=[]
            for item in items[:5]:
                if not isinstance(item,dict):continue
                q=item.get('question');options=item.get('options');correct=item.get('correct');explanation=item.get('explanation','')
                if (isinstance(q,str) and len(q.strip())>=12 and isinstance(options,list) and len(options)==4
                    and all(isinstance(o,str) and o.strip() for o in options)
                    and len(set(o.strip().lower() for o in options))==4
                    and type(correct)==int and 0<=correct<4):
                    valid.append({'question':q.strip(),'options':[o.strip() for o in options],
                                  'correct':correct,'explanation':str(explanation)[:600]})
            if valid:
                return {'chapter':chapter,'title':title,'questions':valid,'provider':model}
            errors.append(model+': no valid questions')
        except (httpx.HTTPError,RuntimeError,ValueError,KeyError,TypeError) as e:
            import logging
            logging.exception('Practice quiz provider %s failed',model)
            errors.append(model+': '+(str(e) if isinstance(e,RuntimeError) else type(e).__name__))
    raise HTTPException(503,'Could not generate the chapter quiz. '+', '.join(errors))

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
