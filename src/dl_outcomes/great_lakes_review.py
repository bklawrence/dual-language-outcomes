"""Four-state source checks, including expansion of an existing state inventory."""
from collections import Counter
import json

from .io import digest
from .northern_central_review import audit_errors as reviewed_errors, render_reports as reviewed_reports, inputs
from .states.great_lakes import BASE, STATES, AUDIT, SUFFIX
from .western_plains_review import csv_text

REPORT = 'data/reports/great_lakes_2026_11_05'
SETTINGS = dict(base=BASE, states=STATES, audit=AUDIT, suffix=SUFFIX, report=REPORT,
    limitations=[
        'Partial structural inventory, not statewide completeness or a contemporaneous annual census.',
        'Illinois original school/programme/site identities and legacy claims are retained; matched sources add evidence to those same identities.',
        'Current directories, old descriptions and future starts retain their actual source periods; 2025–26 is a separate operation assessment.',
        'School-grade classification uses source programme-scope proxies where a separately dated school-grade directory is not matched.',
        'Preschool-only language programmes and language-as-a-subject classes are screening evidence, not automatically academic immersion.',
        'Funding candidates and uncertain programme rollouts are retained but excluded from confirmed qualifying reference-year coverage.',
        'Numerical allocation is school-level availability across source periods, not every strand or observed cohort exposure.'
    ])


def audit_errors(root, tables, *, check_hashes=True):
    from .illinois_history import authorized_additions
    added_schools, added_programmes = authorized_additions(root)
    settings = dict(SETTINGS, additional_programme_ids={'IL': added_programmes})
    errors = reviewed_errors(root, tables, check_hashes=check_hashes, batch=settings)
    audit = json.loads((root / AUDIT).read_text())
    programmes, _ = inputs(root, base=BASE, states=STATES)
    if check_hashes:
        for path, expected in audit['preserved_legacy_inputs'].items():
            if digest(root / path) != expected:
                errors.append('Illinois legacy input changed during expansion: ' + path)
    baseline = json.loads((root / audit['legacy_rows_path']).read_text())
    for table, rows in baseline.items():
        # Every original row remains intact; new evidence is appended separately.
        actual = {json.dumps(r, sort_keys=True, ensure_ascii=False) for r in tables[table]}
        if not all(json.dumps(r, sort_keys=True, ensure_ascii=False) in actual for r in rows):
            errors.append('Original Illinois registry/evidence row replaced: ' + table)
    for state in STATES:
        expected = {p['school_id'] for p in programmes if p['state'] == state}
        if state == 'IL':
            expected |= set(audit['expanded_state_original_ids']['schools']['IL'])
            expected |= added_schools
        actual = {r['school_id'] for r in tables['schools'] if r['state_code'] == state}
        if actual != expected:
            errors.append('Great Lakes school identities lost, invented or duplicated: ' + state)
    rows = json.loads((root / BASE / 'extractions/in_state_directory_rows.json').read_text())
    actual = [o['raw'] for p in programmes if p['state'] == 'IN'
              for o in p['observations'] if o['source'] == 'gl_in_state' and o.get('raw')]
    expected = [dict(reported_school=r[0], reported_district=r[1],
                     language_and_type=r[2], grade_cell=r[3]) for r in rows]
    normalized = lambda records: Counter(json.dumps(r, sort_keys=True) for r in records)
    if len(rows) != 44 or normalized(actual) != normalized(expected):
        errors.append('Indiana state-directory row/type/language/grade reconciliation changed')
    cps = json.loads((root / BASE / 'extractions/il_cps_roster_rows.json').read_text())
    hosts = {p['program_id']: p for p in programmes}
    if (len(cps) != 49
            or sum(r['reference_status'] == 'confirmed_2025_26' for r in cps) != 45
            or sum(r['reference_status'] == 'planned_future' for r in cps) != 3
            or [r['reported_school'] for r in cps if r['program_id'] is None] != ['THOMAS']):
        errors.append('CPS current roster / preschool / later-start reconciliation changed')
    for row in cps:
        if row['program_id'] is None:
            continue
        p = hosts.get(row['program_id'])
        if (not p or p['school_id'] != row['school_id']
                or p['reference']['status'] != row['reference_status']
                or not any(o.get('raw', {}).get('cps_native_school_code') == row['cps_native_code']
                           and o['raw']['reported_school'] == row['reported_school']
                           for o in p['observations'])):
            errors.append('CPS named host/native code changed: ' + row['reported_school'])
    u46 = json.loads((root / BASE / 'extractions/il_u46_2025_26_chart_transcription.json').read_text())
    actual = [p for p in programmes if p['district'] == 'School District U-46']
    if (len(actual) != 27 or {p['school'] for p in actual} != {s + ' Elementary School' for s in u46['school_names']}
            or any(not any(a['source'] == u46['source'] and a['period'] == '2025-26'
                           and a['grade'] == 'K-1' and a['shares'] == {'Spanish': 80, 'English': 20}
                           for a in p['allocations']) for p in actual)):
        errors.append('U-46 dated host/entry-model chart reconciliation changed')
    return errors


def render_reports(root, tables):
    contents, report = reviewed_reports(root, tables, batch=SETTINGS)
    programmes, sources = inputs(root, base=BASE, states=STATES)
    cases = []
    for p in programmes:
        reasons = p.get('review_reasons', [])
        if not reasons and p['reference']['status'] == 'uncertain_2025_26':
            reasons = [p['reference']['notes']]
        for reason in reasons:
            cases.append(dict(state=p['state'], school=p['school'], program_id=p['program_id'],
                review_reason=reason, source_url=sources[p['reference']['source']]['url'], notes=p['notes']))
    contents[REPORT + '_review_cases.csv'] = csv_text(cases)
    return contents, report
