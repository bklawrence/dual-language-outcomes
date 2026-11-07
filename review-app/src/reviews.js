export const FIELD_LABELS = {
  delivery_structure: 'Delivery model',
  population_model: 'One-way / two-way',
  elementary_allocation_model: 'Language allocation',
  instruction_languages: 'Instructional languages',
};

export const VALUE_LABELS = {
  whole_school: 'Whole school', strand: 'Strand', mixed: 'Mixed / varies',
  one_way: 'One-way', two_way: 'Two-way',
};

export const BASIS_LABELS = {
  explicit_source_statement: 'Explicit source statement',
  researcher_interpretation: 'Researcher interpretation',
  not_recorded: 'Not recorded',
};

export function formatValue(value) {
  if (Array.isArray(value)) return value.map(formatValue).join(' + ') || 'Not recorded';
  return VALUE_LABELS[value] || value || 'Not recorded';
}

// Old reviews did not store the selected program. Delivery can cover the whole
// campus while every other variable belongs to a different, selected program.
export function draftFromReview(record, school, empty) {
  const available = new Set(school.sites.map(s => s.site_id));
  const changes = record.changes || {};
  for (const change of Object.values(changes)) {
    if (change.site_ids.some(id => !available.has(id))) {
      throw Error('A program in this review is outside the current inventory. Export a backup before revising its scope.');
    }
  }
  const specific = ['population_model', 'elementary_allocation_model', 'instruction_languages']
    .map(v => changes[v]?.site_ids[0]).find(Boolean);
  const selected = available.has(record.selected_site_id) ? record.selected_site_id
    : specific || changes.delivery_structure?.site_ids[0] || school.sites[0].site_id;
  const deliveryIds = changes.delivery_structure?.site_ids || [selected];
  return {
    ...empty,
    site_id: selected,
    delivery: changes.delivery_structure?.value || '',
    population: changes.population_model?.value || '',
    allocation: changes.elementary_allocation_model?.value || '',
    languages: changes.instruction_languages?.value.join(', ') || '',
    evidence_url: record.evidence_url || '', notes: record.notes || '',
    source_quote: record.source_quote || '', source_locator: record.source_locator || '',
    grade_scope: record.grade_scope || '', source_school_year: record.source_school_year || '',
    reference_year: record.reference_year,
    coding_method: record.coding_method === 'not_recorded' ? '' : record.coding_method || '',
    all_delivery: deliveryIds.length === available.size && deliveryIds.every(id => available.has(id)),
    delivery_site_ids: [...deliveryIds],
    original_targets: Object.fromEntries(Object.entries(changes).map(([v, c]) => [v, [...c.site_ids]])),
    editing_review_id: record.review_id,
    supersedes_review_id: record.supersedes_review_id || null,
  };
}

export function targetsForDraft(draft, variable, selectedSite, school) {
  const ids = variable === 'delivery_structure'
    ? draft.all_delivery ? school.sites.map(s => s.site_id) : draft.delivery_site_ids || [selectedSite.site_id]
    : draft.original_targets?.[variable] || [selectedSite.site_id];
  return [...ids];
}

export function hasReviewEdits(record, draft, school) {
  if (!draft) return false;
  if (!school) return true;
  try {
    const original = draftFromReview(record, school, {});
    const fields = ['delivery', 'population', 'allocation', 'languages', 'evidence_url', 'notes',
      'source_quote', 'source_locator', 'grade_scope', 'source_school_year', 'reference_year', 'coding_method'];
    if (fields.some(key => (draft[key] || '').trim() !== (original[key] || '').trim())) return true;
    const selected = school.sites.find(s => s.site_id === draft.site_id);
    if (!selected) return true;
    return Object.entries(record.changes || {}).some(([variable, change]) =>
      JSON.stringify(targetsForDraft(draft, variable, selected, school).sort()) !== JSON.stringify([...change.site_ids].sort()));
  } catch { return true; }
}

export function sourceLink(value) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : '';
  } catch { return ''; }
}
