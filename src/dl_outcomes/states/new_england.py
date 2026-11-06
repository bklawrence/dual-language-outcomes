"""Reviewed ME/MA/NH/RI/VT structural evidence with separate source vintages."""
import hashlib
import json

from ..io import record_id
from .western_plains import migrate_state

STATES = {'ME', 'MA', 'NH', 'RI', 'VT'}
BASE = 'data/registry/new_england_2026_11_06'
AUDIT = 'config/research_migrations/new_england_2026_11_06.json'
SUFFIX = '_NEW_ENGLAND_STRUCTURAL'


def school_key(state, district, school):
    return f'NE5-{state}-S-' + hashlib.sha256('|'.join([state, district, school]).encode()).hexdigest()[:12]


def membership(b, state, school, district, source, locator, *, year=None):
    if district.startswith(('Public charter operator:', 'Private operator:', 'Tribal operator:', 'State-operated school:')):
        b.claim('school', school, 'operator_or_source_reporting_group_not_verified_LEA', district,
                source, locator + ':reporting_group', year=year, status='metadata_only',
                notes='Cited operator or reporting group; not an inferred LEA/authorizer crosswalk.')
        return
    did = record_id('district', state, district)
    b.district(did, state, district, source, namespace='NE5_research_district_name', native_id=district,
               status='provisional_name_group')
    b.membership(school, did, source, locator, year=year)


def migrate_reviewed_state(build, state):
    audit = json.loads(build.track_input(AUDIT).read_text())
    if state == min(STATES):
        for field in ['preserved_reports', 'preserved_previous_registry', 'preserved_previous_archives']:
            for path in audit[field]:
                build.track_input(path)
    migrate_state(build, state, inventory=dict(states=STATES, base=BASE,
        dataset_suffix=SUFFIX, namespace='NE5', school_key=school_key, membership=membership,
        screening_attribute='new_england_screening_observation',
        batch_description='final five-state New England structural review'))
    index = {s['key']: s for s in json.loads((build.root / BASE / 'sources.json').read_text())}
    extraction_paths = set(json.loads((build.root / BASE / 'extractions/index.json').read_text())[state])
    for key, doc in index.items():
        if BASE + '/extractions/' + key + '.txt' in extraction_paths:
            build.source_file(state + SUFFIX, doc['path'], metadata=doc['metadata_path'])
    for row in json.loads(build.track_input(BASE + '/grade_context_decisions.json').read_text()):
        if row['state'] != state:
            continue
        doc = index[row['source_key']]
        source = build.source_file(state + SUFFIX, doc['path'], metadata=doc['metadata_path'])
        value = {k: row[k] for k in ['ncessch', 'lowest_grade_offered', 'highest_grade_offered',
                                    'match_method', 'source_school_name', 'source_lea_name']}
        value['snapshot_path'] = doc['path']
        build.claim('school', row['school_id'], 'elementary_audit_school_grade_context',
            json.dumps(value, sort_keys=True), source, 'ncessch=' + row['ncessch'],
            year=row.get('year', '2024-25'), period=row['evidence_period_raw'], status='documented', notes=row['notes'])
    for row in json.loads(build.track_input(BASE + '/official_school_identifiers.json').read_text()):
        if row['state'] != state:
            continue
        doc = index[row['source_key']]
        source = build.source_file(state + SUFFIX, doc['path'], metadata=doc['metadata_path'])
        build.identifier('school', row['school_id'], row['namespace'], row['native_id'], source,
            year=row.get('year'), status='official_campus_identifier_not_a_programme_or_NCES_crosswalk')
    for p in json.loads((build.root / BASE / (state.lower() + '_programmes.json')).read_text()):
        selection = p.get('current_allocation_policy')
        if not selection:
            continue
        allocation = p['allocations'][selection['allocation_index']]
        doc = index[allocation['source']]
        source = build.source_file(state + SUFFIX, doc['path'], metadata=doc['metadata_path'])
        site = record_id('site', p['program_id'], p['school_id'])
        locator = p['program_id'] + ':allocation:' + str(selection['allocation_index']) + '; ' + allocation['locator']
        choice = dict(program_id=p['program_id'], school_id=p['school_id'], site_id=site,
            selected_schedule_id=record_id('schedule', site, source, locator), model=selection['model'],
            effective_from=selection['effective_from'], reason=selection['reason'])
        build.claim('program', p['program_id'], 'current_allocation_policy_selection',
            json.dumps(choice, ensure_ascii=False, sort_keys=True), source,
            p['program_id'] + ':current_policy_selection', status='documented',
            notes='Explicit current/former source distinction; no unsupported historical effective year.')
