"""Integrate reviewed structural research without treating its vintages as annual surveys."""
from collections import defaultdict
import json
import re

from ..io import digest, read_csv, record_id

LANGUAGE_CODES = {
    "English": "en", "Spanish": "es", "Mandarin Chinese": "cmn", "Chinese": "zh",
    "Cantonese": "yue", "Korean": "ko", "Japanese": "ja", "Vietnamese": "vi",
    "Hmong": "hmn", "French": "fr", "German": "de", "Italian": "it", "Arabic": "ar",
    "Armenian": "hy", "Eastern Armenian": "hye", "Western Armenian": "hyw",
    "Blackfeet": "bla", "Crow (Apsáalooke)": "cro", "Shoshoni": "shh",
    "Arapaho (Hinono’eitiit)": "arp", "Russian": "ru",
}


def exact_year(value):
    """Only an actual single academic year can become a validity year."""
    value = str(value or '').strip()
    if re.fullmatch(r'\d{4}-\d{2}', value) and int(value[-2:]) == (int(value[:4])+1) % 100:
        return value
    return None


def instruction_languages(value):
    if not value or value.casefold().startswith('unknown'):
        return []
    suffix = ' (English instructional role unconfirmed)'
    return list(dict.fromkeys(x.removesuffix(suffix).strip() for x in value.split(' | ') if x.strip()))


def evidence_status(row):
    kind = row['evidence_classification']
    if row['recorded_value'] in {'', 'unknown', 'not_established'}:
        return 'unverified'
    if kind == 'user_authorized_continuity_assessment':
        return 'continuity_review'
    if kind.startswith('research_'):
        return 'provisional'
    if kind == 'undated_district_policy_applied_to_named_campus_pathway':
        return 'district_policy_only'
    if 'conflicting' in kind:
        return 'unverified'
    return 'documented'


def legacy_document(b, dataset, row):
    """A remote hash alone never upgrades a citation into an archived document."""
    if row['snapshot_path']:
        path = b.root / row['snapshot_path']
        if digest(path) != row['snapshot_sha256']:
            raise ValueError('Legacy public source checksum mismatch: ' + str(path))
        source = b.source_file(dataset, path, url=row['source_url'])
        b.tables['sources'][(source,)].update(
            snapshot_kind='saved_public_source', retrieved_at=row['accessed_at_utc'] or None,
            version_label=row['snapshot_sha256'][:16],
            notes='Original public document bytes retained. ' + row['source_title'])
    else:
        source = b.citation(dataset, row['source_url'], key=row['source_id'],
            retrieved=row['accessed_at_utc'] or None, remote_hash=row['source_sha256'] or None)
        b.tables['sources'][(source,)]['notes'] += ' ' + row['source_title']
    return source


def district(b, state, row, source):
    native = row.get('district_id', '')
    namespace = 'CA_CDS_district_id' if state == 'CA' and native else state + '_research_district_name'
    did = 'CA-D' + native if state == 'CA' and native else record_id('district', state, row['district_name'])
    did = b.resolve('district', namespace, native or row['district_name'], default=did)
    b.district(did, state, row['district_name'], source, namespace=namespace,
               native_id=native or row['district_name'], status='state_identifier' if native else 'provisional_name_group')
    return did


def migrate_state(b, state_code):
    config = json.loads((b.root / f'config/states/{state_code.lower()}.json').read_text())
    paths = config['structural_inputs']
    dataset = b.dataset(state_code + '_STRUCTURAL_RESEARCH', state_code, 'inventory',
        config['state_name'] + ' reviewed structural research', 'repo:data/registry/',
        notes='2025–26 reviewed reference inventory with attribute-specific historical/undated evidence. Prior 2026–27 research is a retained vintage, not a second verified annual census.')
    files = {key: b.source_file(dataset, path) for key, path in paths.items()}
    records = read_csv(b.root / paths['inventory'])
    prior = {r['program_id']: r for r in read_csv(b.root / paths['prior_inventory'])}
    ledger = [r for r in read_csv(b.root / paths['evidence_ledger']) if r['state'] == state_code]
    claims = defaultdict(list)
    for row in ledger:
        claims[row['program_id']].append(row)
    source_rows = {r['source_id']: r for r in read_csv(b.root / paths['sources'])}
    used = {r['source_id'] for r in ledger}
    if state_code == 'CA':
        used.add(next(k for k, r in source_rows.items() if r['source_key'] == 'ca_cde_xlsx'))
    citations = {key: legacy_document(b, dataset, source_rows[key]) for key in sorted(used)}
    sites, schools_by_native = {}, {}
    for row in records:
        pid = row['program_id']
        sid = b.resolve('school', row['school_id_namespace'] or 'FIVE_STATE_RESEARCH_school_id',
            row['school_id'] or row['school_research_id'], year=row['reference_school_year'], default=row['school_research_id'])
        b.school(sid, state_code, row['school_name'], files['inventory'],
            namespace='FIVE_STATE_RESEARCH_school_id', native_id=row['school_research_id'],
            status='state_identifier' if row['school_id'] else 'provisional',
            screening='curated_program_host_including_status_and_eligibility_candidates')
        if row['school_id']:
            native_claim = next(c for c in claims[pid] if c['field_supported'] == 'school_id')
            b.identifier('school', sid, row['school_id_namespace'], row['school_id'], citations[native_claim['source_id']],
                year=exact_year(native_claim['applicable_school_year']), status='historical_official_identifier_crosswalk')
            schools_by_native[row['school_id']] = sid
        did = district(b, state_code, row, files['inventory'])
        b.membership(sid, did, files['inventory'], pid)
        program = b.resolve('program', 'FIVE_STATE_RESEARCH_program_id', pid, default=pid)
        b.add('programs', program_id=program, state_code=state_code, program_name=row['program_name'] or row['school_name'],
            identity_status='provisional_evidence_group', screening_status=row['inclusion_status'],
            notes='Stable reviewed school/program research key, not an official enduring program identifier. Operation and funding/content eligibility are separate in program_status_history.')
        b.identifier('program', program, 'FIVE_STATE_RESEARCH_program_id', pid, files['inventory'], status='reviewed_research_key')
        site = record_id('site', program, sid)
        sites[pid] = site
        b.add('program_sites', site_id=site, program_id=program, school_id=sid,
            link_status='documented' if row['inclusion_status'].startswith('documented_') and row['operating_status_2025_26'] != 'planned_future' else 'provisional',
            source_id=files['inventory'])
        b.add('program_status_history', status_id=record_id('status', site, files['inventory'], row['reference_school_year']),
            site_id=site, school_year=row['reference_school_year'], operating_status=row['operating_status_2025_26'],
            eligibility_status=row['inclusion_status'], instructional_scope=row['instructional_scope'] or None,
            public_funding_status=row['public_funding_status'] or None, confirmation_method=row['confirmation_basis'],
            evidence_period_raw=row['operating_evidence_school_year'] or row['reference_school_year'],
            source_id=files['inventory'], source_locator=pid,
            notes='Operation status does not refresh allocation/design dates. Review IDs: ' + row['continuity_review_ids'] + '. ' + row['change_findings'])
        b.claim('program', program, 'reviewed_inventory_snapshot', json.dumps(row, ensure_ascii=False, sort_keys=True),
            files['inventory'], pid, period='2025-26 reference review; attribute dates remain separate', status='metadata_only')
        b.add('program_configurations', configuration_id=record_id('configuration', site, files['inventory'], 'reviewed_selection'),
            site_id=site, grade_scope=row['grade_span'] or 'not_reported', population_model=row['program_type'],
            delivery_structure=row['school_structure'], program_kind='reviewed_structural_selection_with_separate_source_dates',
            reported_model_label=row['published_model_label'] or None,
            evidence_period_raw='2025-26 research selection; source applicability is attribute-specific',
            verification_status='provisional', source_id=files['inventory'], source_locator=pid,
            notes='This selected metadata row has no validity year. Individual source claims/configurations preserve actual applicable years; do not date undated choices from the operation-status reference year.')
        if pid in prior:
            old = prior[pid]
            b.claim('program', program, 'prior_inventory_snapshot_2026_27', json.dumps(old, ensure_ascii=False, sort_keys=True),
                files['prior_inventory'], pid, status='metadata_only', period='superseded research vintage targeting 2026-27',
                notes='Retained research history, not an independently confirmed annual observation or a new program.')
            b.identifier('program', program, 'FIVE_STATE_RESEARCH_program_id', pid, files['prior_inventory'], status='reviewed_research_key')
            b.identifier('school', sid, 'FIVE_STATE_RESEARCH_school_id', old['school_research_id'], files['prior_inventory'], status='prior_research_alias_retained_by_reviewed_program_lineage')
            if old['school_research_id'] != row['school_research_id']:
                b.claim('school', sid, 'reviewed_research_identity_alias', json.dumps({'previous': old['school_research_id'], 'current': row['school_research_id'], 'previous_name': old['school_name'], 'current_name': row['school_name']}, ensure_ascii=False),
                    files['inventory'], pid + ':identity_correction', status='provisional',
                    notes='Explicit correction retained within the same reviewed program lineage; no automatic fuzzy-name merge.')
        for claim in claims[pid]:
            migrate_claim(b, row, program, site, claim, citations[claim['source_id']], files['evidence_ledger'])
        allocations(b, row, site, sid, claims[pid], citations, files['inventory'])
    for review in read_csv(b.root / paths['continuity_reviews']):
        for pid in review['program_ids'].split(' | '):
            if pid in sites:
                program = b.tables['program_sites'][(sites[pid],)]['program_id']
                b.claim('program', program, 'continuity_review', json.dumps(review, ensure_ascii=False, sort_keys=True),
                    files['continuity_reviews'], review['review_id'] + ':' + pid, year='2025-26', period='2025-26 assessment; reviewed_at=' + review['reviewed_at_utc'],
                    status='continuity_review', method='continuity_review',
                    notes='Bounded documented change/closure review; search snippets are discovery records, not attribute proof.')
    for event in read_csv(b.root / paths['change_events']):
        if event['program_id'] in sites:
            program = b.tables['program_sites'][(sites[event['program_id']],)]['program_id']
            b.claim('program', program, 'program_change_event', json.dumps(event, ensure_ascii=False, sort_keys=True),
                files['change_events'], event['event_id'], status='provisional',
                notes='Change/closure/relocation finding retained at its documented scope; no date inferred from narrative numbers.')
    if state_code == 'CA':
        california_leads(b, paths, files, citations, source_rows, schools_by_native)
    b.notes.append(config['state_name'] + ': reviewed structural records, original research IDs, 2025–26 operation/eligibility and source-dated claims integrated. Historical/undated choices, candidates and prior vintages are not new confirmed annual programs. No assessment collection in this integration.')


def migrate_claim(b, row, program, site, claim, source, ledger_source):
    year = exact_year(claim['applicable_school_year'])
    status = evidence_status(claim)
    note = json.dumps({'source_date': claim['source_date'], 'classification': claim['evidence_classification'],
        'excerpt_or_paraphrase': claim['evidence_excerpt_or_paraphrase'], 'conflicting_or_unresolved': claim['conflicting_or_unresolved']}, ensure_ascii=False, sort_keys=True)
    b.claim('program', program, claim['field_supported'], claim['recorded_value'], source, claim['evidence_id'],
        year=year, period=claim['applicable_school_year'] or None, status=status,
        method='continuity_review' if status == 'continuity_review' else 'source_record', import_source=ledger_source, notes=note)
    field = claim['field_supported']
    if field == 'instruction_languages':
        for language in instruction_languages(claim['recorded_value']):
            b.add('program_languages', language_record_id=record_id('language', site, language, source, claim['evidence_id']),
                site_id=site, language_name=language, language_code=LANGUAGE_CODES.get(language), language_role='instruction_language',
                valid_from_year=year, valid_to_year=year, evidence_period_raw=claim['applicable_school_year'] or None,
                verification_status='provisional' if row['inclusion_status'].startswith('candidate_') else status,
                source_id=source, source_locator=claim['evidence_id'], notes=note)
    if field in {'program_type', 'school_structure', 'grade_span'} and claim['recorded_value'] not in {'', 'unknown'}:
        b.add('program_configurations', configuration_id=record_id('configuration', site, source, claim['evidence_id']),
            site_id=site, school_year=year, grade_scope=claim['recorded_value'] if field=='grade_span' else 'not_reported',
            population_model=claim['recorded_value'] if field=='program_type' else 'unknown',
            delivery_structure=claim['recorded_value'] if field=='school_structure' else 'unknown',
            program_kind='source_attribute:' + field, evidence_period_raw=claim['applicable_school_year'] or None,
            verification_status=status, source_id=source, source_locator=claim['evidence_id'], notes=note)


def allocations(b, row, site, school, claims, citations, inventory_source):
    kinds = {'kindergarten_allocation', 'later_documented_kindergarten_allocation',
             'reported_kindergarten_allocation_school_website', 'reported_kindergarten_allocation_funder_case_study'}
    matching = [c for c in claims if c['field_supported']=='kindergarten_allocation' and c['recorded_value']==row['kindergarten_allocation']]
    preferred = next((c for c in reversed(matching) if c['applicable_school_year']==row['reference_school_year']), matching[-1] if matching else None)
    for claim in claims:
        if claim['field_supported'] not in kinds:
            continue
        selected = claim is preferred and row['kindergarten_allocation'] != 'unknown'
        conflict = bool(row['allocation_conflict_notes'])
        explicit = selected and row['allocation_evidence_type']=='explicit_kindergarten_schedule' and not conflict
        schedule = record_id('schedule', site, claim['evidence_id'])
        support = 'CONFLICTING_SOURCE_CLAIMS' if conflict else 'EXPLICIT_GRADE' if explicit else 'PUBLISHED_MODEL_ONLY'
        b.add('allocation_schedules', schedule_id=schedule, school_id=school, site_id=site,
            school_year=exact_year(claim['applicable_school_year']), grade_scope='K',
            reported_model_label=claim['recorded_value'], percentage_basis='Source-reported K policy/model; selected legacy shares are not automatically verified instructional minutes',
            schedule_status='documented_plan' if explicit else 'reported_policy_requires_review',
            evidence_review_status='SELECTED_EXPLICIT_K_PLAN' if explicit else 'SELECTED_RESEARCH_MODEL' if selected else 'HISTORICAL_OR_ALTERNATIVE_SOURCE_CLAIM',
            grade_support_status=support, evidence_period_raw=claim['applicable_school_year'] or None,
            tested_cohort_exposure='not_established', source_id=citations[claim['source_id']], source_locator=claim['evidence_id'],
            notes=json.dumps({'selected_in_reference_inventory': selected, 'reference_year': row['reference_school_year'],
                'source_date': claim['source_date'], 'evidence_type': row['allocation_evidence_type'],
                'applicability': row['allocation_applicability_2025_26'], 'conflict': row['allocation_conflict_notes'],
                'change': row['allocation_change_notes'], 'excerpt': claim['evidence_excerpt_or_paraphrase']}, ensure_ascii=False, sort_keys=True))
        if selected:
            shares = json.loads(row['kindergarten_language_shares_json'])
            b.claim('schedule', schedule, 'legacy_selected_language_shares', json.dumps(shares, ensure_ascii=False, sort_keys=True),
                inventory_source, row['program_id'] + ':selected_shares', status='documented' if explicit else 'provisional',
                notes='Preserved selected curation. Published model designations alone do not create accepted named-language percentages.')
            if explicit and shares:
                if abs(sum(float(v) for v in shares.values()) - 100) > .001:
                    raise ValueError('Selected explicit schedule does not total 100: ' + row['program_id'])
                for language, value in shares.items():
                    if language not in instruction_languages(row['instruction_languages']):
                        raise ValueError('Allocation uses an unestablished instructional language')
                    b.add('instructional_allocations', allocation_id=record_id('allocation', schedule, language),
                        schedule_id=schedule, language_name=language, language_code=LANGUAGE_CODES.get(language),
                        instruction_share_pct=float(value), evidence_type='documented_plan',
                        source_id=citations[claim['source_id']], source_locator=claim['evidence_id'])


def california_leads(b, paths, files, citations, source_rows, schools_by_native):
    source = citations[next(k for k, r in source_rows.items() if r['source_key']=='ca_cde_xlsx')]
    for row in read_csv(b.root / paths['school_leads']):
        native = row['school_id']
        if not re.fullmatch(r'\d{14}', native):
            raise ValueError('Invalid historical California CDS identifier')
        sid = schools_by_native.get(native) or b.resolve('school', 'CA_CDS', native, year='2024-25', default='CA-S' + native)
        b.school(sid, 'CA', row['school_name'], source,
            status='state_identifier', screening='historical_CDE_school_lead_not_curated_program')
        b.identifier('school', sid, 'CA_CDS', native, source, year='2024-25', status='historical_official_identifier_crosswalk')
        did = district(b, 'CA', row, source)
        b.membership(sid, did, source, native, year='2024-25')
        b.claim('school', sid, 'historical_CDE_school_screening', json.dumps(row, ensure_ascii=False, sort_keys=True),
            source, native, year='2024-25', period='2024-25 school-category listing; published 2025-07',
            status='metadata_only', import_source=files['school_leads'],
            notes='Historical school lead only. No language track, K schedule, structure or current program identity is created; transitional-only rows remain screening evidence.')
