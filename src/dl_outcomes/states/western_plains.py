"""Import the reviewed UT/CO/NM/AZ/NE/KS structural batch without annualizing it."""
import hashlib
import json

from ..io import record_id
from .five_state import LANGUAGE_CODES, exact_year

STATES = {'UT', 'CO', 'NM', 'AZ', 'NE', 'KS'}
BASE = 'data/registry/western_plains_2026_11_04'
CODES = {**LANGUAGE_CODES, 'Portuguese': 'pt', 'Navajo': 'nv', 'ASL': 'ase',
         'American Sign Language': 'ase', 'Hebrew': 'he', 'Tewa': 'tew',
         'Hawaiian': 'haw', "Yup'ik": 'esu', 'Tlingit': 'tli', 'Iñupiaq': 'ik',
         'Lakota': 'lkt', 'Dakota': 'dak', 'Ojibwe': 'oj',
         'Cherokee': 'chr', 'Osage': 'osa', 'Yuchi': 'yuc'}
# Unspecified Keres/Tiwa varieties remain uncoded; "ker" identifies Kera.


def school_key(state, district, school):
    return f'WP-{state}-S-' + hashlib.sha256('|'.join([state, district, school]).encode()).hexdigest()[:12]


def membership(b, state, school, district, source, locator, *, year=None):
    # An appendix's grouping header or private operator is not an invented LEA.
    if (district == 'State Charter Schools' or 'Private operator' in district
            or district == 'Omaha Catholic School Consortium'
            or district == 'Global Village Academy North public charter'):
        b.claim('school', school, 'operator_or_source_reporting_group_not_verified_LEA', district,
                source, locator + ':reporting_group', year=year, status='metadata_only',
                notes='Actual district/LEA identity is unresolved; no district membership manufactured.')
        return
    did = record_id('district', state, district)
    b.district(did, state, district, source, namespace='WP_research_district_name', native_id=district,
               status='provisional_name_group')
    b.membership(school, did, source, locator, year=year)


def migrate_state(b, state, *, inventory=None):
    """Load the common reviewed-source format; batch identities stay separate."""
    options = inventory or {}
    states = options.get('states', STATES)
    base = options.get('base', BASE)
    dataset_suffix = options.get('dataset_suffix', '_WESTERN_PLAINS_STRUCTURAL')
    namespace = options.get('namespace', 'WP')
    school_identity = options.get('school_key', school_key)
    add_membership = options.get('membership', membership)
    if state not in states:
        raise ValueError('Unexpected reviewed inventory state: ' + state)
    config = json.loads((b.root / f'config/states/{state.lower()}.json').read_text())
    dataset = b.dataset(state + dataset_suffix, state, 'inventory',
        config['state_name'] + ' structural research: 2025–26 reference with separate source vintages',
        'repo:' + base, notes='Partial public-source inventory. Directory entries, plans, continuations, '
        'conflicts and operation/eligibility reviews are separate; no new proficiency collection.')
    paths = config['structural_inputs']
    files = {key: b.source_file(dataset, path) for key, path in paths.items()}
    if 'source_extractions' in paths:
        extraction_index = json.loads((b.root / paths['source_extractions']).read_text())
        for path in extraction_index[state]:
            b.track_input(path)
    programmes = json.loads((b.root / paths['programmes']).read_text())
    leads = json.loads((b.root / paths['screening']).read_text())
    reviews = {r['review_id']: r for r in json.loads((b.root / paths['reviews']).read_text())}
    index = {s['key']: s for s in json.loads((b.root / paths['sources']).read_text())}
    needed = {x['source'] for p in programmes for field in ['observations', 'allocations', 'events'] for x in p[field]}
    needed |= {p['reference']['source'] for p in programmes if p['reference']['source']}
    needed |= {r['source'] for r in leads}
    needed |= {key for r in leads for key in r.get('additional_sources', [])}
    needed |= {key for r in reviews.values() if r['state'] == state for key in r['source_keys']}
    sources = {}
    for key in sorted(needed):
        doc = index[key]
        source = b.source_file(dataset, doc['path'], metadata=doc['metadata_path'])
        meta = json.loads((b.root / doc['metadata_path']).read_text())
        b.tables['sources'][(source,)]['notes'] += ' ' + doc['title'] + '. Capture: ' + meta['capture_method'] + '; archive: ' + doc['archive_kind'] + '.'
        if 'excerpt' in doc['archive_kind']:
            b.tables['sources'][(source,)]['notes'] += ' Hash is for the exact saved public school-array excerpt, not the full application bundle. Full response hash is retained in metadata.'
        sources[key] = source
    for p in programmes:
        pid, sid = p['program_id'], p['school_id']
        if sid != school_identity(state, p['district'], p['school']):
            raise ValueError('Reviewed research school identity changed: ' + pid)
        reuse = options.get('reuse_existing_entities', False)
        if not reuse or (sid,) not in b.tables['schools']:
            b.school(sid, state, p['school'], files['programmes'], namespace=namespace + '_reviewed_research_school_key',
                native_id=sid, status='provisional',
                screening='reviewed_programme_host_including_candidates_plans_and_continuations')
        else:
            b.identifier('school', sid, namespace + '_reviewed_research_school_key', sid,
                         files['programmes'])
            b.claim('school', sid, 'reviewed_source_school_name', p['school'], files['programmes'],
                    pid + ':school_name', status='documented',
                    notes='Reviewed name match reuses the existing identity; original registry fields and source claims remain.')
        add_membership(b, state, sid, p['district'], files['programmes'], pid)
        if not reuse or (pid,) not in b.tables['programs']:
            b.add('programs', program_id=pid, state_code=state, program_name=p['school'] + ' / ' + p['track'],
                identity_status='provisional_evidence_group', screening_status=p['reference']['eligibility'],
                notes='Reviewed source/track evidence key, not an official enduring programme ID. ' + p['notes'])
        b.identifier('program', pid, namespace + '_reviewed_research_programme_key', pid, files['programmes'],
                     status='reviewed_evidence_key_not_official_programme_identifier')
        site = p.get('site_id') if reuse else None
        site = site or record_id('site', pid, sid)
        if reuse and (site,) in b.tables['program_sites']:
            existing = b.tables['program_sites'][(site,)]
            if existing['program_id'] != pid or existing['school_id'] != sid:
                raise ValueError('Reviewed existing programme/site match changed: ' + pid)
        else:
            if p.get('site_id'):
                raise ValueError('An existing site override must already exist: ' + site)
            b.add('program_sites', site_id=site, program_id=pid, school_id=sid, link_status='provisional', source_id=files['programmes'])
        ref = p['reference']
        b.add('program_status_history', status_id=record_id('status', site, files['programmes'], ref['year']),
            site_id=site, school_year=ref['year'], operating_status=ref['status'], eligibility_status=ref['eligibility'],
            instructional_scope=ref['scope'], public_funding_status=ref['funding'], confirmation_method=ref['method'],
            evidence_period_raw=ref['period'], source_id=files['programmes'], source_locator=pid,
            notes=ref['notes'] + ' Public evidence key: ' + str(ref['source']) + '; locator: ' + ref['locator'])
        b.claim('program', pid, 'reviewed_reference_year_assessment', json.dumps(ref, ensure_ascii=False, sort_keys=True),
            files['programmes'], pid + ':reference', year=ref['year'], period='2025-26 research assessment; evidence periods remain separate', status='metadata_only')
        if p.get('continuity_review'):
            review = reviews[p['continuity_review']]
            if pid not in review['program_ids']:
                raise ValueError('Continuity scope lost programme membership: ' + pid)
            b.claim('program', pid, 'continuity_review', json.dumps(review, ensure_ascii=False, sort_keys=True),
                files['reviews'], pid + ':' + review['review_id'], year=ref['year'], period=ref['year'],
                status='continuity_review', method='continuity_review', import_source=files['programmes'],
                notes='User-authorized continuity assessment, not government certification or a newly observed annual configuration.')
        for i, event in enumerate(p['events']):
            source = sources[event['source']]
            b.add('program_status_history', status_id=record_id('status', site, source, event['year']),
                site_id=site, school_year=event['year'], operating_status=event['status'], eligibility_status=ref['eligibility'],
                instructional_scope=ref['scope'], public_funding_status=ref['funding'],
                confirmation_method='source_listing_or_change_event', evidence_period_raw=event['year'] or event['notes'],
                source_id=source, source_locator=pid + ':event:' + str(i), notes=event['notes'])
        for i, observation in enumerate(p['observations']):
            source = sources[observation['source']]
            locator = pid + ':observation:' + str(i) + '; ' + observation['locator']
            year = exact_year(observation['period'])
            b.add('program_configurations', configuration_id=record_id('configuration', site, source, locator),
                site_id=site, school_year=year, grade_scope=observation['grade'], population_model=observation['population'],
                delivery_structure=observation['delivery'], program_kind='source_specific_structural_observation',
                reported_model_label=observation['label'], evidence_period_raw=observation['period'],
                verification_status=observation['verification'], source_id=source, source_locator=locator,
                notes=observation['notes'])
            for language in observation['languages']:
                b.add('program_languages', language_record_id=record_id('language', site, source, locator, language),
                    site_id=site, language_name=language, language_code=CODES.get(language),
                    language_role=observation['language_role'], valid_from_year=year, valid_to_year=year,
                    evidence_period_raw=observation['period'], verification_status=observation['verification'],
                    source_id=source, source_locator=locator, notes=observation['notes'])
            b.claim('program', pid, 'source_structural_observation', json.dumps(observation, ensure_ascii=False, sort_keys=True),
                source, locator, year=year, period=observation['period'], status=observation['verification'],
                import_source=files['programmes'], notes='Raw composite cells, language/model caveats and differing grade scopes are retained; not every listed language is an immersion track.')
        for i, allocation in enumerate(p['allocations']):
            source = sources[allocation['source']]
            locator = pid + ':allocation:' + str(i) + '; ' + allocation['locator']
            schedule = record_id('schedule', site, source, locator)
            shares = allocation['shares']
            b.add('allocation_schedules', schedule_id=schedule, school_id=sid, site_id=site,
                school_year=exact_year(allocation['period']), grade_scope=allocation['grade'],
                reported_model_label=allocation['label'], percentage_basis=allocation['basis'],
                schedule_status='documented_plan' if shares else 'reported_policy_requires_review',
                evidence_review_status=allocation.get('review_status', 'NAMED_LANGUAGE_POLICY_NOT_OBSERVED_EXPOSURE' if shares else 'SOURCE_DESCRIPTION_RETAINED_WITHOUT_NUMERIC_PLAN'),
                grade_support_status=allocation['grade_support'], evidence_period_raw=allocation['period'],
                tested_cohort_exposure='not_established', source_id=source, source_locator=locator, notes=allocation['notes'])
            b.claim('schedule', schedule, 'allocation_source_selection', json.dumps(allocation, ensure_ascii=False, sort_keys=True),
                source, locator, year=exact_year(allocation['period']), period=allocation['period'],
                status='documented' if shares else 'provisional', import_source=files['programmes'], notes=allocation['notes'])
            for language, share in (shares or {}).items():
                b.add('instructional_allocations', allocation_id=record_id('allocation', schedule, language),
                    schedule_id=schedule, language_name=language, language_code=CODES.get(language), instruction_share_pct=share,
                    evidence_type='documented_plan', source_id=source, source_locator=locator)
    for i, lead in enumerate(leads):
        source = sources[lead['source']]
        locator = state + ':screening:' + str(i) + '; ' + lead['locator']
        entity_type, entity = 'state', state
        # Government report school rows have reviewed source names; university /
        # third-party aliases stay observations until an identity is reviewed.
        if state == 'NM' and lead['source'] == 'wp_nm_eric_pdf':
            entity_type = 'school'
            entity = school_key(state, lead['district'], lead['school'])
            b.school(entity, state, lead['school'], source, namespace='WP_reviewed_research_school_key', native_id=entity,
                status='provisional', screening='state_report_school_including_non_DL_bilingual_models')
            membership(b, state, entity, lead['district'], source, locator, year='2024-25')
        b.claim(entity_type, entity, options.get('screening_attribute', 'western_plains_screening_observation'), json.dumps(lead, ensure_ascii=False, sort_keys=True),
            source, locator, year=exact_year(lead['period']), period=lead['period'], status='metadata_only',
            import_source=files['screening'], notes='Screening observation only. This row does not create a DL programme, assign a language pair or establish reference-year operation.')
    b.notes.append(state + ': ' + options.get('batch_description', 'six-state structural first pass') + '; 2025–26 reference assessment remains separate from actual source periods. '
        'Statewide completeness and historically stable cohorts are not established; no new proficiency/assessment/context/EL/SEDA observations.')
