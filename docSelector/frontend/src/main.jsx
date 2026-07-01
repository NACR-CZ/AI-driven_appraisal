import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import LlmAnalysisTab from './components/LlmAnalysisTab.jsx';

const API = 'http://localhost:8000';

async function api(path, opts = {}) {
  const res = await fetch(`${API}${path}`, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
function download(path) { window.open(`${API}${path}`, '_blank'); }
function fmtDuration(ms) {
  if (ms === undefined || ms === null || ms === '') return '—';
  const n = Number(ms);
  if (!Number.isFinite(n)) return '—';
  if (n < 1000) return `${n} ms`;
  const sec = n / 1000;
  if (sec < 60) return `${sec.toFixed(1)} s`;
  const min = Math.floor(sec / 60);
  const rest = Math.round(sec % 60);
  return `${min} min ${rest} s`;
}

function App() {
  const [tab, setTab] = useState('context');
  const [store, setStore] = useState(null);
  const [batches, setBatches] = useState([]);
  const [batch, setBatch] = useState(null);
  const [error, setError] = useState('');
  const load = async () => {
    try { setError(''); setStore(await api('/store')); setBatches(await api('/batches')); }
    catch (e) { setError(String(e)); }
  };
  useEffect(() => { load(); }, []);
  const reloadBatch = async (id = batch?.id) => { if (id) setBatch(await api(`/batches/${id}`)); await load(); };
  if (!store) return <div className="page"><h1>DocSelector</h1><p>Načítám backend…</p><p className="muted">Backend má běžet na http://localhost:8000</p>{error && <pre className="error">{error}</pre>}</div>;
  return <div className="page">
    <header className="hero"><div><h1>DocSelector Phase 1</h1><p>Prototyp pro metadata-only appraisal, scan složky, matici komunit/témat, pravidla, vizualizace a exporty.</p></div><button onClick={load}>Obnovit</button></header>
    {error && <pre className="error">{error}</pre>}
    <nav className="tabs">
      {[['context','Kontext a profil'],['matrix','Matice'],['rules','Pravidla'],['import','Import / scan'],['dash','Vizualizace'],['results','Výsledky'],['llm','LLM propojení'],['llm_analysis','LLM analýza'],['llm_analysis_overview','LLM analýzy — přehled'],['events','Log událostí'],['export','Export']].map(([k,v]) => <button key={k} className={tab===k?'active':''} onClick={()=>setTab(k)}>{v}</button>)}
    </nav>
    {tab==='context' && <ContextPanel store={store} onSave={load}/>} 
    {tab==='matrix' && <MatrixPanel store={store} onSave={load}/>} 
    {tab==='rules' && <RulesPanel store={store} onSave={load}/>} 
    {tab==='import' && <ImportPanel batches={batches} batch={batch} setBatch={setBatch} onBatch={reloadBatch}/>} 
    {tab==='dash' && <DashboardPanel batch={batch}/>} 
    {tab==='results' && <ResultsPanel batch={batch} reloadBatch={reloadBatch}/>} 
    {tab==='llm' && <LLMPanel store={store} onSave={load}/>} 
    {tab==='llm_analysis' && <LLMAnalysisPanel batch={batch} setBatch={setBatch} reloadBatch={reloadBatch}/>} 
    {tab==='llm_analysis_overview' && <LlmAnalysisTab batchId={batch?.id || ''}/>} 
    {tab==='events' && <EventsPanel/>}
    {tab==='export' && <ExportPanel store={store} batch={batch} onSave={load}/>} 
  </div>;
}

function ContextPanel({store,onSave}) {
  const [project,setProject] = useState(store.project);
  const [profile,setProfile] = useState(store.decision_profile);
  const save = async () => { await api('/config/project',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(project)}); await api('/config/decision-profile',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(profile)}); onSave(); };
  const setW = (k,v)=>setProfile({...profile,weights:{...profile.weights,[k]:Number(v)}});
  return <section className="grid two">
    <div className="card"><h2>Kontext dávky</h2><Field label="Název dávky" value={project.name} onChange={v=>setProject({...project,name:v})}/><Field label="Původce" value={project.originator} onChange={v=>setProject({...project,originator:v})}/><label>Typ původce<select value={project.originator_type} onChange={e=>setProject({...project,originator_type:e.target.value})}>{['urad','obec','ministerstvo','firma','spolek','nemocnice','skola','fyzicka_osoba','rodina','kulturni_instituce','jine'].map(x=><option key={x}>{x}</option>)}</select></label><label>Účel<select value={project.purpose} onChange={e=>setProject({...project,purpose:e.target.value})}>{['archiv','spisovna','predskartacni_posouzeni','osobni_fond','digitalni_pozustalost','metadata_only_pruzkum'].map(x=><option key={x}>{x}</option>)}</select></label><Field label="Agenda / funkce" value={project.agenda} onChange={v=>setProject({...project,agenda:v})}/><Field label="Místo / územní rozsah" value={project.place} onChange={v=>setProject({...project,place:v})}/><div className="row"><Field label="Od" value={project.date_from} onChange={v=>setProject({...project,date_from:v})}/><Field label="Do" value={project.date_to} onChange={v=>setProject({...project,date_to:v})}/></div><label>Poznámka<textarea value={project.note||''} onChange={e=>setProject({...project,note:e.target.value})}/></label></div>
    <div className="card"><h2>Rozhodovací profil</h2><Field label="Název profilu" value={profile.name} onChange={v=>setProfile({...profile,name:v})}/><h3>Váhy složek skóre</h3>{Object.entries(profile.weights).map(([k,v])=><label key={k}>{k}<input type="number" step="0.05" min="0" max="1" value={v} onChange={e=>setW(k,e.target.value)}/></label>)}<h3>Prahy</h3><div className="row"><Field label="A od skóre" type="number" value={profile.thresholds.preserve} onChange={v=>setProfile({...profile,thresholds:{...profile.thresholds,preserve:Number(v)}})}/><Field label="V od skóre" type="number" value={profile.thresholds.review} onChange={v=>setProfile({...profile,thresholds:{...profile.thresholds,review:Number(v)}})}/></div><button className="primary" onClick={save}>Uložit kontext a profil</button></div>
  </section>
}
function Field({label,value,onChange,type='text'}) { return <label>{label}<input type={type} value={value??''} onChange={e=>onChange(e.target.value)}/></label>; }

function MatrixPanel({store,onSave}) {
  const [communities,setCommunities]=useState(store.communities); const [topics,setTopics]=useState(store.topics); const [scores,setScores]=useState(store.scores);
  const saveItem=async(collection,item)=>{await api(`/${collection}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)}); onSave();};
  const setScore=async(cid,tid,v)=>{const ns={...scores,[`${cid}|${tid}`]:Number(v)}; setScores(ns); await api('/matrix/score',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({community_id:cid,topic_id:tid,value:Number(v)})});};
  return <section className="card wide"><h2>Rozhodovací matice: komunity × témata</h2><p className="muted">Výpočet používá buňku 0–5 × váhu komunity × váhu tématu. Tím jde ladit experimentální politiku výběru.</p><MatrixImportExport onImported={onSave}/><div className="matrix-wrap"><table className="matrix"><thead><tr><th>Komunita / téma</th>{topics.map(t=><th key={t.id}><input value={t.name} onChange={e=>setTopics(topics.map(x=>x.id===t.id?{...x,name:e.target.value}:x))}/><small>váha</small><input type="number" step="0.1" value={t.weight} onChange={e=>setTopics(topics.map(x=>x.id===t.id?{...x,weight:Number(e.target.value)}:x))}/><button onClick={()=>saveItem('topics',t)}>uložit</button></th>)}</tr></thead><tbody>{communities.map(c=><tr key={c.id}><th><input value={c.name} onChange={e=>setCommunities(communities.map(x=>x.id===c.id?{...x,name:e.target.value}:x))}/><small>váha</small><input type="number" step="0.1" value={c.weight} onChange={e=>setCommunities(communities.map(x=>x.id===c.id?{...x,weight:Number(e.target.value)}:x))}/><button onClick={()=>saveItem('communities',c)}>uložit</button></th>{topics.map(t=><td key={t.id}><input className="score" type="number" min="0" max="5" value={scores[`${c.id}|${t.id}`]??0} onChange={e=>setScore(c.id,t.id,e.target.value)}/></td>)}</tr>)}</tbody></table></div><AddCommunity onAdd={async item=>{await saveItem('communities',item)}}/><AddTopic onAdd={async item=>{await saveItem('topics',item)}}/></section>
}

function MatrixImportExport({onImported}) {
  const [msg,setMsg]=useState('');
  const importFile = async (file) => {
    if(!file) return;
    const text = await file.text();
    try {
      const payload = JSON.parse(text);
      const res = await api('/matrix/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      setMsg(`Import hotov: komunity ${res.imported?.communities||0}, témata ${res.imported?.topics||0}, skóre ${res.imported?.scores||0}`);
      onImported && onImported();
    } catch(e) { setMsg(`Chyba importu matice: ${String(e)}`); }
  };
  return <div className="toolbar"><button onClick={()=>download('/matrix/export')}>Export matice JSON</button><label className="filebutton">Import / obohacení matice JSON<input type="file" accept=".json,application/json" onChange={e=>importFile(e.target.files?.[0])}/></label>{msg&&<span className="notice">{msg}</span>}</div>
}

function parseCsvLine(line) {
  const out=[]; let cur=''; let q=false;
  for(let i=0;i<line.length;i++){ const ch=line[i]; if(ch==='"'){ if(q&&line[i+1]==='"'){cur+='"'; i++;} else q=!q; } else if(ch===','&&!q){ out.push(cur.trim()); cur=''; } else cur+=ch; }
  out.push(cur.trim()); return out;
}
function RulesImportExport({onImported}) {
  const [msg,setMsg]=useState('');
  const importFile = async (file) => {
    if(!file) return;
    const text = await file.text();
    try {
      let payload;
      if(file.name.toLowerCase().endsWith('.json')) payload = JSON.parse(text);
      else {
        const lines = text.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
        const first = parseCsvLine(lines[0]||'').map(x=>x.toLowerCase());
        const hasHeader = first.some(x=>['doc_type','typ dokumentu','retention_mark','skartacni znak','sk. znak','znak'].includes(x));
        const rows = [];
        const headers = hasHeader ? first : null;
        for(const line of lines.slice(hasHeader?1:0)){
          const cols = parseCsvLine(line);
          if(headers){
            const obj={};
            headers.forEach((h,i)=>{ const keyMap={ 'typ dokumentu':'doc_type', 'skartacni znak':'retention_mark', 'sk. znak':'retention_mark', 'znak':'retention_mark', 'doba':'retention_years', 'lhuta':'retention_years', 'sk. lhuta':'retention_years', 'spoustec':'retention_trigger', 'uplatnit':'retention_trigger' }; obj[keyMap[h]||h]=cols[i]||''; });
            rows.push(obj);
          } else rows.push({doc_type: cols[0]||'', retention_mark: cols[1]||'V', retention_years: cols[2]||'', retention_trigger: cols[3]||''});
        }
        payload = {retention_rules: rows};
      }
      const res = await api('/retention_rules/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      setMsg(`Import pravidel hotov: ${res.imported||0}`);
      onImported && onImported();
    } catch(e) { setMsg(`Chyba importu pravidel: ${String(e)}`); }
  };
  return <div className="toolbar"><button onClick={()=>download('/retention_rules/export')}>Export pravidel JSON</button><label className="filebutton">Import pravidel CSV/JSON<input type="file" accept=".csv,.json,text/csv,application/json" onChange={e=>importFile(e.target.files?.[0])}/></label><span className="muted">CSV může být třeba: faktury,S,5,od uzavření</span>{msg&&<span className="notice">{msg}</span>}</div>
}

function AddCommunity({onAdd}){const [name,setName]=useState('');return <div className="inline"><input placeholder="Nová komunita" value={name} onChange={e=>setName(e.target.value)}/><button onClick={()=>{onAdd({name,group_id:'cg_academic',weight:1,type:'academic',active:true});setName('')}}>Přidat komunitu</button></div>}
function AddTopic({onAdd}){const [name,setName]=useState('');return <div className="inline"><input placeholder="Nové téma" value={name} onChange={e=>setName(e.target.value)}/><button onClick={()=>{onAdd({name,group_id:'tg_society',keywords:name,weight:1,active:true});setName('')}}>Přidat téma</button></div>}

function RulesPanel({store,onSave}) {
  const [rules,setRules]=useState(store.retention_rules);
  const save=async(r)=>{await api('/retention_rules',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(r)}); onSave();};
  return <section className="card wide"><h2>Retenční / skartační pravidla</h2><p className="muted">Pravidlo se páruje přes kombinaci: typ dokumentu + typ původce + agenda + účel. Hvězdička znamená libovolná hodnota.</p><RulesImportExport onImported={onSave}/><table><thead><tr><th>ID</th><th>Typ dokumentu</th><th>Typ původce</th><th>Agenda</th><th>Účel</th><th>Znak</th><th>Lhůta</th><th>Rozhodnutí</th><th></th></tr></thead><tbody>{rules.map((r,i)=><tr key={r.id||i}>{['id','doc_type','originator_type','agenda','purpose','retention_mark','retention_years','decision'].map(k=><td key={k}><input value={r[k]??''} onChange={e=>setRules(rules.map((x,j)=>j===i?{...x,[k]:e.target.value}:x))}/></td>)}<td><button onClick={()=>save(r)}>uložit</button></td></tr>)}</tbody></table><button onClick={()=>setRules([...rules,{id:'',doc_type:'',originator_type:'*',agenda:'*',purpose:'*',retention_mark:'V',retention_years:'',decision:'V',active:true,priority:50}])}>+ Nové pravidlo</button></section>
}

function ImportPanel({batches,batch,setBatch,onBatch}) {
  const [path,setPath]=useState(''); const [file,setFile]=useState(null); const [loading,setLoading]=useState(false);
  const upload=async()=>{if(!file)return;setLoading(true);const fd=new FormData();fd.append('file',file);const res=await fetch(`${API}/import/metadata`,{method:'POST',body:fd});const b=await res.json();setBatch(b);setLoading(false);onBatch(b.id)};
  const scan=async()=>{setLoading(true);const b=await api('/scan/folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path,extract_text_layer:true,max_files:500})});setBatch(b);setLoading(false);onBatch(b.id)};
  const score=async(mode)=>{if(!batch)return;setLoading(true);const b=await api(`/batches/${batch.id}/score`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});setBatch(b);setLoading(false);onBatch(b.id)};
  return <section className="grid two"><div className="card"><h2>1) Metadata-only seznam</h2><p>CSV/XLSX může být jednoduchý seznam (<code>title</code>, <code>path</code>) nebo český seznam k protokolu výběru se sloupci <code>Spis. znak</code>, <code>Obsah / Název</code>, <code>Sk. znak</code>, <code>Sk. lhůta</code>, <code>Rozhodnutí</code>. Rozhodnutí ze souboru se uloží jako referenční/předchozí rozhodnutí.</p><input type="file" accept=".csv,.xlsx,.xls" onChange={e=>setFile(e.target.files[0])}/><button className="primary" onClick={upload} disabled={!file||loading}>Načíst seznam</button></div><div className="card"><h2>2) Scan složky</h2><p>Vyčte názvy, velikosti, formáty, hash a z textové vrstvy se pokusí vytěžit čas, místo, osoby, instituce, témata a klíčová slova.</p><input placeholder="C:\\cesta\\ke\\slozce" value={path} onChange={e=>setPath(e.target.value)}/><button className="primary" onClick={scan} disabled={!path||loading}>Skenovat složku</button></div><div className="card wide"><h2>Dávky</h2><div className="batchlist">{batches.map(b=><button key={b.id} onClick={async()=>setBatch(await api(`/batches/${b.id}`))}>{b.name} <small>{b.count} záznamů</small></button>)}</div>{batch && <div className="notice">Aktuální dávka: <b>{batch.name}</b> ({batch.records?.length} záznamů) <button onClick={()=>score('algorithmic')}>Spočítat algoritmicky</button><button onClick={()=>score('compare')}>Porovnat s LLM</button></div>}</div></section>
}

function DashboardPanel({batch}) {
  const [dash,setDash]=useState(null);
  useEffect(()=>{if(batch) api(`/batches/${batch.id}/dashboard`).then(setDash)},[batch?.id]);
  if(!batch) return <Empty text="Nejdřív načti nebo vyber dávku."/>; if(!dash) return <p>Načítám dashboard…</p>;
  return <section className="grid two"><Chart title="Čas" data={dash.by_year}/><Chart title="Místa" data={dash.by_place}/><Chart title="Témata" data={dash.by_topic}/><Chart title="Nové rozhodnutí" data={dash.by_decision}/><Chart title="Původní rozhodnutí ze seznamu" data={dash.by_reference_decision}/><Chart title="Formáty / podoba" data={dash.by_extension}/><div className="card"><h2>Kvalita metadat</h2>{Object.entries(dash.missing).map(([k,v])=><p key={k}>{k}: chybí u <b>{v}</b> záznamů</p>)}</div></section>
}
function Chart({title,data}){const rows=Object.entries(data||{}).sort((a,b)=>b[1]-a[1]).slice(0,12);const max=Math.max(...rows.map(r=>r[1]),1);return <div className="card"><h2>{title}</h2>{rows.length===0?<p className="muted">Bez dat</p>:rows.map(([k,v])=><div className="bar" key={k}><span>{k}</span><div><i style={{width:`${(v/max)*100}%`}}></i></div><b>{v}</b></div>)}</div>}
function Empty({text}){return <div className="card"><p>{text}</p></div>}

function ResultsPanel({batch,reloadBatch}) {
  const [filter,setFilter]=useState('all'); if(!batch)return <Empty text="Nejdřív načti dávku."/>;
  const records=(batch.records||[]).filter(r=>filter==='all'||(r.human_decision||r.scoring?.decision||'N')===filter);
  const confirm=async(r,decision)=>{await api(`/batches/${batch.id}/records/${r.id}/decision`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision})}); reloadBatch(batch.id)};
  return <section className="card wide"><h2>Výsledky a lidské potvrzení</h2><div className="tabs small">{['all','A','V','S','N'].map(x=><button className={filter===x?'active':''} onClick={()=>setFilter(x)} key={x}>{x}</button>)}</div><table><thead><tr><th>Název / evidenční údaje</th><th>Typ</th><th>Čas</th><th>Podoba / uloženo</th><th>Témata</th><th>Původní</th><th>Skóre</th><th>Nové rozhodnutí</th><th>Potvrdit</th></tr></thead><tbody>{records.map(r=><tr key={r.id}><td><b>{r.title}</b><div className="muted">{r.evidence_number||''} {r.record_ref?` · ${r.record_ref}`:''} {r.spisovy_znak?` · spis. znak ${r.spisovy_znak}`:''}</div><details><summary>vysvětlení</summary><p>{r.scoring?.explanation}</p><pre>{JSON.stringify(r.scoring?.components||{},null,2)}</pre>{r.llm_analysis&&<pre>LLM: {JSON.stringify(r.llm_analysis,null,2)}</pre>}</details></td><td>{r.doc_type||r.analysis?.document_type}<div className="muted">{r.retention_mark?`Sk. ${r.retention_mark}`:''} {r.retention_years?`/ ${r.retention_years}`:''}</div></td><td>{r.date_from||r.analysis?.time_range?.earliest}–{r.date_to||r.analysis?.time_range?.latest}</td><td>{r.form||''}<div className="muted">{r.storage||''}</div></td><td>{r.analysis?.detected_topics?.map(t=>t.name).join(', ')}</td><td>{r.reference_decision||r.source_decision?<Decision d={r.reference_decision||r.source_decision}/>:<span className="muted">—</span>}</td><td>{r.scoring?.final_score}</td><td><Decision d={r.human_decision||r.scoring?.decision||'N'}/></td><td><button onClick={()=>confirm(r,'A')}>A</button><button onClick={()=>confirm(r,'V')}>V</button><button onClick={()=>confirm(r,'S')}>S</button></td></tr>)}</tbody></table></section>
}
function Decision({d}){return <span className={`dec dec-${d}`}>{d}</span>}


function LLMPanel({store,onSave}) {
  const [llm,setLlm]=useState(store.llm_config || {});
  const [status,setStatus]=useState(null);
  const [testing,setTesting]=useState(false);
  const [msg,setMsg]=useState('');
  const loadStatus=async()=>{try{setStatus(await api('/llm/status'));}catch(e){setStatus({last_test:{ok:false,message:String(e)}})}};
  useEffect(()=>{loadStatus();},[]);
  const save=async()=>{setMsg('Ukládám…'); await api('/config/llm',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(llm)}); setMsg('Nastavení uloženo.'); await loadStatus(); onSave();};
  const test=async()=>{setTesting(true);setMsg('Testuji spojení…'); try{const res=await api('/llm/test',{method:'POST'}); setStatus({...status,last_test:res}); setMsg(res.ok?'Spojení je navázáno.':'Spojení se nepodařilo navázat.');}catch(e){setStatus({...status,last_test:{ok:false,message:String(e)}}); setMsg('Test selhal.');} finally{setTesting(false);}};
  const last=status?.last_test;
  return <section className="grid two">
    <div className="card"><h2>LLM propojení</h2><p className="muted">Tady nastavíš endpoint pro model používaný k sumarizaci, extrakci klíčových slov a porovnání algoritmického vs. LLM rozhodnutí.</p><label><input type="checkbox" checked={!!llm.enabled} onChange={e=>setLlm({...llm,enabled:e.target.checked})}/> zapnout LLM pro režim „Porovnat s LLM“</label><Field label="Base URL" value={llm.base_url} onChange={v=>setLlm({...llm,base_url:v})}/><Field label="Model" value={llm.model} onChange={v=>setLlm({...llm,model:v})}/><label>API key<input type="password" placeholder={status?.has_api_key?'API key je uložený — vyplň jen pro změnu':'vložit API key'} value={llm.api_key||''} onChange={e=>setLlm({...llm,api_key:e.target.value})}/></label><div className="inline"><button className="primary" onClick={save}>Uložit nastavení</button><button onClick={test} disabled={testing}>{testing?'Testuji…':'Otestovat spojení'}</button></div>{msg&&<p className="notice">{msg}</p>}</div>
    <div className="card"><h2>Stav spojení</h2>{!last?<p className="muted">Spojení zatím nebylo testováno.</p>:<div><p><span className={`status ${last.ok?'ok':'bad'}`}>{last.ok?'NAVÁZÁNO':'NENAVÁZÁNO'}</span></p><p><b>Status:</b> {last.status}</p><p><b>Zpráva:</b> {last.message}</p><p><b>Model:</b> {last.model}</p><p><b>Base URL:</b> {last.base_url}</p><p><b>Testováno:</b> {last.tested_at}</p>{last.elapsed_ms!==undefined&&<p><b>Odezva:</b> {last.elapsed_ms} ms</p>}{last.http_status&&<p><b>HTTP:</b> {last.http_status}</p>}{last.reply&&<p><b>Odpověď modelu:</b> {last.reply}</p>}<details><summary>technický detail</summary><pre>{JSON.stringify(last,null,2)}</pre></details></div>}<hr/><p className="muted">API key se nevrací přes stavový endpoint; v detailu se zobrazuje jen informace, zda je uložený.</p></div>
  </section>
}


function LLMAnalysisPanel({batch,setBatch,reloadBatch}) {
  const [maxRecords,setMaxRecords] = useState(20);
  const [onlyWithout,setOnlyWithout] = useState(true);
  const [overwrite,setOverwrite] = useState(false);
  const [fullContext,setFullContext] = useState(false);
  const [running,setRunning] = useState(false);
  const [message,setMessage] = useState('');
  const [filter,setFilter] = useState('all');
  if(!batch) return <Empty text="Nejdřív načti nebo vyber dávku v záložce Import / scan."/>;
  const analyzed = (batch.records||[]).filter(r=>r.llm_analysis);
  const errors = analyzed.filter(r=>r.llm_analysis?.error);
  const disagreements = analyzed.filter(r=>{
    const alg = r.human_decision || r.scoring?.decision;
    const llm = (r.llm_decision || r.llm_analysis?.recommendation || '').toUpperCase();
    return alg && llm && alg !== llm;
  });
  const filtered = (batch.records||[]).filter(r=>{
    if(filter==='all') return true;
    if(filter==='analyzed') return !!r.llm_analysis;
    if(filter==='errors') return !!r.llm_analysis?.error;
    if(filter==='disagree') {
      const alg = r.human_decision || r.scoring?.decision;
      const llm = (r.llm_decision || r.llm_analysis?.recommendation || '').toUpperCase();
      return alg && llm && alg !== llm;
    }
    if(filter==='not_analyzed') return !r.llm_analysis;
    return true;
  });
  const run = async()=>{
    setRunning(true); setMessage('Odesílám záznamy k LLM analýze…');
    try {
      const res = await api(`/batches/${batch.id}/llm/analyze`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({max_records:Number(maxRecords), only_without_llm:onlyWithout, overwrite, full_context: fullContext})});
      setBatch(res.batch);
      setMessage(`Hotovo. Zpracováno: ${res.processed}, přeskočeno: ${res.skipped}, chyby: ${res.errors}, trvání: ${fmtDuration(res.elapsed_ms)}.`);
      await reloadBatch(batch.id);
    } catch(e) {
      setMessage(`Chyba LLM analýzy: ${String(e)}`);
    } finally { setRunning(false); }
  };
  return <section className="grid two">
    <div className="card"><h2>Odeslání dávky k LLM analýze</h2><p className="muted">LLM analýza doplní shrnutí, klíčová slova, témata, entity, časový rozsah, doporučení A/V/S a zdůvodnění. Výsledek se uloží vedle algoritmického rozhodnutí.</p><p>Aktuální dávka: <b>{batch.name}</b> ({batch.records?.length||0} záznamů)</p><label>Kolik záznamů zpracovat v jednom běhu<input type="number" min="1" max="500" value={maxRecords} onChange={e=>setMaxRecords(e.target.value)}/></label><label><input type="checkbox" checked={onlyWithout} onChange={e=>setOnlyWithout(e.target.checked)}/> analyzovat jen záznamy, které ještě nemají LLM výsledek</label><label><input type="checkbox" checked={overwrite} onChange={e=>setOverwrite(e.target.checked)}/> přepsat existující LLM výsledky</label><label><input type="checkbox" checked={fullContext} onChange={e=>setFullContext(e.target.checked)}/> odeslat plný metodický kontext dávky, pravidel, komunit, matice a algoritmického skóre</label><p className="muted">Vypnuto = odešle se jen základ: text / název / popis záznamu a seznam platných témat. Zapnuto = odešle se i kontext dávky, typ původce, účel archivace, agenda, rozhodovací profil, relevantní retenční pravidla, komunity s váhami, matice a algoritmické skóre. Výstup je v promptu vyžadován česky.</p><button className="primary" onClick={run} disabled={running}>{running?'Probíhá LLM analýza…':'Spustit LLM analýzu'}</button>{message&&<p className="notice">{message}</p>}<hr/><p className="muted">Doporučení: u velkých protokolů začni třeba na 10–20 záznamech, zkontroluj kvalitu a potom pokračuj další dávkou.</p></div>
    <div className="card"><h2>Souhrn LLM výsledků</h2><p><b>Analyzováno:</b> {analyzed.length} / {batch.records?.length||0}</p><p><b>Chyby:</b> {errors.length}</p><p><b>Neshoda algoritmus × LLM:</b> {disagreements.length}</p>{batch.last_llm_analysis&&<div className="run-box"><h3>Poslední běh LLM analýzy</h3><p><b>Začátek:</b> {batch.last_llm_analysis.started_at || batch.last_llm_analysis.created_at || '—'}</p><p><b>Konec:</b> {batch.last_llm_analysis.finished_at || '—'}</p><p><b>Trvání:</b> {fmtDuration(batch.last_llm_analysis.elapsed_ms)}</p><p><b>Zpracováno:</b> {batch.last_llm_analysis.processed ?? 0}</p><p><b>Přeskočeno:</b> {batch.last_llm_analysis.skipped ?? 0}</p><p><b>Chyby:</b> {batch.last_llm_analysis.errors ?? 0}</p><p><b>Model:</b> {batch.last_llm_analysis.model || '—'}</p><p><b>Kontext:</b> {batch.last_llm_analysis.context_mode === 'full' ? 'plný metodický kontext' : 'základní údaje'}</p><p><b>Run ID:</b> {batch.last_llm_analysis.model_run_id || '—'}</p><details><summary>technický JSON posledního běhu</summary><pre>{JSON.stringify(batch.last_llm_analysis,null,2)}</pre></details></div>}<div className="tabs small">{[['all','vše'],['analyzed','analyzované'],['not_analyzed','bez LLM'],['disagree','neshody'],['errors','chyby']].map(([k,v])=><button key={k} className={filter===k?'active':''} onClick={()=>setFilter(k)}>{v}</button>)}</div></div>
    <div className="card wide"><h2>Výsledky LLM analýzy</h2><table><thead><tr><th>Název</th><th>Algoritmus</th><th>LLM</th><th>Shrnutí / zdůvodnění</th><th>Klíčová slova, témata, entity</th><th>Detail</th></tr></thead><tbody>{filtered.map(r=>{const llm=r.llm_analysis||{};const llmDec=(r.llm_decision||llm.recommendation||'').toUpperCase();const alg=r.human_decision||r.scoring?.decision||'N';return <tr key={r.id}><td><b>{r.title}</b><div className="muted">{r.evidence_number||''} {r.record_ref?` · ${r.record_ref}`:''}</div></td><td><Decision d={alg}/><div className="muted">{r.scoring?.final_score??''}</div></td><td>{llmDec?<Decision d={llmDec}/>:<span className="muted">—</span>}{llm.error&&<div className="error">{llm.error}</div>}{llmDec&&alg&&llmDec!==alg&&<div className="notice">neshoda</div>}</td><td><p>{llm.summary||<span className="muted">Bez LLM shrnutí</span>}</p>{llm.reasoning&&<p><b>Zdůvodnění:</b> {llm.reasoning}</p>}</td><td><p><b>KW:</b> {(llm.keywords||[]).join(', ')}</p><p><b>Témata:</b> {(llm.detected_topics||[]).join(', ')}</p><p><b>Místa:</b> {(llm.places||[]).join(', ')}</p><p><b>Osoby:</b> {(llm.persons||[]).join(', ')}</p><p><b>Instituce:</b> {(llm.organizations||[]).join(', ')}</p></td><td><details><summary>JSON</summary><pre>{JSON.stringify(llm,null,2)}</pre></details></td></tr>})}</tbody></table></div>
  </section>
}


function EventsPanel() {
  const [events,setEvents]=useState([]); const [msg,setMsg]=useState('');
  const loadEvents=async()=>{try{setMsg(''); setEvents(await api('/events?limit=500'));}catch(e){setMsg(String(e));}};
  useEffect(()=>{loadEvents();},[]);
  const counts = events.reduce((a,e)=>{a[e.type]=(a[e.type]||0)+1; return a;},{});
  return <section className="card wide"><h2>Log událostí</h2><p className="muted">Slouží k opakovatelnosti experimentu: uvidíš, kdy běžel import, scoring, LLM analýza nebo import matice/pravidel, kolik záznamů se zpracovalo a jak dlouho to trvalo.</p><button onClick={loadEvents}>Obnovit log</button>{msg&&<pre className="error">{msg}</pre>}<div className="kpis">{Object.entries(counts).map(([k,v])=><div className="kpi" key={k}><b>{v}</b><span>{k}</span></div>)}</div><table><thead><tr><th>Čas</th><th>Událost</th><th>Dávka</th><th>Počet</th><th>Trvání</th><th>Rychlost</th><th>Detail</th></tr></thead><tbody>{events.map(e=><tr key={e.id}><td>{e.created_at}</td><td>{e.type}</td><td>{e.batch_id||'—'}</td><td>{e.count??0}</td><td>{fmtDuration(e.elapsed_ms)}</td><td>{e.records_per_sec?`${e.records_per_sec} zázn./s`:'—'}</td><td><details><summary>JSON</summary><pre>{JSON.stringify(e.detail||{},null,2)}</pre></details></td></tr>)}</tbody></table></section>
}

function ExportPanel({store,batch,onSave}) {
  const [llm,setLlm]=useState(store.llm_config); const [out,setOut]=useState('');
  const saveLlm=async()=>{await api('/config/llm',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(llm)});onSave();};
  const sort=async()=>{if(!batch||!out)return;const res=await api(`/batches/${batch.id}/sort`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({output_root:out,mode:'copy'})});alert(`Zkopírováno: ${res.processed}`)};
  return <section className="grid two"><div className="card"><h2>Export</h2><button onClick={()=>download('/export/config')}>Export nastavení JSON</button>{batch&&<><button onClick={()=>download(`/export/batch/${batch.id}/json`)}>Export auditní JSON</button><button onClick={()=>download(`/export/batch/${batch.id}/csv`)}>Export výsledků CSV</button></>}<h3>Roztřídit soubory</h3><input placeholder="C:\\vystup\\DocSelector" value={out} onChange={e=>setOut(e.target.value)}/><button disabled={!batch||!out} onClick={sort}>Zkopírovat do A/V/S složek</button><p className="muted">Zachová relativní hierarchii. V tomto prototypu používám bezpečné kopírování, ne mazání.</p></div><div className="card"><h2>LLM nastavení</h2><label><input type="checkbox" checked={!!llm.enabled} onChange={e=>setLlm({...llm,enabled:e.target.checked})}/> zapnout LLM porovnání</label><Field label="Base URL" value={llm.base_url} onChange={v=>setLlm({...llm,base_url:v})}/><Field label="Model" value={llm.model} onChange={v=>setLlm({...llm,model:v})}/><Field label="API key" value={llm.api_key||''} onChange={v=>setLlm({...llm,api_key:v})}/><button className="primary" onClick={saveLlm}>Uložit LLM</button></div></section>
}

createRoot(document.getElementById('root')).render(<App/>);
