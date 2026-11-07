import React from 'react';
import {ArrowDownToLine, ArrowRight, Check, CheckCheck, ExternalLink, Search} from 'lucide-react';
import ReviewDetails from './ReviewDetails';
import {hasReviewEdits} from './reviews';

export default function SavedReviews({store, cases, accepted, pending, awaiting, inventoryYear,
  filters, setFilters, refreshing, onRefresh, onBackup, onQueue, onEdit, onRevisit, onRemove, onCopySubmission, handoffBusy, onPublish}) {
  const schools = new Map(cases.map(c => [c.school_id, c]));
  const districtOf = r => schools.get(r.school_id)?.district_name || 'District unavailable';
  const districts = [...new Set(store.saved.map(districtOf))].sort();
  const rows = [...store.saved].reverse().filter(r => {
    const status = accepted.has(r.review_id) ? 'published'
      : store.batches.some(b => b.review_ids.includes(r.review_id)) ? 'awaiting' : 'ready';
    const text = [r.school_name, districtOf(r), schools.get(r.school_id)?.state_code, r.notes].join(' ').toLowerCase();
    return (filters.status === 'all' || filters.status === status)
      && (filters.district === 'all' || filters.district === districtOf(r))
      && (!filters.query || text.includes(filters.query.toLowerCase()));
  });
  const filter = (key, value) => setFilters(f => ({...f, [key]: value}));
  return <main className="saved-view">
    <div className="section-eyebrow">SAVED WORK</div><h1>Review and revise</h1>
    <p className="section-intro">Keep researching, then return to any saved review. Edit your coding, source, or notes before publishing a batch.</p>
    <div className="saved-toolbar"><span>{pending.length} saved locally · {awaiting.length} awaiting GitHub · {store.saved.filter(r => accepted.has(r.review_id)).length} published</span>
      <div>{pending.length>0&&<button className="primary small" onClick={onPublish}>Review &amp; submit <ArrowRight size={14}/></button>}<button className="text-button" onClick={onRefresh}><CheckCheck size={15}/>{refreshing ? 'Checking…' : 'Check publishing status'}</button><button className="secondary small" onClick={onBackup}><ArrowDownToLine size={14}/>Export backup</button></div>
    </div>
    {store.saved.length > 0 && <div className="review-filters">
      <label className="review-search"><Search size={15}/><input aria-label="Search saved reviews" placeholder="School, district, state, or notes" value={filters.query} onChange={e => filter('query', e.target.value)}/></label>
      <select aria-label="Saved review district" value={filters.district} onChange={e => filter('district', e.target.value)}><option value="all">All districts</option>{districts.map(d => <option key={d}>{d}</option>)}</select>
      <select aria-label="Saved review status" value={filters.status} onChange={e => filter('status', e.target.value)}><option value="all">All reviews</option><option value="ready">Not yet submitted</option><option value="awaiting">Awaiting GitHub</option><option value="published">Published</option></select>
    </div>}
    {!store.saved.length ? <div className="empty-state"><h2>No saved reviews yet</h2><p>Save a school review to start your research log.</p><button className="primary" onClick={onQueue}>Go to the review queue <ArrowRight size={15}/></button></div>
      : !rows.length ? <p className="review-empty">No saved reviews match these filters.</p>
      : <div className="review-log">{rows.map(r => {
        const published = accepted.has(r.review_id);
        const batch = store.batches.find(b => b.review_ids.includes(r.review_id));
        const draft = store.drafts['review:' + r.review_id];
        const dirty = hasReviewEdits(r,draft,schools.get(r.school_id));
        return <article key={r.review_id} className="log-card">
          <div className="log-heading"><div><h3>{r.school_name}</h3><span>{districtOf(r)} · {r.reviewer} · {new Date(r.coded_at).toLocaleDateString(undefined, {month: 'short', day: 'numeric'})}</span></div><span className={'status-pill ' + (published ? 'green' : '')}><Check size={12}/>{published ? 'Published' : batch ? 'Confirm on GitHub' : dirty ? 'Unsaved edits' : 'Saved on this device'}</span></div>
          <ReviewDetails record={r} school={schools.get(r.school_id)} inventoryYear={inventoryYear}/>
          <div className="log-bottom"><span className="hand-coded">Hand-coded</span>
            {batch && !published && <><a href={batch.url}>Confirm batch <ExternalLink size={12}/></a><button className="text-button" disabled={handoffBusy} onClick={()=>onCopySubmission(batch)}>Copy submission link</button></>}
            {!batch && !published && <button className="text-button" onClick={() => onRemove(r)}>Remove unpublished review</button>}
            <button className="secondary small review-edit" onClick={() => batch && !published ? onRevisit(r) : onEdit(r)}>{batch && !published ? 'Revisit school' : draft ? 'Resume editing' : published ? 'Add a correction' : 'Edit review'}<ArrowRight size={13}/></button>
          </div>
          {batch && !published && <p className="review-year-note">This batch has been handed to GitHub. Check its status before adding a correction; the submitted version is kept intact.</p>}
        </article>;
      })}</div>}
  </main>;
}
