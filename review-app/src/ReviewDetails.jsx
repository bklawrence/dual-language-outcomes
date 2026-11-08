import React from 'react';
import {ExternalLink} from 'lucide-react';
import {FIELD_LABELS, BASIS_LABELS, STATUS_LABELS, formatValue, sourceLink} from './reviews';

export default function ReviewDetails({record, school, inventoryYear}) {
  const entries = Object.entries(record.changes || {});
  const evidence = sourceLink(record.evidence_url);
  return <div className="review-details">
    {entries.length ? <table className="review-changes">
      <caption className="sr-only">Coding changes for {record.school_name}</caption>
      <thead><tr><th>Variable &amp; program scope</th><th>Inventory · {inventoryYear.replace('-', '–')}</th><th>Your entry</th></tr></thead>
      <tbody>{entries.map(([variable, change]) => {
        const sites = (change.site_ids || []).map(id => school?.sites.find(s => s.site_id === id)).filter(Boolean);
        const before = [...new Set(sites.map(s => formatValue(s.known[variable]?.value)))];
        const all = school && sites.length === school.sites.length && sites.length > 1;
        const scope = all ? `All ${sites.length} program records` : sites.map(s => s.label).join('; ') || 'Program scope unavailable';
        const percentage=change.kindergarten_partner_language_pct;
        const entry=variable==='elementary_allocation_model'&&Number.isInteger(percentage)
          ? `${percentage}% partner language · ${100-percentage}% English (kindergarten)` : formatValue(change.value);
        return <tr key={variable}><th>{FIELD_LABELS[variable] || variable}<small>{scope}</small></th><td>{before.join(' / ') || 'Not recorded'}</td><td>{entry}</td></tr>;
      })}</tbody>
    </table> : !record.program_event&&<p className="parked-note">Evidence and research notes only. No program values have been assigned; this school remains available for coding.</p>}
    {record.program_event&&<div className="program-event-summary">
      <dl className="review-context"><div><dt>Program status</dt><dd>{STATUS_LABELS[record.program_event.kind]}</dd></div><div><dt>First supported school year</dt><dd>{record.program_event.first_school_year}</dd></div><div><dt>Program scope</dt><dd>{record.program_event.site_ids.map(id=>school?.sites.find(s=>s.site_id===id)?.label||id).join('; ')}</dd></div></dl>
      {record.program_event.kind==='moved'&&<p>Destination: {record.program_event.destination_school_name||'Not stated / needs follow-up'}{sourceLink(record.program_event.destination_url)&&<> · <a href={record.program_event.destination_url} target="_blank" rel="noreferrer">School website <ExternalLink size={11}/></a></>}</p>}
    </div>}
    <dl className="review-context">
      <div><dt>Applies to</dt><dd>{record.reference_year.replace('-', '–')}</dd></div>
      <div><dt>Grades described</dt><dd>{record.grade_scope || 'Not specified'}</dd></div>
      <div><dt>Source school year</dt><dd>{record.source_school_year?.replace('-', '–') || 'Undated / not stated'}</dd></div>
      <div><dt>Coding basis</dt><dd>{BASIS_LABELS[record.coding_method] || 'Not recorded'}</dd></div>
    </dl>
    {record.reference_year !== inventoryYear && <p className="review-year-note">Inventory values above describe {inventoryYear.replace('-', '–')}; your entry applies to {record.reference_year.replace('-', '–')}.</p>}
    {evidence && <p className="review-evidence"><span>Evidence</span><a href={evidence} target="_blank" rel="noreferrer">{evidence}<ExternalLink size={11}/></a></p>}
    {record.source_locator && <p className="review-location"><span>Page / section</span>{record.source_locator}</p>}
    {record.source_quote && <div className="review-quotation"><span>Supporting quotation</span><blockquote>{record.source_quote}</blockquote></div>}
    {record.notes && <div className="review-notes"><span>Research notes</span><p>{record.notes}</p></div>}
  </div>;
}
