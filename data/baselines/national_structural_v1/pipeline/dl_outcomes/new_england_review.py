"""Source conservation and readable exports for the final five-state pass."""
import json
import zipfile
from xml.etree import ElementTree

from .io import digest
from .northern_central_review import audit_errors as reviewed_errors, render_reports as reviewed_reports, inputs
from .states.new_england import AUDIT, BASE, STATES, SUFFIX
from .western_plains_review import csv_text
from .policy_selection import current_policy_choices

REPORT = 'data/reports/new_england_2026_11_06'
SETTINGS = dict(base=BASE, states=STATES, audit=AUDIT, suffix=SUFFIX, report=REPORT,
    limitations=[
        'Completes a first structural research pass across all 50 states; it is not a census of all dual-language schools.',
        '2025-26 reference operation is distinct from document dates, calendar-year establishment claims, later launches and relocation plans.',
        'Secondary-only continuation hosts are retained without an elementary entry-allocation model. Schools containing any K-5 grade remain in the elementary school audit.',
        'Programme/school keys and unverified district-name groups are provisional, not official programme identifiers or NCES crosswalks.',
        'Language shares describe published instructional policies or explicitly flagged estimates; they do not establish actual tested-cohort exposure.',
        'Preschool language nests, language-subject classes, generic bilingual support and private funding candidates remain distinguishable from public academic immersion.',
        'Proficiency, demographic, EL-exit and SEDA collection remains deferred; twelve prior outputs are preserved.'
    ])


def audit_errors(root, tables, *, check_hashes=True):
    errors = reviewed_errors(root, tables, check_hashes=check_hashes, batch=SETTINGS)
    audit = json.loads((root / AUDIT).read_text())
    programmes, sources = inputs(root, base=BASE, states=STATES)
    by_id = {p['program_id']: p for p in programmes}
    canonical_observations = {}
    for claim in tables['evidence_claims']:
        if claim['attribute'] == 'source_structural_observation':
            canonical_observations.setdefault(claim['entity_id'], []).append(json.loads(claim['reported_value']))
    if check_hashes:
        for field in ['preserved_previous_registry', 'preserved_previous_archives']:
            for path, expected in audit[field].items():
                if digest(root / path) != expected:
                    errors.append('New England pass changed previous research: ' + path)
    # The state Word directory is a paragraph roster, not an HTML table.
    roster = json.loads((root / BASE / 'extractions/roster_reconciliation.json').read_text())
    for selection in roster:
        rows = selection['rows']
        if len(rows) != selection['expected_rows'] or len({r['source_row'] for r in rows}) != len(rows):
            errors.append('New England source row count or ordinals changed: ' + selection['name'])
        if selection['name'] == 'massachusetts_dese_dle_docx':
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            with zipfile.ZipFile(root / sources[selection['source_key']]['path']) as archive:
                document = ElementTree.fromstring(archive.read('word/document.xml'))
            paragraphs = [''.join(n.text or '' for n in p.findall('.//w:t', ns))
                          for p in document.findall('.//w:p', ns)]
            if len(rows) != 75 or any(paragraphs[r['source_paragraph']] != r['raw']['text_raw'] for r in rows):
                errors.append('Massachusetts official paragraph roster changed or was truncated')
        for row in rows:
            if not row['program_ids'] and not row.get('disposition'):
                errors.append('New England source row lacks a disposition')
            for pid in row['program_ids']:
                if pid not in by_id or by_id[pid]['school_id'] not in row['school_ids']:
                    errors.append('New England source/strand/host link changed: ' + pid)
                if not any(o.get('raw_directory_row') == row['raw']
                           for o in canonical_observations.get(pid, [])):
                    errors.append('New England canonical raw directory row lost: ' + pid)
    schedules = {r['schedule_id']: r for r in tables['allocation_schedules']}
    sites = {r['site_id']: r for r in tables['program_sites']}
    shares = {}
    for r in tables['instructional_allocations']:
        shares.setdefault(r['schedule_id'], []).append(r)
    for claim in tables['evidence_claims']:
        if claim['attribute'] != 'allocation_source_selection':
            continue
        schedule = schedules[claim['entity_id']]
        if sites[schedule['site_id']]['program_id'] not in by_id:
            continue
        a = json.loads(claim['reported_value'])
        if a.get('evidence_type') == 'researcher_inference':
            if (not a.get('source_passage') or not a.get('notes')
                    or not a.get('classification_method')
                    or schedule['schedule_status'] != 'inferred_plan'
                    or not shares.get(claim['entity_id'])
                    or any(r['evidence_type'] != 'researcher_inference' for r in shares[claim['entity_id']])):
                errors.append('New England inferred allocation lost its source, method or typed distinction: ' + claim['entity_id'])
    choices = current_policy_choices(tables, '2025-26')
    for p in programmes:
        if p.get('current_allocation_policy'):
            selected = next((v for v in choices.values() if v['program_id'] == p['program_id']), None)
            if not selected or selected['model'] != p['current_allocation_policy']['model']:
                errors.append('New England current/former model selection lost: ' + p['program_id'])
    return errors


def render_reports(root, tables):
    contents, report = reviewed_reports(root, tables, batch=SETTINGS)
    programmes, sources = inputs(root, base=BASE, states=STATES)
    cases = [dict(state=p['state'], school=p['school'], program_id=p['program_id'],
                  review_reason=reason, source_url=sources[p['reference']['source']]['url'], notes=p['notes'])
             for p in programmes for reason in p.get('review_reasons', [])]
    for p in programmes:
        if p['reference']['eligibility'] == 'public_funding_unconfirmed':
            cases.append(dict(state=p['state'], school=p['school'], program_id=p['program_id'],
                review_reason='Public funding or reference-year academic eligibility needs verification',
                source_url=sources[p['reference']['source']]['url'], notes=p['notes']))
    contents[REPORT + '_review_cases.csv'] = csv_text(cases, fields=['state','school','program_id','review_reason','source_url','notes'])
    selections = json.loads((root / BASE / 'extractions/roster_reconciliation.json').read_text())
    for state in sorted(STATES):
        screening = json.loads((root / BASE / (state.lower() + '_screening.json')).read_text())
        contents[BASE + '/' + state.lower() + '_screening.csv'] = csv_text(screening,
            fields=['school', 'district', 'source', 'period', 'locator', 'disposition', 'reason', 'notes'])
    source_rows = [dict(source_row=r['source_row'], source_paragraph=r['source_paragraph'],
        district_raw=r['raw']['district_raw'], school_paragraph_raw=r['raw']['text_raw'],
        programme_ids=' | '.join(r['program_ids']), school_ids=' | '.join(r['school_ids']),
        disposition=r['disposition']) for selection in selections for r in selection['rows']]
    contents[BASE + '/extractions/massachusetts_directory_reconciliation.csv'] = csv_text(source_rows)
    report['source_reconciliation_counts'] = {r['name']: len(r['rows']) for r in selections}
    report['states_with_programme_records'] = sorted({p['state'] for p in programmes})
    report['screened_only_states'] = sorted(STATES - {p['state'] for p in programmes})
    contents[REPORT + '.json'] = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    return contents, report
