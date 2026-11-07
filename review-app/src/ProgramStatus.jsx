import React,{useMemo} from 'react';
import {destinationLabel} from './reviews';

export default function ProgramStatus({draft,school,site,destinations,years,patch}){
  const options=useMemo(()=>destinations.filter(s=>s.school_id!==school.school_id
    && destinationLabel(s).toLowerCase().includes(draft.destination_name.toLowerCase())).slice(0,30),
    [destinations,school.school_id,draft.destination_name]);
  return <div className="program-status-fields">
    <label className="field"><span>Program operating status</span><select aria-label="Program operating status" value={draft.program_status} onChange={e=>patch({program_status:e.target.value,...(e.target.value==='moved'?{}:{destination_name:'',destination_id:'',destination_url:''})})}>
      <option value="">Keep current status</option><option value="ended">Ended</option><option value="moved">Moved to another school</option><option value="operating">Operating / reopened</option>
    </select></label>
    {draft.program_status&&<>
      <label className="field"><span>First school year supported by this evidence</span><select aria-label="Status school year" value={draft.status_year||draft.reference_year} onChange={e=>patch('status_year',e.target.value)}>{years.map(y=><option key={y}>{y}</option>)}</select></label>
      <p className="field-help">Record the earliest year this source supports. Earlier history stays intact. This finding applies to {site.label}.</p>
      {school.sites.length>1&&<label className="checkline apply-all"><input type="checkbox" checked={Boolean(draft.all_status)} onChange={e=>patch({all_status:e.target.checked,event_site_ids:[site.site_id]})}/>Apply this status to all {school.sites.length} DL program records at this campus</label>}
      {draft.program_status==='moved'&&<>
        <label className="field"><span>Destination school <span className="optional">If known</span></span><input aria-label="Destination school" maxLength={300} list="destination-schools" value={draft.destination_name} onChange={e=>{
          const matches=destinations.filter(s=>s.school_id!==school.school_id&&destinationLabel(s)===e.target.value);
          patch({destination_name:e.target.value,destination_id:matches.length===1?matches[0].school_id:''});
        }}/><datalist id="destination-schools">{options.map(s=><option key={s.school_id} value={destinationLabel(s)}/>)}</datalist></label>
        <label className="field"><span>Destination school URL <span className="optional">Optional</span></span><input aria-label="Destination school URL" type="url" maxLength={2048} value={draft.destination_url} onChange={e=>patch('destination_url',e.target.value)}/></label>
        <p className="field-help">Choose a listed school to link it, or enter the name from the source. Leave it blank if the destination is not stated. A move does not assign a language model to the new campus.</p>
      </>}
    </>}
  </div>;
}
