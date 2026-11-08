import React from 'react';
import {allocationRows,allocationGradeLabel,kindergartenChoice,COMMON_KINDERGARTEN_PERCENTAGES} from './allocation';

export default function AllocationEditor({field,draft,patch}){
  const rows=allocationRows(field);
  const notApplicable=field?.status?.startsWith('not_applicable');
  const choice=kindergartenChoice(draft);
  const other=Boolean(draft.allocation_other)||(choice&&!COMMON_KINDERGARTEN_PERCENTAGES.includes(choice.percentage));
  const legacy=Boolean(draft.allocation)&&!choice;
  const options=percentages=>percentages.map(p=><option key={p} value={String(p)}>{p}% partner language · {100-p}% English</option>);
  return <section className="allocation-editor" aria-label="Language allocation">
    <h3>Language allocation</h3>
    {notApplicable?<p className="field-help">This program record does not require an elementary allocation. Retain secondary or preschool course details in the notes.</p>:rows.length?<dl className="allocation-schedule" aria-label="Recorded allocation by grade">{rows.map((r,i)=><div key={i}>
      <dt>{allocationGradeLabel(r.grade_scope)}</dt><dd><strong>{r.model}</strong>
        {!!Object.keys(r.named_language_shares||{}).length&&<span>{Object.entries(r.named_language_shares).sort(([a],[b])=>a==='English'?1:b==='English'?-1:a.localeCompare(b)).map(([language,share])=>`${share}% ${language}`).join(' · ')}</span>}
        {r.source_grade_scope&&<small>Source covers {r.source_grade_scope}; other grades have a separate correction.</small>}
        {r.pending_review_id&&<small>Saved on this device</small>}
      </dd></div>)}</dl>:<p className="field-help">{field?.value?.length?'Recorded label: '+field.value.join(' · ')+'. Grades were not specified.':'No elementary allocation is recorded yet.'}</p>}
    {field?.status==='conflicting'&&<p className="field-help">The recorded sources conflict. Use the grades and source details to record a correction.</p>}
    <label className="field kindergarten-allocation"><span>Partner-language instruction in kindergarten</span>
      <select aria-label="Kindergarten partner-language percentage" disabled={notApplicable} value={other?'other':choice?String(choice.percentage):''}
        onChange={e=>{const value=e.target.value;patch(value==='other'?{allocation:'',kindergarten_partner_language_pct:'',allocation_other:true,grade_scope:'K'}:value===''?{allocation:'',kindergarten_partner_language_pct:'',allocation_other:false}:{allocation:`${Number(value)}/${100-Number(value)}`,kindergarten_partner_language_pct:value,allocation_other:false,grade_scope:'K'});}}>
        <option value="">Keep current allocation</option>
        {options(COMMON_KINDERGARTEN_PERCENTAGES)}
        <option value="other">Other</option>
      </select>
    </label>
    {legacy&&<p className="field-help legacy-allocation">This older entry records {draft.allocation} for {draft.grade_scope||'unspecified grades'}. Choose a kindergarten percentage to revise it; the entry’s evidence and notes are retained.</p>}
    {(choice||legacy||other)&&<button type="button" className="clear-allocation" onClick={()=>patch({allocation:'',kindergarten_partner_language_pct:'',allocation_other:false})}>Clear allocation change</button>}
    {other&&<p className="field-help other-allocation">{choice?`Saved kindergarten allocation: ${choice.percentage}% partner language, ${100-choice.percentage}% English. `:''}Describe the kindergarten model in Research notes below. Other arrangements are saved for review.</p>}
    <p className="field-help">English is the remaining percentage. New allocation edits apply to kindergarten only; other grades stay as recorded. If the source does not fit these choices, save its details in the notes.</p>
  </section>;
}
