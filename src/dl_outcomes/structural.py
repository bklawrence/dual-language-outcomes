"""Audit structural migration and produce source-scoped, reproducible review views."""
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import re

from .io import digest, read_csv
from .validation import load
from .identity_audit import preserved_identity_fingerprint

AUDIT = 'config/research_migrations/structural_integration_2026_11_04.json'
FIVE = {'CA': 'california', 'ID': 'idaho', 'MT': 'montana', 'NV': 'nevada', 'WY': 'wyoming'}
REPORT = 'data/reports/structural_inventory_2026_11_04'
REFERENCE_REVIEW_STATES = set(FIVE) | {'UT', 'CO', 'NM', 'AZ', 'NE', 'KS', 'ND', 'SD', 'MN', 'IA', 'MO', 'AK', 'HI', 'WI', 'MI', 'IL', 'IN', 'OK', 'AR', 'LA', 'AL', 'MS', 'FL', 'GA', 'SC', 'NC', 'TN', 'OH', 'KY', 'WV', 'VA', 'PA', 'MD', 'DE', 'NJ', 'NY', 'CT', 'ME', 'MA', 'NH', 'RI', 'VT'}


def report_prefix(root):
    explicit = json.loads((root / 'config/project.json').read_text()).get('national_review_report_prefix')
    if explicit:
        return explicit
    new_england=root/'config/research_migrations/new_england_2026_11_06.json'
    if new_england.exists():return json.loads(new_england.read_text())['national_report_prefix']
    followup=root/'config/research_migrations/ny_allocation_followup_2026_11_06.json'
    if followup.exists():return json.loads(followup.read_text())['national_report_prefix']
    atlantic=root/'config/research_migrations/mid_atlantic_ct_2026_11_05.json'
    if atlantic.exists():return json.loads(atlantic.read_text())['national_report_prefix']
    eastern=root/'config/research_migrations/oh_ky_wv_va_2026_11_05.json'
    if eastern.exists():return json.loads(eastern.read_text())['national_report_prefix']
    southeast=root/'config/research_migrations/southeast_2026_11_05.json'
    if southeast.exists():return json.loads(southeast.read_text())['national_report_prefix']
    south_central=root/'config/research_migrations/south_central_2026_11_05.json'
    if south_central.exists():return json.loads(south_central.read_text())['national_report_prefix']
    historical=root/'config/research_migrations/illinois_2021_22_user_2026_11_05.json'
    if historical.exists():return json.loads(historical.read_text())['national_report_prefix']
    great_lakes=root/'config/research_migrations/great_lakes_2026_11_05.json'
    if great_lakes.exists():return json.loads(great_lakes.read_text())['national_report_prefix']
    batch=root/'config/research_migrations/northern_central_ak_hi_2026_11_05.json'
    if batch.exists():return json.loads(batch.read_text())['national_report_prefix']
    review=root/'config/research_migrations/tx_allocation_review_2026_11_05.json'
    if review.exists():return json.loads(review.read_text())['national_report_prefix']
    followup=root/'config/research_migrations/ut_tx_allocations_2026_11_05.json'
    return json.loads(followup.read_text()).get('national_report_prefix',REPORT) if followup.exists() else REPORT


def migration_errors(root, tables, *, check_hashes=True):
    audit = json.loads((root / AUDIT).read_text())
    errors = []
    if check_hashes:
        for rel, expected in audit['legacy_inputs'].items():
            if digest(root / rel) != expected:
                errors.append('Altered legacy research input: ' + rel)
        for rel, expected in audit['unchanged_assessment_outputs'].items():
            if digest(root / rel) != expected:
                errors.append('Assessment/proficiency pilot changed during structural integration: ' + rel)
    for table, states in audit['baseline_identity_sets'].items():
        field = 'school_id' if table=='schools' else 'program_id'
        for state, expected in states.items():
            ids = sorted(r[field] for r in tables[table] if r['state_code']==state)
            fingerprint = preserved_identity_fingerprint(root, table, state, ids, expected)
            if fingerprint != expected:
                errors.append('Previously integrated identity set changed: ' + table + '/' + state)
    programs = {r['program_id']: r for r in tables['programs']}
    sites = {r['site_id']: r for r in tables['program_sites']}
    sources = {r['source_id']: r for r in tables['sources']}
    statuses = defaultdict(list)
    for row in tables['program_status_history']:
        statuses[sites[row['site_id']]['program_id']].append(row)
    claims_by_locator = defaultdict(list)
    for row in tables['evidence_claims']:
        claims_by_locator[row['source_locator']].append(row)
    original = []
    for state, name in FIVE.items():
        original += read_csv(root / f'data/registry/state_dl_programs_{name}_2025_26.csv')
    for state in FIVE:
        expected = {r['program_id'] for r in original if r['state']==state}
        actual = {pid for pid,p in programs.items() if p['state_code']==state}
        if actual != expected:
            errors.append('Reviewed program set changed or screening leads became programs: ' + state)
    for row in original:
        pid = row['program_id']
        if pid not in programs:
            errors.append('Reviewed program identity missing: ' + pid)
            continue
        current = [r for r in statuses[pid] if r['school_year']==row['reference_school_year']]
        if len(current)!=1:
            errors.append('Reviewed status lost or duplicated: ' + pid)
            continue
        status = current[0]
        for source_field, field in [('operating_status_2025_26','operating_status'),('inclusion_status','eligibility_status'),('public_funding_status','public_funding_status'),('instructional_scope','instructional_scope'),('confirmation_basis','confirmation_method')]:
            if (status[field] or '') != row[source_field]:
                errors.append('Operation/eligibility distinction changed: ' + pid + '/' + field)
    original_claims = {r['evidence_id']:r for r in read_csv(root / 'data/registry/five_state_2025_26/evidence_ledger.csv')}
    for row in original_claims.values():
        matches = [r for r in claims_by_locator[row['evidence_id']] if r['entity_type']=='program' and r['attribute']==row['field_supported']]
        if len(matches)!=1:
            errors.append('Original attribute claim lost or duplicated: ' + row['evidence_id'])
            continue
        claim = matches[0]
        period = row['applicable_school_year'] or None
        actual_year = period if period and re.fullmatch(r'\d{4}-\d{2}', period) and int(period[-2:]) == (int(period[:4])+1)%100 else None
        if claim['reported_value'] != (row['recorded_value'] or None) or claim['evidence_period_raw'] != period:
            errors.append('Original claim value/raw period changed: ' + row['evidence_id'])
        if claim['valid_from_year'] != actual_year or claim['valid_to_year'] != actual_year:
            errors.append('Source applicability replaced by a reference/publication year: ' + row['evidence_id'])
    or_rows = read_csv(root / 'data/registry/oregon_nces/reconciled/oregon_program_observations_with_nces_reconciled.csv')
    expected_keys = {r['program_identity_key'] for r in or_rows if not r['verification_status'].startswith('excluded_')}
    if {pid for pid,p in programs.items() if p['state_code']=='OR'} != expected_keys:
        errors.append('Oregon reviewed program keys lost, invented or duplicated')
    raw_claims = [r for r in tables['evidence_claims'] if r['attribute']=='oregon_directory_source_record']
    if len(raw_claims)!=len(or_rows):
        errors.append('Oregon source observations lost or duplicated')
    related = [r for r in tables['evidence_claims'] if r['attribute']=='related_language_program_screening' and sources[r['source_id']]['dataset_id']=='OR_STRUCTURAL_DIRECTORY']
    if len(related)!=sum(r['verification_status'].startswith('excluded_') for r in or_rows):
        errors.append('Oregon heritage/revitalization screening rows disappeared')
    lead_claims = [r for r in tables['evidence_claims'] if r['attribute']=='historical_CDE_school_screening']
    if len(lead_claims)!=1310 or any(r['entity_type']!='school' or r['valid_from_year']!='2024-25' for r in lead_claims):
        errors.append('Historical CDE screening leads were lost or promoted beyond their source year/unit')
    for row in tables['program_languages']:
        if sources[row['source_id']]['dataset_id']=='OR_STRUCTURAL_DIRECTORY' and row['language_name']=='English':
            errors.append('Oregon directory silently acquired an English instructional partner')
    for row in tables['allocation_schedules']:
        claim = original_claims.get(row['source_locator'])
        if claim:
            period = claim['applicable_school_year']
            expected_year = period if re.fullmatch(r'\d{4}-\d{2}', period) and int(period[-2:]) == (int(period[:4])+1)%100 else None
            if row['school_year'] != expected_year:
                errors.append('Allocation source period replaced by the operation reference year')
        if row['grade_support_status']=='COMPOSITE_TRACK_SCOPE_UNRESOLVED' and row['site_id']:
            errors.append('Composite Oregon campus model assigned to a language track')
        if sources[row['source_id']]['dataset_id']=='OR_STRUCTURAL_DIRECTORY' and row['grade_scope']=='K':
            errors.append('Oregon annual model converted to a kindergarten-only schedule')
    baseline_assessments = {'TX_TPRS_DL_PILOT','WA_ACADEMICS','WA_ENROLLMENT'}
    if json.loads((root/'config/project.json').read_text()).get('collection_phase')=='structural_inventory':
        if any(r['layer']!='inventory' and r['dataset_id'] not in baseline_assessments for r in tables['datasets']):
            errors.append('New non-structural dataset collected before the structural phase is finished')
    if json.loads((root/'config/project.json').read_text()).get('collection_phase')=='school_assessment_collection':
        if any(r['layer']!='inventory' and r['dataset_id'] not in baseline_assessments | {'EDC_SADR_V3_1_SCHOOL_GRADES'} for r in tables['datasets']):
            errors.append('New non-EDC assessment dataset outside the currently authorized collection')
    batch_audit = root / 'config/research_migrations/western_plains_2026_11_04.json'
    if batch_audit.exists():
        from .western_plains_review import audit_errors
        errors.extend(audit_errors(root, tables, check_hashes=check_hashes))
    if (root/'config/research_migrations/northern_central_ak_hi_2026_11_05.json').exists():
        from .northern_central_review import audit_errors as northern_errors
        errors.extend(northern_errors(root, tables, check_hashes=check_hashes))
    if (root/'config/research_migrations/great_lakes_2026_11_05.json').exists():
        from .great_lakes_review import audit_errors as great_lakes_errors
        errors.extend(great_lakes_errors(root, tables, check_hashes=check_hashes))
    if (root/'config/research_migrations/illinois_2021_22_user_2026_11_05.json').exists():
        from .illinois_history import audit_errors as historical_errors
        errors.extend(historical_errors(root, tables, check_hashes=check_hashes))
    if (root/'config/research_migrations/south_central_2026_11_05.json').exists():
        from .south_central_review import audit_errors as south_central_errors
        errors.extend(south_central_errors(root, tables, check_hashes=check_hashes))
    if (root/'config/research_migrations/southeast_2026_11_05.json').exists():
        from .southeast_review import audit_errors as southeast_errors
        errors.extend(southeast_errors(root, tables, check_hashes=check_hashes))
    if (root/'config/research_migrations/oh_ky_wv_va_2026_11_05.json').exists():
        from .oh_ky_wv_va_review import audit_errors as eastern_errors
        errors.extend(eastern_errors(root, tables, check_hashes=check_hashes))
    if (root/'config/research_migrations/mid_atlantic_ct_2026_11_05.json').exists():
        from .mid_atlantic_ct_review import audit_errors as atlantic_errors
        errors.extend(atlantic_errors(root, tables, check_hashes=check_hashes))
    if (root/'config/research_migrations/ny_allocation_followup_2026_11_06.json').exists():
        from .ny_allocation_followup import audit_errors as ny_errors
        errors.extend(ny_errors(root, tables, check_hashes=check_hashes))
    if (root/'config/research_migrations/new_england_2026_11_06.json').exists():
        from .new_england_review import audit_errors as new_england_errors
        errors.extend(new_england_errors(root, tables, check_hashes=check_hashes))
    return errors


def report_rows(root, tables):
    from .study_scope import excluded_school_ids
    excluded=excluded_school_ids(tables)
    from .allocation_coverage import report_rows as allocation_rows
    allocation_details, _, allocation_summary = allocation_rows(tables)
    allocation_by_site = {r['site_id']:r for r in allocation_details}
    allocation_by_state = {r['state_code']:r for r in allocation_summary}
    schools = {r['school_id']: r for r in tables['schools'] if r['school_id'] not in excluded}
    programs = {r['program_id']: r for r in tables['programs']}
    sites = {r['site_id']: r for r in tables['program_sites'] if r['school_id'] not in excluded}
    statuses, configurations, languages, allocations = [defaultdict(list) for _ in range(4)]
    campus_allocations=defaultdict(list)
    for row in tables['allocation_schedules']:
        if not row['site_id']:
            campus_allocations[row['school_id']].append(row)
    for table, index in [('program_status_history',statuses),('program_configurations',configurations),('program_languages',languages),('allocation_schedules',allocations)]:
        for row in tables[table]:
            if row['site_id']:
                index[row['site_id']].append(row)
    inventory = []
    share_claims = defaultdict(list)
    schedule_sites = {r['schedule_id']:r['site_id'] for r in tables['allocation_schedules']}
    for claim in tables['evidence_claims']:
        if claim['entity_type']=='schedule' and claim['attribute']=='legacy_selected_language_shares':
            share_claims[schedule_sites[claim['entity_id']]].append(claim['reported_value'])
    for site_id, site in sorted(sites.items()):
        program, school = programs[site['program_id']], schools[site['school_id']]
        k_scope = allocation_by_site[site_id]
        def joined(rows, field, *, omit=()):
            return ' | '.join(sorted({r[field] for r in rows if r[field] and r[field] not in omit}))
        states = statuses[site_id]
        inventory.append(dict(state_code=program['state_code'], school_id=site['school_id'], school_name=school['school_name'],
            program_id=site['program_id'], site_id=site_id, program_name=program['program_name'],
            identity_status=program['identity_status'], screening_status=program['screening_status'],
            reviewed_status_years=joined(states,'school_year'), operating_status=joined(states,'operating_status'),
            eligibility_status=joined(states,'eligibility_status'), confirmation_methods=joined(states,'confirmation_method'),
            public_funding_status=joined(states,'public_funding_status'),
            reported_instruction_languages_all_periods=joined(languages[site_id],'language_name'),
            language_verification_statuses=joined(languages[site_id],'verification_status'),
            population_models_all_source_periods=joined(configurations[site_id],'population_model',omit=('unknown',)),
            delivery_structures_all_source_periods=joined(configurations[site_id],'delivery_structure',omit=('unknown',)),
            model_labels_all_source_periods=joined(allocations[site_id],'reported_model_label',omit=('unknown','not_reported','Other','Allocation Other','.','N/A')) or joined(configurations[site_id],'reported_model_label',omit=('Other','Allocation Other','.','N/A')),
            allocation_grade_scopes=joined(allocations[site_id],'grade_scope'),
            allocation_review_flags=joined(allocations[site_id],'grade_support_status'),
            allocation_evidence_review_statuses=joined(allocations[site_id],'evidence_review_status'),
            school_level_model_labels_all_source_periods=joined(campus_allocations[site['school_id']],'reported_model_label'),
            school_level_model_evidence_statuses=joined(campus_allocations[site['school_id']],'evidence_review_status'),
            kindergarten_allocation_eligibility=k_scope['k_eligibility'],
            kindergarten_allocation_status=k_scope['k_allocation_status'],
            in_allocation_reference_working_set=k_scope['in_reference_working_set'],
            preserved_selected_share_claims=' | '.join(sorted(set(share_claims[site_id]))),
            interpretation='Source-period union for review, not a single contemporaneous configuration, verified program count or tested-cohort exposure. Blank operating status in legacy pilots means no status-history row collected.'))
    inventory.sort(key=lambda r:(r['state_code'],r['school_name'],r['program_id'],r['site_id']))
    summary = []
    for state in tables['states']:
        code = state['state_code']
        current = [r for r in inventory if r['state_code']==code]
        registry = [r for r in schools.values() if r['state_code']==code]
        if not current and not registry:
            continue
        config = json.loads((root/f'config/states/{code.lower()}.json').read_text())
        state_status = [r for r in tables['program_status_history'] if r['site_id'] in sites and programs[sites[r['site_id']]['program_id']]['state_code']==code]
        qualifying = [r for r in state_status if r['operating_status']=='confirmed_2025_26' and r['eligibility_status'].startswith('documented_')]
        summary.append(dict(state_code=code,state_name=state['state_name'],integration_status=config['collection_status'],
            registry_school_units_including_screening=len(registry), program_site_school_units=len({r['school_id'] for r in current}),
            provisional_program_evidence_groups=len({r['program_id'] for r in current}),
            status_history_rows=len(state_status),
            confirmed_qualifying_2025_26_program_records=len(qualifying) if code in REFERENCE_REVIEW_STATES or (code=='TX' and (root/'config/research_migrations/structural_gaps_pilot_2026_11_06.json').exists()) else None,
            confirmed_qualifying_2025_26_school_units=len({sites[r['site_id']]['school_id'] for r in qualifying}) if code in REFERENCE_REVIEW_STATES or (code=='TX' and (root/'config/research_migrations/structural_gaps_pilot_2026_11_06.json').exists()) else None,
            program_groups_with_some_population_model=len({r['program_id'] for r in current if r['population_models_all_source_periods']}),
            program_groups_with_some_delivery_structure=len({r['program_id'] for r in current if r['delivery_structures_all_source_periods']}),
            k_allocation_denominator_school_units=allocation_by_state[code]['k_denominator_school_units'],
            secondary_school_units_excluded_from_k_coverage=allocation_by_state[code]['secondary_school_units_excluded'],
            other_non_k_school_units_excluded=allocation_by_state[code]['other_non_k_school_units_excluded'],
            k_eligibility_unknown_school_units=allocation_by_state[code]['k_eligibility_unknown_school_units'],
            k_allocation_denominator_status=allocation_by_state[code]['denominator_status'],
            statewide_completeness='not_established',
            notes='All-source-period structural evidence. Registry schools may include historical leads or non-DLI screening; program groups include candidates, closures and proposals. Status/eligibility must be filtered separately.'))
    return inventory, sorted(summary,key=lambda r:r['state_code'])


def csv_text(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue()


def generate_report(root, *, check=False):
    _, tables = load(root)
    errors = migration_errors(root,tables)
    if errors:
        raise ValueError('\n'.join(errors))
    from .study_scope import source_history_tables
    historical_tables=source_history_tables(tables)
    inventory, summary = report_rows(root,tables)
    manifest = json.loads((root/'data/curated/manifest.json').read_text())
    prefix=report_prefix(root)
    contents = {
        prefix + '_program_view.csv':csv_text(inventory),
        prefix + '_by_state.csv':csv_text(summary),
    }
    from .allocation_coverage import render_reports as allocation_reports
    contents.update(allocation_reports(root, tables))
    if (root/'config/research_migrations/elementary_allocation_audit_2026_11_04.json').exists():
        from .elementary_audit import render_reports as elementary_reports
        contents.update(elementary_reports(root,tables))
    if (root/'config/research_migrations/ut_tx_allocations_2026_11_05.json').exists():
        from .allocation_enrichment import render_reports as enrichment_reports
        contents.update(enrichment_reports(root,tables))
    if (root/'config/research_migrations/tx_allocation_review_2026_11_05.json').exists():
        from .allocation_review import render_reports as reviewed_reports
        contents.update(reviewed_reports(root,tables))
    batch_summary = None
    if (root / 'config/research_migrations/western_plains_2026_11_04.json').exists():
        from .western_plains_review import render_reports
        batch_contents, batch_summary = render_reports(root, historical_tables)
        contents.update(batch_contents)
    followup=root/'config/research_migrations/ut_tx_allocations_2026_11_05.json'
    report_date=json.loads(followup.read_text())['date'] if followup.exists() else '2026-11-04'
    audit = dict(migration_date=report_date, build_id=manifest['build_id'],schema_version=manifest['schema_version'],
        collection_phase='structural_inventory', proficiency_collection='deferred_until_50_state_structural_inventories_finished',
        states_with_integrated_program_evidence=[r['state_code'] for r in summary],
        other_states_without_program_evidence=[r['state_code'] for r in tables['states'] if r['state_code'] not in {x['state_code'] for x in summary}],
        program_evidence_groups=len({r['program_id'] for r in inventory}),program_site_school_units=len({r['school_id'] for r in inventory}),
        imported_five_state_program_records=338, original_five_state_attribute_claims=3480,
        oregon_source_observations=223,oregon_directory_program_evidence_groups=209,
        historical_CDE_screening_school_leads=1310,oregon_separate_language_screening_rows=12,
        original_assessment_outputs_unchanged=True, statewide_completeness='not_established',
        view_interpretation='Source-period unions for review, not a current operating census or assumed historically stable configurations. The earlier nine-state integration report is a preserved milestone; this is the current inventory view.',
        reports={rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in contents.items()})
    if batch_summary:
        audit['western_plains_batch'] = {k: batch_summary[k] for k in ['programme_evidence_groups', 'school_units_with_programme_evidence', 'public_source_documents', 'source_extraction_counts']}
    if (root/'config/research_migrations/northern_central_ak_hi_2026_11_05.json').exists():
        from .northern_central_review import render_reports as northern_reports
        northern_contents, northern_summary = northern_reports(root, historical_tables)
        contents.update(northern_contents)
        audit['northern_central_ak_hi_batch'] = northern_summary
        audit['reports'].update({rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in northern_contents.items()})
    if (root/'config/research_migrations/great_lakes_2026_11_05.json').exists():
        if (root/'config/research_migrations/illinois_2021_22_user_2026_11_05.json').exists():
            from .illinois_history import frozen_great_lakes_reports
            batch_contents, batch_report = frozen_great_lakes_reports(root)
        else:
            from .great_lakes_review import render_reports as great_lakes_reports
            batch_contents, batch_report = great_lakes_reports(root, historical_tables)
        contents.update(batch_contents)
        audit['great_lakes_batch'] = batch_report
        audit['reports'].update({rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in batch_contents.items()})
    if (root/'config/research_migrations/illinois_2021_22_user_2026_11_05.json').exists():
        from .illinois_history import render_reports as historical_reports
        historical_contents, historical_report = historical_reports(root, historical_tables, inventory)
        contents.update(historical_contents)
        audit['illinois_user_2021_22_history'] = historical_report
        audit['reports'].update({rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in historical_contents.items()})
    if (root/'config/research_migrations/south_central_2026_11_05.json').exists():
        from .south_central_review import render_reports as south_central_reports
        new_contents, new_summary = south_central_reports(root, historical_tables)
        contents.update(new_contents)
        audit['south_central_batch'] = new_summary
        audit['states_with_screening_only_research'] = [r['state'] for r in new_summary['state_summary']
            if r['programme_records']==0]
        reviewed = set(audit['states_with_integrated_program_evidence']) | set(audit['states_with_screening_only_research'])
        audit['states_with_structural_research'] = sorted(reviewed)
        audit['other_states_without_structural_research'] = [r['state_code'] for r in tables['states']
            if r['state_code'] not in reviewed]
        audit['reports'].update({rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in new_contents.items()})
    if (root/'config/research_migrations/southeast_2026_11_05.json').exists():
        from .southeast_review import render_reports as southeast_reports
        new_contents, new_summary = southeast_reports(root, historical_tables)
        contents.update(new_contents)
        audit['southeast_batch'] = new_summary
        screened = set(audit.get('states_with_screening_only_research', []))
        screened.update(r['state'] for r in new_summary['state_summary'] if r['programme_records']==0)
        audit['states_with_screening_only_research'] = sorted(screened)
        reviewed = set(audit['states_with_integrated_program_evidence']) | screened
        audit['states_with_structural_research'] = sorted(reviewed)
        audit['other_states_without_structural_research'] = [r['state_code'] for r in tables['states']
            if r['state_code'] not in reviewed]
        audit['reports'].update({rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in new_contents.items()})
    if (root/'config/research_migrations/oh_ky_wv_va_2026_11_05.json').exists():
        from .oh_ky_wv_va_review import render_reports as eastern_reports
        new_contents, new_summary = eastern_reports(root, historical_tables)
        contents.update(new_contents)
        audit['oh_ky_wv_va_batch'] = new_summary
        screened = set(audit.get('states_with_screening_only_research', []))
        screened.update(r['state'] for r in new_summary['state_summary'] if r['programme_records']==0)
        audit['states_with_screening_only_research'] = sorted(screened)
        reviewed = set(audit['states_with_integrated_program_evidence']) | screened
        audit['states_with_structural_research'] = sorted(reviewed)
        audit['other_states_without_structural_research'] = [r['state_code'] for r in tables['states']
            if r['state_code'] not in reviewed]
        audit['reports'].update({rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in new_contents.items()})
    if (root/'config/research_migrations/mid_atlantic_ct_2026_11_05.json').exists():
        from .mid_atlantic_ct_review import render_reports as atlantic_reports
        new_contents, new_summary = atlantic_reports(root, historical_tables)
        contents.update(new_contents)
        audit['mid_atlantic_ct_batch'] = new_summary
        screened = set(audit.get('states_with_screening_only_research', []))
        screened.update(r['state'] for r in new_summary['state_summary'] if r['programme_records']==0)
        audit['states_with_screening_only_research'] = sorted(screened)
        reviewed = set(audit['states_with_integrated_program_evidence']) | screened
        audit['states_with_structural_research'] = sorted(reviewed)
        audit['other_states_without_structural_research'] = [r['state_code'] for r in tables['states'] if r['state_code'] not in reviewed]
        audit['reports'].update({rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in new_contents.items()})
    if (root/'config/research_migrations/ny_allocation_followup_2026_11_06.json').exists():
        from .ny_allocation_followup import render_reports as ny_reports
        new_contents, new_summary = ny_reports(root, historical_tables)
        contents.update(new_contents)
        audit['new_york_allocation_followup'] = new_summary
        audit['reports'].update({rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in new_contents.items()})
    if (root/'config/research_migrations/new_england_2026_11_06.json').exists():
        from .new_england_review import render_reports as new_england_reports
        new_contents, new_summary = new_england_reports(root, historical_tables)
        contents.update(new_contents)
        audit['new_england_batch'] = new_summary
        screened = set(audit.get('states_with_screening_only_research', []))
        screened.update(r['state'] for r in new_summary['state_summary'] if r['programme_records']==0)
        audit['states_with_screening_only_research'] = sorted(screened)
        reviewed = set(audit['states_with_integrated_program_evidence']) | screened
        audit['states_with_structural_research'] = sorted(reviewed)
        audit['other_states_without_structural_research'] = [r['state_code'] for r in tables['states'] if r['state_code'] not in reviewed]
        audit['reports'].update({rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in new_contents.items()})
    if (root/'config/research_migrations/structural_gaps_pilot_2026_11_06.json').exists():
        from .gap_pilot import render_reports as pilot_reports, revise_report_paths
        new_contents,new_summary=pilot_reports(root,tables)
        contents.update(new_contents)
        contents,aliases=revise_report_paths(root,contents)
        audit['structural_gaps_pilot']=new_summary
        audit['preserved_prior_report_versions']=aliases
        audit['reports']={rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in contents.items()}
    if (root/'config/research_migrations/delivery_scope_cleanup_2026_11_06.json').exists():
        from .delivery_review import render_reports as delivery_reports, revise_report_paths as delivery_paths
        new_contents,new_summary=delivery_reports(root,tables)
        contents.update(new_contents)
        contents,aliases=delivery_paths(root,contents)
        audit['delivery_scope_cleanup']=new_summary
        audit['delivery_review_preserved_report_versions']=aliases
        audit['reports']={rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in contents.items()}
    if (root/'config/hand_coding.json').exists():
        from .hand_coding import revise_report_paths as manual_paths
        contents,aliases=manual_paths(root,contents,tables)
        audit['hand_coding_preserved_report_versions']=aliases
        audit['reports']={rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in contents.items()}
    from .study_scope import excluded_school_ids, report as scope_report, REPORT as scope_path
    excluded=excluded_school_ids(tables)
    if excluded:
        contents[scope_path]=scope_report(tables)
        audit['study_scope_excluded_school_units']=len(excluded)
        audit['study_scope_excluded_program_school_units']=len({r['school_id'] for r in tables['program_sites'] if r['school_id'] in excluded})
        audit['archived_source_program_evidence_groups']=len(tables['programs'])
        audit['reports'][scope_path]=hashlib.sha256(contents[scope_path].encode()).hexdigest()
    contents[prefix+'.json'] = json.dumps(audit,indent=2,ensure_ascii=False)+'\n'
    for rel, text in contents.items():
        path=root/rel
        if check:
            if not path.exists() or path.read_text()!=text:
                raise ValueError('Structural report is missing or stale: '+rel)
        else:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    return audit
