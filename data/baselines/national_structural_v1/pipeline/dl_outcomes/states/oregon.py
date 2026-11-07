"""Integrate reviewed Oregon directory identities without inventing language pairs."""
import json
import re

from ..io import read_csv, record_id
from .five_state import LANGUAGE_CODES, district


def grade_models(text):
    """Split only explicitly labeled grade bands; school names do not supply grades."""
    return [(m[0], m[1] + '/' + m[2]) for m in re.findall(r'\b(K-\d+|\d+-\d+):\s*(\d+)\s*/\s*(\d+)', text)]


def migrate(b):
    config = json.loads((b.root / 'config/states/or.json').read_text())['structural_inputs']
    dataset = b.dataset('OR_STRUCTURAL_DIRECTORY', 'OR', 'inventory', 'Oregon 2026–27 reviewed structural directory',
        'https://www.oregon.gov/ode/', publisher='Oregon Department of Education',
        notes='Reviewed school aliases and 2024–25 NCES reference identities; source listings and composite track scope are not verified cohorts.')
    files = {key: b.source_file(dataset, path) for key, path in config.items()}
    summary = json.loads((b.root / config['source_summary']).read_text())
    citation = b.citation(dataset, summary['source_url'], key='OR_ODE_directory_2026_27',
        period='2026-27 directory', remote_hash=summary['source_sha256'])
    b.tables['sources'][(citation,)]['notes'] += ' The saved extraction is archived; the original directory PDF bytes are not archived in this repository. The extraction timestamp is not asserted as a download timestamp.'
    rows = read_csv(b.root / config['inventory'])
    for i, row in enumerate(rows, 2):
        year = row['school_year']
        excluded = row['verification_status'].startswith('excluded_')
        native = row['nces_school_id']
        if native and not re.fullmatch(r'\d{12}', native):
            raise ValueError('Oregon reviewed NCES identifier must retain 12 digits')
        if excluded and native:
            raise ValueError('Oregon screened-out row unexpectedly acquired a reviewed NCES match')
        raw_key = row['oregon_school_key'] or record_id('OR_source_school', row['district_name'], row['school_name'])
        sid = b.resolve('school', 'NCES_school_id' if native else 'OR_reviewed_school_key', native or raw_key,
            year=year, default='OR-S' + native if native else raw_key)
        b.school(sid, 'OR', row['canonical_school_name'] or row['school_name'], files['inventory'],
            namespace='OR_reviewed_school_key', native_id=raw_key,
            status='provisional', screening='related_language_listing_requires_review' if excluded else 'reviewed_state_directory_identity')
        if native:
            b.identifier('school', sid, 'NCES_school_id', native, files['school_crosswalk'],
                year=row['nces_reference_year'], status=row['nces_match_status'])
        did = district(b, 'OR', row, files['inventory'])
        locator = f'CSV record {i}; PDF page {row["source_page"]}'
        b.membership(sid, did, files['inventory'], locator, year=year)
        b.claim('school', sid, 'oregon_directory_source_record', json.dumps(row, ensure_ascii=False, sort_keys=True),
            citation, locator, year=year, period=year, status='metadata_only', import_source=files['inventory'],
            notes='Original directory observation, NCES reconciliation and all raw labels retained. Identity match does not establish historical program exposure.')
        if excluded:
            b.claim('school', sid, 'related_language_program_screening', row['verification_status'], citation, locator + ':screening',
                year=year, period=year, status='unverified', method='eligibility_requires_review', import_source=files['inventory'],
                notes='Source extraction classifies this as heritage-language or revitalization/language classes. Retained for review without manufacturing an academic immersion program or permanently excluding future evidence.')
            continue
        key = row['program_identity_key']
        if not key or not row['partner_language']:
            raise ValueError('DLI candidate lacks a reviewed program/language research key')
        program = b.resolve('program', 'OR_reviewed_program_identity_key', key, year=year, default=key)
        if (program,) not in b.tables['programs']:
            b.add('programs', program_id=program, state_code='OR',
                program_name=(row['canonical_school_name'] or row['school_name']) + ' / ' + row['partner_language'],
                identity_status='provisional_evidence_group', screening_status=row['verification_status'],
                notes='Reviewed directory evidence key, not an official enduring program ID. Four Rivers grade-band keys remain separate evidence groups sharing one school identity; McDaniel aliases share reviewed program keys.')
        b.identifier('program', program, 'OR_reviewed_program_identity_key', key, files['inventory'], year=year,
            status='reviewed_directory_evidence_key_not_official_program_id')
        site = record_id('site', program, sid)
        b.add('program_sites', site_id=site, program_id=program, school_id=sid, link_status='provisional', source_id=files['inventory'])
        composite = row['verification_status'] == 'listed_multi_language_cell_needs_review'
        b.add('program_status_history', status_id=record_id('status', site, files['inventory'], year),
            site_id=site, school_year=year, operating_status='listed_in_state_directory',
            eligibility_status=row['verification_status'], instructional_scope='source_listing_requires_campus_and_track_scope_review',
            public_funding_status=None, confirmation_method='state_directory_listing', evidence_period_raw=year,
            source_id=files['inventory'], source_locator=key,
            notes='Directory year is separate from the 2024–25 NCES identity reference. A listing does not verify a participant cohort; expanded composite language cells remain provisional.')
        b.add('program_languages', language_record_id=record_id('language', site, citation, locator),
            site_id=site, language_name=row['partner_language'], language_code=LANGUAGE_CODES.get(row['partner_language']),
            language_role='reported_instruction_language', valid_from_year=year, valid_to_year=year, evidence_period_raw=year,
            verification_status='provisional' if composite else 'documented', source_id=citation, source_locator=locator,
            notes='Reported directory language only. English is not inferred. Composite cells do not establish independent immersion or content-course scope for each expanded language.')
        b.add('program_configurations', configuration_id=record_id('configuration', site, citation, locator),
            site_id=site, school_year=year, grade_scope='not_reported',
            population_model='unknown' if composite else row['population_model'],
            delivery_structure='unknown' if composite else row['program_structure'], program_kind='state_directory_structural_observation',
            reported_model_label=row['allocation_detail'] or None, evidence_period_raw=year,
            verification_status='provisional' if composite else 'documented', source_id=citation, source_locator=locator,
            notes='Source raw population model: ' + row['source_population_model_raw'] + '; structure: ' + row['source_structure_raw'] +
                '. Composite campus descriptions are not assigned as language-specific strand/whole-school or one-way/two-way proof. ' + row['program_notes'])
        allocation(b, row, sid, site, citation, files['inventory'], composite)
    b.notes.append('Oregon: 223 reviewed 2026–27 source observations retain 211 DLI-directory observations and 12 separate screening records. McDaniel aliases and shared Four Rivers NCES identity are preserved. English pairing, composite track models and historical cohorts are not inferred; no assessment collection.')


def allocation(b, row, school, site, citation, import_source, composite):
    raw = {key: row[key] for key in ['source_district_raw', 'source_school_raw', 'source_language_raw',
        'source_population_model_raw', 'source_structure_raw', 'allocation_detail', 'program_notes', 'source_page']}
    signature = json.dumps(raw, ensure_ascii=False, sort_keys=True)
    cell = record_id('directory_cell', signature)
    parts = grade_models(row['allocation_detail']) or [('not_reported', row['allocation_detail'] or 'not_reported')]
    for grade, label in parts:
        # A shared source cell becomes one campus-level policy, not a second
        # timetable for every language produced by extraction expansion.
        schedule = record_id('schedule', school, None if composite else site, citation, cell, grade)
        if (schedule,) in b.tables['allocation_schedules']:
            continue
        b.add('allocation_schedules', schedule_id=schedule, school_id=school, site_id=None if composite else site,
            school_year=row['school_year'], grade_scope=grade, reported_model_label=label,
            percentage_basis='Directory ratio/model; language ordering and K applicability are not inferred',
            schedule_status='reported_policy_requires_review',
            evidence_review_status='COMPOSITE_CAMPUS_POLICY_NOT_LANGUAGE_ATTRIBUTED' if composite else 'STATE_DIRECTORY_MODEL_RETAINED',
            grade_support_status='COMPOSITE_TRACK_SCOPE_UNRESOLVED' if composite else 'EXPLICIT_GRADE' if grade != 'not_reported' else 'SOURCE_GRADE_SCOPE_NOT_REPORTED',
            evidence_period_raw=row['school_year'], tested_cohort_exposure='not_established',
            source_id=citation, source_locator=cell + '; PDF page ' + row['source_page'],
            notes=signature + ' Reviewed extraction source: ' + import_source + '. No named-language shares or tested-cohort exposure are created; generic Other labels remain unquantified.')
