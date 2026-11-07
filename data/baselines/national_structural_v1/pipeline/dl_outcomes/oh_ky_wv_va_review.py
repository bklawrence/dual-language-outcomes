"""Source conservation, longitudinal scope and prior-preservation checks for OH/KY/WV/VA."""
from collections import Counter
import csv
from html.parser import HTMLParser
import io
import json

from .io import digest
from .northern_central_review import audit_errors as reviewed_errors, render_reports as reviewed_reports, inputs
from .states.oh_ky_wv_va import BASE, STATES, AUDIT, SUFFIX
from .western_plains_review import csv_text

REPORT = 'data/reports/oh_ky_wv_va_2026_11_05'
SETTINGS = dict(base=BASE, states=STATES, audit=AUDIT, suffix=SUFFIX, report=REPORT,
    limitations=[
        'Partial structural review, not a statewide census; all four states were screened, including states with no verified qualifying programme.',
        '2025–26 reference operation is distinct from source vintages, later entry-grade expansions, plans, cuts and campus changes.',
        'Reference model availability uses undated or no-later-than-reference sources; explicitly later models remain in the all-recorded view. Neither view is an observed cohort timetable.',
        'One-way/two-way pupil composition, seat quotas, at-least percentages and FLES minutes are not exact instructional-time models.',
        'Academic immersion and formal secondary continuation are retained separately from language electives, specials, preschool-only provision and summer camps.',
        'Public charter operators are reporting groups, not inferred LEAs. School/campus and programme keys are provisional.',
        'CCD 2024–25 school-grade metadata supplies denominator context, not programme operation, durable identifier crosswalks or stable cohorts.',
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
                errors.append('OH/KY/WV/VA changed previous registry input/export: '+path)
    for row in json.loads((root/BASE/'source_redactions.json').read_text()):
        doc=sources[row['key']];metadata=json.loads((root/doc['metadata_path']).read_text())
        if doc['path']!=row['redacted_path'] or doc['sha256']!=row['saved_redacted_sha256'] or metadata.get('full_response_sha256')!=row['original_response_sha256'] or not metadata.get('redactions') or not row['programme_text_unchanged']:
            errors.append('OH/KY/WV/VA public snapshot redaction provenance changed: '+row['key'])
    for state in STATES:
        actual = {r['school_id'] for r in tables['schools'] if r['state_code']==state}
        if actual != {p['school_id'] for p in programmes if p['state']==state}:
            errors.append('OH/KY/WV/VA school identity set changed: '+state)
    reconciliations = json.loads((root/BASE/'extractions/roster_reconciliation.json').read_text())
    for selection in reconciliations:
        rows=selection['rows']
        if len(rows)!=selection['expected_rows'] or len({r['source_row'] for r in rows})!=len(rows):
            errors.append('OH/KY/WV/VA roster row count or ordinals changed: '+selection['name'])
        for row in rows:
            if row['source_key']!=selection['source_key']:
                errors.append('OH/KY/WV/VA roster source changed: '+selection['name'])
            for pid in row['program_ids']:
                if pid not in by_id or by_id[pid]['school_id'] not in row['school_ids']:
                    errors.append('OH/KY/WV/VA roster programme/host link changed: '+selection['name'])
            if not row['program_ids'] and row['disposition']!='screening_only':
                errors.append('OH/KY/WV/VA source row lost its disposition: '+selection['name'])
        if selection['name'].endswith('_directory_cards'):
            parser = DirectoryCards()
            parser.feed((root / sources[selection['source_key']]['path']).read_text())
            selected = [(r['raw']['source_school'], r['raw']['directory_url']) for r in rows]
            if Counter(parser.cards) != Counter(selected):
                errors.append('OH/KY/WV/VA actual directory cards changed: '+selection['name'])
    # Keep primary-source ambiguities explicit rather than manufacturing a model.
    for p in programmes:
        for allocation in p['allocations']:
            if allocation['source'] in {'e4_va_loudoun', 'e4_va_winchester_trajectory', 'e4_va_henrico_alt'}:
                errors.append('Pupil ratio/lower bound/qualitative source became exact allocation: '+p['program_id'])
        if p['school']=='Ravensworth Elementary School' and any('German' in o['languages'] for o in p['observations']):
            errors.append('Fairfax Ravensworth Spanish strand was misclassified as German')
        if p['school']=='Fairview-Clifton German Language School':
            errors.append('Explicit intensive FLES school was incorrectly promoted to academic immersion')
        if p['state']=='WV':
            errors.append('WV screening lead was promoted without new reviewed academic bilingual evidence')
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
            errors.append('OH/KY/WV/VA grade-context source/year changed: '+row['school'])
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
