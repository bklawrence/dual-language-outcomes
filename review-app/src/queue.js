const UNRESOLVED = new Set(['conflicting', 'later_only', 'not_reported']);
const DELIVERY_MODELS = new Set(['whole_school', 'strand', 'mixed']);

export function fieldWithReviews(school, site, variable, saved = [], accepted = new Set(), year = '2025-26') {
  const review = [...saved].reverse().find(r => !accepted.has(r.review_id)
    && r.school_id === school.school_id && r.reference_year === year
    && r.changes?.[variable]?.site_ids.includes(site.site_id));
  if (!review) return site.known[variable] || {value: [], status: 'not_reported'};
  const value = review.changes[variable].value;
  return {value: Array.isArray(value) ? value : [value],
    status: review.coding_method === 'explicit_source_statement' ? 'documented' : 'provisional'};
}

export function allocationRecorded(field) {
  return Boolean(field?.value?.length) && !UNRESOLVED.has(field.status)
    && !field.status?.startsWith('not_applicable');
}

export function deliveryRecorded(field) {
  return Boolean(field?.value?.length) && !UNRESOLVED.has(field.status)
    && field.value.every(value => DELIVERY_MODELS.has(value));
}

export function programEventFor(school, site, saved = [], accepted = new Set(), year = '2025-26') {
  const local=saved.filter(r=>r.school_id===school.school_id&&!accepted.has(r.review_id)&&r.program_event);
  const superseded=new Set(local.filter(r=>local.some(old=>old.review_id===r.supersedes_review_id
    &&old.program_event.kind===r.program_event.kind&&old.reference_year===r.reference_year))
    .map(r=>r.supersedes_review_id));
  let published=site.program_event;
  if(published&&local.some(r=>r.supersedes_review_id===published.review_id
    &&r.program_event.kind===published.kind&&r.reference_year===published.reference_year))published=null;
  const candidates=[...(published?[published]:[]),...local.filter(r=>!superseded.has(r.review_id)&&r.program_event.site_ids.includes(site.site_id))
    .map(r=>({...r.program_event,review_id:r.review_id,submitted_at:r.coded_at||'',reference_year:r.reference_year}))]
    .filter(e=>e.first_school_year<=year);
  return candidates.sort((a,b)=>a.first_school_year.localeCompare(b.first_school_year)
    ||(a.submitted_at||'').localeCompare(b.submitted_at||'' )).at(-1)||null;
}

export function schoolPriorityStatus(school, saved = [], accepted = new Set(), year = '2025-26') {
  const relevant = school.sites.filter(s => !s.known.elementary_allocation_model?.status?.startsWith('not_applicable'));
  const active = school.sites.filter(s=>!['ended','moved'].includes(programEventFor(school,s,saved,accepted,year)?.kind));
  const sites = relevant.filter(s=>active.includes(s));
  const facts = sites.map(site => ({
    allocation: fieldWithReviews(school, site, 'elementary_allocation_model', saved, accepted, year),
    delivery: fieldWithReviews(school, site, 'delivery_structure', saved, accepted, year),
  }));
  return {
    allocation_known: Boolean(school.allocation_known || facts.some(f => allocationRecorded(f.allocation))),
    priorityComplete: facts.length > 0 && facts.every(f => allocationRecorded(f.allocation) && deliveryRecorded(f.delivery)),
    retired: relevant.length>0&&sites.length===0,
    active_site_ids:active.map(s=>s.site_id),priority_site_ids:sites.map(s=>s.site_id),
  };
}
