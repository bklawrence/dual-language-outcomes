import React from 'react';
import {allocationRows,allocationGradeLabel} from './allocation';

export default function AllocationEditor({field,draft,patch}){
  const rows=allocationRows(field);
  const notApplicable=field?.status?.startsWith('not_applicable');
  return <section className="allocation-editor" aria-label="Language allocation">
    <h3>Language allocation</h3>
    {notApplicable?<p className="field-help">This program record does not require an elementary allocation. Retain secondary or preschool course details in the notes.</p>:rows.length?<dl className="allocation-schedule" aria-label="Recorded allocation by grade">{rows.map((r,i)=><div key={i}>
      <dt>{allocationGradeLabel(r.grade_scope)}</dt><dd><strong>{r.model}</strong>
        {!!Object.keys(r.named_language_shares||{}).length&&<span>{Object.entries(r.named_language_shares).sort(([a],[b])=>a==='English'?1:b==='English'?-1:a.localeCompare(b)).map(([language,share])=>`${share}% ${language}`).join(' · ')}</span>}
        {r.source_grade_scope&&<small>Source covers {r.source_grade_scope}; other grades have a separate correction.</small>}
        {r.pending_review_id&&<small>Saved on this device</small>}
      </dd></div>)}</dl>:<p className="field-help">{field?.value?.length?'Recorded label: '+field.value.join(' · ')+'. Grades were not specified.':'No elementary allocation is recorded yet.'}</p>}
    {field?.status==='conflicting'&&<p className="field-help">The recorded sources conflict. Use the grades and source details to record a correction.</p>}
    <div className="two-fields allocation-inputs">
      <label className="field"><span>Allocation to record</span><input aria-label="Allocation model" value={draft.allocation} onChange={e=>patch('allocation',e.target.value)} placeholder="e.g. 90/10, 80/20, 50/50" maxLength={30}/></label>
      <label className="field"><span>Grades for this allocation</span><input aria-label="Grades described" placeholder="e.g. K, K–1, 2–5" maxLength={120} value={draft.grade_scope} onChange={e=>patch('grade_scope',e.target.value)}/></label>
    </div>
    <p className="field-help">Enter the source’s allocation label and the grades it describes. Leave blank to keep the recorded allocation. A correction keeps other grades and earlier years in the data.</p>
  </section>;
}
