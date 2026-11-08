export const COMMON_KINDERGARTEN_PERCENTAGES=[90,80,70,60,50];

export function kindergartenChoice(draft) {
  const raw=draft.kindergarten_partner_language_pct;
  if(raw===''||raw===null||raw===undefined||!/^\d{1,3}$/.test(String(raw)))return null;
  const percentage=Number(raw);
  if(!Number.isInteger(percentage)||percentage<0||percentage>100)return null;
  const grades=allocationGrades(draft.grade_scope);
  if(!grades||grades.length!==1||grades[0]!==0)return null;
  const value=`${percentage}/${100-percentage}`;
  return draft.allocation===value?{percentage,value}:null;
}

export function kindergartenReviewError(record) {
  const change=record.changes?.elementary_allocation_model;
  if(!change)return '';
  const grades=allocationGrades(record.grade_scope),pieces=String(change.value).match(/^(\d{1,3})\/(\d{1,3})$/);
  if(!grades||grades.length!==1||grades[0]!==0||!pieces||Number(pieces[1])+Number(pieces[2])!==100)
    return 'Allocation edits now apply to kindergarten only. Open this review in My reviews and choose a kindergarten percentage, or clear its allocation change.';
  const percentage=change.kindergarten_partner_language_pct;
  if(percentage!==undefined&&(!Number.isInteger(percentage)||percentage<0||percentage>100||change.value!==`${percentage}/${100-percentage}`))
    return 'Choose a valid kindergarten percentage from the menu before publishing.';
  return '';
}

export function allocationGrades(scope) {
  const match=String(scope||'').toUpperCase().replace(/\bPRE[ -]?KINDERGARTEN\b/g,'PK')
    .replace(/\bKINDERGARTEN\b/g,'K').replace(/\bPRE[ -]?K\b/g,'PK').replace(/[–—]/g,'-').trim()
    .match(/^(?:GRADES?\s+)?(PK|PRE-K|K|KG|\d{1,2})(?:\s*-\s*(K|\d{1,2}))?$/);
  if(!match)return null;
  const number=s=>['PK','PRE-K'].includes(s)?-1:['K','KG'].includes(s)?0:Number(s);
  const low=number(match[1]),high=number(match[2]||match[1]);
  return low>=-1&&high<=12&&low<=high?Array.from({length:high-low+1},(_,i)=>low+i):null;
}

const gradeName=n=>n===-1?'PK':n===0?'K':String(n);
function unreviewedParts(row,occupied){
  const grades=allocationGrades(row.grade_scope);
  if(!grades)return [];
  const remaining=grades.filter(g=>!occupied.has(g));
  if(remaining.length===grades.length)return [row];
  const groups=[];
  for(const g of remaining){if(groups.length&&g===groups.at(-1).at(-1)+1)groups.at(-1).push(g);else groups.push([g]);}
  return groups.map(group=>({...row,grade_scope:group.length===1?gradeName(group[0]):gradeName(group[0])+'-'+gradeName(group.at(-1)),source_grade_scope:row.source_grade_scope||row.grade_scope}));
}

export function allocationWithReviews(field, reviews) {
  if(!reviews.length)return field||{value:[],status:'not_reported',schedules:[]};
  let selected=[],occupied=new Set(),bounded=true;
  for(const review of [...reviews].reverse()){
    const value=review.changes.elementary_allocation_model.value;
    const row={grade_scope:review.grade_scope,model_label:value,model_label_normalized:value,
      named_language_shares:{},source_year:review.source_school_year||null,pending_review_id:review.review_id,
      schedule_status:'reported_policy_requires_review'};
    const grades=allocationGrades(row.grade_scope);
    if(!grades){if(!selected.length)selected=[row];bounded=false;break;}
    selected.push(...unreviewedParts(row,occupied));grades.forEach(g=>occupied.add(g));
  }
  if(bounded)for(const row of field?.schedules||[])selected.push(...unreviewedParts(row,occupied));
  selected.sort((a,b)=>(allocationGrades(a.grade_scope)?.[0]??99)-(allocationGrades(b.grade_scope)?.[0]??99));
  const conflict=selected.some((a,i)=>a.schedule_status==='conflicting_documented_plan'||selected.slice(i+1).some(b=>{
    if(a.service_scope&&b.service_scope&&a.service_scope!==b.service_scope)return false;
    const ag=allocationGrades(a.grade_scope),bg=allocationGrades(b.grade_scope);
    if(ag&&bg&&!ag.some(g=>bg.includes(g)))return false;
    const av=Object.entries(a.named_language_shares||{}).sort(),bv=Object.entries(b.named_language_shares||{}).sort();
    return av.length&&bv.length?JSON.stringify(av)!==JSON.stringify(bv)
      :(a.model_label||a.model_label_normalized)!==(b.model_label||b.model_label_normalized);
  }));
  return {value:[...new Set(selected.map(r=>r.model_label_normalized).filter(Boolean))],
    status:conflict?'conflicting':'reported_model_requires_review',schedules:selected};
}

export function allocationRows(field) {
  const rows=field?.schedules||[];
  const unique=new Map();
  for(const row of rows){
    const model=row.model_label_normalized||row.model_label;
    if(!model)continue;
    const key=JSON.stringify([row.grade_scope,model,row.named_language_shares,row.service_scope]);
    if(!unique.has(key))unique.set(key,{...row,model});
  }
  return [...unique.values()].sort((a,b)=>(allocationGrades(a.grade_scope)?.[0]??99)-(allocationGrades(b.grade_scope)?.[0]??99));
}

export function allocationSummary(field) {
  if(field?.status?.startsWith('not_applicable'))return field.status.includes('preschool')?'Not applicable: preschool only':'Not applicable: secondary program';
  const rows=allocationRows(field);
  const kindergarten=rows.filter(r=>allocationGrades(r.grade_scope)?.includes(0));
  if(kindergarten.length)return 'K: '+[...new Set(kindergarten.map(r=>r.model))].join(' · ');
  if(rows.length)return rows.map(r=>`${r.grade_scope&&r.grade_scope!=='not_reported'?r.grade_scope+': ':''}${r.model}`).join(' · ');
  return field?.value?.join(' · ')||'Not yet recorded';
}

export function allocationGradeLabel(scope) {
  const grades=allocationGrades(scope);
  if(!grades)return scope&&scope!=='not_reported'?scope:'Grades not specified';
  if(grades.length===1)return grades[0]===0?'Kindergarten':grades[0]===-1?'Pre-K':'Grade '+grades[0];
  return 'Grades '+gradeName(grades[0])+'–'+gradeName(grades.at(-1));
}
