"""Kindergarten allocation review, with explicit denominator exclusions/unknowns.

These are within-working-set counts. Directory grades are eligibility proxies;
model labels, supported K policies and named-language plans are different layers.
No report here assigns a kindergarten schedule to a secondary continuation.
"""
from collections import defaultdict
import csv
import io
import json
import re
from .policy_selection import current_policy_choices

PREFIX = 'data/reports/kindergarten_allocation_coverage_2026_11_04'
WA_DIRECTORY = 'data/registry/washington'
REVIEWED_STATES = {'CA', 'ID', 'MT', 'NV', 'WY', 'UT', 'CO', 'NM', 'AZ', 'NE', 'KS', 'ND', 'SD', 'MN', 'IA', 'MO', 'AK', 'HI', 'WI', 'MI', 'IL', 'IN', 'OK', 'AR', 'LA', 'AL', 'MS', 'FL', 'GA', 'SC', 'NC', 'TN', 'OH', 'KY', 'WV', 'VA', 'PA', 'MD', 'DE', 'NJ', 'NY', 'CT', 'ME', 'MA', 'NH', 'RI', 'VT'}
SUPPORTED_K = {'EXPLICIT_GRADE', 'DISTRICT_ENTRY_GRADE_MODEL',
               'CAMPUS_GRADE_BAND_MODEL', 'DISTRICT_GRADE_BAND_MODEL'}
REJECTED_K = {'SOURCE_DOES_NOT_SUPPORT_PROGRAM_GRADE_PERIOD', 'UNRECOVERED',
              'EARLIER_GRADE_PROXY_NOT_TARGET_QUANTIFIED', 'CONFLICTING_SOURCE_CLAIMS',
              'COMPOSITE_TRACK_SCOPE_UNRESOLVED'}


def csv_text(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def grade_eligibility(scope, *, directory=False):
    """Read actual grade labels, never school names or a numeric model label."""
    text = (scope or '').casefold().replace('–', '-').replace('—', '-').strip(" '\u00a0")
    if not text or text in {'not_reported', 'unknown', 'elementary'}:
        return 'unknown'
    if 'k intake documented' in text:
        return 'eligible_k'
    if any(word in text for word in ('unresolved', 'unverified', 'most start', 'planned')):
        return 'unknown'
    if directory:
        # Whitespace separates disjoint bands: "PK 01-08" excludes K.
        values = {'ee': -2, 'pk': -1, 'kg': 0, 'k': 0}
        grades = set()
        for part in text.split():
            match = re.fullmatch(r'(ee|pk|kg|k|\d{1,2})(?:-(ee|pk|kg|k|\d{1,2}))?', part)
            if not match:
                return 'unknown'
            start, end = match[1], match[2] or match[1]
            low = values[start] if start in values else int(start)
            high = values[end] if end in values else int(end)
            if high < low or high > 12:
                return 'unknown'
            grades.update(range(low, high + 1))
        if 0 in grades:
            return 'eligible_k'
        return 'excluded_secondary' if min(grades) >= 6 else 'excluded_no_k'
    if re.search(r'\bstarts? (?:in )?grade 1\b', text):
        return 'excluded_no_k'
    if re.search(r'\b(secondary|middle|high school)\b', text) and not re.search(r'\bk\b', text):
        return 'excluded_secondary'
    if '|' in text:
        return merge_eligibility(grade_eligibility(part) for part in text.split('|'))
    if re.search(r'\b(?<!pre-)(?<!pre )k(?:indergarten|g)?\b', text):
        return 'eligible_k'
    match = re.fullmatch(r'(?:grades? )?(tk|pre-?k|pk|ece|\d+)(?:st|nd|rd|th)?(?:-(\d+)(?:st|nd|rd|th)?)?', text)
    if match:
        low = -1 if not match[1].isdigit() else int(match[1])
        high = int(match[2]) if match[2] else low
        if low < 0 and high > 0:
            return 'eligible_k'
        return 'excluded_secondary' if low >= 6 else 'excluded_no_k'
    return 'unknown'


def reference_year(state):
    return {'TX': '2023-24', 'OR': '2026-27'}.get(state, '2025-26')


def select_grade_rows(rows, state):
    """Prefer reviewed scope or dated reference-year scope over older observations."""
    from .evidence_scope import within_reviewed_reference
    year = reference_year(state)
    rows = [r for r in rows if within_reviewed_reference(r,year)]
    rows = [r for r in rows if r['grade_scope'] not in {None, '', 'not_reported'}]
    selected = [r for r in rows if r['program_kind'] == 'reviewed_structural_selection_with_separate_source_dates']
    if selected:
        return selected
    year = reference_year(state)
    exact = [r for r in rows if r['school_year'] == year] if year else []
    if exact:
        return exact
    undated = [r for r in rows if not r['school_year']]
    if undated:
        return undated
    earlier = [r for r in rows if year and r['school_year'] and r['school_year'] < year]
    latest = max((r['school_year'] for r in earlier), default=None)
    return [r for r in earlier if r['school_year'] == latest]


def merge_eligibility(values):
    values = set(values)
    # A school can have a K strand and a secondary continuation at the same site.
    if 'eligible_k' in values:
        return 'eligible_k'
    if not values or 'unknown' in values:
        return 'unknown'
    return 'excluded_no_k' if 'excluded_no_k' in values else 'excluded_secondary'


def report_rows(tables):
    from .evidence_scope import reference_bounds, scoped_row, within_reviewed_reference
    bounds=reference_bounds(tables)
    ceilings=reference_bounds(tables,latest=True)
    schools = {r['school_id']: r for r in tables['schools']}
    programs = {r['program_id']: r for r in tables['programs']}
    configurations, statuses, allocations = [defaultdict(list) for _ in range(3)]
    directory = {}
    for row in tables['program_configurations']:
        configurations[row['site_id']].append(scoped_row('program_configurations','configuration_id',row,bounds,ceilings))
    for row in tables['program_status_history']:
        statuses[row['site_id']].append(row)
    for row in tables['allocation_schedules']:
        allocations[row['school_id']].append(scoped_row('allocation_schedules','schedule_id',row,bounds,ceilings))
    for row in tables['evidence_claims']:
        if row['attribute'] == 'campus_grade_range_context':
            directory[row['entity_id']] = row
    shares = {r['schedule_id'] for r in tables['instructional_allocations']}
    details = []
    policy_cache = {}
    for site in sorted(tables['program_sites'], key=lambda r:r['site_id']):
        pid, sid = site['program_id'], site['school_id']
        program, school = programs[pid], schools[sid]
        state = program['state_code']
        configs = configurations[site['site_id']]
        if state in REVIEWED_STATES:
            included = any(r['school_year']=='2025-26' and r['operating_status']=='confirmed_2025_26'
                           and r['eligibility_status'].startswith('documented_') for r in statuses[site['site_id']])
        elif state == 'WA':
            included = any(r['school_year']=='2025-26' for r in configs)
        else:
            included = True
        grade_rows = select_grade_rows(configs, state)
        eligibility = merge_eligibility(grade_eligibility(r['grade_scope']) for r in grade_rows)
        basis = 'reported_programme_scope' if eligibility != 'unknown' else 'programme_grades_not_established'
        grade_evidence = [r['configuration_id'] for r in grade_rows]
        grade_periods = {r['evidence_period_raw'] or 'not_reported' for r in grade_rows}
        schedules = [r for r in allocations[sid] if r['site_id'] in {None, site['site_id']}]
        year = reference_year(state)
        usable = [r for r in schedules if within_reviewed_reference(r,year) and (not r['school_year'] or not year or r['school_year'] <= year)]
        if year not in policy_cache:
            policy_cache[year] = current_policy_choices(tables, year)
        choice = policy_cache[year].get(site['site_id'])
        if choice:
            usable = [r for r in usable if r['schedule_id'] == choice['selected_schedule_id']]
        # An explicitly campus/programme-linked grade statement is evidence of
        # K scope; a bare ratio or district entry policy is not that statement.
        grade_schedules = [r for r in usable if r['site_id']==site['site_id']
            and (r['grade_support_status'] in {'EXPLICIT_GRADE','CAMPUS_GRADE_BAND_MODEL'}
                 or (not r['grade_support_status'] and r['schedule_status']=='documented_plan'))
            and grade_eligibility(r['grade_scope'])=='eligible_k']
        if eligibility == 'unknown' and grade_schedules:
            eligibility, basis = 'eligible_k', 'campus_programme_schedule_grade_scope'
            grade_evidence.extend(r['schedule_id'] for r in grade_schedules)
            grade_periods.update(r['evidence_period_raw'] or 'not_reported' for r in grade_schedules)
        campus_grade = directory.get(sid)
        campus_range = None
        if campus_grade:
            campus_range = json.loads(campus_grade['reported_value'])['USER_Grade_Range']
            campus_eligibility = grade_eligibility(campus_range, directory=True)
            grade_evidence.append(campus_grade['claim_id'])
            grade_periods.add(campus_grade['valid_from_year'])
            if campus_eligibility.startswith('excluded_'):
                # K-labelled legacy district policies cannot make a secondary campus K-serving.
                eligibility, basis = campus_eligibility, 'campus_directory_excludes_k'
            elif eligibility == 'unknown' and campus_eligibility == 'eligible_k':
                eligibility, basis = 'eligible_k', 'k_campus_proxy_programme_grades_unverified'
        k_models = [r for r in usable if grade_eligibility(r['grade_scope'])=='eligible_k'
                    and (r['schedule_id'] in shares or re.search(r'\d+\s*%|\d+\s*[/:-]\s*\d+', r['reported_model_label'] or ''))
                    and r['grade_support_status'] not in REJECTED_K]
        supported = [r for r in k_models if r['grade_support_status'] in SUPPORTED_K
                     or (not r['grade_support_status'] and r['schedule_status']=='documented_plan')]
        plans = [r for r in supported if r['schedule_id'] in shares and r['schedule_status']=='documented_plan']
        applicable = included and eligibility == 'eligible_k'
        if not included:
            allocation_status = 'outside_reference_working_set'
        elif eligibility.startswith('excluded_'):
            allocation_status = 'not_applicable_' + eligibility.removeprefix('excluded_')
        elif eligibility == 'unknown':
            allocation_status = 'k_eligibility_needs_review'
        elif plans:
            allocation_status = 'named_language_k_plan_available'
        elif supported:
            allocation_status = 'grade_supported_k_model_available'
        elif k_models:
            allocation_status = 'cited_k_model_grade_support_needs_review'
        else:
            allocation_status = 'k_allocation_not_established'
        details.append(dict(state_code=state, reference_working_set_year=year, school_id=sid,
            school_name=school['school_name'], program_id=pid, site_id=site['site_id'],
            in_reference_working_set=int(included), k_eligibility=eligibility, k_eligibility_basis=basis,
            reported_programme_grades=' | '.join(sorted({r['grade_scope'] for r in grade_rows})),
            campus_grade_range_context=campus_range, grade_evidence_periods=' | '.join(sorted(grade_periods)),
            grade_evidence_record_ids=' | '.join(sorted(grade_evidence)),
            k_allocation_status=allocation_status, has_cited_k_model=int(applicable and bool(k_models)),
            has_grade_supported_k_model=int(applicable and bool(supported)),
            has_named_language_k_plan=int(applicable and bool(plans)),
            k_schedule_ids=' | '.join(sorted(r['schedule_id'] for r in k_models)) if applicable else '',
            retained_source_model_labels=' | '.join(sorted({r['reported_model_label'] for r in configs+schedules if r['reported_model_label']})),
            interpretation='Mixed source periods retained. K-campus proxy is not programme-grade confirmation. Secondary models remain contextual evidence; no K exposure assigned.'))
    by_school = []
    grouped = defaultdict(list)
    for row in details:
        grouped[(row['state_code'],row['school_id'])].append(row)
    for (state,sid), rows in sorted(grouped.items()):
        current = [r for r in rows if r['in_reference_working_set']]
        eligibility = merge_eligibility(r['k_eligibility'] for r in current) if current else 'outside_reference_working_set'
        by_school.append(dict(state_code=state, reference_working_set_year=reference_year(state), school_id=sid,
            school_name=schools[sid]['school_name'], in_reference_working_set=int(bool(current)),
            k_eligibility=eligibility, allocation_denominator=int(eligibility=='eligible_k'),
            k_campus_proxy=int(any(r['k_eligibility_basis']=='k_campus_proxy_programme_grades_unverified' for r in current)),
            k_allocation_status=' | '.join(sorted({r['k_allocation_status'] for r in current})) if current else 'outside_reference_working_set',
            has_cited_k_model=max((r['has_cited_k_model'] for r in current),default=0),
            has_grade_supported_k_model=max((r['has_grade_supported_k_model'] for r in current),default=0),
            has_named_language_k_plan=max((r['has_named_language_k_plan'] for r in current),default=0),
            program_ids=' | '.join(sorted(r['program_id'] for r in rows)),
            grade_evidence_record_ids=' | '.join(sorted({x for r in current for x in r['grade_evidence_record_ids'].split(' | ') if x}))))
    summary = []
    for state in sorted({r['state_code'] for r in details}):
        rows = [r for r in by_school if r['state_code']==state and r['in_reference_working_set']]
        eligible = [r for r in rows if r['allocation_denominator']]
        unknown = sum(r['k_eligibility']=='unknown' for r in rows)
        def pct(field):
            return round(100*sum(r[field] for r in eligible)/len(eligible),1) if eligible else None
        summary.append(dict(state_code=state, reference_working_set_year=reference_year(state),
            working_set_school_units=len(rows), k_denominator_school_units=len(eligible),
            k_campus_proxy_school_units=sum(r['k_campus_proxy'] for r in eligible),
            secondary_school_units_excluded=sum(r['k_eligibility']=='excluded_secondary' for r in rows),
            other_non_k_school_units_excluded=sum(r['k_eligibility']=='excluded_no_k' for r in rows),
            k_eligibility_unknown_school_units=unknown,
            schools_with_cited_k_model=sum(r['has_cited_k_model'] for r in eligible),
            cited_k_model_pct_among_identified_k_schools=pct('has_cited_k_model'),
            schools_with_grade_supported_k_model=sum(r['has_grade_supported_k_model'] for r in eligible),
            grade_supported_k_model_pct_among_identified_k_schools=pct('has_grade_supported_k_model'),
            schools_with_named_language_k_plan=sum(r['has_named_language_k_plan'] for r in eligible),
            named_language_k_plan_pct_among_identified_k_schools=pct('has_named_language_k_plan'),
            denominator_status='not_established' if not eligible else 'partial_grades_need_review' if unknown else 'classified_working_set',
            statewide_completeness='not_established',
            interpretation='Schools deduplicated across tracks; one known K track suffices. Unknown grades are reported separately, not counted as missing allocations. Percentages use only identified K schools, including explicitly flagged campus proxies. Model/plan evidence may be older or undated; no 2025-26 schedule or cohort exposure implied.'))
    return details, by_school, summary


def washington_exports(root, tables):
    """Preserve every native structural row, including related-language screening."""
    sources = [r for r in tables['sources'] if r['dataset_id']=='WA_PROGRAMS']
    site_lookup = {r['site_id']:r for r in tables['program_sites']}
    school_lookup = {(r['source_id'],r['native_id'],r['valid_from_year']):r['entity_id']
        for r in tables['identifiers'] if r['entity_type']=='school' and r['namespace']=='WA_OSPI_school_organization_id'}
    configs = {(r['source_id'],r['source_locator']):r for r in tables['program_configurations']}
    rows = []
    for source in sorted(sources, key=lambda r:r['source_id']):
        for native in json.loads((root / source['snapshot_path']).read_text()):
            is_dl = native['programdesigntype'].casefold() == 'dual language program'
            config = configs.get((source['source_id'],'rowid='+native['rowid'])) if is_dl else None
            site = site_lookup[config['site_id']] if config else None
            row = dict(native)
            row.update(is_state_reported_dl=int(is_dl),
                school_id=school_lookup[(source['source_id'],native['schoolorganizationid'],native['schoolyear'])],
                program_id=site['program_id'] if site else None,
                site_id=site['site_id'] if site else None,
                reported_population_model=config['population_model'] if config else None,
                programme_grade_scope='not_reported',
                kindergarten_allocation_status='not_established_source_has_no_grade_scope' if is_dl else 'related_language_screening_only',
                source_id=source['source_id'], source_snapshot_path=source['snapshot_path'],
                source_snapshot_sha256=source['sha256'], source_url=source['source_url'],
                retrieved_at=source['retrieved_at'], source_locator='rowid='+native['rowid'])
            rows.append(row)
    rows.sort(key=lambda r:(r['schoolyear'],r['schoolorganizationid'],r['rowid'],r['source_id']))
    return {WA_DIRECTORY+'/wa_programs.csv':csv_text(rows),
            WA_DIRECTORY+'/wa_dl_programs_2025_26.csv':csv_text([r for r in rows if r['is_state_reported_dl'] and r['schoolyear']=='2025-26'])}


def render_reports(root, tables):
    details, schools, summary = report_rows(tables)
    followup=root/'config/research_migrations/ut_tx_allocations_2026_11_05.json'
    tag='2026_11_05' if followup.exists() else '2026_11_04'
    review=root/'config/research_migrations/tx_allocation_review_2026_11_05.json'
    if review.exists():tag=json.loads(review.read_text())['report_tag']
    batch=root/'config/research_migrations/northern_central_ak_hi_2026_11_05.json'
    if batch.exists():tag=json.loads(batch.read_text())['report_tag']
    great_lakes=root/'config/research_migrations/great_lakes_2026_11_05.json'
    if great_lakes.exists():tag=json.loads(great_lakes.read_text())['report_tag']
    historical=root/'config/research_migrations/illinois_2021_22_user_2026_11_05.json'
    if historical.exists():tag=json.loads(historical.read_text())['report_tag']
    south_central=root/'config/research_migrations/south_central_2026_11_05.json'
    if south_central.exists():tag=json.loads(south_central.read_text())['report_tag']
    southeast=root/'config/research_migrations/southeast_2026_11_05.json'
    if southeast.exists():tag=json.loads(southeast.read_text())['report_tag']
    eastern=root/'config/research_migrations/oh_ky_wv_va_2026_11_05.json'
    if eastern.exists():tag=json.loads(eastern.read_text())['report_tag']
    atlantic=root/'config/research_migrations/mid_atlantic_ct_2026_11_05.json'
    if atlantic.exists():tag=json.loads(atlantic.read_text())['report_tag']
    ny=root/'config/research_migrations/ny_allocation_followup_2026_11_06.json'
    if ny.exists():tag=json.loads(ny.read_text())['report_tag']
    new_england=root/'config/research_migrations/new_england_2026_11_06.json'
    if new_england.exists():tag=json.loads(new_england.read_text())['report_tag']
    prefix=PREFIX.replace('2026_11_04',tag)
    contents = {prefix+'_by_program.csv':csv_text(details), prefix+'_by_school.csv':csv_text(schools),
                prefix+'_by_state.csv':csv_text(summary)}
    contents.update(washington_exports(root, tables))
    for state, name in [('TX','texas'),('WA','washington')]:
        contents[f'data/reports/{name}_kindergarten_allocation_coverage_{tag}.csv'] = csv_text([r for r in schools if r['state_code']==state])
    return contents
