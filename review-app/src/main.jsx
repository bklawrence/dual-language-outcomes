import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ArrowDownToLine, ArrowLeft, ArrowRight, BookOpen, Check, CheckCheck, ChevronDown, ChevronRight, CircleHelp, ClipboardList, Clock3, ExternalLink, FileText, Filter, Github, History, Leaf, Link2, LoaderCircle, MessageSquareText, PanelLeftClose, Search, Send, Sparkles, Sprout, Trophy, X} from 'lucide-react';
import Plant from './Plant';
import {freshGarden, waterGarden} from './garden';
import {loadWorkspace,saveWorkspace} from './storage';
import SavedReviews from './SavedReviews';
import ReviewDetails from './ReviewDetails';
import ProgramStatus from './ProgramStatus';
import Leaderboard from './Leaderboard';
import AllocationEditor from './AllocationEditor';
import {allocationSummary,allocationGrades} from './allocation';
import {VALUE_LABELS, draftFromReview, targetsForDraft, hasReviewEdits} from './reviews';
import {allocationRecorded, deliveryRecorded, fieldWithReviews, matchesReviewTask, schoolPriorityStatus} from './queue';
import '@fontsource-variable/dm-sans';
import '@fontsource/libre-caslon-display/latin-400.css';
import './fieldnotes.css';

const KEY='fieldnotes.workspace.v1';
const EMPTY={site_id:'',delivery:'',population:'',allocation:'',languages:'',evidence_url:'',notes:'',source_quote:'',grade_scope:'',source_locator:'',source_school_year:'',reference_year:'2025-26',coding_method:'explicit_source_statement',all_delivery:true,program_status:'',status_year:'',all_status:false,event_site_ids:null,destination_name:'',destination_id:'',destination_url:''};
const YEARS=['2026-27','2025-26','2024-25','2023-24','2022-23','2021-22','2020-21','2019-20'];
const SOURCE_YEARS=Array.from({length:27},(_,i)=>`${2026-i}-${String(2027-i).slice(-2)}`);
function readStore(){try{return JSON.parse(localStorage.getItem(KEY))||{};}catch{return {};}}
function hrefSearch(c){return 'https://www.google.com/search?q='+encodeURIComponent(c.school_name+' '+c.district_name+' dual language');}
function stateLabel(code,data){return data?.state_names?.[code]||code;}
function valuesText(field){return field?.value?.map(v=>VALUE_LABELS[v]||v).join(' · ')||'Not yet recorded';}
function missingFor(c, saved, accepted, onlyAllocated=false, year='2025-26'){
  const scopedSites=onlyAllocated?c.sites.filter(s=>allocationRecorded(fieldWithReviews(c,s,'elementary_allocation_model',saved,accepted,year))):c.sites;
  const fields=new Set(c.missing);
  for(const variable of c.missing){
    const remaining=scopedSites.some(site=>{
      const f=fieldWithReviews(c,site,variable,saved,accepted,year);
      return variable==='elementary_allocation_model'?!allocationRecorded(f):variable==='delivery_structure'?!deliveryRecorded(f):!f.value.length||f.status!=='documented';
    });
    if(!remaining)fields.delete(variable);
  }
  return [...fields];
}

function Modal({title,children,onClose,className=''}){
  const ref=useRef();useEffect(()=>{const previous=document.activeElement;ref.current?.focus();function key(e){if(e.key==='Escape')onClose();if(e.key==='Tab'){const targets=[...ref.current.querySelectorAll('button,a,input,select,textarea')].filter(el=>!el.disabled);if(!targets.length)return;let first=targets[0],last=targets.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}}document.addEventListener('keydown',key);return()=>{document.removeEventListener('keydown',key);previous?.focus();};},[]);
  return <div className="modal-shade" onMouseDown={e=>e.target===e.currentTarget&&onClose()}><section role="dialog" aria-modal="true" aria-label={title} tabIndex="-1" ref={ref} className={'modal '+className}><div className="modal-title"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={20}/></button></div>{children}</section></div>;
}

async function prepareBatch(records, data){
  let count=Math.min(10,records.length);const batch_id=crypto.randomUUID();
  while(count>0){
    const chosen=records.slice(0,count);const payload={version:1,batch_id,records:chosen};const text=JSON.stringify(payload);
    if(new TextEncoder().encode(text).length>60000){count--;continue;}
    if(!window.CompressionStream)throw Error('Batch publishing needs a current version of Chrome, Firefox, Edge, or Safari. Your reviews remain saved here.');
    const compressed=await new Response(new Blob([text]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer();
    const encoded=btoa(String.fromCharCode(...new Uint8Array(compressed))).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');
    const schools=[...new Set(chosen.map(r=>r.school_name))];
    const body='## Hand-coded school program reviews\n\n'+chosen.length+' review(s), prepared in [Fieldnotes]('+data.site_url+').\n\n'+schools.map(n=>'- '+n.replace(/[\r\n]/g,' ')).join('\n')+'\n\nEach decision includes its school year, researcher, evidence link, notes, and coding method. The dataset retains the original observations.\n\n<!-- DL_REVIEW_V1:'+encoded+' -->';
    const url='https://github.com/'+data.repository+'/issues/new?'+new URLSearchParams({title:'[DL Review] '+chosen.length+' reviews · '+batch_id,body});
    if(url.length<=7000)return {batch_id,records:chosen,url,created_at:new Date().toISOString()};count--;
  }
  throw Error('This review is too long for the GitHub handoff. Shorten its notes or quotation and try again. Your draft is still saved.');
}

function App(){
  const [store,setStore]=useState(()=>{const old=readStore();return {reviewer:'',drafts:{},saved:[],batches:[],garden:freshGarden(),...old};});
  const [data,setData]=useState(null),[loadError,setLoadError]=useState(''),[active,setActive]=useState(store.lastSchoolId||''),[siteId,setSiteId]=useState('');
  const [editingId,setEditingId]=useState(store.editingReviewId||'');
  const [handoffBusy,setHandoffBusy]=useState(false),[handoffError,setHandoffError]=useState(''),[manualLink,setManualLink]=useState('');
  const [reviewFilters,setReviewFilters]=useState({query:'',district:'all',status:'all'});
  const [includeResearchLeads,setIncludeResearchLeads]=useState(Boolean(store.includeResearchLeads));
  const [hydrated,setHydrated]=useState(false),[savingDraft,setSavingDraft]=useState(false);
  const [query,setQuery]=useState(''),[state,setState]=useState('all'),[district,setDistrict]=useState('all'),[variable,setVariable]=useState(store.reviewTask||'delivery_structure'),[allocationOnly,setAllocationOnly]=useState((store.reviewTask||'delivery_structure')==='delivery_structure'),[view,setView]=useState('queue');
  const [modal,setModal]=useState(''),[toast,setToast]=useState(''),[formError,setFormError]=useState(''),[watering,setWatering]=useState(false),[now,setNow]=useState(Date.now()),[batch,setBatch]=useState(null),[batchError,setBatchError]=useState(''),[refreshing,setRefreshing]=useState(false),[mobileQueue,setMobileQueue]=useState(false),[listLimit,setListLimit]=useState(150),[storageError,setStorageError]=useState(false);
  const mainRef=useRef(), importRef=useRef();
  const refresh=async(silent=false)=>{if(silent!==true)setRefreshing(true);try{const response=await fetch('./data/queue.json?v='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error('Could not load the research inventory.');setData(await response.json());setLoadError('');}catch(e){setLoadError(e.message);}finally{if(silent!==true)setRefreshing(false);}};
  useEffect(()=>{
    refresh();
    const timer=setInterval(()=>setNow(Date.now()),60000);
    const sharedTimer=setInterval(()=>{if(!document.hidden)refresh(true);},120000);
    const onFocus=()=>refresh(true);
    const onVisible=()=>{if(!document.hidden)refresh(true);};
    window.addEventListener('focus',onFocus);document.addEventListener('visibilitychange',onVisible);
    return()=>{clearInterval(timer);clearInterval(sharedTimer);window.removeEventListener('focus',onFocus);document.removeEventListener('visibilitychange',onVisible);};
  },[]);
  useEffect(()=>{loadWorkspace().then(old=>{if(old&&Array.isArray(old.saved)&&old.drafts){setStore(s=>({...s,...old}));if(old.lastSchoolId)setActive(old.lastSchoolId);setEditingId(old.editingReviewId||'');setIncludeResearchLeads(Boolean(old.includeResearchLeads));if(typeof old.reviewTask==='string'){setVariable(old.reviewTask);setAllocationOnly(old.reviewTask==='delivery_structure'&&(old.allocationOnly??true));}}setHydrated(true);});},[]);
  useEffect(()=>{if(!hydrated)return;let latest=true;setSavingDraft(true);saveWorkspace({...store,lastSchoolId:active,editingReviewId:editingId,reviewTask:variable,allocationOnly,includeResearchLeads}).then(()=>{if(latest){setStorageError(false);setSavingDraft(false);}}).catch(()=>{if(latest){setStorageError(true);setSavingDraft(false);}});return()=>{latest=false;};},[store,active,editingId,hydrated,variable,allocationOnly,includeResearchLeads]);
  useEffect(()=>{if(!toast)return;const t=setTimeout(()=>setToast(''),4500);return()=>clearTimeout(t);},[toast]);
  const accepted=useMemo(()=>new Set(data?.accepted_review_ids||[]),[data]);
  const preparedIds=useMemo(()=>new Set(store.batches.flatMap(b=>b.review_ids)),[store.batches]);
  const pending=useMemo(()=>store.saved.filter(r=>!accepted.has(r.review_id)&&!preparedIds.has(r.review_id)),[store.saved,accepted,preparedIds]);
  const awaiting=store.saved.filter(r=>!accepted.has(r.review_id)&&preparedIds.has(r.review_id));
  const cases=useMemo(()=>data?.cases.map(c=>({...c,...schoolPriorityStatus(c,store.saved,accepted,data.reference_year),effectiveMissing:missingFor(c,store.saved,accepted,allocationOnly,data.reference_year)}))||[],[data,store.saved,accepted,allocationOnly]);
  const districtCounts=useMemo(()=>{const out={};for(const c of cases)if(matchesReviewTask(c,variable,allocationOnly,includeResearchLeads))out[c.district_name]=(out[c.district_name]||0)+1;return out;},[cases,variable,allocationOnly,includeResearchLeads]);
  const filtered=useMemo(()=>cases.filter(c=>matchesReviewTask(c,variable,allocationOnly,includeResearchLeads)&&(state==='all'||c.state_code===state)&&(district==='all'||c.district_name===district)&&(!query||(c.school_name+' '+c.district_name+' '+c.state_code).toLowerCase().includes(query.toLowerCase()))).sort((a,b)=>(districtCounts[b.district_name]||0)-(districtCounts[a.district_name]||0)||a.school_name.localeCompare(b.school_name)),[cases,query,state,district,variable,allocationOnly,districtCounts,includeResearchLeads]);
  const editingReview=store.saved.find(r=>r.review_id===editingId);
  const editingDraft=store.drafts['review:'+editingId];
  const current=editingReview?cases.find(c=>c.school_id===editingReview.school_id):filtered.find(c=>c.school_id===active)||filtered[0];
  const availableSites=editingReview||variable==='corrections'?current?.sites:current?.sites.filter(s=>current.active_site_ids.includes(s.site_id));
  const site=availableSites?.find(s=>s.site_id===(editingDraft?.site_id||siteId))||availableSites?.find(s=>current.priority_site_ids.includes(s.site_id))||availableSites?.[0];
  const draftKey=editingReview?'review:'+editingId:current?.school_id+':'+site?.site_id;
  const draft={...EMPTY,reference_year:data?.reference_year||'2025-26',...store.drafts[draftKey]};
  const recordedAllocation=site&&current?fieldWithReviews(current,site,'elementary_allocation_model',store.saved,accepted,data.reference_year):null;
  const allocationFirst=variable==='elementary_allocation_model'||variable==='corrections'||Boolean(editingReview?.changes?.elementary_allocation_model);
  const hasCoding=Boolean(draft.delivery||draft.population||draft.allocation.trim()||draft.languages.trim()||draft.program_status);
  const hasEvidence=Boolean(draft.evidence_url.trim()||draft.notes.trim()||draft.source_quote.trim());
  const patch=(key,value)=>{setFormError('');setStore(s=>({...s,drafts:{...s.drafts,[draftKey]:{...draft,...(typeof key==='object'?key:{[key]:value})}}}));};
  const openCase=c=>{setEditingId('');setActive(c.school_id);setSiteId(c.sites[0].site_id);setFormError('');setMobileQueue(false);setView('queue');mainRef.current?.scrollTo({top:0});};
  const chooseTask=task=>{setVariable(task);setAllocationOnly(task==='delivery_structure');setActive('');setEditingId('');setListLimit(150);};
  useEffect(()=>{if(!editingId&&filtered[0]&&!filtered.some(c=>c.school_id===active)){setActive(filtered[0].school_id);setSiteId(filtered[0].sites[0].site_id);}},[filtered,active,editingId]);
  const goNext=()=>{const index=filtered.findIndex(c=>c.school_id===current?.school_id);const next=filtered[index+1]||filtered.find(c=>c.school_id!==current?.school_id);if(next)openCase(next);else setToast('You’ve reached the end of this filtered queue.');};
  const save=(park=false)=>{
    if(!current||!site)return;const changes={};
    if(draft.delivery)changes.delivery_structure={value:draft.delivery,site_ids:targetsForDraft(draft,'delivery_structure',site,current)};
    if(draft.population)changes.population_model={value:draft.population,site_ids:targetsForDraft(draft,'population_model',site,current)};
    if(draft.allocation.trim()){const v=draft.allocation.trim().replace(/\s/g,'').replace(/[-–:]/g,'/');const pieces=v.split('/').map(Number);if(!/^\d{1,3}(\.\d+)?\/\d{1,3}(\.\d+)?$/.test(v)||pieces.some(x=>x<0||x>100)||Math.abs(pieces.reduce((a,b)=>a+b,0)-100)>.001){setFormError('Enter an allocation such as 90/10 or 50/50, totaling 100.');return;}if(!draft.grade_scope.trim()){setFormError('Add the grades to which the allocation applies.');return;}const grades=allocationGrades(draft.grade_scope);if(grades&&(grades.every(g=>g<0)||grades.every(g=>g>=6))){setFormError('Use an elementary grade or grade range for this allocation. Put preschool-only or secondary course details in the notes.');return;}changes.elementary_allocation_model={value:v,site_ids:targetsForDraft(draft,'elementary_allocation_model',site,current)};}
    if(draft.languages.trim())changes.instruction_languages={value:[...new Set(draft.languages.split(/[,;+]/).map(s=>s.trim()).filter(Boolean))],site_ids:targetsForDraft(draft,'instruction_languages',site,current)};
    let programEvent=null;
    if(draft.program_status){
      const statusYear=draft.status_year||draft.reference_year;
      if(statusYear>draft.reference_year){setFormError('The status year cannot be later than the review year.');return;}
      if(draft.program_status==='moved'&&draft.destination_url){try{const u=new URL(draft.destination_url);if(!['http:','https:'].includes(u.protocol)||u.username||u.password)throw Error();}catch{setFormError('Use an http(s) destination school URL.');return;}}
      const destination=(data.destination_schools||[]).find(s=>s.school_id===draft.destination_id);
      programEvent={kind:draft.program_status,first_school_year:statusYear,site_ids:targetsForDraft(draft,'program_event',site,current),
        destination_school_id:draft.program_status==='moved'?(draft.destination_id||null):null,
        destination_school_name:draft.program_status==='moved'?(destination?.school_name||draft.destination_name.trim()):'',
        destination_url:draft.program_status==='moved'?draft.destination_url.trim():''};
    }
    if(!hasCoding&&(hasEvidence||editingReview?.disposition==='needs_review'))park=true;
    if(park&&hasCoding){setFormError('Use the save button to record your finding. Clear coding choices before parking this case.');return;}
    if(!park&&!hasCoding){setFormError('Add an evidence URL, quotation, or research note, or choose a program value.');return;}
    if(!store.reviewer.trim()){setFormError('Add your reviewer name in the profile menu.');setModal('profile');return;}
    if(!park||draft.evidence_url){try{const u=new URL(draft.evidence_url);if(!['http:','https:'].includes(u.protocol)||u.username||u.password)throw Error();}catch{setFormError('Add the website URL where you found the evidence.');return;}}
    if(draft.source_school_year&&draft.source_school_year>draft.reference_year){setFormError('The year described by the source is later than the review year. Check those years.');return;}
    if(draft.delivery==='mixed'&&!draft.notes.trim()){setFormError('Add a note explaining how delivery varies by grade or program.');return;}
    const earnsWater=!park||hasEvidence;
    const editable=store.saved.find(r=>r.review_id===draft.editing_review_id&&!accepted.has(r.review_id)&&!preparedIds.has(r.review_id));
    const record={review_id:editable?editable.review_id:crypto.randomUUID(),supersedes_review_id:editingReview&&accepted.has(editingReview.review_id)?editingReview.review_id:draft.supersedes_review_id||null,school_id:current.school_id,school_name:current.school_name,selected_site_id:site.site_id,reviewer:store.reviewer.trim(),coded_at:new Date().toISOString(),reference_year:draft.reference_year,source_school_year:draft.source_school_year||null,coding_method:draft.coding_method||'not_recorded',grade_scope:draft.grade_scope.trim(),evidence_url:draft.evidence_url.trim()?new URL(draft.evidence_url.trim()).href:'',source_locator:draft.source_locator.trim(),source_quote:draft.source_quote.trim(),notes:draft.notes.trim(),disposition:park?'needs_review':'coded',changes,...(programEvent?{program_event:programEvent}:{})};
    setStore(s=>{const drafts={...s.drafts};delete drafts[draftKey];return {...s,drafts,saved:[...s.saved.filter(r=>r.review_id!==record.review_id),record],garden:!earnsWater?s.garden:waterGarden(s.garden,record.review_id+(editable?':'+record.coded_at:''))};});
    if(earnsWater){setWatering(true);setTimeout(()=>setWatering(false),2200);}setToast(park?hasEvidence?'Evidence saved on this device.':'Case parked for another look.':editingReview?'Changes saved on this device.':'Review saved on this device.');if(editingReview){setEditingId('');setView('saved');}else goNext();
  };
  useEffect(()=>{const handler=e=>{if((e.metaKey||e.ctrlKey)&&e.key==='Enter'&&view==='queue'&&!modal){e.preventDefault();save();}};window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);});
  const editReview=r=>{
    const c=cases.find(c=>c.school_id===r.school_id);if(!c){setToast('This school is outside the current inventory. Export a backup to keep its review.');return;}
    if(preparedIds.has(r.review_id)&&!accepted.has(r.review_id)){setToast('Check publishing status before correcting a batch already handed to GitHub.');return;}
    try{
      const key='review:'+r.review_id;
      const restored=store.drafts[key]||draftFromReview(r,c,EMPTY);
      setStore(s=>({...s,drafts:{...s.drafts,[key]:restored}}));
      openCase(c);setSiteId(restored.site_id);setEditingId(r.review_id);setModal('');
      setToast(accepted.has(r.review_id)?'Your correction will keep the published decision in the research history.':'Editing your saved review.');
    }catch(e){setToast(e.message);}
  };
  const discardEdits=()=>{setStore(s=>{const drafts={...s.drafts};delete drafts['review:'+editingId];return {...s,drafts};});setEditingId('');setView('saved');setFormError('');setToast('Edits discarded. The saved review is unchanged.');};
  const removeReview=r=>{setStore(s=>{const drafts={...s.drafts};delete drafts['review:'+r.review_id];return {...s,drafts,saved:s.saved.filter(x=>x.review_id!==r.review_id)};});if(editingId===r.review_id)setEditingId('');setToast('Unpublished review removed.');};
  const backup=()=>{const b=new Blob([JSON.stringify({version:1,...store},null,2)],{type:'application/json'});const url=URL.createObjectURL(b);const a=document.createElement('a');a.href=url;a.download='fieldnotes-backup-'+new Date().toLocaleDateString('en-CA')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  const restore=async file=>{try{const b=JSON.parse(await file.text());if(b.version!==1||!Array.isArray(b.saved)||typeof b.drafts!=='object')throw Error();const ids=new Set(store.saved.map(r=>r.review_id));setStore(s=>({...s,drafts:{...b.drafts,...s.drafts},saved:[...s.saved,...b.saved.filter(r=>!ids.has(r.review_id))],garden:b.garden&&b.garden.reviews>s.garden.reviews?b.garden:s.garden,batches:[...s.batches,...(b.batches||[]).filter(v=>!s.batches.some(o=>o.batch_id===v.batch_id))]}));setToast('Backup restored. Existing reviews were kept.');}catch{setToast('That file is not a valid Fieldnotes backup.');}};
  useEffect(()=>{if(modal!=='publish')return;setBatch(null);setBatchError('');if(!pending.length)return;let valid=true;prepareBatch(pending,data).then(b=>valid&&setBatch(b)).catch(e=>valid&&setBatchError(e.message));return()=>{valid=false;};},[modal,pending,data]);
  const unfinishedReviews=batch?.records.filter(r=>hasReviewEdits(r,store.drafts['review:'+r.review_id],cases.find(c=>c.school_id===r.school_id)))||[];
  const unfinishedBatchEdits=unfinishedReviews.length>0;
  const openPublish=()=>{setBatch(null);setBatchError('');setHandoffError('');setManualLink('');setModal('publish');};
  const rememberBatch=async b=>{
    const next=store.batches.some(old=>old.batch_id===b.batch_id)?store:{...store,batches:[...store.batches,
      {batch_id:b.batch_id,review_ids:b.records.map(r=>r.review_id),url:b.url,created_at:b.created_at}]};
    const ids=b.review_ids||b.records.map(r=>r.review_id);
    const nextEditingId=ids.includes(editingId)?'':editingId;
    // Finish the browser write before leaving the page. GitHub sign-in and
    // submission may take time, and Back must recover this exact batch.
    await saveWorkspace({...next,lastSchoolId:active,editingReviewId:nextEditingId});
    setStore(next);setEditingId(nextEditingId);
  };
  const handoff=async e=>{
    e.preventDefault();if(!batch||unfinishedBatchEdits||handoffBusy)return;
    setHandoffBusy(true);setHandoffError('');
    try{await rememberBatch(batch);window.location.assign(batch.url);setModal('');setView('saved');}
    catch{setHandoffError('GitHub could not be opened. Your reviews are still here. Try the saved submission link, or export a backup if browser storage is unavailable.');}
    finally{setHandoffBusy(false);}
  };
  const copySubmission=async b=>{
    if(handoffBusy)return;setHandoffBusy(true);setHandoffError('');
    try{await rememberBatch(b);
      try{await navigator.clipboard.writeText(b.url);setToast('Submission link copied. Paste it into your browser, then sign in and submit on GitHub.');}
      catch{setManualLink(b.url);setModal('publish');}
    }catch{setHandoffError('The batch could not be saved locally. Export a backup before leaving this page.');setModal('publish');}
    finally{setHandoffBusy(false);}
  };
  const allocationCases=cases.filter(c=>c.allocation_known&&!c.retired);
  const needingDelivery=allocationCases.filter(c=>missingFor(c,store.saved,accepted,true,data?.reference_year).includes('delivery_structure')).length;
  const completed=allocationCases.length-needingDelivery;
  const activeIndex=filtered.findIndex(c=>c.school_id===current?.school_id);
  useEffect(()=>{if(activeIndex>=listLimit)setListLimit(activeIndex+50);},[activeIndex,listLimit]);
  if(!data||!hydrated)return <div className="loading-screen"><div className="brand-mark"><BookOpen/></div><h1>Loading the school inventory</h1>{loadError?<><p>{loadError}</p><button className="primary" onClick={refresh}>Try again</button></>:<LoaderCircle className="spin"/>}</div>;

  return <div className="app-shell">
    <aside className="rail">
      <a className="brand" href="#" onClick={e=>{e.preventDefault();setEditingId('');setView('queue');}}><span className="brand-mark"><BookOpen size={20}/></span><span>fieldnotes<span className="brand-dot">.</span></span></a>
      <div className="rail-label">DUAL-LANGUAGE RESEARCH</div>
      <nav><button className={view==='queue'?'nav-item selected':'nav-item'} onClick={()=>{setEditingId('');setView('queue');}}><ClipboardList size={18}/>Review queue<span className="nav-count">{filtered.length.toLocaleString()}</span></button><button className={view==='saved'?'nav-item selected':'nav-item'} onClick={()=>setView('saved')}><History size={18}/>My reviews{store.saved.length>0&&<span className="nav-count">{store.saved.length}</span>}</button><button className={view==='leaderboard'?'nav-item selected':'nav-item'} onClick={()=>setView('leaderboard')}><Trophy size={18}/>Leaderboard</button></nav>
      <div className="rail-progress"><div className="progress-label"><span>Delivery model coverage</span><strong>{(completed/Math.max(1,allocationCases.length)*100).toFixed(1)}%</strong></div><p><strong>{completed.toLocaleString()}</strong> of <strong>{allocationCases.length.toLocaleString()}</strong> have a delivery model recorded.</p><p>All {allocationCases.length.toLocaleString()} already have allocation data.</p></div>
      <div className="rail-spacer"/><Plant garden={store.garden} watering={watering} now={now}/>
      <button className="rail-help" onClick={()=>setModal('help')}><CircleHelp size={16}/>How this works</button>
      <button className="profile" aria-label={store.reviewer?'Reviewer: '+store.reviewer:'Set reviewer name'} onClick={()=>setModal('profile')}><span className="avatar">{store.reviewer.slice(0,2).toUpperCase()||'?'}</span><span><strong>{store.reviewer||'Set reviewer name'}</strong><small>Researcher</small></span><ChevronDown size={15}/></button>
    </aside>
    <div className="workspace">
      <header className="topbar"><div className="breadcrumb"><BookOpen size={15}/><span>National DL inventory</span><ChevronRight size={13}/><strong>{view==='queue'?'School review':view==='leaderboard'?'Leaderboard':'My reviews'}</strong></div><div className="top-actions"><span className="inventory-year">Inventory {data.reference_year.replace('-','–')}</span><a className="github-link" href={'https://github.com/'+data.repository} target="_blank" rel="noreferrer"><Github size={17}/><span>Dataset</span><ExternalLink size={12}/></a><button className="primary publish-button" onClick={openPublish}><Send size={15}/>Publish{pending.length>0&&<span>{pending.length}</span>}</button></div></header>
      {storageError&&<div className="error-banner">Browser storage is full or unavailable. Export a backup before closing this tab.<button onClick={backup}>Export backup</button></div>}
      {view==='leaderboard'?<Leaderboard rows={data.leaderboard||[]} reviewer={store.reviewer} updatedAt={data.updated_at} onRefresh={refresh} refreshing={refreshing}/>:view==='saved'?<SavedReviews store={store} cases={cases} accepted={accepted} pending={pending} awaiting={awaiting} inventoryYear={data.reference_year}
        filters={reviewFilters} setFilters={setReviewFilters} refreshing={refreshing} onRefresh={refresh} onBackup={backup} onPublish={openPublish}
        onQueue={()=>{setEditingId('');setView('queue');}} onEdit={editReview} onCopySubmission={copySubmission} handoffBusy={handoffBusy} onRevisit={r=>{const c=cases.find(c=>c.school_id===r.school_id);if(c)openCase(c);}} onRemove={removeReview}/>:
      <div className="desk-layout">
        <aside className={'queue-panel '+(mobileQueue?'queue-open':'')}><div className="queue-title"><h2>Review queue</h2><span>{filtered.length.toLocaleString()}</span><button className="icon-button mobile-only" onClick={()=>setMobileQueue(false)} aria-label="Close school list"><X size={18}/></button></div><p className="queue-caption">{variable==='corrections'?'Search recorded data, including completed schools.':variable==='elementary_allocation_model'?'Schools missing an allocation; unconfirmed DL leads are labeled.':'Schools needing delivery or allocation data'}</p><div className="search-box"><Search size={17}/><input aria-label="Search schools or districts" placeholder="Search schools or districts" value={query} onChange={e=>setQuery(e.target.value)}/>{query&&<button className="icon-button" onClick={()=>setQuery('')} aria-label="Clear search"><X size={13}/></button>}</div><label className="task-select"><span className="filter-label">Review task</span><select aria-label="Review task" value={variable} onChange={e=>chooseTask(e.target.value)}><option value="delivery_structure">Delivery model gaps</option><option value="elementary_allocation_model">Missing allocation</option><option value="corrections">Find &amp; correct data</option><option value="population_model">One-way / two-way gaps</option><option value="instruction_languages">Language gaps</option><option value="">All incomplete schools</option></select></label><div className="filter-row"><label><span className="sr-only">State</span><select aria-label="State" value={state} onChange={e=>{setState(e.target.value);setDistrict('all');}}><option value="all">All states</option>{Object.keys(data.state_names).sort((a,b)=>data.state_names[a].localeCompare(data.state_names[b])).map(c=><option key={c} value={c}>{data.state_names[c]}</option>)}</select></label><label className="district-filter"><select aria-label="District" value={district} onChange={e=>setDistrict(e.target.value)}><option value="all">All districts</option>{[...new Set(cases.filter(c=>state==='all'||c.state_code===state).map(c=>c.district_name))].sort().map(d=><option key={d}>{d}</option>)}</select></label></div>{variable==='delivery_structure'&&<label className="checkline queue-scope"><input type="checkbox" checked={allocationOnly} onChange={e=>setAllocationOnly(e.target.checked)}/><span>Allocation already recorded</span><CircleHelp size={12}/></label>}{variable!=='corrections'&&(!allocationOnly||variable!=='delivery_structure')&&<label className="checkline queue-scope"><input aria-label="Include unconfirmed DL leads" type="checkbox" checked={includeResearchLeads} onChange={e=>setIncludeResearchLeads(e.target.checked)}/><span>Include unconfirmed DL leads</span></label>}<div className="queue-list">{filtered.slice(0,listLimit).map(c=><button className={'school-row '+(c.school_id===current?.school_id?'active':'')} key={c.school_id} onClick={()=>openCase(c)}><div className="school-row-top"><span className="state-code">{c.state_code}</span>{store.saved.some(r=>r.school_id===c.school_id)&&<span className="tiny-saved"><Check size={11}/>Reviewed</span>}</div><strong>{c.school_name}</strong>{c.dl_status==='needs_confirmation'&&<span className="candidate-label">DL status needs confirmation</span>}<span className="school-district">{c.district_name}</span><div className="school-row-bottom"><span>{[...new Set(c.sites.map(s=>allocationSummary(fieldWithReviews(c,s,'elementary_allocation_model',store.saved,accepted,data.reference_year))))].join(' · ')}</span><span>{c.sites.length>1?c.sites.length+' records':'1 program record'}</span></div></button>)}{filtered.length>listLimit&&<button className="list-end" onClick={()=>setListLimit(n=>n+150)}>Show 150 more schools <ChevronDown size={13}/></button>}{!filtered.length&&<div className="queue-empty"><CheckCheck size={28}/><strong>No schools match these filters.</strong><p>Try another state or variable.</p></div>}</div><div className="queue-footer"><span className="live-dot"/>Research inventory · {data.reference_year.replace('-','–')}</div></aside>
        <main className="case-workspace" ref={mainRef}>
          <button className="secondary mobile-only school-list-button" onClick={()=>setMobileQueue(true)}><Filter size={15}/>Choose a school</button>
          {current&&site?<><div className="case-page-header"><div><div className="section-eyebrow">SCHOOL REVIEW <span>/</span> {stateLabel(current.state_code,data).toUpperCase()}</div><h1>{current.school_name}</h1><p className="case-district">{current.district_name}<span>·</span>{stateLabel(current.state_code,data)}</p></div><div className="case-position"><span>{activeIndex>=0?activeIndex+1:'—'} <i>/</i> {filtered.length.toLocaleString()}</span><div><button className="icon-button" aria-label="Previous school" disabled={activeIndex<=0} onClick={()=>openCase(filtered[activeIndex-1])}><ArrowLeft size={16}/></button><button className="icon-button" aria-label="Next school" onClick={goNext}><ArrowRight size={16}/></button></div></div></div>
          {editingReview&&<div className="editing-banner"><div><strong>{accepted.has(editingId)?'Correcting a published review':'Editing a saved review'}</strong><p>Save your changes, or return to My reviews and resume later. Each variable keeps its saved program scope.</p></div><div><button className="text-button" onClick={()=>setView('saved')}>Back to My reviews</button><button className="text-button" onClick={discardEdits}>Discard edits</button></div></div>}
          <div className="case-status-note">{current.dl_status==='needs_confirmation'&&<p>This school is a research lead. DL operation for {data.reference_year.replace('-','–')} is not yet confirmed in the inventory. Use a source describing its academic dual-language program.</p>}{variable==='corrections'&&<p>Correct a recorded value below. The source, school year and earlier observations will remain in the data.</p>}</div><div className="known-strip"><div className="known-item"><span>INSTRUCTIONAL LANGUAGES</span><strong>{valuesText(site.known.instruction_languages)}</strong></div><div className="known-item"><span>LANGUAGE ALLOCATION</span><strong>{allocationSummary(recordedAllocation)}</strong></div><div className="known-item"><span>PROGRAM TYPE</span><strong>{valuesText(site.known.population_model)}</strong></div><div className="known-item known-grades"><span>RECORDED GRADES</span><strong>{valuesText(site.known.programme_grade_scope)}</strong></div></div>
          <div className="case-grid"><section className="coding-card"><div className="card-header"><h2>{editingReview?'Revise your finding':'Record a finding'}</h2><span className="hand-coded">Hand-coded</span></div>
            {current.sites.length>1&&<label className="field program-picker"><span>Program record being reviewed</span><select disabled={Boolean(editingReview)} value={site.site_id} onChange={e=>{setSiteId(e.target.value);setFormError('');}}>{availableSites.map(s=><option key={s.site_id} value={s.site_id}>{s.label} · {s.program_name}</option>)}</select></label>}
            <div className="review-period"><label className="year-control"><span>Applies to</span><select aria-label="Review school year" value={draft.reference_year} onChange={e=>patch('reference_year',e.target.value)}>{YEARS.map(y=><option key={y} value={y}>{y.replace('-','–')}</option>)}</select></label></div>{allocationFirst&&<AllocationEditor field={recordedAllocation} draft={draft} patch={patch}/>}<ProgramStatus draft={draft} school={current} site={site} destinations={data.destination_schools||data.cases} years={SOURCE_YEARS} patch={patch}/>
            <div className="delivery-label"><div><h3>Delivery model</h3></div></div>
            <p className="recorded-delivery" aria-label="Recorded delivery model"><span>Recorded for {data.reference_year.replace('-','–')}:</span> <strong>{valuesText(site.known.delivery_structure)}</strong>{site.known.delivery_structure.status==='provisional'&&<span> · Provisional</span>}{site.known.delivery_structure.status==='conflicting'&&<span> · Conflicting evidence</span>}</p>
            <fieldset className="choice-grid"><legend className="sr-only">Delivery model</legend>{[
              ['whole_school','Whole school','All students receive academic DL.'],['strand','Strand','DL runs alongside a non-DL pathway.'],['mixed','Mixed / varies','Participation differs by grade or program.']
            ].map(([v,label,help])=><label key={v} className={'choice-card '+(draft.delivery===v?'chosen':'')}><input type="radio" name="delivery" value={v} checked={draft.delivery===v} onChange={()=>patch('delivery',v)}/><strong>{label}</strong><span>{help}</span></label>)}</fieldset>
            {draft.delivery&&<button className="clear-choice" onClick={()=>patch('delivery','')}>Clear delivery choice</button>}
            {current.sites.length>1&&draft.delivery&&<label className="checkline apply-all"><input type="checkbox" checked={draft.all_delivery} onChange={e=>patch({all_delivery:e.target.checked,delivery_site_ids:[site.site_id]})}/>Apply this delivery finding to all {current.sites.length} DL program records at this campus</label>}
            {!allocationFirst&&<AllocationEditor field={recordedAllocation} draft={draft} patch={patch}/>}<label className="field evidence-field"><span>Evidence URL <b>Required for coding</b></span><div className="input-with-icon"><Link2 size={16}/><input aria-label="Evidence website URL" type="url" maxLength={2048} placeholder="Paste the school or program webpage URL" value={draft.evidence_url} onChange={e=>patch('evidence_url',e.target.value)}/>{draft.evidence_url.startsWith('http')&&<a href={draft.evidence_url} target="_blank" rel="noreferrer" aria-label="Open entered evidence URL"><ExternalLink size={14}/></a>}</div></label>
            <label className="field"><span>Research notes <span className="optional">Optional</span></span><textarea aria-label="Research notes" maxLength={3000} rows={3} placeholder="Capture useful evidence, open questions, grades, or changes over time." value={draft.notes} onChange={e=>patch('notes',e.target.value)}/></label>
            <div className="basis-control"><div className="basis-label">Basis for this decision</div>{draft.coding_method&&<button className="clear-basis" onClick={()=>patch('coding_method','')}>Clear coding basis</button>}</div><fieldset className="confidence"><legend className="sr-only">Coding method</legend><label className={draft.coding_method==='explicit_source_statement'?'on':''}><input type="radio" name="basis" checked={draft.coding_method==='explicit_source_statement'} onChange={()=>patch('coding_method','explicit_source_statement')}/><span>Explicitly stated</span></label><label className={draft.coding_method==='researcher_interpretation'?'on':''}><input type="radio" name="basis" checked={draft.coding_method==='researcher_interpretation'} onChange={()=>patch('coding_method','researcher_interpretation')}/><span>My interpretation</span></label></fieldset>
            <details className="extra-fields"><summary>Source details &amp; other variables <ChevronDown size={16}/></summary><div className="extra-content"><div className="two-fields"><label className="field"><span>School year described by source</span><select aria-label="Source school year" value={draft.source_school_year} onChange={e=>patch('source_school_year',e.target.value)}><option value="">Not stated / undated</option>{SOURCE_YEARS.map(y=><option key={y}>{y}</option>)}</select></label></div><label className="field"><span>Supporting quotation</span><textarea aria-label="Supporting quotation" maxLength={3000} rows={3} value={draft.source_quote} onChange={e=>patch('source_quote',e.target.value)} placeholder="Paste the relevant wording, if useful."/></label><label className="field"><span>Page or section</span><input aria-label="Page or section" maxLength={200} value={draft.source_locator} onChange={e=>patch('source_locator',e.target.value)} placeholder="e.g. Handbook page 12, Program overview"/></label><div className="extra-divider">Additional program variables <span>Leave blank to keep the current data.</span></div><div className="two-fields"><label className="field"><span>One-way / two-way</span><select aria-label="Population model" value={draft.population} onChange={e=>patch('population',e.target.value)}><option value="">Keep current value</option><option value="one_way">One-way</option><option value="two_way">Two-way</option></select></label></div><label className="field"><span>Instructional languages</span><input aria-label="Instructional languages" placeholder="e.g. English, Spanish" maxLength={500} value={draft.languages} onChange={e=>patch('languages',e.target.value)}/></label><p className="field-help">{editingReview?'Existing changes retain their saved program scope; new variables apply to the selected program.':'Other-variable changes apply to the selected program.'} Record the source’s grades for an allocation label; its language order and full-day shares are not assumed.</p></div></details>
            {formError&&<div role="alert" className="form-error">{formError}</div>}
            {!hasCoding&&<p className="field-help evidence-save-help">Save links, quotations, or notes now. You can code program values later.</p>}
            <div className="coding-footer"><span className="draft-indicator"><CheckCheck size={14}/>{storageError?'Draft needs a backup':savingDraft?'Saving draft…':'Draft saved on this device'}</span><div>{!editingReview&&<button className="text-button park-button" onClick={()=>save(true)}><Clock3 size={14}/>Park case</button>}<button className="primary save-button" onClick={()=>save(false)}>{hasCoding?(editingReview?'Save changes':'Save & next'):(editingReview?'Save evidence':'Save evidence & next')}<ArrowRight size={16}/></button></div></div>
          </section>
          <aside className="evidence-column"><div className="source-heading"><h2>Sources &amp; research leads</h2><span>{current.references.length} {current.references.length===1?'lead':'leads'}</span></div><p className="source-intro">{current.references.length?'Existing inventory sources. Cite the page that supports your finding.':'No source link is attached to this record. Use the school and district search below.'}</p><div className="source-cards">{current.references.map((r,i)=><article className="source-card" key={r.url}><span className="source-number">{i+1}.</span><h3><a href={r.url} target="_blank" rel="noreferrer">{r.label}</a></h3><p>{r.domain}</p>{r.locator&&!/source_|claim_|\.csv|\.json|row[_ :]|^[A-Z]{2}[-–]P[-–]/i.test(r.locator)&&<span className="source-locator">{r.locator}</span>}{r.excerpt&&<blockquote className="source-excerpt">{r.excerpt}</blockquote>}<button className="use-source" onClick={()=>{patch('evidence_url',r.url);setToast('Source URL added to your draft.');}} title="Use this URL as your evidence link"><span aria-hidden="true">Cite this source</span><span className="sr-only">Use source {i+1} URL</span></button></article>)}</div><a className="search-lead" href={hrefSearch(current)} target="_blank" rel="noreferrer"><Search size={15}/><span>Search school + district<small>Dual-language program information</small></span><ExternalLink size={12}/></a><div className="research-tip"><h3>Coding the delivery model</h3><dl><dt>Whole school</dt><dd>All students receive academic instruction through a dual-language program. The school may offer several partner languages.</dd><dt>Strand</dt><dd>Some students participate in DL; others at the same campus follow a non-DL academic program.</dd><dt>Mixed / varies</dt><dd>The school uses different delivery models by grade or program. Explain the differences in your notes.</dd></dl><p>Ratios such as 50/50 and 90/10 describe language allocation. Choose the delivery model based on which students participate.</p><p>English-learner support services can be provided within either a whole-school or strand program.</p></div><div className="inventory-note">Known details above describe the {data.reference_year.replace('-','–')} inventory. Your review keeps its own applicable year and source context.</div></aside></div><div className="desk-footnote"><span><CheckCheck size={13}/>Original evidence stays in the dataset.</span><span>⌘ / Ctrl + Enter to save</span></div></>:<div className="empty-state"><CheckCheck size={38}/><h2>No school selected</h2><p>No school is selected. Adjust the queue filters to continue.</p></div>}
        </main>
      </div>}
    </div>
    {toast&&<div className="toast" role="status"><Check size={17}/>{toast}<button className="icon-button" onClick={()=>setToast('')} aria-label="Dismiss notification"><X size={14}/></button></div>}
    {modal==='profile'&&<Modal title="Your research workspace" onClose={()=>setModal('')}><label className="field"><span>Reviewer name</span><input aria-label="Reviewer name" maxLength={100} value={store.reviewer} onChange={e=>setStore(s=>({...s,reviewer:e.target.value}))}/></label><p className="modal-copy">Use your own name for hand-coded decisions. GitHub records the account that publishes each batch separately. To publish, the repository owner must add your GitHub username to the approved-reviewer list; repository write access is not required.</p><div className="backup-options"><button className="secondary" onClick={backup}><ArrowDownToLine size={15}/>Export a backup</button><button className="secondary" onClick={()=>importRef.current.click()}>Restore a backup</button><input ref={importRef} type="file" accept="application/json" className="sr-only" onChange={e=>e.target.files[0]&&restore(e.target.files[0])}/></div><p className="modal-note">Drafts, saved reviews, and your plant live in this browser. Export a backup before moving to another device or clearing browser data.</p><button className="primary full-width" onClick={()=>setModal('')}>Back to the research <ArrowRight size={15}/></button></Modal>}
    {modal==='help'&&<Modal title="Using Fieldnotes" onClose={()=>setModal('')}><ol className="how-steps"><li><span>01</span><div><h3>Choose a school and follow a lead.</h3><p>Filter by state, district, or missing variable. Sources open in another tab.</p></div></li><li><span>02</span><div><h3>Record what the evidence supports.</h3><p>Add sources, notes, or a quotation. Save evidence now even if you cannot assign a program value yet. Keep the year and grade scope clear.</p></div></li><li><span>03</span><div><h3>Save, compare, and revise.</h3><p>Drafts autosave locally. Use My reviews to find earlier schools by district, check the full evidence, and edit before submitting. A saved finding or research note adds a little water.</p></div></li><li><span>04</span><div><h3>Publish a batch when you’re ready.</h3><p>Review the full batch and edit any entry before continuing to GitHub. Each contributor needs a GitHub account and the repository owner’s approval of their username. Confirm with your usual sign-in. Authorized reviews are checked, added to the data, and marked hand-coded. Return here and check publishing status after the dataset refreshes.</p></div></li></ol><p className="modal-note">The published record preserves your evidence URL, notes, coding method, school year and reviewer. An interpretation stays distinct from an explicit source statement.</p><button className="primary full-width" onClick={()=>setModal('')}>Return to the review queue <ArrowRight size={15}/></button></Modal>}
    {modal==='publish'&&<Modal title="Review before publishing" onClose={()=>setModal('')} className="publish-modal">
      <p className="modal-copy">Check each saved entry, its program scope, and its evidence. Edit any review before continuing to GitHub.</p>
      <button className="text-button" onClick={()=>{setModal('');setView('saved');}}>Review all saved work <ArrowRight size={14}/></button>
      {batchError?<div role="alert" className="form-error">{batchError}</div>:pending.length&&!batch?<div className="batch-loading"><LoaderCircle className="spin" size={20}/>Preparing your batch…</div>:batch?<>
        <div className="batch-summary"><span><strong>{batch.records.length}</strong> reviews in this batch</span><span className="hand-coded">Hand-coded</span></div>
        <div className="batch-reviews">{batch.records.map(r=><article className="batch-review" key={r.review_id}>
          <div className="log-heading"><div><h3>{r.school_name}</h3><span>{cases.find(c=>c.school_id===r.school_id)?.district_name} · {r.reviewer}</span></div><button className="secondary small" onClick={()=>editReview(r)}>{store.drafts['review:'+r.review_id]?'Resume editing':'Edit review'}<ArrowRight size={13}/></button></div>
          <ReviewDetails record={r} school={cases.find(c=>c.school_id===r.school_id)} inventoryYear={data.reference_year}/>
          {hasReviewEdits(r,store.drafts['review:'+r.review_id],cases.find(c=>c.school_id===r.school_id))&&<p className="form-error">This review has unsaved edits. Resume editing and save or discard them before publishing.</p>}
        </article>)}</div>
        {pending.length>batch.records.length&&<p className="modal-note">The remaining {pending.length-batch.records.length} reviews will stay saved for your next batch.</p>}
        <div className="github-explainer"><Github size={23}/><p>Confirm on GitHub.<span>GitHub opens in this tab after your work is saved. Sign in if prompted and select Submit new issue. Use Back to return here and check publishing status.</span></p></div>
        {handoffBusy?<button className="primary full-width" disabled>Saving your submission…</button>:unfinishedBatchEdits?<button className="primary full-width" onClick={()=>editReview(unfinishedReviews[0])}>Review unsaved changes <ArrowRight size={15}/></button>:<a className="primary full-width" href={batch.url} onClick={handoff}>Continue on GitHub <ArrowRight size={15}/></a>}
        <button className="text-button copy-submission" disabled={unfinishedBatchEdits||handoffBusy} onClick={()=>copySubmission(batch)}><Link2 size={13}/>Copy submission link</button>
      </>:<><div className="empty-publish"><CheckCheck size={30}/><h3>{awaiting.length?'Your prepared reviews are waiting for confirmation.':'No unpublished reviews yet.'}</h3><p>{awaiting.length?'Open the saved submission below in this tab. Sign in and select Submit new issue, then use Back to check publishing status here.':'Save a review from the school queue, then publish it here.'}</p></div>
        {awaiting.length>0&&store.batches.filter(b=>b.review_ids.some(id=>!accepted.has(id))).map(b=><div className="pending-submission" key={b.batch_id}><a className="secondary full-width batch-link" href={b.url}>Confirm {b.review_ids.length} reviews on GitHub <ArrowRight size={14}/></a><button className="text-button copy-submission" disabled={handoffBusy} onClick={()=>copySubmission(b)}><Link2 size={13}/>Copy submission link</button></div>)}
        <button className="secondary full-width" onClick={()=>{refresh();setModal('');setView('saved');}}>Check publishing status</button>
      </>}
      {handoffError&&<div role="alert" className="form-error">{handoffError}</div>}
      {manualLink&&<label className="field manual-submission"><span>Copy this submission link into your browser’s address bar</span><textarea aria-label="Prepared GitHub submission URL" readOnly rows={3} value={manualLink} onFocus={e=>e.target.select()}/></label>}
    </Modal>}
  </div>;
}
createRoot(document.getElementById('root')).render(<App/>);
