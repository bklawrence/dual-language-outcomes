"""Reviewed PA/MD/DE/NJ/NY/CT sources, including screened-only states."""
import hashlib
import json

from ..io import record_id
from .western_plains import migrate_state

STATES = {'MD', 'NY', 'CT', 'NJ', 'DE', 'PA'}
BASE = 'data/registry/mid_atlantic_ct_2026_11_05'
AUDIT = 'config/research_migrations/mid_atlantic_ct_2026_11_05.json'
SUFFIX = '_MID_ATLANTIC_CT_STRUCTURAL'


def school_key(state, district, school):
    return f'M6-{state}-S-' + hashlib.sha256('|'.join([state, district, school]).encode()).hexdigest()[:12]


def membership(b, state, school, district, source, locator, *, year=None):
    if district.startswith(('Public charter operator:', 'Private operator:', 'Tribal operator:', 'State-operated school:')):
        b.claim('school', school, 'operator_or_source_reporting_group_not_verified_LEA', district,
                source, locator + ':reporting_group', year=year, status='metadata_only',
                notes='Cited operator, not a verified LEA/authorizer crosswalk.')
        return
    did = record_id('district', state, district)
    b.district(did, state, district, source, namespace='M6_research_district_name', native_id=district,
               status='provisional_name_group')
    b.membership(school, did, source, locator, year=year)


def migrate_reviewed_state(build, state):
    audit = json.loads(build.track_input(AUDIT).read_text())
    build.track_input(BASE + '/source_redactions.json')
    for field in ['preserved_reports', 'preserved_previous_registry']:
        for path in audit[field]:
            build.track_input(path)
    migrate_state(build, state, inventory=dict(states=STATES, base=BASE,
        dataset_suffix=SUFFIX, namespace='M6', school_key=school_key, membership=membership,
        screening_attribute='mid_atlantic_ct_screening_observation',
        batch_description='six-state PA/MD/DE/NJ/NY/CT structural review'))
    # Retain every reviewed public snapshot, including directory/context documents used for screening.
    index = {s['key']:s for s in json.loads((build.root / BASE / 'sources.json').read_text())}
    extraction_paths = set(json.loads((build.root / BASE / 'extractions/index.json').read_text())[state])
    for key, doc in index.items():
        if BASE + '/extractions/' + key + '.txt' in extraction_paths:
            build.source_file(state + SUFFIX, doc['path'], metadata=doc['metadata_path'])
    decisions = json.loads((build.root / BASE / 'grade_context_decisions.json').read_text())
    for row in decisions:
        if row['state'] != state:
            continue
        doc = index[row['source_key']]
        source = build.source_file(state + SUFFIX, doc['path'], metadata=doc['metadata_path'])
        value = dict(ncessch=row['ncessch'], lowest_grade_offered=row['lowest_grade_offered'],
            highest_grade_offered=row['highest_grade_offered'], snapshot_path=doc['path'],
            match_method=row['match_method'], source_school_name=row['source_school_name'],
            source_lea_name=row['source_lea_name'])
        build.claim('school',row['school_id'],'elementary_audit_school_grade_context',
            json.dumps(value,sort_keys=True),source,'ncessch='+row['ncessch'],year='2024-25',
            period=row['evidence_period_raw'],status='documented',notes=row['notes'])
    # A dated district reconfiguration supersedes older CCD grade metadata.
    updates = json.loads(build.track_input(BASE + '/school_grade_updates.json').read_text())
    for row in updates:
        if row['state'] != state:
            continue
        doc = index[row['source_key']]
        source = build.source_file(state + SUFFIX, doc['path'], metadata=doc['metadata_path'])
        value = {k: row[k] for k in ['ncessch', 'lowest_grade_offered',
            'highest_grade_offered', 'match_method']}
        value['snapshot_path'] = doc['path']
        build.claim('school', row['school_id'], 'elementary_audit_school_grade_context',
            json.dumps(value, sort_keys=True), source, row['school'] + ':grade_reconfiguration',
            year=row['year'], period=row['period'], status='documented', notes=row['notes'])
    if state == 'NY':
        doc = index['m6_nyc_csv25']
        source = build.source_file(state + SUFFIX, doc['path'], metadata=doc['metadata_path'])
        for p in json.loads((build.root / BASE / 'ny_programmes.json').read_text()):
            if p.get('nyc_dbn'):
                build.identifier('school', p['school_id'], 'NYC_DBN', p['nyc_dbn'], source,
                    year='2025-26', status='official_source_school_identifier_not_NCES_programme_crosswalk')
