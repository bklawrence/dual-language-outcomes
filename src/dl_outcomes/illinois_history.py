"""User's 2021–22 district-website research and explicit model-history corrections."""
from collections import Counter, defaultdict
import csv
import hashlib
import json

from .io import digest, record_id
from .policy_selection import ATTRIBUTE, current_policy_choices
from .western_plains_review import csv_text

CONFIG = 'config/research_migrations/illinois_2021_22_user_2026_11_05.json'
BASE = 'data/registry/illinois_2021_22_user_2026_11_05'
DATASET = 'IL_USER_RESEARCH_2021_22'
YEAR = '2021-22'
HISTORICAL_MODEL = 'USER_HISTORICAL_2021_22_MODEL_LABEL'
BASE_KEYS = dict(schools='school_id', programs='program_id', program_sites='site_id',
    program_languages='language_record_id', program_configurations='configuration_id',
    allocation_schedules='schedule_id', program_status_history='status_id')


def row_hash(row):
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()


def inputs(root):
    config = json.loads((root / CONFIG).read_text())
    records = json.loads((root / BASE / 'records.json').read_text())
    schools = json.loads((root / BASE / 'new_schools.json').read_text())
    programmes = json.loads((root / BASE / 'new_programmes.json').read_text())
    decisions = json.loads((root / BASE / 'policy_decisions.json').read_text())
    return config, records, schools, programmes, decisions


def authorized_additions(root):
    """Earlier batch audits still reject additions not explicitly in this source."""
    if not (root / CONFIG).exists():
        return set(), set()
    config = json.loads((root / CONFIG).read_text())
    return set(config['new_school_ids']), set(config['new_programme_ids'])


def frozen_great_lakes_reports(root):
    config = json.loads((root / CONFIG).read_text())
    contents = {p: (root / p).read_text() for p in config['frozen_great_lakes_report_paths']}
    report = json.loads((root / 'data/reports/great_lakes_2026_11_05.json').read_text())
    return contents, report


def historical_schedule_id(row):
    return record_id('schedule', DATASET, row['row_id'])


def migrate(b):
    config, records, schools, programmes, decisions = inputs(b.root)
    for path in [CONFIG, BASE + '/records.json', BASE + '/new_schools.json',
                 BASE + '/new_programmes.json', BASE + '/policy_decisions.json', BASE + '/codebook.json',
                 config['raw'] + '/metadata.json', *config['preserved_reports'],
                 *config['preserved_great_lakes_inputs']]:
        b.track_input(path)
    dataset = b.dataset(DATASET, 'IL', 'inventory',
        'User district-website compilation: 2021–22, collected in 2022',
        'repo:' + config['raw'] + '/inventory.tsv', publisher='User-provided research',
        notes='Original district webpage URLs were not supplied. Uploaded compilation and clarification '
        'are archived; historical model labels, source codes and later corrections remain separate.')
    source = b.source_file(dataset, config['raw'] + '/inventory.tsv')
    clarification = b.source_file(dataset, config['raw'] + '/clarifications.json')
    assignments = b.source_file(dataset, BASE + '/records.json')
    decision_source = b.source_file(dataset, BASE + '/policy_decisions.json')
    b.tables['sources'][(source,)]['evidence_period_raw'] = YEAR
    b.tables['sources'][(source,)]['notes'] = ('User compilation of the then-current district website '
        'information collected in 2022; user explicitly assigns school year 2021–22. Original bytes '
        'archived; no original webpage URLs or publication dates fabricated.')
    b.tables['sources'][(clarification,)]['notes'] = ('User school-year and programme-history '
        'clarifications received November 5, 2026; effective school years are recorded separately.')
    existing_sites = {r['site_id']:r for r in b.rows('program_sites')}
    known_languages = defaultdict(set)
    for language in b.rows('program_languages'):
        if language['language_name']!='English':
            known_languages[language['site_id']].add(language['language_name'])
    new_ids = {p['program_id'] for p in programmes}
    for r in records:
        if r['program_id'] and r['program_id'] not in new_ids:
            site = existing_sites.get(r['site_id'])
            if (not site or site['program_id']!=r['program_id'] or site['school_id']!=r['school_id']
                    or not set(r['languages_as_reported']) <= known_languages[r['site_id']]):
                raise ValueError('Historical row changes an existing school/programme/language identity: '+r['row_id'])
    for school in schools:
        b.school(school['school_id'], 'IL', school['school'], source,
            namespace='IL_USER_RESEARCH_historical_school_key', native_id=school['school_id'],
            status='provisional',
            screening='historical_programme_candidate_current_operation_not_confirmed')
    for p in programmes:
        b.add('programs', program_id=p['program_id'], state_code='IL',
            program_name=p['school'] + ' / ' + p['language'] + ' (2021–22 research)',
            identity_status='provisional_evidence_group',
            screening_status='historical_user_research_current_status_not_established',
            notes='Target language as reported; English pairing and present operation are not inferred.')
        b.add('program_sites', site_id=p['site_id'], program_id=p['program_id'], school_id=p['school_id'],
            valid_to_year=p['closed_after_school_year'], link_status='provisional',
            source_id=clarification if p['closed_after_school_year'] else source)
    for r in records:
        locator = r['row_id']
        entity_type, entity = ('school', r['school_id']) if r['school_id'] else ('state', 'IL')
        b.claim(entity_type, entity, 'illinois_user_2021_22_source_row',
            json.dumps(r, ensure_ascii=False, sort_keys=True), source, locator, year=YEAR,
            period=YEAR, status='provisional', method='user_district_website_research',
            import_source=assignments,
            notes='All original fields, blanks, codes and source spelling retained. No 2025–26 confirmation implied.')
        if r['school_id']:
            b.identifier('school', r['school_id'], 'IL_USER_RESEARCH_2021_22_row',
                locator, source, year=YEAR, status=r['match_method'])
            b.claim('school', r['school_id'], 'historical_reported_district_name',
                r['raw']['District'] or None, source, locator + ':district', year=YEAR, period=YEAR,
                status='provisional', notes='Source reporting label, not a new official LEA crosswalk.')
            if r['sector_label']=='public' and r['raw']['District']:
                district = record_id('district', 'IL', r['district_name'])
                b.district(district, 'IL', r['district_name'], source,
                    namespace='IL_USER_RESEARCH_reported_district_name', native_id=r['raw']['District'],
                    year=YEAR, status='provisional_name_group')
                b.membership(r['school_id'], district, source, locator + ':district', year=YEAR)
        if not r['program_id']:
            continue
        pid, site, sid = r['program_id'], r['site_id'], r['school_id']
        b.add('program_configurations', configuration_id=record_id('configuration', DATASET, locator),
            site_id=site, school_year=YEAR, grade_scope=r['programme_grade_proxy'],
            population_model='unknown', delivery_structure=r['delivery_structure'],
            program_kind='historical_district_website_research_transcription',
            reported_model_label=r['model_label'], evidence_period_raw=YEAR,
            verification_status='provisional', source_id=source, source_locator=locator,
            notes='School level is a source-code proxy; exact grades were not supplied. No one-way/two-way '
                'classification inferred from strand, neighbourhood or boundary flags.')
        for language in r['languages_as_reported']:
            b.add('program_languages', language_record_id=record_id('language', DATASET, locator, language),
                site_id=site, language_name=language, language_code={'Spanish':'es','French':'fr','Japanese':'ja'}.get(language),
                language_role='reported_instruction_language', valid_from_year=YEAR, valid_to_year=YEAR,
                evidence_period_raw=YEAR, verification_status='provisional', source_id=source,
                source_locator=locator, notes='Single language in user district-website compilation; English not silently added.')
        if r['model_label'] in {'50/50', '80/20', '90/10'}:
            b.add('allocation_schedules', schedule_id=historical_schedule_id(r), school_id=sid,
                site_id=site, school_year=YEAR, grade_scope=r['programme_grade_proxy'],
                reported_model_label=r['model_label'], percentage_basis='historical_programme_model_label',
                schedule_status='reported_policy_requires_review', evidence_review_status=HISTORICAL_MODEL,
                grade_support_status='PUBLISHED_MODEL_ONLY', evidence_period_raw=YEAR,
                tested_cohort_exposure='not_established', source_id=source, source_locator=locator,
                notes='User-researched district model in 2021–22; no exact K timetable, observed exposure or '
                'named-language share plan is inferred. Source level and public/private codes retain qualifications.')
        if r['reported_start_calendar_year'] is not None:
            b.claim('program', pid, 'reported_programme_start_calendar_year',
                str(r['reported_start_calendar_year']), source, locator + ':start', year=YEAR, period=YEAR,
                status='provisional', notes='Reported calendar year only; not converted into a programme validity interval.')
    grouped = defaultdict(list)
    for r in records:
        if r['program_id']:
            grouped[r['program_id']].append(r)
    for pid, rs in grouped.items():
        r = rs[0]
        b.add('program_status_history', status_id=record_id('status', DATASET, pid, YEAR), site_id=r['site_id'],
            school_year=YEAR, operating_status='user_reported_programme_2021_22',
            eligibility_status='historical_research_not_current_eligibility_certification',
            instructional_scope='reported_historical_language_programme_with_scope_qualifications',
            public_funding_status='source_sector_' + r['sector_label'],
            confirmation_method='user_district_website_research_snapshot', evidence_period_raw=YEAR,
            source_id=source, source_locator=' | '.join(x['row_id'] for x in rs),
            notes='User compiled current district website information in 2022 and assigns this to 2021–22. '
                'This status does not confirm operation or public funding in 2025–26.')
    spanish = next(d for d in decisions if d['decision_id'] == 'IL22-YANKEE-SPANISH-2024')
    b.add('allocation_schedules', schedule_id=spanish['selected_schedule_id'], site_id=spanish['site_id'],
        school_id='IL-S018', school_year='2024-25', grade_scope='K entry model; later-grade allocation not supplied',
        reported_model_label='80/20', percentage_basis='user_confirmed_programme_entry_model',
        schedule_status='documented_plan', evidence_review_status='USER_CONFIRMED_ELEMENTARY_MODEL',
        grade_support_status='DISTRICT_ENTRY_GRADE_MODEL', evidence_period_raw='2024-25 model change confirmed by user',
        tested_cohort_exposure='not_established', source_id=clarification, source_locator=spanish['decision_id'],
        notes='Spanish programme changed to 80/20 in 2024–25. Conventional starting-model classification '
              'follows the user-authorized interpretation; later-grade progression was not supplied.')
    for language, share in [('Spanish',80),('English',20)]:
        b.add('instructional_allocations', allocation_id=record_id('allocation', spanish['selected_schedule_id'],language),
            schedule_id=spanish['selected_schedule_id'], language_name=language,
            language_code='es' if language=='Spanish' else 'en', instruction_share_pct=share,
            evidence_type='documented_plan', source_id=clarification, source_locator=spanish['decision_id'])
    for choice in decisions:
        b.claim('program', choice['program_id'], ATTRIBUTE, json.dumps(choice, sort_keys=True),
            clarification, choice['decision_id'], period='User clarification; effective dates in structured decision',
            status='documented', method='user_confirmed_programme_history',
            import_source=decision_source,
            notes='Selects the current policy for the stated programme without replacing historical source rows.')
    predecessors = [p for p in programmes if p['closed_after_school_year']]
    for p in predecessors:
        b.add('program_status_history', status_id=record_id('status', DATASET, p['program_id'], '2024-25'),
            site_id=p['site_id'], school_year='2024-25', operating_status='programme_relocated_to_Yankee_Ridge',
            eligibility_status='historical_host_programme_relocated', instructional_scope='historical_DL_host',
            public_funding_status='user_reported_public_district_programme',
            confirmation_method='user_confirmed_consolidation', evidence_period_raw='2024-25',
            source_id=clarification, source_locator=p['program_id'] + ':relocation',
            notes='DPW/Leal Spanish programmes consolidated at Yankee Ridge. Programme moved; the school itself is not labelled closed.')
    b.claim('program', spanish['program_id'], 'programme_consolidation_predecessor_sites',
        json.dumps(dict(effective_school_year='2024-25', predecessor_programmes=predecessors,
            successor_site_id=spanish['site_id'], successor_school_id='IL-S018'), sort_keys=True),
        clarification, 'URBANA-CONSOLIDATION-2024-25', year='2024-25', period='2024-25', status='documented',
        method='user_confirmed_programme_history', notes='Many-to-one consolidation; no assumed stable student cohort or one-to-one identity merger.')
    french = next(d for d in decisions if d['decision_id']=='IL22-YANKEE-FRENCH-STABLE')
    b.claim('program', french['program_id'], 'historical_allocation_stability', '50/50 throughout programme existence',
        clarification, french['decision_id'] + ':history', status='documented',
        notes='User statement; programme origin date not supplied. No invented annual observations before the known snapshots.')
    b.claim('program', 'IL-P008', 'allocation_change_date_interval',
        json.dumps(dict(earlier_model='50/50',earlier_observation='2021-22',later_model='90/10',
            later_plan='2025-26',effective_change_school_year=None),sort_keys=True), clarification,
        'IPA-CHANGE-INTERVAL', status='documented', notes='User confirms a change; its exact first school year remains unspecified.')
    b.notes.append('Illinois: 144 user-researched 2021–22 rows retained; later IPA/Urbana changes are separate '
        'user-confirmed policies. Historical-only schools do not become confirmed 2025–26 hosts; proficiency remains deferred.')


def audit_errors(root, tables, *, check_hashes=True):
    config, records, schools, programmes, decisions = inputs(root)
    errors = []
    if check_hashes:
        for group in ['preserved_reports', 'preserved_great_lakes_inputs', 'preserved_assessment_outputs']:
            for path, expected in config[group].items():
                if digest(root / path) != expected:
                    errors.append('Illinois history changed preserved file: ' + path)
        if digest(root / config['raw'] / 'inventory.tsv') != config['source_sha256']:
            errors.append('Original user research bytes changed')
    with (root / config['raw'] / 'inventory.tsv').open() as stream:
        raw = list(csv.DictReader(stream, delimiter='\t'))
    if (len(raw) != 144 or len(records) != 144 or any(r['raw'] != row for r, row in zip(records, raw))
            or Counter(r['model_label'] for r in records) != Counter(r['Model'] or None for r in raw)):
        errors.append('Illinois 144-row/cell/model conservation changed')
    for table, expected in config['preserved_row_hashes'].items():
        actual = {r[BASE_KEYS[table]]: row_hash(r) for r in tables[table]}
        if any(actual.get(key) != value for key, value in expected.items()):
            errors.append('Original Illinois row replaced: ' + table)
    actual_schools = {r['school_id'] for r in tables['schools'] if r['state_code']=='IL'}
    actual_programmes = {r['program_id'] for r in tables['programs'] if r['state_code']=='IL'}
    if actual_schools != set(config['baseline_school_ids']) | set(config['new_school_ids']):
        errors.append('Illinois history school identity set changed')
    if actual_programmes != set(config['baseline_programme_ids']) | set(config['new_programme_ids']):
        errors.append('Illinois history programme identity set changed')
    sources = {r['source_id']: r for r in tables['sources']}
    own = {key for key, r in sources.items() if r['dataset_id']==DATASET}
    original = next((r['source_id'] for r in tables['sources']
                     if r['snapshot_path']==config['raw']+'/inventory.tsv'), None)
    claims = {r['source_locator']: r for r in tables['evidence_claims']
              if r['attribute']=='illinois_user_2021_22_source_row'}
    if len(claims) != 144:
        errors.append('Illinois historical source-row claims missing or duplicated')
    configs = {r['source_locator']: r for r in tables['program_configurations'] if r['source_id']==original}
    allocations = {r['schedule_id']: r for r in tables['allocation_schedules'] if r['source_id']==original}
    expected_schedules = {historical_schedule_id(r) for r in records if r['program_id'] and r['model_label'] in {'50/50','80/20','90/10'}}
    if len(expected_schedules)!=86 or set(allocations)!=expected_schedules:
        errors.append('Historical numeric model set changed')
    for r in records:
        claim = claims.get(r['row_id'])
        if (not claim or claim['source_id']!=original or json.loads(claim['reported_value'])!=r
                or claim['valid_from_year']!=YEAR or claim['valid_to_year']!=YEAR):
            errors.append('Historical row/date/identity claim changed: ' + r['row_id'])
        c = configs.get(r['row_id'])
        if r['program_id']:
            expected = dict(site_id=r['site_id'],school_year=YEAR,grade_scope=r['programme_grade_proxy'],
                population_model='unknown',delivery_structure=r['delivery_structure'],reported_model_label=r['model_label'])
            if not c or any(c[k]!=v for k,v in expected.items()):
                errors.append('Historical configuration/source code changed: '+r['row_id'])
        elif c:
            errors.append('Unresolved language/enrichment/preschool row became a programme: '+r['row_id'])
        if r['model_label'] in {'50/50','80/20','90/10'} and r['program_id']:
            a = allocations.get(historical_schedule_id(r))
            if (not a or a['school_year']!=YEAR or a['reported_model_label']!=r['model_label']
                    or a['grade_scope']!=r['programme_grade_proxy'] or a['schedule_status']!='reported_policy_requires_review'
                    or a['evidence_review_status']!=HISTORICAL_MODEL):
                errors.append('Historical model promoted, redated or lost: '+r['row_id'])
    if any(r['schedule_id'] in expected_schedules for r in tables['instructional_allocations']):
        errors.append('Historical model labels acquired invented named-language shares')
    if any(r['language_name'] in {'English','Arabic','Mandarin Chinese','Korean'}
           for r in tables['program_languages'] if r['source_id']==original):
        errors.append('Composite cells or target-only rows acquired unverified language roles')
    current = current_policy_choices(tables, '2025-26')
    for d in decisions:
        if current.get(d['site_id']) != d:
            errors.append('User-confirmed current policy selection changed: '+d['decision_id'])
    spanish = next(d for d in decisions if d['decision_id']=='IL22-YANKEE-SPANISH-2024')
    schedules = {r['schedule_id']: r for r in tables['allocation_schedules']}
    a = schedules.get(spanish['selected_schedule_id'])
    if not a or a['school_year']!='2024-25' or a['reported_model_label']!='80/20':
        errors.append('Urbana Spanish change lost its 2024–25 effective year')
    shares = {r['language_name']:r['instruction_share_pct'] for r in tables['instructional_allocations']
              if r['schedule_id']==spanish['selected_schedule_id']}
    if shares!={'Spanish':80,'English':20}:
        errors.append('Urbana Spanish policy shares changed or crossed language strands')
    source_statuses = [r for r in tables['program_status_history'] if r['source_id'] in own]
    if any(r['school_year']=='2025-26' or r['operating_status']=='confirmed_2025_26' for r in source_statuses):
        errors.append('Historical rows silently confirmed 2025–26 operation')
    sites = {r['site_id']:r for r in tables['program_sites']}
    confirmed = {sites[r['site_id']]['school_id'] for r in tables['program_status_history']
                 if r['school_year']=='2025-26' and r['operating_status']=='confirmed_2025_26'
                 and r['eligibility_status'].startswith('documented_') and sites[r['site_id']]['school_id'] in actual_schools}
    if confirmed != set(config['reference_confirmed_school_ids']):
        errors.append('Current Illinois confirmed-host set changed during historical import')
    for p in programmes:
        site = sites.get(p['site_id'])
        if not site or site['valid_to_year']!=p['closed_after_school_year']:
            errors.append('Historical host consolidation/end boundary changed: '+p['school'])
    return errors


def render_reports(root, tables, inventory):
    from .elementary_audit import report_rows
    config, records, new_schools, programmes, decisions = inputs(root)
    details, coverage = report_rows(tables)
    current = {r['school_id']:r for r in details if r['state_code']=='IL' and r['audit_scope']=='reference_working_set'}
    choices = {r['program_id']:r for r in decisions}
    gl = json.loads((root / 'data/registry/great_lakes_2026_11_05/il_programmes.json').read_text())
    sources = {r['key']:r for r in json.loads((root/'data/registry/great_lakes_2026_11_05/sources.json').read_text())}
    previous = {p['program_id']:p for p in gl}
    reconciliation, source_rows, followup, models = [], [], [], []
    for r in records:
        p = previous.get(r['program_id'])
        current_models = [a['label'] for a in p['allocations']] if p else []
        if r['program_id'] in choices:
            current_models = [choices[r['program_id']]['model']]
        source_rows.append(dict(source_row_id=r['row_id'],school_year=YEAR,**r['raw']))
        row = dict(source_row_id=r['row_id'],source_school_year=YEAR,name_as_reported=r['raw']['Name'],
            district_as_reported=r['raw']['District'],location_as_reported=r['raw']['Location'],
            reviewed_district_name=r['district_name'],
            school_id=r['school_id'],program_id=r['program_id'],site_id=r['site_id'],
            canonical_school_name=r['school_name'],match_method=r['match_method'],disposition=r['disposition'],
            languages_as_reported=' | '.join(r['languages_as_reported']),reported_level=r['level_label'],
            reported_sector=r['sector_label'],reported_delivery=r['delivery_structure'],
            historical_model=r['model_label'],reported_start_calendar_year=r['reported_start_calendar_year'],
            confirmed_2025_26_host=int(r['school_id'] in current),
            later_source_models=' | '.join(sorted(set(current_models))),
            later_policy_selection_basis=choices.get(r['program_id'],{}).get('reason',''),
            later_programme_source_url=sources[p['reference']['source']]['url'] if p else '',
            review_notes=' | '.join(r['review_notes']))
        if p and p['reference']['status']!='confirmed_2025_26':
            row['review_notes'] += ' | Historical evidence supports renewed current-host review; no reference confirmation added.'
        reconciliation.append(row)
        if r['model_label'] in {'50/50','80/20','90/10'}:
            models.append(dict(row,schedule_id=historical_schedule_id(r),grade_scope=r['programme_grade_proxy'],
                named_language_shares='not_inferred',source_basis='User district-website compilation; original links not supplied'))
        if row['review_notes'] or not r['program_id']:
            followup.append(row)
    by_school = defaultdict(list)
    for r in inventory:
        if r['state_code']=='IL':by_school[r['school_id']].append(r)
    school_rows=[]
    for sid, ps in sorted(by_school.items()):
        rs=[r for r in records if r['school_id']==sid]
        c=current.get(sid)
        school_rows.append(dict(school_id=sid,school=ps[0]['school_name'],programme_records=len(ps),
            historical_reported_districts=' | '.join(sorted({r['raw']['District'] for r in rs if r['raw']['District']})),
            program_ids=' | '.join(sorted(p['program_id'] for p in ps)),
            source_2021_22_row_ids=' | '.join(r['row_id'] for r in rs),
            source_2021_22_models=' | '.join(sorted({r['model_label'] for r in rs if r['model_label']})),
            confirmed_qualifying_2025_26=int(c is not None),
            reference_elementary_denominator=c['elementary_denominator'] if c else 0,
            reference_numerical_model_available=c['has_numerical_allocation_model'] if c else 0,
            reference_model_labels=c['numerical_model_labels'] if c else '',
            interpretation='Historical-only hosts are retained separately from confirmed current hosts; source years and language roles require filtering.'))
    prefix=config['report_prefix']
    contents={BASE+'/inventory_2021_22.csv':csv_text(source_rows),
        BASE+'/identity_reconciliation.csv':csv_text(reconciliation),BASE+'/historical_models.csv':csv_text(models),
        BASE+'/il_schools.csv':csv_text(school_rows),BASE+'/il_programmes.csv':csv_text([
            dict(r,current_policy_selected_model=choices.get(r['program_id'],{}).get('model',''),
                current_policy_effective_from=choices.get(r['program_id'],{}).get('effective_from'),
                current_policy_selection_reason=choices.get(r['program_id'],{}).get('reason',''))
            for r in inventory if r['state_code']=='IL']),
        prefix+'_followup.csv':csv_text(followup),prefix+'_policy_decisions.csv':csv_text(decisions)}
    lineage=[]
    successor=next(d for d in decisions if d['decision_id']=='IL22-YANKEE-SPANISH-2024')
    for p in programmes:
        if p['closed_after_school_year']:
            lineage.append(dict(predecessor_school=p['school'],predecessor_program_id=p['program_id'],
                predecessor_site_id=p['site_id'],last_host_school_year='2023-24',
                consolidation_school_year='2024-25',successor_school='Yankee Ridge Multilingual School',
                successor_program_id=successor['program_id'],successor_site_id=successor['site_id'],
                spanish_entry_model_from_2024_25='80/20',french_model='50/50',
                cohort_continuity='not_established_by_programme_consolidation'))
    contents[prefix+'_urbana_lineage.csv']=csv_text(lineage)
    reference=next(r for r in coverage if r['state_code']=='IL' and r['audit_scope']=='reference_working_set')
    report=dict(source_school_year=YEAR,collection_calendar_year=2022,source_rows=len(records),
        numerical_model_rows=len(models),matched_existing_school_rows=sum(r['school_id'] in config['baseline_school_ids'] for r in records),
        new_historical_school_units=len(new_schools),new_historical_programme_groups=len(programmes),
        confirmed_2025_26_school_units=len(current),reference_elementary_coverage=reference,
        new_current_operation_confirmations=0,proficiency_collection='deferred',
        original_webpage_urls='not_supplied; user compilation and clarifications archived',
        limitations=['Earlier and later records are source-specific observations, not assumed stable cohorts.',
            'Additional languages in composite cells remain school-level research claims, not verified immersion strands.',
            'Programme model labels do not supply exact K schedules or observed named-language shares.',
            'Current numerical information availability includes dated historical research at already-confirmed hosts.',
            'Historical-only hosts require current-operation checks; preschool/enrichment/blank-language rows remain screening.'])
    contents[prefix+'.json']=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    return contents, report
