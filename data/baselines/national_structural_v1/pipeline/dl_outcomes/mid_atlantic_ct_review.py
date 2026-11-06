"""Source conservation, longitudinal scope and prior-preservation checks for PA/MD/DE/NJ/NY/CT."""
from collections import Counter
import csv
from html.parser import HTMLParser
import io
import json

from .io import digest
from .northern_central_review import audit_errors as reviewed_errors, render_reports as reviewed_reports, inputs
from .states.mid_atlantic_ct import BASE, STATES, AUDIT, SUFFIX
from .western_plains_review import csv_text

REPORT = 'data/reports/mid_atlantic_ct_2026_11_05'
SETTINGS = dict(base=BASE, states=STATES, audit=AUDIT, suffix=SUFFIX, report=REPORT,
    limitations=[
        'Partial structural review, not a statewide census; all six states have programme records, with additional unresolved discovery leads.',
        '2025–26 reference operation is distinct from source vintages, later entry-grade expansions, plans, cuts and campus changes.',
        'Reference model availability uses undated or no-later-than-reference sources; explicitly later models remain in the all-recorded view. Neither view is an observed cohort timetable.',
        'One-way/two-way pupil composition, seat quotas, at-least percentages and FLES minutes are not exact instructional-time models.',
        'Academic immersion and formal secondary continuation are retained separately from language electives, specials, preschool-only provision and summer camps.',
        'Public charter operators are reporting groups, not inferred LEAs. School/campus and programme keys are provisional.',
        'CCD 2024–25 school-grade metadata supplies denominator context, not programme operation, durable identifier crosswalks or stable cohorts; dated district grade changes supersede older directory context.',
        'Proficiency, demographic, EL-exit and SEDA collection remains deferred.'
    ])


class DirectoryCards(HTMLParser):
    """Read actual school links, excluding the directory's global filter choices."""

    def __init__(self):
        super().__init__()
        self.cards = []
        self.url = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get('href', '')
        if tag == 'a' and '/school/' in href:
            self.url, self.parts = href, []

    def handle_data(self, value):
        if self.url:
            self.parts.append(value)

    def handle_endtag(self, tag):
        if tag == 'a' and self.url:
            self.cards.append((' '.join(''.join(self.parts).split()), self.url))
            self.url = None


def audit_errors(root, tables, *, check_hashes=True):
    errors = reviewed_errors(root, tables, check_hashes=check_hashes, batch=SETTINGS)
    audit = json.loads((root / AUDIT).read_text())
    programmes, sources = inputs(root, base=BASE, states=STATES)
    by_id = {p['program_id']:p for p in programmes}
    if check_hashes:
        for path, expected in audit['preserved_previous_registry'].items():
            if digest(root/path) != expected:
                errors.append('PA/MD/DE/NJ/NY/CT changed previous registry input/export: '+path)
    for row in json.loads((root/BASE/'source_redactions.json').read_text()):
        doc=sources[row['key']];metadata=json.loads((root/doc['metadata_path']).read_text())
        if doc['path']!=row['redacted_path'] or doc['sha256']!=row['saved_redacted_sha256'] or metadata.get('full_response_sha256')!=row['original_response_sha256'] or not metadata.get('redactions') or not row['programme_text_unchanged']:
            errors.append('PA/MD/DE/NJ/NY/CT public snapshot redaction provenance changed: '+row['key'])
    for state in STATES:
        actual = {r['school_id'] for r in tables['schools'] if r['state_code']==state}
        if actual != {p['school_id'] for p in programmes if p['state']==state}:
            errors.append('PA/MD/DE/NJ/NY/CT school identity set changed: '+state)
    reconciliations = json.loads((root/BASE/'extractions/roster_reconciliation.json').read_text())
    for selection in reconciliations:
        rows=selection['rows']
        if len(rows)!=selection['expected_rows'] or len({r['source_row'] for r in rows})!=len(rows):
            errors.append('PA/MD/DE/NJ/NY/CT roster row count or ordinals changed: '+selection['name'])
        for row in rows:
            if row['source_key']!=selection['source_key']:
                errors.append('PA/MD/DE/NJ/NY/CT roster source changed: '+selection['name'])
            for pid in row['program_ids']:
                if pid not in by_id or by_id[pid]['school_id'] not in row['school_ids']:
                    errors.append('PA/MD/DE/NJ/NY/CT roster programme/host link changed: '+selection['name'])
            if not row['program_ids'] and row['disposition']!='screening_only':
                errors.append('PA/MD/DE/NJ/NY/CT source row lost its disposition: '+selection['name'])
        if selection['name'].endswith('_directory_cards'):
            parser = DirectoryCards()
            parser.feed((root / sources[selection['source_key']]['path']).read_text())
            selected = [(r['raw']['source_school'], r['raw']['directory_url']) for r in rows]
            if Counter(parser.cards) != Counter(selected):
                errors.append('PA/MD/DE/NJ/NY/CT actual directory cards changed: '+selection['name'])
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
            errors.append('PA/MD/DE/NJ/NY/CT grade-context source/year changed: '+row['school'])
    # Full city CSV conservation, including excluded TBE and repeated service cells.
    city = next(r for r in reconciliations if r['name'] == 'nyc_2025_26_bilingual_csv')
    original = list(csv.DictReader(io.StringIO((root / sources['m6_nyc_csv25']['path']).read_text(encoding='utf-8-sig'))))
    if [r['raw'] for r in city['rows']] != original or len(original) != 579:
        errors.append('NYC original CSV fields/row order changed or lost')
    dl = [r for r in original if r['Program'] == 'Dual Language Bilingual Education']
    if (len(dl), len(original)-len(dl), len({(r['School'],r['Language']) for r in dl}), len({r['School'] for r in dl})) != (300,279,254,240):
        errors.append('NYC service/strand/school distinction changed')
    for row in city['rows']:
        is_dl = row['raw']['Program'] == 'Dual Language Bilingual Education'
        ps = [by_id[x] for x in row['program_ids']]
        if (is_dl and (len(ps) != 1 or ps[0].get('nyc_dbn') != row['raw']['School']
                or ps[0]['track'] != row['raw']['Language'] + ' immersion')) or (not is_dl and ps):
            errors.append('NYC DLBE/TBE or school-language cell classification changed')
    city_programmes = [p for p in programmes if p.get('nyc_dbn')]
    observations = [o['raw'] for p in city_programmes for o in p['observations'] if o['source']=='m6_nyc_csv25']
    pack = lambda row: json.dumps(row,sort_keys=True,ensure_ascii=False)
    if Counter(map(pack,observations)) != Counter(map(pack,dl)):
        errors.append('NYC service-model observations lost or duplicated')
    claims = {(r['entity_id'],r['source_locator']): r for r in tables['evidence_claims']
              if r['attribute']=='source_structural_observation'}
    for p in city_programmes:
        for i, o in enumerate(p['observations']):
            if o['source']!='m6_nyc_csv25':
                continue
            locator=p['program_id']+':observation:'+str(i)+'; '+o['locator']
            claim=claims.get((p['program_id'],locator))
            if not claim or json.loads(claim['reported_value'])!=o:
                errors.append('NYC canonical raw service observation changed: '+p['nyc_dbn'])
    official_ids = {(r['entity_id'],r['native_id']) for r in tables['identifiers'] if r['namespace']=='NYC_DBN'}
    if official_ids != {(p['school_id'],p['nyc_dbn']) for p in city_programmes}:
        errors.append('NYC official DBN identifiers changed')
    # The newer official grade reconfiguration replaces the old context claim.
    updates = json.loads((root/BASE/'school_grade_updates.json').read_text())
    expected_grades = {'Windham Middle School': (5,8), 'North Windham Elementary School': (0,4)}
    if {r['school'] for r in updates} != set(expected_grades):
        errors.append('Windham dated grade-update host set changed')
    for row in updates:
        claim=context.get(row['school_id']); value=json.loads(claim['reported_value']) if claim else {}
        if (row['source_key']!='m6_ct_windham_close' or row['year']!='2025-26'
                or (row['lowest_grade_offered'],row['highest_grade_offered'])!=expected_grades.get(row['school'])
                or row['school_id'] in {r['school_id'] for r in decisions}
                or not claim or claim['valid_from_year']!='2025-26'
                or any(value.get(k)!=row[k] for k in ['ncessch','lowest_grade_offered','highest_grade_offered'])):
            errors.append('Windham official grade update was lost or overridden: '+row['school'])
    de=next(r for r in reconciliations if r['name']=='de_state_map_2021_22_hosts')
    if len(de['rows'])!=57 or sum(len(r['program_ids']) for r in de['rows'])!=60:
        errors.append('Delaware historical host/multiple-language row conservation changed')
    no_numeric={'DiLoreto Elementary and Middle School','North Windham Elementary School','Windham Middle School','Regional Multicultural Magnet School'}
    for p in programmes:
        if p['school'] in no_numeric and p['allocations']:
            errors.append('Minimum, aspiration or unquantified alternation became exact model: '+p['school'])
        if p['school']=='Baltimore International Academy West' and any(o['languages'][0] in {'Russian','Arabic'} for o in p['observations']):
            errors.append('Baltimore West planned language became implemented')
        if p['district']=='Rochester City School District' and any(o['languages']!=['English'] and not o['source'].startswith('nyf_rochester_') for o in p['observations']):
            errors.append('Rochester partner language assigned without follow-up verification')
    denton=next(p for p in programmes if p['school']=='Denton Avenue Elementary School')
    faq=[a for a in denton['allocations'] if a['source']=='m6_ny_herricks_faq']
    if (len(faq)!=1 or faq[0]['grade']!='K-5' or faq[0]['label']!='50/50'
            or faq[0]['shares']!={'Spanish':50,'English':50}
            or 'September 2023' not in faq[0]['period']
            or not any(o['source']=='m6_ny_herricks_faq' and o['population']=='one_way' for o in denton['observations'])):
        errors.append('Herricks documented elementary one-way 50/50 model or source vintage changed')
    secondary={p['program_id'] for p in programmes if p['district']=='Herricks Union Free School District' and p['program_id']!=denton['program_id']}
    sites={r['site_id'] for r in tables['program_sites'] if r['program_id'] in secondary}
    if any(r['site_id'] in sites for r in tables['allocation_schedules']):
        errors.append('Herricks elementary percentage incorrectly assigned to secondary continuation')
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
    # Later numerical policies remain useful, but do not silently fill a reference-year gap.
    schools = list(csv.DictReader(io.StringIO(contents[REPORT+'_schools.csv'])))
    later_only = {r['school_id'] for r in schools
                  if r['elementary_reference_denominator']=='1'
                  and r['elementary_reference_numerical_model']=='0'
                  and r['numerical_models_all_source_periods']}
    backlog = list(csv.DictReader(io.StringIO(contents[REPORT+'_backlog.csv'])))
    for row in backlog:
        programme = next(p for p in programmes if p['program_id']==row['program_id'])
        if programme['school_id'] in later_only:
            row['gaps'] += ' | reference_year_numerical_allocation_later_policy_only'
    contents[REPORT+'_backlog.csv'] = csv_text(backlog)
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
