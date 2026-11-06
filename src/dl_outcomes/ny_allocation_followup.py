"""Preservation checks and transparent exports for the school-specific NY pass."""
from collections import Counter, defaultdict
import csv
import io
import json

from .elementary_audit import report_rows
from .io import digest
from .states.mid_atlantic_ct import BASE as INVENTORY
from .western_plains_review import csv_text

BASE = 'data/registry/ny_allocation_followup_2026_11_06'
AUDIT = 'config/research_migrations/ny_allocation_followup_2026_11_06.json'
REPORT = 'data/reports/ny_allocation_followup_2026_11_06'


def inputs(root):
    return (json.loads((root / INVENTORY / 'ny_programmes.json').read_text()),
            {s['key']: s for s in json.loads((root / INVENTORY / 'sources.json').read_text())},
            json.loads((root / BASE / 'school_reviews.json').read_text()))


def audit_errors(root, tables, *, check_hashes=True):
    audit = json.loads((root / AUDIT).read_text())
    programmes, sources, reviews = inputs(root)
    old = json.loads((root / BASE / 'baseline/ny_programmes.json').read_text())
    by_id = {p['program_id']: p for p in programmes}
    errors = []
    if check_hashes:
        for field in ['preserved_baseline_files', 'preserved_original_sources',
                      'preserved_other_state_inputs', 'preserved_assessment_outputs']:
            for path, expected in audit[field].items():
                if digest(root / path) != expected:
                    errors.append('NY follow-up changed preserved input/output: ' + path)
    if set(by_id) != set(audit['baseline_programme_ids'] + audit['new_programme_ids']):
        errors.append('NY follow-up lost or invented programme identities')
    if {p['school_id'] for p in programmes} != set(audit['baseline_school_ids'] + audit['new_school_ids']):
        errors.append('NY follow-up lost or invented school identities')
    for prior in old:
        current = by_id.get(prior['program_id'])
        if not current:
            continue
        for field in ['school_id', 'school', 'district']:
            if current[field] != prior[field]:
                errors.append('NY follow-up rewrote original identity: ' + prior['program_id'])
        if current['track'] != prior['track']:
            update = current.get('track_label_update', {})
            evidence = [o for o in current['observations'] if o['source'] == update.get('source')]
            if (update.get('previous_label') != prior['track'] or update.get('verified_label') != current['track']
                    or current['track'] != 'Spanish immersion'
                    or not any(o['languages'] == ['Spanish', 'English'] for o in evidence)):
                errors.append('NY follow-up track label changed without explicit language verification: ' + prior['program_id'])
        for field in ['observations', 'allocations', 'events']:
            if current[field][:len(prior[field])] != prior[field]:
                errors.append('NY follow-up rewrote original source observations: ' + prior['program_id'])
    baseline = list(csv.DictReader(io.StringIO((root / BASE / 'baseline/mid_atlantic_ct_2026_11_05_schools.csv').read_text())))
    expected = {r['school_id'] for r in baseline if r['state'] == 'NY' and r['elementary_reference_denominator'] == '1'}
    if len(reviews) != 200 or {r['school_id'] for r in reviews} != expected:
        errors.append('NY follow-up does not review all 200 original primary hosts exactly once')
    city = {p['nyc_dbn'] for p in old if p.get('nyc_dbn') and p['school_id'] in expected}
    if len(city) != 187:
        errors.append('NY follow-up original NYC primary-host grain changed')
    for row in reviews:
        if row['dbn'] and 'nyf_cep_' + row['dbn'] not in row['archived_source_keys']:
            errors.append('NY follow-up missing school-specific annual plan: ' + row['dbn'])
    schedule_claims = {r['entity_id']: json.loads(r['reported_value']) for r in tables['evidence_claims']
                       if r['attribute'] == 'allocation_source_selection'}
    schedules = {r['schedule_id']: r for r in tables['allocation_schedules']}
    shares = defaultdict(list)
    for row in tables['instructional_allocations']:
        shares[row['schedule_id']].append(row)
    for sid, allocation in schedule_claims.items():
        if allocation.get('evidence_type') != 'researcher_inference':
            continue
        if (schedules[sid]['schedule_status'] != 'inferred_plan'
                or not shares[sid] or any(r['evidence_type'] != 'researcher_inference' for r in shares[sid])
                or not allocation.get('notes') or not allocation.get('source_passage')
                or not allocation.get('review_status', '').startswith('USER_AUTHORIZED_')):
            errors.append('NY follow-up inference lost method, source or typed distinction: ' + sid)
    for p in programmes:
        for a in p['allocations']:
            if a.get('classification_method') == 'inferred_kindergarten_subject_distribution':
                if a['grade'] != 'K' or not a.get('subject_language_distribution'):
                    errors.append('NY subject inference lost K scope or subject map: ' + p['program_id'])
    return errors


def render_reports(root, tables):
    programmes, sources, reviews = inputs(root)
    audit = json.loads((root / AUDIT).read_text())
    details, summaries = report_rows(tables)
    elementary = [r for r in details if r['state_code'] == 'NY' and r['audit_scope'] == 'reference_working_set']
    by_school = {sid: r for r in elementary for sid in r['research_school_ids'].split(' | ')}
    old_ids = set(audit['baseline_school_ids'])
    original = [by_school[r['school_id']] for r in reviews]
    allocations = []
    cases = []
    for p in programmes:
        for a in p['allocations']:
            if not a['source'].startswith('nyf_'):
                continue
            allocations.append(dict(school=p['school'], district=p['district'],
                school_id=p['school_id'], program_id=p['program_id'], dbn=p.get('nyc_dbn'),
                track=p['track'], source_period=a['period'], grade_scope=a['grade'],
                model=a['label'], named_language_shares=json.dumps(a['shares'], ensure_ascii=False),
                method=a.get('classification_method', 'documented'),
                evidence_type=a.get('evidence_type', 'documented_plan'),
                review_status=a.get('review_status', ''), service_scope=a.get('service_scope'),
                subject_language_distribution=json.dumps(a.get('subject_language_distribution'), ensure_ascii=False),
                source_url=sources[a['source']]['url'], source_locator=a['locator'], notes=a['notes']))
            flag = a.get('review_status', '')
            if any(term in flag for term in ['CONFLICT', 'UNCONFIRMED', 'QUALIFIER', 'REVIEW', 'DISCREPANCY']):
                cases.append(dict(school=p['school'], program_id=p['program_id'],
                    issue=flag, source_url=sources[a['source']]['url'], notes=a['notes']))
        for reason in p.get('review_reasons', []):
            cases.append(dict(school=p['school'], program_id=p['program_id'],
                issue='programme_or_source_scope_review', source_url=sources[p['reference']['source']]['url'], notes=reason))
    rows = []
    for r in reviews:
        coverage = by_school[r['school_id']]
        urls = [sources[k]['url'] for k in r['archived_source_keys']]
        rows.append(dict(school=r['school'], district=r['district'], dbn=r['dbn'],
            school_id=r['school_id'], review_date=r['review_date'],
            has_reference_elementary_model=coverage['has_numerical_allocation_model'],
            models=coverage['numerical_model_labels'], classification_bases=coverage['model_classification_bases'],
            methods=' | '.join(r['allocation_methods']),
            checked_sources=json.dumps(r['attempted_source_keys'], ensure_ascii=False),
            archived_source_urls=json.dumps(urls, ensure_ascii=False), notes=r['decision_notes']))
    missing = [r for r in rows if not r['has_reference_elementary_model']]
    for coverage in elementary:
        if coverage['school_id'] in {r['school_id'] for r in reviews} or not coverage['elementary_denominator'] or coverage['has_numerical_allocation_model']:
            continue
        ps = [p for p in programmes if p['school_id'] == coverage['school_id']]
        keys = sorted({o['source'] for p in ps for o in p['observations']})
        missing.append(dict(school=ps[0]['school'], district=ps[0]['district'], dbn=None,
            school_id=coverage['school_id'], review_date='2026-11-06', has_reference_elementary_model=0,
            models='', classification_bases='', methods='', checked_sources=json.dumps(keys),
            archived_source_urls=json.dumps([sources[k]['url'] for k in keys]), notes=ps[0]['notes']))
    summary = next(r for r in summaries if r['state_code'] == 'NY' and r['audit_scope'] == 'reference_working_set')
    report = dict(research_date='2026-11-06', reference_year='2025-26',
        baseline_primary_schools_reviewed=len(reviews), baseline_nyc_primary_schools_reviewed=sum(bool(r['dbn']) for r in reviews),
        before=audit['initial_reference_elementary'],
        after_same_baseline_schools=dict(schools=len(original),
            schools_with_models=sum(r['has_numerical_allocation_model'] for r in original),
            coverage_pct=round(100 * sum(r['has_numerical_allocation_model'] for r in original) / len(original), 1)),
        current_reference_summary=summary,
        programme_records=len(programmes), school_units=len({p['school_id'] for p in programmes}),
        added_programme_records=len(audit['new_programme_ids']),
        added_school_units=len({p['school_id'] for p in programmes} - old_ids),
        archived_followup_sources=len(audit['archived_followup_sources']),
        inference_allocations=dict(Counter(r['method'] for r in allocations if r['evidence_type'] == 'researcher_inference')),
        limitations=['Partial inventory, not a complete New York census.',
            'Coverage means a numerical elementary model is available for at least one strand/grade; not every strand or kindergarten has an exact schedule.',
            'Inferences estimate scheduled core instruction. Unequal period lengths, English-only supplements and pupil services can change actual exposure.',
            'Contradictory source claims are retained with review flags, including possible programme-type changes without established closure dates.',
            'Source periods and later 2026-27 policies remain separate from the 2025-26 operating reference.',
            'Proficiency collection remains deferred.'])
    contents = {REPORT + '.json': json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                REPORT + '_schools_reviewed.csv': csv_text(rows),
                REPORT + '_allocations.csv': csv_text(allocations),
                REPORT + '_missing_models.csv': csv_text(missing),
                REPORT + '_review_cases.csv': csv_text(cases),
                REPORT + '_reference_by_school.csv': csv_text(elementary)}
    return contents, report
