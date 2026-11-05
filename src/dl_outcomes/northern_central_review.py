"""Conservation checks and readable exports for the seven-state source review."""
from collections import defaultdict
import hashlib
import json

from .elementary_audit import elementary_scope, numeric_model, report_rows as elementary_rows
from .io import digest, record_id
from .identity_audit import preserved_identity_fingerprint
from .states.five_state import exact_year
from .states.northern_central import BASE, STATES
from .western_plains_review import csv_text

AUDIT = 'config/research_migrations/northern_central_ak_hi_2026_11_05.json'
REPORT = 'data/reports/northern_central_ak_hi_2026_11_05'
SUFFIX = '_NORTHERN_CENTRAL_AK_HI_STRUCTURAL'


def inputs(root, *, base=BASE, states=STATES):
    base = root / base
    programmes = [p for s in sorted(states)
                  for p in json.loads((base / (s.lower() + '_programmes.json')).read_text())]
    sources = {s['key']: s for s in json.loads((base / 'sources.json').read_text())}
    return programmes, sources


def source_id(state, key, sources, *, suffix=SUFFIX):
    return record_id('source', state + suffix, sources[key]['sha256'])


def audit_errors(root, tables, *, check_hashes=True, batch=None):
    settings = dict(base=BASE, states=STATES, audit=AUDIT, suffix=SUFFIX)
    settings.update(batch or {})
    audit = json.loads((root / settings['audit']).read_text())
    programmes, sources = inputs(root, base=settings['base'], states=settings['states'])
    errors = []
    for table, states in audit['prior_identity_sets'].items():
        key = 'school_id' if table == 'schools' else 'program_id'
        for state, expected in states.items():
            ids = sorted(r[key] for r in tables[table] if r['state_code'] == state)
            actual = preserved_identity_fingerprint(root, table, state, ids, expected)
            if actual != expected:
                errors.append('Seven-state batch changed prior identities: ' + table + '/' + state)
    if check_hashes:
        for group in ['preserved_assessment_outputs', 'preserved_reports']:
            for rel, expected in audit[group].items():
                if digest(root / rel) != expected:
                    errors.append('Seven-state batch changed preserved output: ' + rel)
        for doc in sources.values():
            if digest(root / doc['path']) != doc['sha256']:
                errors.append('Seven-state public snapshot changed: ' + doc['key'])
    for state, expected in audit['programme_ids'].items():
        actual = {p['program_id'] for p in tables['programs'] if p['state_code'] == state}
        if actual != set(expected):
            errors.append('Seven-state programme set changed: ' + state)
    sites = {r['program_id']: r for r in tables['program_sites']}
    configs = {r['configuration_id']: r for r in tables['program_configurations']}
    schedules = {r['schedule_id']: r for r in tables['allocation_schedules']}
    languages, shares, statuses = (defaultdict(list) for _ in range(3))
    for r in tables['program_languages']:
        languages[(r['site_id'], r['source_id'], r['source_locator'])].append(r)
    for r in tables['instructional_allocations']:
        shares[r['schedule_id']].append(r)
    for r in tables['program_status_history']:
        statuses[r['site_id']].append(r)
    for p in programmes:
        pid, state = p['program_id'], p['state']
        site = sites.get(pid)
        if not site or site['school_id'] != p['school_id']:
            errors.append('Seven-state programme host changed: ' + pid)
            continue
        sid = site['site_id']
        import_id = record_id('source', state + settings['suffix'],
                             digest(root / settings['base'] / (state.lower() + '_programmes.json')))
        ref = [r for r in statuses[sid] if r['source_id'] == import_id and r['school_year'] == '2025-26']
        expected = dict(operating_status=p['reference']['status'], eligibility_status=p['reference']['eligibility'],
                        instructional_scope=p['reference']['scope'], public_funding_status=p['reference']['funding'],
                        confirmation_method=p['reference']['method'], evidence_period_raw=p['reference']['period'])
        if len(ref) != 1 or any(ref[0][k] != v for k, v in expected.items()):
            errors.append('Seven-state reference operation/funding distinction changed: ' + pid)
        for i, o in enumerate(p['observations']):
            source = source_id(state, o['source'], sources, suffix=settings['suffix'])
            locator = pid + ':observation:' + str(i) + '; ' + o['locator']
            row = configs.get(record_id('configuration', sid, source, locator))
            expected = dict(school_year=exact_year(o['period']), grade_scope=o['grade'],
                            population_model=o['population'], delivery_structure=o['delivery'],
                            reported_model_label=o['label'], evidence_period_raw=o['period'])
            if row is None or any(row[k] != v for k, v in expected.items()):
                errors.append('Seven-state source grade/model/period changed: ' + locator)
            ls = languages[(sid, source, locator)]
            if ({r['language_name'] for r in ls} != set(o['languages'])
                    or any(r['language_role'] != o['language_role']
                           or r['valid_from_year'] != exact_year(o['period']) for r in ls)):
                errors.append('Seven-state source languages/roles/dates changed: ' + locator)
        for i, a in enumerate(p['allocations']):
            source = source_id(state, a['source'], sources, suffix=settings['suffix'])
            locator = pid + ':allocation:' + str(i) + '; ' + a['locator']
            row = schedules.get(record_id('schedule', sid, source, locator))
            expected = dict(school_year=exact_year(a['period']), grade_scope=a['grade'],
                            reported_model_label=a['label'], evidence_period_raw=a['period'],
                            grade_support_status=a['grade_support'])
            if row is None or any(row[k] != v for k, v in expected.items()):
                errors.append('Seven-state allocation source scope changed: ' + locator)
                continue
            actual_shares = {r['language_name']: r['instruction_share_pct'] for r in shares[row['schedule_id']]}
            if actual_shares != (a['shares'] or {}):
                errors.append('Seven-state allocation invented/lost named shares: ' + locator)
            if elementary_scope(a['grade']) == 'secondary_6_plus':
                errors.append('Seven-state elementary allocation attached to secondary scope: ' + locator)
            if a.get('review_status') and row['evidence_review_status'] != a['review_status']:
                errors.append('Seven-state inferred allocation lost its review flag: ' + locator)
    if batch:
        return errors
    hi = json.loads((root / BASE / 'extractions/hi_directory_rows.json').read_text())
    ak = json.loads((root / BASE / 'extractions/ak_asd_school_language_cells.json').read_text())
    if (len(hi), sum(r['sector'] == 'HIDOE' for r in hi), len(ak), len({r['school'] for r in ak})) != (34, 27, 18, 16):
        errors.append('Seven-state Hawaii/Anchorage directory reconciliation changed')
    if {r['school'] for r in hi} != {p['school'] for p in programmes if p['state'] == 'HI' and p['track'] == 'Hawaiian immersion'}:
        errors.append('Hawaii directory row lost or satellite inflated into an extra school')
    return errors


def render_reports(root, tables, *, batch=None):
    settings = dict(base=BASE, states=STATES, report=REPORT)
    settings.update(batch or {})
    programmes, sources = inputs(root, base=settings['base'], states=settings['states'])
    detail, coverage = elementary_rows(tables)
    elementary = {(r['audit_scope'], sid): r for r in detail
                  for sid in r['research_school_ids'].split(' | ')}
    rows, backlog, schools = [], [], []
    by_school = defaultdict(list)
    for p in programmes:
        ref = p['reference']
        allocations = [dict(a, source_url=sources[a['source']]['url']) for a in p['allocations']]
        row = dict(state=p['state'], district_or_operator=p['district'], school=p['school'], track=p['track'],
            program_id=p['program_id'], school_id=p['school_id'], reference_school_year=ref['year'],
            operating_status=ref['status'], eligibility_status=ref['eligibility'],
            public_funding_status=ref['funding'], confirmation_method=ref['method'],
            operation_evidence_period=ref['period'], operation_evidence_url=sources[ref['source']]['url'],
            languages_all_source_periods=' | '.join(sorted({x for o in p['observations'] for x in o['languages']})),
            grade_scopes_all_source_periods=' | '.join(sorted({o['grade'] for o in p['observations']})),
            population_models=' | '.join(sorted({o['population'] for o in p['observations']} - {'unknown'})),
            delivery_structures=' | '.join(sorted({o['delivery'] for o in p['observations']} - {'unknown'})),
            allocations_json=json.dumps(allocations, ensure_ascii=False, separators=(',', ':')),
            notes=p['notes'] + ' ' + ref['notes'])
        rows.append(row)
        by_school[p['school_id']].append((p, row))
        grade = elementary.get(('all_recorded_programme_hosts', p['school_id']))
        gaps = []
        if ref['status'] != 'confirmed_2025_26':gaps.append('reference_year_operation')
        if not ref['eligibility'].startswith('documented_'):gaps.append('public_funding_or_eligibility')
        if not row['population_models']:gaps.append('one_way_two_way')
        if not row['delivery_structures']:gaps.append('strand_whole_school')
        if (grade and grade['elementary_denominator']
                and not any(numeric_model(a['label']) for a in p['allocations'])
                and not any(numeric_model(o['label']) for o in p['observations'])):
            gaps.append('elementary_numerical_allocation')
        if gaps:
            backlog.append(dict(state=p['state'], program_id=p['program_id'], school=p['school'], track=p['track'],
                gaps=' | '.join(gaps), evidence_url=row['operation_evidence_url'], notes=ref['notes']))
    for sid, values in sorted(by_school.items()):
        p = values[0][0]
        all_row = elementary[('all_recorded_programme_hosts', sid)]
        reference = elementary.get(('reference_working_set', sid))
        schools.append(dict(state=p['state'], school_id=sid, school=p['school'], district_or_operator=p['district'],
            programme_records=len(values), tracks=' | '.join(sorted(v['track'] for _, v in values)),
            programme_ids=' | '.join(sorted(q['program_id'] for q, _ in values)),
            elementary_classification=all_row['elementary_classification'],
            confirmed_qualifying_2025_26=int(reference is not None),
            elementary_reference_denominator=reference['elementary_denominator'] if reference else 0,
            elementary_reference_numerical_model=reference['has_numerical_allocation_model'] if reference else 0,
            numerical_models_all_source_periods=all_row['numerical_model_labels'],
            model_source_periods=all_row['model_source_periods'], model_review_flags=all_row['model_review_flags'],
            interpretation='One provisional school/campus unit; multiple rows in the programme CSV are distinct language strands. Coverage is within the reviewed working inventory, not a statewide census.'))
    summary = []
    for state in sorted(settings['states']):
        ps = [p for p in programmes if p['state'] == state]
        eligible = [p for p in ps if p['reference']['status'] == 'confirmed_2025_26'
                    and p['reference']['eligibility'].startswith('documented_')]
        cov = next(r for r in coverage if r['state_code'] == state and r['audit_scope'] == 'reference_working_set')
        summary.append(dict(state=state, programme_records=len(ps), school_units=len({p['school_id'] for p in ps}),
            confirmed_qualifying_reference_school_units=len({p['school_id'] for p in eligible}),
            elementary_reference_school_units=cov['elementary_school_units'],
            elementary_reference_schools_with_numerical_model=cov['elementary_schools_with_numerical_model'],
            elementary_reference_model_coverage_pct=cov['numerical_allocation_coverage_pct'],
            secondary_6_plus_reference_units_excluded=cov['secondary_6_plus_school_units_excluded'],
            statewide_completeness='not_established'))
    screening = [dict(state=s, **lead) for s in sorted(settings['states'])
                 for lead in json.loads((root / settings['base'] / (s.lower() + '_screening.json')).read_text())]
    if batch:
        fields = list(dict.fromkeys(key for row in screening for key in row))
        screening = [{key: json.dumps(row[key], ensure_ascii=False)
                      if isinstance(row.get(key), (list, dict)) else row.get(key, '')
                      for key in fields} for row in screening]
    prefix = settings['report']
    contents = {prefix + '_program_view.csv': csv_text(rows), prefix + '_schools.csv': csv_text(schools),
                prefix + '_by_state.csv': csv_text(summary), prefix + '_backlog.csv': csv_text(backlog),
                prefix + '_screening.csv': csv_text(screening), settings['base'] + '/sources.csv': csv_text(list(sources.values()))}
    changes = [dict(state=p['state'], school=p['school'], program_id=p['program_id'],
                    event_status=e['status'], event_year=e['year'], source_url=sources[e['source']]['url'], notes=e['notes'])
               for p in programmes for e in p['events']]
    changes += [dict(state=p['state'], school=p['school'], program_id=p['program_id'],
                     event_status=p['reference']['status'], event_year='2025-26 reference assessment',
                     source_url=sources[p['reference']['source']]['url'], notes=p['reference']['notes'])
                for p in programmes if p['reference']['status'] != 'confirmed_2025_26']
    contents[prefix + '_change_events.csv'] = csv_text(changes)
    cases = []
    for p in programmes:
        reason = None
        if p['school'] == 'Hmong International Academy':
            reason = 'Single 50% label versus 120 daily Hmong-literacy minutes; no total-day ratio synthesized.'
        elif p['school'] == 'Txuj Ci HMong Language & Culture – Upper Campus':
            reason = 'Same district page gives 6–8 in heading and 5–8 in detailed paragraph; elementary inclusion uses reported grade-5 scope provisionally.'
        elif not p['reference']['eligibility'].startswith('documented_'):
            reason = 'Academic immersion described; public funding for the reference-year provision requires verification.'
        elif p['reference']['status'] == 'uncertain_2025_26':
            reason = 'Announced 2025 start needs an implementation or change/ending check.'
        if reason:
            cases.append(dict(state=p['state'], school=p['school'], program_id=p['program_id'],
                review_reason=reason, source_url=sources[p['reference']['source']]['url'],
                notes=p['notes']))
    contents[prefix + '_review_cases.csv'] = csv_text(cases)
    for state in sorted(settings['states']):
        contents[settings['base'] + '/' + state.lower() + '_programmes.csv'] = csv_text([r for r in rows if r['state'] == state])
        contents[settings['base'] + '/' + state.lower() + '_schools.csv'] = csv_text([r for r in schools if r['state'] == state])
    report = dict(reference_school_year='2025-26', programme_records=len(programmes), school_units=len(schools),
        public_source_documents=len(sources), state_summary=summary, statewide_completeness='not_established',
        proficiency_collection='deferred; twelve existing assessment/context/EL/SEDA outputs preserved',
        limitations=['Programme/campus keys are provisional research identities, not NCES matches or official programme IDs.',
            'North Dakota has a documented Indigenous academic school candidate; its public funding remains unresolved. A zero qualifying denominator is not evidence of no programmes.',
            'Current directories and older descriptions do not establish the same annual grade roster, timetable or cohort exposure.',
            'School-grade classification uses programme-scope proxies where a school-grade directory was not matched.',
            'Published classroom-only models and conflicting model/minute descriptions carry review notes; they are not whole-day observed plans.',
            'Preschool networks, unimplemented pathways, uncertain new hosts, nonpublic funding candidates and historical relocations remain separate.'])
    if batch and batch.get('limitations'):
        report['limitations'] = batch['limitations']
    contents[prefix + '.json'] = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    return contents, report
