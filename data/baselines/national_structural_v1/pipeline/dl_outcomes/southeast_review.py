"""Source conservation, longitudinal scope and prior-preservation checks for FL/GA/SC/NC/TN."""
from collections import Counter
import csv
import io
import json

from .io import digest
from .northern_central_review import audit_errors as reviewed_errors, render_reports as reviewed_reports, inputs
from .states.southeast import BASE, STATES, AUDIT, SUFFIX
from .western_plains_review import csv_text

REPORT = 'data/reports/southeast_2026_11_05'
SETTINGS = dict(base=BASE, states=STATES, audit=AUDIT, suffix=SUFFIX, report=REPORT,
    limitations=[
        'Partial structural review, not a statewide census. Official rosters differ in date, selection and level of detail.',
        '2025–26 reference operation is distinct from actual source dates, launch-year cells, later policy descriptions and closure/move events.',
        'Live NC directory Full/Partial/Continuing categories do not establish numerical time allocations; all 316 source rows are reconciled.',
        'Georgia FY25 appendix has 87 schools and 93 language-school cells, including preschool entries; typically 50/50 is not a universal state rule.',
        'FL BISO and International Studies academic programmes are distinguished from 47 EFL leads whose academic content scope needs review.',
        'Broward daily-hour ranges and pupil ratios are not single instructional models. Osceola working-toward language is not implemented 50/50.',
        'Palm Beach 2026 elementary policy is separately dated from its 2025 two-model guidance; availability across source periods is not a 2025 campus-specific model.',
        'School/campus keys are provisional. Separate school levels in a roster can describe one campus; source identifiers are not durable programme crosswalks.',
        'School-grade CCD context is 2024–25 metadata, not programme operation, stable cohort exposure, or a newly asserted NCES identifier.',
        'Proficiency, demographic, EL-exit and SEDA collection remains deferred.'
    ])


def audit_errors(root, tables, *, check_hashes=True):
    errors = reviewed_errors(root, tables, check_hashes=check_hashes, batch=SETTINGS)
    audit = json.loads((root / AUDIT).read_text())
    programmes, sources = inputs(root, base=BASE, states=STATES)
    by_id = {p['program_id']:p for p in programmes}
    if check_hashes:
        for path, expected in audit['preserved_previous_registry'].items():
            if digest(root/path) != expected:
                errors.append('Southeast changed previous registry input/export: '+path)
    for row in json.loads((root/BASE/'source_redactions.json').read_text()):
        doc=sources[row['key']];metadata=json.loads((root/doc['metadata_path']).read_text())
        if doc['path']!=row['redacted_path'] or doc['sha256']!=row['saved_redacted_sha256'] or metadata.get('full_response_sha256')!=row['original_response_sha256'] or not metadata.get('redactions') or not row['programme_text_unchanged']:
            errors.append('Southeast public snapshot redaction provenance changed: '+row['key'])
    for state in STATES:
        actual = {r['school_id'] for r in tables['schools'] if r['state_code']==state}
        if actual != {p['school_id'] for p in programmes if p['state']==state}:
            errors.append('Southeast school identity set changed: '+state)
    reconciliations = json.loads((root/BASE/'extractions/roster_reconciliation.json').read_text())
    for selection in reconciliations:
        rows=selection['rows']
        if len(rows)!=selection['expected_rows'] or len({r['source_row'] for r in rows})!=len(rows):
            errors.append('Southeast roster row count or ordinals changed: '+selection['name'])
        for row in rows:
            if row['source_key']!=selection['source_key']:
                errors.append('Southeast roster source changed: '+selection['name'])
            for pid in row['program_ids']:
                if pid not in by_id or by_id[pid]['school_id'] not in row['school_ids']:
                    errors.append('Southeast roster programme/host link changed: '+selection['name'])
            if not row['program_ids'] and row['disposition']!='screening_only':
                errors.append('Southeast source row lost its disposition: '+selection['name'])
    nc=next(s for s in reconciliations if s['name']=='nc_state_directory')
    original=list(csv.DictReader(io.StringIO((root/sources['se_nc_csv']['path']).read_text(encoding='utf-8-sig'))))
    normalized=lambda rs:Counter(json.dumps(r,sort_keys=True,ensure_ascii=False) for r in rs)
    if len(original)!=316 or normalized(original)!=normalized(r['raw'] for r in nc['rows']):
        errors.append('North Carolina actual source CSV rows/fields changed')
    ga=next(s for s in reconciliations if s['name']=='ga_state_school_appendix')
    if len(ga['rows'])!=87 or sum(len(r['raw']['languages']) for r in ga['rows'])!=93:
        errors.append('Georgia 87-school/93-language-cell appendix changed')
    for p in programmes:
        if p['state']=='NC':
            for o in p['observations']:
                if o['source']=='se_nc_csv' and o['label']:
                    errors.append('NC qualitative directory type acquired numerical allocation: '+p['program_id'])
            for o in p['observations']:
                launch=o.get('raw',{}).get('Year of Launch','')
                if launch.startswith(('2026-','2028-')) and p['reference']['status']=='confirmed_2025_26':
                    errors.append('NC future launch backdated: '+p['program_id'])
        for a in p['allocations']:
            if a['source'] in {'se_fl_broward_guide25','se_fl_osceola_brochure26'}:
                errors.append('Range or aspirational language became implemented allocation: '+p['program_id'])
        if p['school'] in {'Treadwell Elementary School'} and any(a['label']!='90/10' for a in p['allocations']):
            errors.append('Treadwell pupil ratio replaced K instructional allocation')
    decisions=json.loads((root/BASE/'grade_context_decisions.json').read_text())
    context={r['entity_id']:r for r in tables['evidence_claims'] if r['attribute']=='elementary_audit_school_grade_context'}
    directory={}
    for row in decisions:
        key=row['source_key']
        if key not in directory:
            raw=json.loads((root/sources[key]['path']).read_text())
            if raw['next']:errors.append('Uncollected CCD grade-context pages: '+key)
            directory[key]={r['ncessch']:r for r in raw['results']}
        original=directory[key].get(row['ncessch']);claim=context.get(row['school_id'])
        value=json.loads(claim['reported_value']) if claim else {}
        if not original or not claim or claim['valid_from_year']!='2024-25' or any(original[k]!=row[k] or value.get(k)!=row[k] for k in ['ncessch','lowest_grade_offered','highest_grade_offered']):
            errors.append('Southeast grade-context source/year changed: '+row['school'])
    return errors


def render_reports(root,tables):
    contents,report=reviewed_reports(root,tables,batch=SETTINGS)
    programmes,sources=inputs(root,base=BASE,states=STATES)
    cases=[dict(state=p['state'],school=p['school'],program_id=p['program_id'],review_reason=reason,
                source_url=sources[p['reference']['source']]['url'],notes=p['notes'])
           for p in programmes for reason in p.get('review_reasons',[])]
    for p in programmes:
        if not p['reference']['eligibility'].startswith('documented_'):
            cases.append(dict(state=p['state'],school=p['school'],program_id=p['program_id'],review_reason='Public funding or reference-year academic grade eligibility needs verification',source_url=sources[p['reference']['source']]['url'],notes=p['notes']))
    contents[REPORT+'_review_cases.csv']=csv_text(cases)
    for state in sorted(STATES):
        leads=json.loads((root/BASE/(state.lower()+'_screening.json')).read_text())
        rows=[dict(state=state,**r,source_url=sources[r['source']]['url']) for r in leads]
        fields=list(dict.fromkeys(k for row in rows for k in row)) if rows else ['state','school','disposition','reason','source_url']
        rows=[{k:json.dumps(row[k],ensure_ascii=False) if isinstance(row.get(k),(list,dict)) else row.get(k,'') for k in fields} for row in rows]
        contents[BASE+'/'+state.lower()+'_screening.csv']=csv_text(rows,fields=fields)
    selections=json.loads((root/BASE/'extractions/roster_reconciliation.json').read_text())
    report['source_reconciliation_counts']={r['name']:len(r['rows']) for r in selections}
    report['states_with_programme_records']=sorted({p['state'] for p in programmes})
    report['screened_only_states']=sorted(STATES-{p['state'] for p in programmes})
    contents[REPORT+'.json']=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    return contents,report
