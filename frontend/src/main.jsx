import React,{useState,useEffect,useRef} from 'react';import{createRoot}from'react-dom/client';import{motion}from'framer-motion';import{BookOpen,LayoutDashboard,MessageCircle,Search,Bookmark,History,BarChart3,Settings,User,Layers,GraduationCap,LogOut,Send,Upload,ChevronLeft,ChevronRight,ZoomIn,ZoomOut,Moon,Sun,Copy,Highlighter,Eye,EyeOff,Trash2}from'lucide-react';import * as pdfjs from 'pdfjs-dist';import worker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';import './style.css';pdfjs.GlobalWorkerOptions.workerSrc=worker;
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';


const names=['Dashboard','AI Chatbot','Textbook Reader','Find Book Line','Quick Revision','Practice Questions','Bookmarks','Chat History','Learning Progress','Profile','Settings'];const icons=[LayoutDashboard,MessageCircle,BookOpen,Search,Layers,GraduationCap,Bookmark,History,BarChart3,User,Settings];const colors=['#4f46e5','#0284c7','#0d9488','#16a34a','#d97706','#db2777','#7c3aed'];



function App(){const [token,setToken]=useState(localStorage.getItem('edu_token')||'');const[user,setUser]=useState(JSON.parse(localStorage.getItem('edu_user')||'null'));const[tab,setTab]=useState('Dashboard');const[dark,setDark]=useState(localStorage.getItem('edu_dark')==='1');const[accent,setAccent]=useState(localStorage.getItem('edu_accent')||colors[0]);const[error,setError]=useState('');const[busy,setBusy]=useState(false);const[records,setRecords]=useState([]);const[chats,setChats]=useState([]);const[pages,setPages]=useState({count:0,pdf:false});const[chapters,setChapters]=useState([]);const[question,setQuestion]=useState('');const[mode,setMode]=useState('simple');const[provider,setProvider]=useState('auto');const[search,setSearch]=useState('');const[results,setResults]=useState([]);const[page,setPage]=useState(1);const[selection,setSelection]=useState('');const[revisionChapter,setRevisionChapter]=useState('1');const[revisionNotes,setRevisionNotes]=useState('');const[revisionBusy,setRevisionBusy]=useState(false);const[quiz,setQuiz]=useState([]);const[quizChapter,setQuizChapter]=useState("1");const[quizBusy,setQuizBusy]=useState(false);const[quizSubmitted,setQuizSubmitted]=useState(false);const[quizSaved,setQuizSaved]=useState(false);const[answers,setAnswers]=useState({});const [showPassword,setShowPassword]=useState(false);const messagesEndRef=useRef(null);const [loginMode,setLoginMode]=useState('login');const [form,setForm]=useState({name:'',email:'',password:''});



const api=async(path,opts={})=>{const r=await fetch('/api'+path,{...opts,headers:{...(opts.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(token?{Authorization:'Bearer '+token}:{}),...opts.headers}});let d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||'Request failed');return d};



const refresh=()=>{if(!token)return;Promise.all([api('/records'),api('/chat/history'),api('/book/pages'),api('/book/chapters')]).then(([r,c,p,ch])=>{setRecords(r);setChats(c);setPages(p);setChapters(ch)}).catch(e=>setError(e.message))};useEffect(refresh,[token]);useEffect(()=>{document.documentElement.style.setProperty('--accent',accent);document.documentElement.classList.toggle('dark',dark);localStorage.setItem('edu_dark',dark?'1':'0');localStorage.setItem('edu_accent',accent)},[dark,accent]);



useEffect(()=>{if(tab==='AI Chatbot')messagesEndRef.current?.scrollTo({top:messagesEndRef.current.scrollHeight,behavior:'smooth'})},[chats,tab,busy]);



const clearChats=async()=>{if(!window.confirm('Clear all your saved chat history? This cannot be undone.'))return;try{await api('/chat/history',{method:'DELETE'});setChats([]);setError('')}catch(e){setError(e.message)}};



const submitAuth=async(e)=>{e.preventDefault();setError('');try{let d=await api('/auth/'+(loginMode==='login'?'login':'signup'),{method:'POST',body:JSON.stringify(form)});localStorage.setItem('edu_token',d.token);localStorage.setItem('edu_user',JSON.stringify(d.user));setToken(d.token);setUser(d.user)}catch(e){setError(e.message)}};



const save=async(kind,payload)=>{try{await api('/records',{method:'POST',body:JSON.stringify({kind,payload})});refresh()}catch(e){setError(e.message)}};



const ask=async(text=question)=>{if(!text.trim())return;setBusy(true);setError('');try{let r=await api('/chat',{method:'POST',body:JSON.stringify({message:text,provider,mode,page,history:chats.slice(-8)})});setChats(v=>[...v,{role:'user',content:text},{role:'assistant',content:r.answer}]);setQuestion('');setTab('AI Chatbot')}catch(e){setError(e.message)}finally{setBusy(false)}};



const find=async()=>{try{setResults(await api('/book/search?q='+encodeURIComponent(search)))}catch(e){setError(e.message)}};



const revisionChapterInfo=Array.from({length:16},(_,i)=>{const number=i+1;const matched=chapters.find(c=>new RegExp('(?:chapter|unit)\\s*[-:]?\\s*0*'+number+'(?!\\d)','i').test(c.title));return {number,title:matched?.title||'Chapter '+number,page:matched?.page||null}});

 const generateRevision=async()=>{const selected=revisionChapterInfo.find(c=>String(c.number)===revisionChapter);if(!selected)return;setRevisionBusy(true);setRevisionNotes('');setError('');try{const prompt='Prepare concise, student-friendly revision notes ONLY for Chapter '+selected.number+' ('+selected.title+') of the Tamil Nadu Class 12 Computer Science textbook. Include key definitions, main concepts, and important exam points. Do not cover other chapters. If the provided textbook excerpts do not establish the chapter content, say that clearly rather than inventing notes or page citations.';const r=await api('/chat',{method:'POST',body:JSON.stringify({message:prompt,provider,mode:'textbook',page:selected.page,history:[]})});setRevisionNotes(r.answer)}catch(e){setError(e.message)}finally{setRevisionBusy(false)}};

 const upload=async(f)=>{if(!f)return;setBusy(true);try{const fd=new FormData();fd.append('file',f);await api('/book/upload',{method:'POST',body:fd});refresh();setPage(1)}catch(e){setError(e.message)}finally{setBusy(false)}};



const logout=()=>{localStorage.removeItem('edu_token');localStorage.removeItem('edu_user');setToken('');setUser(null);setChats([]);setRecords([])};



if(!token)return <main className="auth"><motion.form initial={{opacity:0,y:20}} animate={{opacity:1,y:0}} className="authbox" onSubmit={submitAuth}><div className="logo"><GraduationCap/> EduNova AI</div><h1>Learn Smarter. Explore Deeper.</h1><p>Your Class 12 Computer Science study companion</p>{loginMode==='signup'&&<input placeholder="Your name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})} required/>}<input type="email" placeholder="Email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} required/><div className="password-wrap"><input type={showPassword?"text":"password"} placeholder="Password (8+ characters)" value={form.password} onChange={e=>setForm({...form,password:e.target.value})} required/><button type="button" className="password-eye" aria-label={showPassword?"Hide password":"Show password"} onClick={()=>setShowPassword(v=>!v)}>{showPassword?<EyeOff size={19}/>:<Eye size={19}/>}</button></div><button>{loginMode==='login'?'Sign in':'Create account'}</button><p className="link" onClick={()=>setLoginMode(loginMode==='login'?'signup':'login')}>{loginMode==='login'?'New student? Sign up':'Already registered? Sign in'}</p>{error&&<p className="error">{error}</p>}</motion.form></main>;



const nav=names.map((n,i)=>{const Icon=icons[i];return <button key={n} className={'nav '+(tab===n?'active':'')} onClick={()=>setTab(n)}><Icon size={19}/><span>{n}</span></button>});



return <div className="shell"><aside><div className="logo"><GraduationCap/> EduNova AI</div><nav>{nav}</nav><button className="nav" onClick={logout}><LogOut size={19}/> Sign out</button></aside><div className="main"><header><div><strong>{tab}</strong><small>Learn Smarter. Explore Deeper.</small></div><div className="headright"><button className="iconbtn" onClick={()=>setDark(!dark)}>{dark?<Sun/>:<Moon/>}</button><span className="avatar">{user?.name?.[0]?.toUpperCase()||'S'}</span></div></header>{error&&<div className="error banner" onClick={()=>setError('')}>{error} ×</div>}<motion.section key={tab} initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} className="content">



{tab==='Dashboard'&&<><div className="hero"><h1>Welcome back, {user?.name} 👋</h1><p>Continue exploring Computer Science with your AI study companion.</p><button onClick={()=>setTab('Textbook Reader')}>Open textbook →</button></div><div className="stats"><article><BookOpen/> <b>{pages.count}</b><small>Indexed PDF pages</small></article><article><Bookmark/><b>{records.filter(x=>x.kind==='bookmark').length}</b><small>Bookmarks</small></article><article><MessageCircle/><b>{chats.filter(x=>x.role==='user').length}</b><small>AI questions</small></article><article><BarChart3/><b>{records.filter(x=>x.kind==='score').length}</b><small>Practice attempts</small></article></div><div className="grid2"><article><h3>Study with AI</h3><p>Get simple, detailed, or exam-focused explanations.</p><button onClick={()=>setTab('AI Chatbot')}>Ask AI</button></article><article><h3>Find a textbook line</h3><p>Locate passages using exact or fuzzy matching.</p><button onClick={()=>setTab('Find Book Line')}>Search textbook</button></article></div></>}



{tab==='AI Chatbot'&&<div className="panel"><div className="toolbar"><select aria-label="AI provider" value={provider} onChange={e=>setProvider(e.target.value)}><option value="auto">Auto AI (Gemini → Ollama)</option><option value="gemini">Gemini</option><option value="ollama">Ollama Cloud</option></select><select value={mode} onChange={e=>setMode(e.target.value)}>{[['simple','Simple Explanation'],['detailed','Detailed Explanation'],['textbook','Textbook Answer'],['2marks','2 Marks'],['3marks','3 Marks'],['5marks','5 Marks']].map(([v,n])=><option value={v}>{n}</option>)}</select><button type="button" className="clear-chat" onClick={clearChats} disabled={!chats.length||busy}><Trash2 size={16}/> Clear chat</button></div><div className="messages" ref={messagesEndRef}>{!chats.length&&<p className="muted">Ask a question about Class 12 Computer Science. Upload your textbook to enable grounded references.</p>}{chats.map((m,i)=><div className={'bubble '+m.role} key={i}><small>{m.role==='user'?'You':'EduNova AI'}</small><p>{m.content}</p></div>)}</div><form className="ask" onSubmit={e=>{e.preventDefault();ask()}}><input value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Ask anything about your textbook..."/><button disabled={busy}><Send size={18}/>{busy?'Thinking...':'Send'}</button></form></div>}



{tab==='Textbook Reader'&&<div className="panel"><div className="toolbar"><label className="upload"><Upload size={17}/> Upload textbook PDF<input type="file" accept="application/pdf" hidden onChange={e=>upload(e.target.files[0])}/></label><button onClick={()=>save('bookmark',{page})}><Bookmark size={17}/> Bookmark</button><button onClick={()=>save('progress',{page})}>Save progress</button><select onChange={e=>setPage(Number(e.target.value))} value={page}><option value={page}>Page {page}</option>{chapters.map((x,i)=><option key={i} value={x.page}>{x.title.slice(0,45)}</option>)}</select></div>{pages.pdf?<Reader page={page} setPage={setPage} total={pages.count} onSelection={setSelection}/>:<div className="empty">Upload your original Class 12 Computer Science PDF to begin reading.</div>}{selection&&<div className="selection"><span>{selection.slice(0,90)}…</span><button onClick={()=>navigator.clipboard.writeText(selection)}><Copy size={15}/> Copy</button><button onClick={()=>save('highlight',{page,text:selection})}><Highlighter size={15}/> Highlight</button><button onClick={()=>ask('Explain simply: '+selection)}>Explain</button><button onClick={()=>ask(selection)}>Ask AI</button><button onClick={()=>ask('Translate to Tamil: '+selection)}>Translate</button><button onClick={()=>ask('Write a 5-mark exam answer about: '+selection)}>Exam answer</button></div>}</div>}



{tab==='Find Book Line'&&<div className="panel"><h2>Find any textbook line</h2><div className="ask"><input value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>e.key==='Enter'&&find()} placeholder="Paste a sentence from your textbook"/><button onClick={find}><Search size={17}/> Find</button></div>{results.filter(r=>Number(r.score)>=90).map((r,i)=><article className="result" key={i} onClick={()=>{setPage(r.page);setTab('Textbook Reader');sessionStorage.setItem('edu_highlight',search)}}><b>PDF page {r.page} · Printed page {r.printed}</b><small>Match {r.score}%</small><p>{r.snippet}</p></article>)}{results.length>0&&!results.some(r=>Number(r.score)>=90)&&<p className="muted">No textbook lines found with 90% or higher similarity. Try a more specific search.</p>}</div>}



{tab==='Quick Revision'&&
  <div className="panel">
    <h2>Quick Revision</h2>
    <p>Select a chapter to generate revision notes on this page.</p>

    <div className="actions">
      <select
        aria-label="Choose chapter"
        value={revisionChapter}
        onChange={e=>{
          setRevisionChapter(e.target.value);
          setRevisionNotes('');
        }}
      >
        {revisionChapterInfo.map(c=>
          <option key={c.number} value={String(c.number)}>
            {c.title}
          </option>
        )}
      </select>

      <button onClick={generateRevision} disabled={revisionBusy}>
        {revisionBusy?'Generating notes...':'Generate Notes'}
      </button>
    </div>

    {revisionBusy&&
      <p className="muted" role="status">
        Preparing chapter revision notes...
      </p>
    }

    {revisionNotes&&
      <article className="result" style={{marginTop:24}}>
        <h3>Chapter {revisionChapter} — Revision Notes</h3>

        <div className="markdown-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {revisionNotes}
          </ReactMarkdown>
        </div>
      </article>
    }
  </div>
}


 {tab==='Practice Questions'&&<div className="panel"><h2>Practice Questions</h2><p>Select a chapter and take a multiple-choice quiz from its textbook content. Your questions and results stay on this page.</p><div className="actions"><select aria-label="Practice chapter" value={quizChapter} onChange={e=>{setQuizChapter(e.target.value);setQuiz([]);setAnswers({});setQuizSubmitted(false);setQuizSaved(false)}}>{Array.from({length:16},(_,i)=><option key={i+1} value={String(i+1)}>Chapter {i+1}</option>)}</select><button disabled={quizBusy} onClick={async()=>{setQuizBusy(true);setQuiz([]);setAnswers({});setQuizSubmitted(false);setQuizSaved(false);setError('');try{const data=await api('/practice?chapter='+encodeURIComponent(quizChapter)+'&provider='+encodeURIComponent(provider));setQuiz(data.questions||[]);if(!(data.questions||[]).length)setError(data.message||'No quiz questions available for this chapter.')}catch(e){setError(e.message)}finally{setQuizBusy(false)}}}>{quizBusy?'Generating quiz...':'Generate Practice Quiz'}</button></div>{quizBusy&&<p className="muted" role="status">Preparing questions from Chapter {quizChapter}...</p>}{quiz.map((q,i)=><article className="result" key={i} style={{marginTop:18}}><b>{i+1}. {q.question}</b>{q.options.map((o,j)=><label className="option" key={j} style={{display:'flex',alignItems:'center',gap:10,marginTop:12,cursor:quizSubmitted?'default':'pointer'}}><input type="radio" name={'practice-q'+i} checked={answers[i]===j} disabled={quizSubmitted} onChange={()=>setAnswers(v=>({...v,[i]:j}))}/><span>{o}</span></label>)}{quizSubmitted&&<div style={{marginTop:12}}><strong style={{color:answers[i]===q.correct?'#16a34a':'#dc2626'}}>{answers[i]===q.correct?'Correct':'Incorrect'} — Answer: {q.options[q.correct]}</strong>{q.explanation&&<p>{q.explanation}</p>}</div>}</article>)}{!!quiz.length&&<div className="actions" style={{marginTop:24}}>{!quizSubmitted?<button disabled={Object.keys(answers).length!==quiz.length} onClick={async()=>{setQuizSubmitted(true);if(!quizSaved){setQuizSaved(true);await save('score',{chapter:Number(quizChapter),score:quiz.filter((q,i)=>answers[i]===q.correct).length,total:quiz.length,date:new Date().toISOString()})}}}>Submit Answers ({Object.keys(answers).length}/{quiz.length})</button>:<><h3>Score: {quiz.filter((q,i)=>answers[i]===q.correct).length} / {quiz.length}</h3><button onClick={()=>{setAnswers({});setQuizSubmitted(false);setQuizSaved(false)}}>Try Again</button><button onClick={()=>{setQuiz([]);setAnswers({});setQuizSubmitted(false);setQuizSaved(false)}}>New Quiz</button></>}</div>}</div>}

{tab==='Bookmarks'&&<div className="panel"><h2>Saved bookmarks & highlights</h2>{records.filter(x=>['bookmark','highlight','note'].includes(x.kind)).map(r=><article className="result"><b>{r.kind} · PDF page {r.payload.page||'—'}</b><p>{r.payload.text||''}</p><button onClick={()=>{setPage(r.payload.page||1);setTab('Textbook Reader')}}>Open</button><button onClick={async()=>{await api('/records/'+r.id,{method:'DELETE'});refresh()}}>Delete</button></article>)}</div>}



{tab==='Chat History'&&<div className="panel"><div className="history-heading"><h2>Conversation history</h2><button type="button" className="clear-chat" onClick={clearChats} disabled={!chats.length||busy}><Trash2 size={16}/> Clear history</button></div>{chats.map((m,i)=><article className="result"><b>{m.role==='user'?'You':'AI'}</b><p>{m.content}</p></article>)}</div>}



{tab==='Learning Progress'&&<div className="panel"><h2>Learning progress</h2><p>Saved reading positions and quiz results.</p>{records.filter(x=>['progress','score'].includes(x.kind)).map(r=><article className="result"><b>{r.kind==='score'?'Practice score':'Reading progress'}</b><p>{JSON.stringify(r.payload)}</p></article>)}</div>}



{tab==='Profile'&&<div className="panel"><h2>Student profile</h2><p>Name: {user?.name}</p><p>Email: {user?.email}</p><input placeholder="Update name" id="newname"/><button onClick={async()=>{try{await api('/me',{method:'PUT',body:JSON.stringify({name:document.getElementById('newname').value})});const u=await api('/me');setUser(u);localStorage.setItem('edu_user',JSON.stringify(u))}catch(e){setError(e.message)}}}>Save profile</button></div>}



{tab==='Settings'&&<div className="panel"><h2>Appearance</h2><label className="option"><input type="checkbox" checked={dark} onChange={e=>setDark(e.target.checked)}/> Dark mode</label><h3>Accent color</h3><div className="swatches">{colors.map(c=><button style={{background:c,outline:c===accent?'3px solid var(--text)':'none'}} onClick={()=>setAccent(c)} title={c}/>)}</div><h3>AI providers</h3><p>Gemini and Ollama Cloud credentials are configured securely on the backend through Render environment variables.</p><button onClick={logout}>Sign out</button></div>}



</motion.section></div><div className="mobile-nav">{nav.slice(0,5)}</div></div>}



function Reader({page,setPage,total,onSelection}){const canvas=useRef(null),layer=useRef(null),[doc,setDoc]=useState(null),[zoom,setZoom]=useState(1),[renderError,setRenderError]=useState('');useEffect(()=>{let task=pdfjs.getDocument('/api/book/pdf');task.promise.then(setDoc).catch(e=>setRenderError(e.message));return()=>task.destroy()},[total]);useEffect(()=>{if(!doc)return;let cancel=false;doc.getPage(Math.max(1,Math.min(page,doc.numPages))).then(async p=>{if(cancel)return;let viewport=p.getViewport({scale:zoom*1.35});let c=canvas.current;c.width=viewport.width;c.height=viewport.height;await p.render({canvasContext:c.getContext('2d'),viewport}).promise;if(cancel)return;let text=await p.getTextContent();let el=layer.current;el.innerHTML='';el.style.width=viewport.width+'px';el.style.height=viewport.height+'px';for(let item of text.items){let span=document.createElement('span');span.textContent=item.str;let tx=pdfjs.Util.transform(viewport.transform,item.transform);span.style.cssText=`position:absolute;left:${tx[4]}px;top:${tx[5]-Math.abs(tx[3])}px;font-size:${Math.abs(tx[3])}px;white-space:pre;color:transparent;transform-origin:0 0;`;el.appendChild(span)}let q=sessionStorage.getItem('edu_highlight');if(q){let t=[...el.children].filter(s=>q.toLowerCase().includes(s.textContent.toLowerCase())&&s.textContent.trim().length>3);t.forEach(s=>s.style.background='rgba(255,230,0,.55)');sessionStorage.removeItem('edu_highlight')}}).catch(e=>setRenderError(e.message));return()=>{cancel=true}},[doc,page,zoom]);return <><div className="readerbar"><button onClick={()=>setPage(Math.max(1,page-1))}><ChevronLeft/></button><span>PDF page {page} / {total||doc?.numPages||'?'}</span><button onClick={()=>setPage(Math.min(total||doc?.numPages||page,page+1))}><ChevronRight/></button><button onClick={()=>setZoom(Math.max(.5,zoom-.15))}><ZoomOut/></button><button onClick={()=>setZoom(Math.min(2,zoom+.15))}><ZoomIn/></button><button onClick={()=>layer.current?.parentElement?.requestFullscreen()}>Full screen</button></div>{renderError&&<p className="error">{renderError}</p>}<div className="pdfscroll" onMouseUp={()=>{let t=window.getSelection()?.toString().trim();if(t)onSelection(t)}}><div className="pdfpage"><canvas ref={canvas}/><div ref={layer} className="textlayer"/></div></div></>};createRoot(document.getElementById('root')).render(<App/>);
