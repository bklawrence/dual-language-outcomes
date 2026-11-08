"""Research-scope exclusions, separate from source history and operating status."""
import json
import re

CONFIG = 'config/study_scope.json'
ATTRIBUTE = 'research_scope_exclusion'
DATASET = 'RESEARCH_SCOPE_DECISIONS'
REPORT = 'data/reports/hand_coding/current/study_scope_exclusions.csv'
SPECIALIZED_NAME = re.compile(
    r'\b(?:schools?|academ(?:y|ies)|institutes?|cent(?:er|re)s?)\s+(?:for\s+)?(?:the\s+)?'
    r'(?:deaf|blind|hard[-\s]+of[-\s]+hearing|hearing[-\s]+impaired|visually[-\s]+impaired)\b'
    r'|\b(?:deaf|blind|hearing[-\s]+impaired|visually[-\s]+impaired)\s+(?:school|academy|institute)\b', re.I)


def excluded_school_ids(tables):
    # Only saved research decisions affect selections. Loading an older frozen
    # evidence snapshot must not apply a newer policy retroactively to that file.
    return {r['entity_id'] for r in tables['evidence_claims']
            if r['entity_type']=='school' and r['attribute']==ATTRIBUTE}


def source_history_tables(tables):
    """Render preserved source-vintage reports using their original scope."""
    return dict(tables,evidence_claims=[r for r in tables['evidence_claims'] if r['attribute']!=ATTRIBUTE])


def migrate(build):
    path=build.root/CONFIG
    if not path.exists():
        return
    policy=json.loads(build.track_input(CONFIG).read_text())
    decisions={r['school_id']:r for r in policy['schools']}
    schools={r['school_id']:r for r in build.rows('schools')}
    if set(decisions)-set(schools):
        raise ValueError('A reviewed scope-exclusion identity is missing from the source registry.')
    by_name={(r['state_code'],r['school_name'].casefold()):r for r in policy['schools']}
    dataset=build.dataset(DATASET,None,'inventory','Researcher-defined study scope',
        'repo:'+CONFIG,publisher='Project researcher',notes=policy['policy'])
    source=build.source_file(dataset,CONFIG)
    for school in schools.values():
        decision=decisions.get(school['school_id']) or by_name.get((school['state_code'],school['school_name'].casefold()))
        if not decision and not SPECIALIZED_NAME.search(school['school_name']):
            continue
        if decision:
            if decision['state_code']!=school['state_code']:
                raise ValueError('Scope-exclusion state does not match the reviewed school.')
            build.track_input(decision['evidence_snapshot'])
        value=dict(decision or {},school_id=school['school_id'],school_name=school['school_name'],state_code=school['state_code'],
            decision_date=policy['decision_date'],decision_authority=policy['decision_authority'],
            reason_code=policy['reason_code'],applies_to=policy['applies_to'],
            basis=decision['basis'] if decision else 'School name explicitly identifies a specialized deaf/blind education institution under the saved study-scope rule.')
        build.claim('school',school['school_id'],ATTRIBUTE,json.dumps(value,ensure_ascii=False,sort_keys=True),source,
            school['school_id'],status='documented',method='researcher_defined_study_scope',
            notes='Excluded from live research views and Fieldnotes. Source observations and identities retained for audit; not a program ending or a disability-based student filter.')
    build.notes.append('Specialized deaf/blind schools are excluded from the live research cohort by config/study_scope.json; canonical source history and frozen research releases remain archived. See '+REPORT+'.')


def report(tables):
    from .baseline import csv_text
    sites={}
    for row in tables['program_sites']:
        sites.setdefault(row['school_id'],[]).append(row['site_id'])
    rows=[]
    for claim in tables['evidence_claims']:
        if claim['entity_type']!='school' or claim['attribute']!=ATTRIBUTE:
            continue
        value=json.loads(claim['reported_value'])
        rows.append({k:value.get(k,'') for k in ['school_id','state_code','school_name','decision_date','reason_code','basis','evidence_url','evidence_snapshot']}
                    | dict(excluded_site_ids=' | '.join(sorted(sites.get(claim['entity_id'],[]))),
                           previous_inventory_role='program_school' if sites.get(claim['entity_id']) else 'historical_screening_lead',
                           decision_source_id=claim['source_id']))
    return csv_text(sorted(rows,key=lambda r:(r['state_code'],r['school_name'])),fields=[
        'school_id','state_code','school_name','decision_date','reason_code','basis','evidence_url',
        'evidence_snapshot','excluded_site_ids','previous_inventory_role','decision_source_id'])
