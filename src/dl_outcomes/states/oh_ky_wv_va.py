"""Reviewed OH/KY/WV/VA sources, including screened-only states."""
import hashlib
import json

from ..io import record_id
from .western_plains import migrate_state

STATES = {'OH', 'KY', 'WV', 'VA'}
BASE = 'data/registry/oh_ky_wv_va_2026_11_05'
AUDIT = 'config/research_migrations/oh_ky_wv_va_2026_11_05.json'
SUFFIX = '_OH_KY_WV_VA_STRUCTURAL'


def school_key(state, district, school):
    return f'E4-{state}-S-' + hashlib.sha256('|'.join([state, district, school]).encode()).hexdigest()[:12]


def membership(b, state, school, district, source, locator, *, year=None):
    if district.startswith(('Public charter operator:', 'Private operator:', 'Tribal operator:', 'State-operated school:')):
        b.claim('school', school, 'operator_or_source_reporting_group_not_verified_LEA', district,
                source, locator + ':reporting_group', year=year, status='metadata_only',
                notes='Cited operator, not a verified LEA/authorizer crosswalk.')
        return
    did = record_id('district', state, district)
    b.district(did, state, district, source, namespace='E4_research_district_name', native_id=district,
               status='provisional_name_group')
    b.membership(school, did, source, locator, year=year)


def migrate_reviewed_state(build, state):
    audit = json.loads(build.track_input(AUDIT).read_text())
    build.track_input(BASE + '/source_redactions.json')
    for field in ['preserved_reports', 'preserved_previous_registry']:
        for path in audit[field]:
            build.track_input(path)
    migrate_state(build, state, inventory=dict(states=STATES, base=BASE,
        dataset_suffix=SUFFIX, namespace='E4', school_key=school_key, membership=membership,
        screening_attribute='oh_ky_wv_va_screening_observation',
        batch_description='four-state OH/KY/WV/VA structural review'))
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
