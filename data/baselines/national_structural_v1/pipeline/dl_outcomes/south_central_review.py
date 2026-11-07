"""Source, date and scope checks for OK/AR/LA/AL/MS structural research."""
from collections import Counter
import json

from .io import digest
from .northern_central_review import audit_errors as reviewed_errors, render_reports as reviewed_reports, inputs
from .states.south_central import BASE, STATES, AUDIT, SUFFIX
from .western_plains_review import csv_text

REPORT = 'data/reports/south_central_2026_11_05'
SETTINGS = dict(base=BASE, states=STATES, audit=AUDIT, suffix=SUFFIX, report=REPORT,
    limitations=[
        'Partial structural research, not a statewide census or a contemporaneous annual roster.',
        '2025–26 operation assessment is separate from source publication dates and later starts, moves, closures and governance changes.',
        'Mississippi has screened sources but no verified programme in this pass; this is not evidence of statewide absence.',
        'Government map and certified-site lists are different selections; actual source rows and aliases are retained.',
        'School/campus keys are provisional reporting identities. Source grade context does not establish durable NCES programme crosswalks or stable cohorts.',
        'Published percentage ranges and pupil-language balance do not become single instructional allocation models.',
        'Numerical model information across source periods is not exact K exposure, named-language shares for every model, or every-strand completeness.',
        'Language classes, adult provision and preschool/summer networks remain separate screening evidence.',
        'New proficiency, context, EL-exit and SEDA collection remains deferred.'
    ])


def audit_errors(root, tables, *, check_hashes=True):
    errors = reviewed_errors(root, tables, check_hashes=check_hashes, batch=SETTINGS)
    audit = json.loads((root / AUDIT).read_text())
    programmes, sources = inputs(root, base=BASE, states=STATES)
    if check_hashes:
        for path, expected in audit['preserved_previous_registry'].items():
            if digest(root / path) != expected:
                errors.append('South-central review changed previous registry input/export: ' + path)
    for state in STATES:
        actual = {r['school_id'] for r in tables['schools'] if r['state_code']==state}
        if actual != {p['school_id'] for p in programmes if p['state']==state}:
            errors.append('South-central school identity set changed: ' + state)
    ext = root / BASE / 'extractions'
    maps = json.loads((ext / 'la_codofil_map_rows.json').read_text())
    source = json.loads((root / sources['sc_la_codofil_objects5']['path']).read_text())
    actual = [o['raw'] for p in programmes for o in p['observations']
              if o['source']=='sc_la_codofil_objects5' and o.get('raw')]
    normalized = lambda rows: Counter(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows)
    if (len(maps)!=35 or len(source['items'])!=35 or source['hasMore']
            or normalized(actual)!=normalized(source['items'])
            or normalized(r['raw'] for r in maps)!=normalized(source['items'])):
        errors.append('CODOFIL actual map rows, original fields or pagination changed')
    for filename, expected in [('la_state_certified_rows.json',24),
                               ('la_calcasieu_directory_rows.json',13),
                               ('la_jefferson_two_way_rows.json',11)]:
        rows=json.loads((ext/filename).read_text())
        if len(rows)!=expected:
            errors.append('Louisiana source selection row count changed: '+filename)
    by_id={p['program_id']:p for p in programmes}
    for row in maps:
        p=by_id.get(row['program_id'])
        if not p or p['school_id']!=row['school_id'] or not any(o.get('raw')==row['raw'] for o in p['observations']):
            errors.append('CODOFIL row-to-school/language mapping changed: '+row['source_map_id'])
    redactions=json.loads((root/BASE/'source_redactions.json').read_text())
    if {r['key'] for r in redactions}!={'sc_la_isl','sc_la_isl_admissions','sc_la_isl_copy','sc_la_isl_curriculum'}:
        errors.append('Declared public-snapshot redaction set changed')
    for row in redactions:
        doc=sources[row['key']]
        metadata=json.loads((root/doc['metadata_path']).read_text())
        if (doc['path']!=row['redacted_path'] or doc['sha256']!=row['saved_redacted_sha256']
                or metadata['full_response_sha256']!=row['original_response_sha256']
                or not row['programme_text_unchanged'] or not metadata.get('redactions')
                or 'redacted' not in doc['archive_kind']):
            errors.append('Public snapshot redaction provenance changed: '+row['key'])
    decisions = json.loads((root / BASE / 'grade_context_decisions.json').read_text())
    context = {r['entity_id']:r for r in tables['evidence_claims']
        if r['attribute']=='elementary_audit_school_grade_context'}
    directory = {}
    for row in decisions:
        key=row['source_key']
        if key not in directory:
            raw=json.loads((root/sources[key]['path']).read_text())
            if raw['next']:
                errors.append('School-grade directory capture has uncollected pages: '+key)
            directory[key]={r['ncessch']:r for r in raw['results']}
        original=directory[key].get(row['ncessch'])
        claim=context.get(row['school_id'])
        value=json.loads(claim['reported_value']) if claim else {}
        if (not original or not claim or claim['valid_from_year']!='2024-25'
                or any(original[k]!=row[k] or value.get(k)!=row[k]
                       for k in ['ncessch','lowest_grade_offered','highest_grade_offered'])):
            errors.append('School-grade context/source-year changed: '+row['school'])
    if any(p['state']=='MS' for p in programmes):
        errors.append('Mississippi screening acquired an unverified DL programme')
    for p in programmes:
        if p['state']=='AR' and (p['reference']['status']=='confirmed_2025_26'
                or any(o['period']=='2025-26' for o in p['observations'])):
            errors.append('Arkansas 2026–27 launch backdated to reference year')
        if p['state']=='AL' and p['allocations']:
            errors.append('Birmingham pupil balance or incomplete timetable became a day model')
        if p['school'] in {'Baton Rouge FLAIM'}:
            if any(a['shares'] or a['label'] not in {'60–70% target-language range; no single day model'}
                   for a in p['allocations']):
                errors.append('FLAIM range rounded into an unsupported point allocation')
        if 'Hynes Charter School' in p['school'] and any(a['shares'] for a in p['allocations']):
            errors.append('Hynes remainder acquired invented named-language shares')
    return errors


def render_reports(root, tables):
    contents, report = reviewed_reports(root, tables, batch=SETTINGS)
    programmes, sources = inputs(root, base=BASE, states=STATES)
    cases=[]
    for p in programmes:
        reasons=p.get('review_reasons',[])
        for reason in reasons:
            cases.append(dict(state=p['state'],school=p['school'],program_id=p['program_id'],
                review_reason=reason,source_url=sources[p['reference']['source']]['url'],notes=p['notes']))
    contents[REPORT+'_review_cases.csv']=csv_text(cases)
    for state in sorted(STATES):
        leads=json.loads((root/BASE/(state.lower()+'_screening.json')).read_text())
        rows=[dict(state=state,**r,source_url=sources[r['source']]['url']) for r in leads]
        contents[BASE+'/'+state.lower()+'_screening.csv']=csv_text(rows,
            fields=list(rows[0]) if rows else ['state','school','disposition','reason','source_url'])
    report['states_with_programme_records']=sorted({p['state'] for p in programmes})
    report['screened_only_states']=sorted(STATES-{p['state'] for p in programmes})
    report['source_reconciliation_counts']=dict(codofil_actual_map_rows=35,
        state_certification_site_rows=24,calcasieu_language_school_rows=13,
        jefferson_two_way_spanish_host_rows=11)
    contents[REPORT+'.json']=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    return contents, report
