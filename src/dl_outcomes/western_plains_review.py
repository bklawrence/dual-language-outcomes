"""Source-scope checks and review views for the six-state structural first pass."""
from collections import defaultdict
import csv
import hashlib
import io
import json

from .io import digest, record_id
from .states.five_state import exact_year
from .states.western_plains import BASE, STATES

AUDIT = 'config/research_migrations/western_plains_2026_11_04.json'
REPORT = 'data/reports/western_plains_2026_11_04'


def inputs(root):
    base = root / BASE
    programmes = [p for code in sorted(STATES) for p in json.loads((base / (code.lower() + '_programmes.json')).read_text())]
    sources = {s['key']: s for s in json.loads((base / 'sources.json').read_text())}
    return programmes, sources


def source_id(state, key, sources):
    return record_id('source', state + '_WESTERN_PLAINS_STRUCTURAL', sources[key]['sha256'])


def audit_errors(root, tables, *, check_hashes=True):
    audit = json.loads((root / AUDIT).read_text())
    errors = []
    programmes, sources = inputs(root)
    for table, states in audit['prior_identity_sets'].items():
        field = 'school_id' if table == 'schools' else 'program_id'
        for state, expected in states.items():
            ids = sorted(r[field] for r in tables[table] if r['state_code'] == state)
            actual = hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest()
            if actual != expected:
                errors.append('Six-state batch changed prior identity set: ' + table + '/' + state)
    if check_hashes:
        for rel, expected in audit['preserved_assessment_outputs'].items():
            if digest(root / rel) != expected:
                errors.append('Six-state structural batch changed assessment/context/EL/SEDA output: ' + rel)
        for doc in sources.values():
            if digest(root / doc['path']) != doc['sha256']:
                errors.append('Six-state archived public bytes changed: ' + doc['key'])
    sites = {r['program_id']: r for r in tables['program_sites']}
    configurations = {r['configuration_id']: r for r in tables['program_configurations']}
    languages = defaultdict(list)
    for r in tables['program_languages']:
        languages[(r['site_id'], r['source_id'], r['source_locator'])].append(r)
    schedules = {r['schedule_id']: r for r in tables['allocation_schedules']}
    shares = defaultdict(dict)
    for r in tables['instructional_allocations']:
        shares[r['schedule_id']][r['language_name']] = r['instruction_share_pct']
    statuses = defaultdict(list)
    for r in tables['program_status_history']:
        statuses[r['site_id']].append(r)
    actual_programs = {r['program_id'] for r in tables['programs']}
    for state, expected in audit['programme_ids'].items():
        if not set(expected) <= actual_programs:
            errors.append('Six-state reviewed programme evidence keys lost: ' + state)
    for p in programmes:
        pid, state = p['program_id'], p['state']
        site = sites.get(pid)
        if not site or site['school_id'] != p['school_id']:
            errors.append('Six-state programme/school identity changed: ' + pid)
            continue
        sid = site['site_id']
        import_source = record_id('source', state + '_WESTERN_PLAINS_STRUCTURAL', digest(root / BASE / (state.lower() + '_programmes.json')))
        reference = [r for r in statuses[sid] if r['school_year'] == '2025-26' and r['source_id'] == import_source]
        if len(reference) != 1:
            errors.append('Six-state reference assessment lost or duplicated: ' + pid)
        else:
            for field, key in [('operating_status', 'status'), ('eligibility_status', 'eligibility'),
                    ('instructional_scope', 'scope'), ('public_funding_status', 'funding'),
                    ('confirmation_method', 'method'), ('evidence_period_raw', 'period')]:
                if reference[0][field] != p['reference'][key]:
                    errors.append('Six-state operation/eligibility/source-period distinction changed: ' + pid + '/' + field)
        for i, observation in enumerate(p['observations']):
            source = source_id(state, observation['source'], sources)
            locator = pid + ':observation:' + str(i) + '; ' + observation['locator']
            row = configurations.get(record_id('configuration', sid, source, locator))
            if row is None:
                errors.append('Six-state source configuration lost: ' + locator)
                continue
            expected = dict(school_year=exact_year(observation['period']), grade_scope=observation['grade'],
                population_model=observation['population'], delivery_structure=observation['delivery'],
                evidence_period_raw=observation['period'], verification_status=observation['verification'])
            if any(row[k] != v for k, v in expected.items()):
                errors.append('Six-state source grade/model/year scope changed: ' + locator)
            ls = languages[(sid, source, locator)]
            if {r['language_name'] for r in ls} != set(observation['languages']):
                errors.append('Six-state language inferred or source language lost: ' + locator)
            if any(r['language_role'] != observation['language_role'] or r['valid_from_year'] != exact_year(observation['period'])
                    or r['valid_to_year'] != exact_year(observation['period']) for r in ls):
                errors.append('Six-state language role or period changed: ' + locator)
            if observation['source'] == 'wp_nm_eric_pdf' and ',' in observation.get('raw', {}).get('language', '') and observation['languages']:
                errors.append('Composite New Mexico report cell promoted to individual DL languages: ' + pid)
        for i, allocation in enumerate(p['allocations']):
            source = source_id(state, allocation['source'], sources)
            locator = pid + ':allocation:' + str(i) + '; ' + allocation['locator']
            schedule = record_id('schedule', sid, source, locator)
            row = schedules.get(schedule)
            if row is None:
                errors.append('Six-state allocation description lost: ' + locator)
                continue
            expected = dict(grade_scope=allocation['grade'], school_year=exact_year(allocation['period']),
                evidence_period_raw=allocation['period'], grade_support_status=allocation['grade_support'],
                schedule_status='documented_plan' if allocation['shares'] else 'reported_policy_requires_review',
                tested_cohort_exposure='not_established')
            if any(row[k] != v for k, v in expected.items()) or shares[schedule] != (allocation['shares'] or {}):
                errors.append('Six-state allocation source scope changed or numeric shares invented: ' + locator)
    ext = root / BASE / 'extractions'
    ut = json.loads((ext / 'ut_roster_rows.json').read_text())
    nm = json.loads((ext / 'nm_report_rows.json').read_text())
    actual_counts = dict(ut_roster_rows=len(ut), ut_school_language_cells=sum(len(r['language'].split(', ')) for r in ut),
        co_roster_rows=len(json.loads((ext / 'co_roster_rows.json').read_text())), nm_report_school_rows=len(nm),
        nm_report_DL_flags=sum(int(r['DL'] or 0) for r in nm),
        nm_map_rows=len(json.loads((ext / 'nm_map_structural_rows.json').read_text())),
        az_directory_leads=len(json.loads((ext / 'az_directory_leads.json').read_text())))
    if actual_counts != audit['source_extraction_counts']:
        errors.append('Six-state source row reconciliation changed')
    totals = json.loads((ext / 'nm_report_totals.json').read_text())
    for total in totals:
        if total['district'] == 'TOTAL BMEPs by Model':
            continue
        actual = [sum(int(r[k] or 0) for r in nm if r['district'] == total['district']) for k in ['DL', 'M', 'H', 'E', 'T']]
        if actual != [int(x or 0) for x in total['models']]:
            errors.append('New Mexico Appendix F district/model totals do not reconcile: ' + total['district'])
    return errors


def csv_text(rows, fields=None):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=fields or list(rows[0]), lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
    return out.getvalue()


def render_reports(root, tables):
    programmes, sources = inputs(root)
    rows, backlog, changes = [], [], []
    for p in programmes:
        ref = p['reference']
        language_names = sorted({name for o in p['observations'] for name in o['languages']})
        populations = sorted({o['population'] for o in p['observations']} - {'unknown'})
        delivery = sorted({o['delivery'] for o in p['observations']} - {'unknown'})
        allocations = [{**a, 'source_url': sources[a['source']]['url']} for a in p['allocations']]
        row = dict(state=p['state'], district_or_source_group=p['district'], school=p['school'], track=p['track'],
            program_id=p['program_id'], school_id=p['school_id'], reference_school_year='2025-26',
            operating_status=ref['status'], eligibility_status=ref['eligibility'], public_funding_status=ref['funding'],
            confirmation_method=ref['method'], operation_evidence_period=ref['period'],
            operation_evidence_url=sources[ref['source']]['url'] if ref['source'] else '',
            reported_languages_all_source_periods=' | '.join(language_names),
            grade_scopes_all_source_periods=' | '.join(sorted({o['grade'] for o in p['observations']})),
            population_models_all_source_periods=' | '.join(populations), delivery_structures_all_source_periods=' | '.join(delivery),
            allocation_descriptions=len(allocations), named_share_plans=sum(bool(a['shares']) for a in allocations),
            allocations_json=json.dumps(allocations, ensure_ascii=False, separators=(',', ':')),
            notes=p['notes'] + ' ' + ref['notes'],
            interpretation='Partial evidence group. Source-period unions are not one annual configuration, a statewide count, or participant exposure.')
        rows.append(row)
        gaps = []
        if ref['status'] != 'confirmed_2025_26':gaps.append('reference_year_operation_not_confirmed')
        if not ref['eligibility'].startswith('documented_'):gaps.append('content_funding_or_track_eligibility_requires_review')
        if 'English' not in language_names or len(set(language_names) - {'English'}) == 0:gaps.append('instructional_language_pair_not_fully_documented')
        if not populations:gaps.append('one_way_two_way_not_documented')
        if not delivery:gaps.append('strand_whole_school_not_documented')
        if not allocations:gaps.append('allocation_not_collected')
        elif not any(a['shares'] for a in allocations):gaps.append('named_language_share_plan_not_verified')
        if gaps:backlog.append(dict(state=p['state'],program_id=p['program_id'],school=p['school'],track=p['track'],gaps=' | '.join(gaps),
            priority='high' if ref['status'] == 'confirmed_2025_26' else 'scope_and_history',notes=ref['notes']))
        for event in p['events']:
            if event['status'].startswith('listed_'):
                continue
            changes.append(dict(state=p['state'],program_id=p['program_id'],school=p['school'],track=p['track'],
                school_year=event['year'],event_status=event['status'],source_url=sources[event['source']]['url'],notes=event['notes']))
        if ref['status'] in {'planned_future', 'not_offered_reference_year'}:
            changes.append(dict(state=p['state'],program_id=p['program_id'],school=p['school'],track=p['track'],
                school_year='2025-26 reference; evidence '+ref['period'],event_status=ref['status'],
                source_url=sources[ref['source']]['url'],notes=ref['notes']))
    summary = []
    for state in ['UT', 'CO', 'NM', 'AZ', 'NE', 'KS']:
        ps = [p for p in programmes if p['state'] == state]
        confirmed = [p for p in ps if p['reference']['status'] == 'confirmed_2025_26' and p['reference']['eligibility'].startswith('documented_')]
        summary.append(dict(state=state, school_units_with_programme_evidence=len({p['school_id'] for p in ps}),
            provisional_programme_evidence_groups=len(ps), confirmed_qualifying_2025_26_school_units=len({p['school_id'] for p in confirmed}),
            confirmed_qualifying_2025_26_evidence_groups=len(confirmed),
            school_units_with_some_allocation_description_any_source_period=len({p['school_id'] for p in ps if p['allocations']}),
            school_units_with_named_language_share_plan_any_source_period=len({p['school_id'] for p in ps if any(a['shares'] for a in p['allocations'])}),
            confirmed_2025_26_school_units_with_named_share_plan_any_source_period=len({p['school_id'] for p in confirmed if any(a['shares'] for a in p['allocations'])}),
            statewide_completeness='not_established',
            allocation_interpretation='Any-source-period plan counts; may be older, undated or later. Not a statewide coverage percentage or proof of reference-year grade allocation.'))
    contents = {REPORT+'_program_view.csv':csv_text(rows), REPORT+'_by_state.csv':csv_text(summary),
        REPORT+'_backlog.csv':csv_text(backlog), REPORT+'_change_events.csv':csv_text(changes)}
    report = dict(reference_school_year='2025-26', collection_phase='structural_inventory',
        programme_evidence_groups=len(programmes),school_units_with_programme_evidence=len({p['school_id'] for p in programmes}),
        public_source_documents=len(sources),source_extraction_counts=json.loads((root/AUDIT).read_text())['source_extraction_counts'],
        state_summary=summary, statewide_completeness='not_established', proficiency_collection='deferred; prior pilot outputs unchanged',
        limitations=['Provisional research keys are not official programme counts or NCES matches.',
            '419 New Mexico Appendix F school-name rows and 524 model flags are retained as printed; narrative totals say 415 schools and 525 programmes. The 137 DL flags reconcile to every printed district total.',
            'Public university map is non-exhaustive; many entries were not independently phone-verified. Mixed-language/model rows remain unresolved unless a source distinguishes them.',
            'Utah 2026–27 roster is a later listing and includes secondary continuations. It is not backdated wholesale.',
            'Arizona third-party directory supplies 138 extracted discovery records. It does not supply verified DL models, pairs or a complete census.',
            'Any-source-period allocation data do not verify the same schedule, grade, or cohort in 2025–26.'])
    contents[REPORT+'.json'] = json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    return contents, report
