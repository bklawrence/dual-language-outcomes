"""Create and verify immutable national structural baselines from saved data.

The baseline is a derived product. It never edits the canonical evidence tables,
research identities, state inventories, archived reports or assessment layers.
"""
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tempfile

from .baseline_selection import (Selection, VARIABLES, academic_year, evidence_year,
    joined, known, later_period_mention, model_description, packed, select_rows)
from .contracts import typed_row
from .elementary_audit import elementary_scope, numeric_model
from .io import digest, read_csv

HOME = 'data/baselines'
INDEX = HOME + '/index.json'
EVIDENCE = ('states', 'schools', 'districts', 'identifiers', 'school_district_history',
    'programs', 'program_sites', 'program_configurations', 'program_languages',
    'program_status_history', 'allocation_schedules', 'instructional_allocations',
    'datasets', 'sources', 'evidence_claims')
AVAILABLE = {'documented', 'inferred', 'mixed_documented_and_inferred', 'provisional',
             'reported_model_requires_review', 'conflicting'}
RESOLVED = {'documented', 'inferred', 'mixed_documented_and_inferred'}
OFFICIAL_SCHOOL_NAMESPACES = {'NCES_school_id', 'CA_CDS', 'TX_TEA_campus_id',
    'WA_OSPI_school_code', 'WA_OSPI_school_organization_id', 'NYC_DBN', 'IL_state_school_id'}
KEYS = {
    'schools.csv': ['school_id'], 'source_vintage_schools.csv': ['school_id', 'selection_year'],
    'programmes.csv': ['site_id'], 'working_programmes_2025_26.csv': ['site_id'],
    'source_vintage_programmes.csv': ['site_id', 'selection_year'],
    'programme_fields.csv': ['site_id', 'selection_year', 'variable'],
    'field_evidence.csv': ['site_id', 'selection_year', 'variable', 'evidence_table', 'evidence_record_id'],
    'allocations.csv': ['schedule_id'], 'state_summary.csv': ['state_code'],
    'completeness_by_state.csv': ['cohort', 'state_code', 'selection_year', 'variable'],
    'completeness_by_language.csv': ['cohort', 'state_code', 'selection_year', 'reported_language', 'variable'],
    'completeness_by_school_level.csv': ['cohort', 'state_code', 'selection_year', 'school_level', 'variable'],
    'gaps_by_district.csv': ['cohort', 'state_code', 'selection_year', 'district_ids', 'variable'],
    'review_queue.csv': ['site_id', 'selection_year', 'variable'],
    'research_priorities.csv': ['state_code', 'selection_year', 'variable'],
    'allocation_coverage_by_state.csv': ['cohort', 'state_code', 'selection_year'],
    'allocation_school_units.csv': ['cohort', 'selection_year', 'allocation_school_unit_id'],
    'coverage_reconciliation.csv': ['state_code', 'selection_year'],
    'coverage_changes.csv': ['state_code', 'selection_year', 'school_ids'],
    'identity_review_queue.csv': ['state_code', 'grade_context_nces_candidate'],
    'screening_school_candidates.csv': ['school_id'],
}


def csv_text(rows, fields=None):
    fields = fields or (list(rows[0]) if rows else [])
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows({k: '' if r.get(k) is None else r.get(k, '') for k in fields} for r in rows)
    return out.getvalue()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def safe_id(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,100}', value):
        raise ValueError('Baseline ID must be a filename-safe identifier')
    return value


def freeze_inputs(root, destination, rules_path):
    """Snapshot the structural evidence and rules; no new data collection."""
    from .validation import load
    schema, tables = load(root)
    (destination / 'evidence').mkdir()
    snapshots = {}
    for name in EVIDENCE:
        relative = schema['$defs'][name]['x-path']
        target = 'evidence/' + name + '.csv'
        shutil.copyfile(root / relative, destination / target)
        snapshots[name] = dict(original_path=relative, snapshot_path=target,
            sha256=digest(destination / target), rows=len(tables[name]))
    (destination / 'evidence/schema.json').write_text(json_text(schema))
    shutil.copyfile(root / 'data/curated/manifest.json', destination / 'evidence/build_manifest.json')
    rules = json.loads(rules_path.read_text())
    (destination / 'rules.json').write_text(json_text(rules))
    profiles = [json.loads(p.read_text()) for p in sorted((root / 'config/states').glob('*.json'))]
    (destination / 'state_profiles.json').write_text(json_text(profiles))
    build_manifest = json.loads((root / 'data/curated/manifest.json').read_text())
    prior = [name for name in build_manifest.get('reports', {})
             if 'elementary_allocation_coverage_' in name and name.endswith('_reference_by_state.csv')]
    if len(prior) != 1:
        raise ValueError('Expected one current elementary coverage audit to reconcile')
    shutil.copyfile(root / prior[0], destination / 'evidence/previous_allocation_coverage.csv')
    previous_school_path = prior[0].replace('_reference_by_state.csv', '_by_school.csv')
    columns = ['state_code', 'reference_working_set_year', 'audit_school_id', 'research_school_ids',
               'school_name', 'elementary_denominator', 'has_numerical_allocation_model', 'numerical_model_labels']
    school_units = [r for r in read_csv(root / previous_school_path) if r['audit_scope'] == 'reference_working_set']
    (destination / 'evidence/previous_allocation_school_units.csv').write_text(csv_text(school_units, columns))
    shutil.copyfile(root / 'requirements-lock.txt', destination / 'requirements-lock.txt')
    # Retain the exact implementation for future rechecks after the live
    # pipeline evolves. These are source files, not installed dependencies.
    package = destination / 'pipeline/dl_outcomes'
    for path in sorted((root / 'src/dl_outcomes').rglob('*')):
        if path.suffix not in {'.py', '.json'}:
            continue
        target = package / path.relative_to(root / 'src/dl_outcomes')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return snapshots


def load_snapshot(directory):
    schema = json.loads((directory / 'evidence/schema.json').read_text())
    tables = {name: [] for name in schema['$defs']}
    for name in EVIDENCE:
        tables[name] = [typed_row(r, schema['$defs'][name])
                        for r in read_csv(directory / 'evidence' / (name + '.csv'))]
    return schema, tables


def official_identifiers(selection, sid, year):
    return [r for r in selection.identifiers[sid] if r['namespace'] in OFFICIAL_SCHOOL_NAMESPACES
        and not any(w in r['match_status'] for w in ('unverified', 'pending', 'not_resolved', 'provisional'))
        and not (r['valid_from_year'] and r['valid_from_year'] > year)]


def school_rows(selection, tables, target, *, states=None):
    hosts = {r['school_id'] for r in tables['program_sites']
             if r['school_id'] not in selection.excluded_schools
             and (states is None or selection.schools[r['school_id']]['state_code'] in states)}
    by_school = defaultdict(list)
    for site in tables['program_sites']:
        by_school[site['school_id']].append(site)
    districts = {r['district_id']: r for r in tables['districts']}
    result = []
    for sid in sorted(hosts):
        school = selection.schools[sid]
        grade = selection.school_grade(sid, target)
        scopes = []
        for site in by_school[sid]:
            field, _ = selection.select_field(site, 'programme_grade_scope', target)
            scopes.extend(json.loads(field['value_json']))
        if grade['school_level'] == 'unknown':
            levels = {elementary_scope(s) for s in scopes}
            if 'elementary' in levels:
                grade['school_level'] = 'elementary'
            elif levels and 'unknown' not in levels and len(levels) == 1:
                grade['school_level'] = next(iter(levels))
            if grade['school_level'] != 'unknown':
                grade['grade_context_status'] = 'programme_scope_proxy_not_official_campus_grades'
        if grade['school_level'] == 'unknown':
            schedules = selection.campus_allocations[sid] + [r for site in by_school[sid] for r in selection.allocations[site['site_id']]]
            supported = [r for r in schedules if not later_period_mention(r, target)
                and r['grade_support_status'] in {'EXPLICIT_GRADE', 'CAMPUS_GRADE_BAND_MODEL', 'DISTRICT_ENTRY_GRADE_MODEL', 'DISTRICT_GRADE_BAND_MODEL'}
                and elementary_scope(r['grade_scope']) == 'elementary']
            if supported:
                grade.update(school_level='elementary', grade_context_status='explicit_primary_policy_scope_proxy_not_official_campus_grades',
                    grade_context_record_ids=joined(r['_id'] for r in supported),
                    grade_context_years=joined(evidence_year(r) for r in supported))
        if grade['school_level'] == 'unknown' and selection.grade_claims[sid]:
            grade = selection.school_grade(sid, target, allow_later_context=True)
        memberships = selection.memberships[sid]
        exact = [r for r in memberships if r['school_year'] == target]
        undated = [r for r in memberships if not r['school_year']]
        older = [r for r in memberships if r['school_year'] and r['school_year'] < target]
        latest = max((r['school_year'] for r in older), default=None)
        use = exact or undated + [r for r in older if r['school_year'] == latest]
        ids = sorted({r['district_id'] for r in use})
        official = official_identifiers(selection, sid, target)
        campus = []
        for c in selection.school_claims[sid]:
            if c['attribute'] == 'reported_delivery_structure':
                value = json.loads(c['reported_value'])
                if value.get('structure_class') not in {None, '', 'unknown_campus_structure'}:
                    campus.append(dict(c, _id=c['claim_id'], _table='evidence_claims',
                        school_year=c['valid_from_year'], structure_class=value['structure_class']))
        selected_campus, campus_timing = select_rows(campus, target)
        result.append(dict(school_id=sid, state_code=school['state_code'], school_name=school['school_name'],
            target_school_year=selection.target, selection_year=target, identity_status=school['identity_status'],
            district_ids=joined(ids), district_names=joined(districts[d]['district_name'] for d in ids),
            district_identity_statuses=joined(districts[d]['identity_status'] for d in ids),
            district_membership_record_ids=joined(r['membership_id'] for r in use),
            programme_site_records=len(by_school[sid]), **grade,
            official_identifier_namespaces=joined(r['namespace'] for r in official),
            official_identifier_record_ids=joined(r['identifier_id'] for r in official),
            official_identifier_source_years=joined(r['valid_from_year'] for r in official),
            campus_structure_evidence_classes=joined(r['structure_class'] for r in selected_campus),
            campus_structure_record_ids=joined(r['_id'] for r in selected_campus),
            campus_structure_temporal_status=campus_timing,
            campus_structure_is_automatic_programme_assignment=0,
            grade_context_candidate_is_automatic_outcome_join=0,
            identity_interpretation='Existing research identity retained. Native identifiers retain source/review/year scope; names and grade-context matches do not create an outcome crosswalk.'))
    return result


def programme_rows(selection, tables, schools, target):
    school_index = {(r['school_id'], r['selection_year']): r for r in schools}
    rows, supplement, fields, evidence = [], [], [], []
    for site in sorted(tables['program_sites'], key=lambda r: r['site_id']):
        if site['school_id'] in selection.excluded_schools:
            continue
        program = selection.programs[site['program_id']]
        state = program['state_code']
        source_year = selection.rules['source_vintage_exceptions'].get(state, target)
        for year in sorted({target, source_year}):
            school = school_index[(site['school_id'], year)]
            chosen = {}
            for variable in VARIABLES:
                if variable == 'reference_operation':
                    field, detail = selection.operation_field(site, year)
                elif variable == 'elementary_allocation_model':
                    scopes = json.loads(chosen['programme_grade_scope']['value_json'])
                    field, detail = selection.select_allocations(site, year, school['school_level'], scopes)
                else:
                    field, detail = selection.select_field(site, variable, year)
                chosen[variable] = field; fields.append(field); evidence.extend(detail)
            op = selection.operation(site, year)
            config_years = {evidence_year(r) for r in selection.configs[site['site_id']]}
            listed = year in config_years
            working = (bool(op['confirmed_qualifying']) if state not in {'TX', 'OR', 'WA'}
                       else (True if state == 'TX' and year == source_year else listed))
            if op['operation_status'] in {'hand_coded_ended','hand_coded_moved'}:
                working = False
            row = dict(site_id=site['site_id'], program_id=site['program_id'], school_id=site['school_id'],
                state_code=state, school_name=school['school_name'], program_name=program['program_name'],
                target_school_year=target, selection_year=year, source_inventory_reference_year=source_year,
                is_target_year_row=int(year == target),
                in_confirmed_qualifying_cohort=int(bool(op['confirmed_qualifying'])),
                in_working_cohort=int(working),
                source_listing_in_selection_year=int(listed),
                **{k: v for k, v in op.items() if k != 'selected'},
                identity_status=program['identity_status'], programme_screening_status=program['screening_status'],
                school_level=school['school_level'], district_ids=school['district_ids'], district_names=school['district_names'],
                campus_only_schedule_count=len(selection.campus_allocations[site['school_id']]),
                population_model=None, delivery_structure=None, reported_instruction_languages=None,
                programme_grade_scopes=None, elementary_model_labels=None)
            for variable, column in [('population_model', 'population_model'), ('delivery_structure', 'delivery_structure'),
                                     ('instruction_languages', 'reported_instruction_languages'),
                                     ('programme_grade_scope', 'programme_grade_scopes')]:
                value = json.loads(chosen[variable]['value_json'])
                row[column] = joined(value) if chosen[variable]['value_status'] != 'conflicting' else None
                row[column + '_status'] = chosen[variable]['value_status']
                row[column + '_temporal_status'] = chosen[variable]['temporal_status']
            policies = json.loads(chosen['elementary_allocation_model']['value_json'])
            row['elementary_model_labels'] = joined(a['model_label'] for a in policies)
            row['elementary_model_labels_normalized'] = joined(a['model_label_normalized'] for a in policies)
            row['elementary_model_status'] = chosen['elementary_allocation_model']['value_status']
            row['elementary_model_selected_schedule_ids'] = joined(a['schedule_id'] for a in policies if a['schedule_id'])
            row['interpretation'] = ('One programme-site evidence group, not a verified distinct programme or student cohort. '
                'Selections retain source dates and scope; policies do not establish measured exposure.')
            (rows if year == target else supplement).append(row)
    return rows, supplement, fields, evidence


def completeness(programmes, supplement, fields, schools, tables, rules):
    field_index = {(r['site_id'], r['selection_year'], r['variable']): r for r in fields}
    groups = defaultdict(list)
    language_groups, level_groups, district_groups = defaultdict(list), defaultdict(list), defaultdict(list)
    gaps = []
    all_rows = programmes + supplement
    for p in all_rows:
        cohorts = []
        if p['selection_year'] == rules['target_school_year']:
            cohorts.append('all_inventory_reference_selections')
            if p['in_confirmed_qualifying_cohort']:
                cohorts.append('confirmed_qualifying_reference_year')
            if p['in_working_cohort']:
                cohorts.append('working_reference_year')
        if p['in_working_cohort'] and p['selection_year'] == p['source_inventory_reference_year']:
            cohorts.append('source_vintage_working_inventory')
        languages = json.loads(field_index[(p['site_id'], p['selection_year'], 'instruction_languages')]['value_json']) or ['not_reported']
        for variable in VARIABLES:
            f = field_index[(p['site_id'], p['selection_year'], variable)]
            for cohort in cohorts:
                groups[(cohort, p['state_code'], p['selection_year'], variable)].append(f)
                level_groups[(cohort, p['state_code'], p['selection_year'], p['school_level'], variable)].append(f)
                for language in languages:
                    language_groups[(cohort, p['state_code'], p['selection_year'], language, variable)].append(f)
                # A set of district memberships is retained as one group; it
                # does not expand one programme into multiple district samples.
                district_groups[(cohort, p['state_code'], p['selection_year'], p['district_ids'] or 'not_established',
                                 p['district_names'] or 'operator_or_unresolved', variable)].append(f)
            if p['in_working_cohort'] and p['selection_year'] == p['source_inventory_reference_year'] and f['applicability'] != 'not_applicable' and (f['value_status'] not in RESOLVED or f['applicability'] == 'unknown'):
                gaps.append(dict(state_code=p['state_code'], school_id=p['school_id'], school_name=p['school_name'],
                    site_id=p['site_id'], program_id=p['program_id'], selection_year=p['selection_year'], variable=variable,
                    issue='applicability_unresolved' if f['applicability'] == 'unknown' else f['value_status'],
                    applicability=f['applicability'], temporal_status=f['temporal_status'], district_names=p['district_names'],
                    source_ids=f['selected_source_ids'], evidence_ids=f['selected_evidence_ids'],
                    reason=f['reason']))
    def metric(values):
        counts = Counter(r['value_status'] for r in values if r['applicability'] == 'applicable')
        na = sum(r['applicability'] == 'not_applicable' for r in values)
        unknown = sum(r['applicability'] == 'unknown' for r in values)
        applicable = len(values) - na - unknown
        available = sum(counts[k] for k in AVAILABLE)
        resolved = sum(counts[k] for k in RESOLVED)
        return dict(unit='programme_site', total_records=len(values), not_applicable=na, applicability_unknown=unknown,
            applicable_records=applicable, with_selected_evidence=available,
            with_resolved_classification=resolved, documented=counts['documented'],
            inferred_or_mixed=counts['inferred'] + counts['mixed_documented_and_inferred'],
            provisional=counts['provisional'], reported_model_requires_review=counts['reported_model_requires_review'],
            conflicting=counts['conflicting'], later_only=counts['later_only'],
            not_reported=counts['not_reported'] + counts['requires_reference_year_review'],
            selected_evidence_pct=round(100 * available / applicable, 1) if applicable else None,
            resolved_classification_pct=round(100 * resolved / applicable, 1) if applicable else None,
            school_list_completeness='not_established')
    def summarize(groups, names):
        return [dict(zip(names, key), **metric(values)) for key, values in sorted(groups.items())]
    state_rows = summarize(groups, ['cohort', 'state_code', 'selection_year', 'variable'])
    # All 50 states appear even when screening has not yielded programme rows.
    present = {(r['cohort'], r['state_code'], r['selection_year'], r['variable']) for r in state_rows}
    for cohort in ['all_inventory_reference_selections', 'confirmed_qualifying_reference_year',
                   'working_reference_year', 'source_vintage_working_inventory']:
        for state in sorted(r['state_code'] for r in tables['states']):
            year = (rules['source_vintage_exceptions'].get(state, rules['target_school_year'])
                    if cohort == 'source_vintage_working_inventory' else rules['target_school_year'])
            for variable in VARIABLES:
                if (cohort, state, year, variable) not in present:
                    state_rows.append(dict(cohort=cohort, state_code=state,
                        selection_year=year, variable=variable, **metric([])))
    return dict(state=sorted(state_rows, key=lambda r: (r['cohort'], r['state_code'], r['selection_year'], r['variable'])),
        language=summarize(language_groups, ['cohort', 'state_code', 'selection_year', 'reported_language', 'variable']),
        level=summarize(level_groups, ['cohort', 'state_code', 'selection_year', 'school_level', 'variable']),
        district=summarize(district_groups, ['cohort', 'state_code', 'selection_year', 'district_ids', 'district_names', 'variable']),
        gaps=gaps)


def allocation_coverage(selection, programmes, supplement, schools, rules, tables):
    schools = {(r['school_id'], r['selection_year']): r for r in schools}
    by_school = defaultdict(list)
    for row in programmes + supplement:
        by_school[(row['school_id'], row['selection_year'])].append(row)
    results, details = [], []
    for cohort in ['confirmed_qualifying_reference_year', 'working_reference_year', 'source_vintage_working_inventory']:
        for state in tables['states']:
            code = state['state_code']
            year = rules['source_vintage_exceptions'].get(code, rules['target_school_year']) if cohort == 'source_vintage_working_inventory' else rules['target_school_year']
            selected = []
            for (sid, sy), ps in by_school.items():
                if sy != year or schools[(sid, sy)]['state_code'] != code:
                    continue
                eligible = [p for p in ps if p['in_confirmed_qualifying_cohort']] if cohort == 'confirmed_qualifying_reference_year' else [p for p in ps if p['in_working_cohort']]
                if eligible:
                    selected.append((schools[(sid, sy)], eligible))
            # Existing grade-context unit IDs are for school-count auditing,
            # not new durable identity matches or programme/outcome joins.
            units = defaultdict(list)
            for school, ps in selected:
                key = school['grade_context_nces_candidate'] or school['school_id']
                units[key].append((school, ps))
            counts = Counter()
            for unit_key, values in units.items():
                levels = {s['school_level'] for s, _ in values}
                level = 'elementary' if 'elementary' in levels else next(iter(levels)) if len(levels) == 1 else 'unknown'
                counts[level] += 1
                detail = dict(cohort=cohort, state_code=code, selection_year=year,
                    allocation_school_unit_id=code + ':' + unit_key,
                    school_ids=joined(s['school_id'] for s, _ in values),
                    school_names=joined(s['school_name'] for s, _ in values), school_level=level,
                    elementary_denominator=int(level == 'elementary'), has_reported_model=0,
                    model_evidence_record_ids='', excluded_later_model_record_ids='',
                    model_labels='', grade_context_statuses=joined(s['grade_context_status'] for s, _ in values))
                if level != 'elementary':
                    details.append(detail)
                    continue
                models = []
                for school, ps in values:
                    for p in ps:
                        models.extend(selection.allocations[p['site_id']])
                        # Annual WA labels are programme model evidence; this
                        # does not synthesize named shares or a K schedule.
                        models.extend(dict(r, reported_model_label=r.get('reported_model_label')) for r in selection.configs[p['site_id']] if numeric_model(r.get('reported_model_label')))
                    models.extend(selection.campus_allocations[school['school_id']])
                usable = [r for r in models if not later_period_mention(r, year)
                    and r.get('grade_support_status') not in {'SOURCE_DOES_NOT_SUPPORT_PROGRAM_GRADE_PERIOD', 'UNRECOVERED', 'EARLIER_GRADE_PROXY_NOT_TARGET_QUANTIFIED'}
                    and elementary_scope(r.get('grade_scope')) not in {'secondary_6_plus', 'preschool_only'}
                    and (numeric_model(r.get('reported_model_label')) or selection.shares[r['_id']])]
                # Respect explicit selections, notably Lyseth's former/current
                # policy, while retaining every schedule in the evidence tables.
                for p in [p for _, ps in values for p in ps]:
                    choice = selection.policy_choices(year).get(p['site_id'])
                    if choice:
                        usable = [r for r in usable if r.get('site_id') != p['site_id'] or r.get('schedule_id') == choice['selected_schedule_id']]
                if usable:
                    counts['with_model'] += 1
                detail.update(has_reported_model=int(bool(usable)),
                    model_evidence_record_ids=joined(r['_id'] for r in usable),
                    excluded_later_model_record_ids=joined(r['_id'] for r in models if later_period_mention(r, year)),
                    model_labels=joined(r.get('reported_model_label') for r in usable))
                details.append(detail)
            n = counts['elementary']
            results.append(dict(cohort=cohort, state_code=code, selection_year=year,
                unit='school_count_unit_existing_grade_context_grouping', inventory_school_units=len(units),
                elementary_school_units=n, with_reported_model=counts['with_model'],
                without_reported_model=n - counts['with_model'],
                reported_model_coverage_pct=round(100 * counts['with_model'] / n, 1) if n else None,
                secondary_units_excluded=counts['secondary_6_plus'], preschool_units_excluded=counts['preschool_only'],
                unresolved_school_grade_units=counts['unknown'],
                denominator_status='reviewed_working_inventory' if n else 'no_qualifying_elementary_units_in_this_cohort',
                statewide_school_list_completeness='not_established',
                interpretation='Model availability at any primary grade; not all strands, named shares or observed exposure. Source-year cohorts cannot be pooled as a 2025-26 census.'))
    return results, details


def render(tables, rules, profiles, prior_coverage=(), prior_school_units=()):
    selection = Selection(tables, rules)
    target = rules['target_school_year']
    schools = school_rows(selection, tables, target)
    supplement_schools = [r for state, year in sorted(rules['source_vintage_exceptions'].items())
                         for r in school_rows(selection, tables, year, states={state})]
    all_schools = schools + supplement_schools
    programmes, supplement, fields, evidence = programme_rows(selection, tables, all_schools, target)
    audits = completeness(programmes, supplement, fields, schools, tables, rules)
    coverage, coverage_schools = allocation_coverage(selection, programmes, supplement, all_schools, rules, tables)
    source_ids = {r['source_id']: r for r in tables['sources']}
    selected_schedules = defaultdict(set)
    for f in fields:
        if f['selection_year'] == target and f['variable'] == 'elementary_allocation_model':
            for schedule_id in filter(None, f['selected_evidence_ids'].split(' | ')):
                selected_schedules[schedule_id].add(f['site_id'])
    allocated = []
    for a in tables['allocation_schedules']:
        if a['school_id'] in selection.excluded_schools:
            continue
        metadata = selection.allocation_claims.get(a['schedule_id'], {})
        allocated.append(dict(a, attributed_unit='programme_site' if a['site_id'] else 'campus_only_not_a_strand_assignment',
            source_url=source_ids[a['source_id']]['source_url'],
            **{k: packed(v) if isinstance(v, dict) else v for k, v in model_description(
                a, selection.shares[a['schedule_id']], rules['language_aliases']).items() if k != 'schedule_status'},
            classification_method=metadata.get('classification_method'), service_scope=metadata.get('service_scope'),
            source_passage=metadata.get('source_passage'),
            selected_for_target_programmes=joined(selected_schedules[a['schedule_id']])))
    profiles = {r['state_code']: r for r in profiles}
    state_rows = []
    for state in tables['states']:
        code = state['state_code']; ps = [p for p in programmes if p['state_code'] == code]
        ss = [s for s in schools if s['state_code'] == code]
        source_year = rules['source_vintage_exceptions'].get(code, target)
        state_rows.append(dict(state_code=code, state_name=state['state_name'], target_school_year=target,
            source_inventory_reference_year=source_year, reference_year_alignment='aligned' if source_year == target else 'separate_source_vintage_supplement',
            research_status=profiles[code]['collection_status'], programme_site_evidence_records=len(ps),
            research_school_identities=len(ss), confirmed_qualifying_reference_sites=sum(p['in_confirmed_qualifying_cohort'] for p in ps),
            working_reference_sites=sum(p['in_working_cohort'] for p in ps),
            screening_school_candidates=sum(s['state_code'] == code and s['school_id'] not in selection.excluded_schools and s['school_id'] not in {s['school_id'] for s in ss} for s in tables['schools']),
            historical_school_grade_context_only=sum(bool(s['grade_context_nces_candidate']) for s in ss),
            schools_with_official_native_identifier=sum(bool(s['official_identifier_record_ids']) for s in ss),
            statewide_school_list_completeness='not_established',
            interpretation='No programme rows or zero eligible rows means no verified record in this cohort, not statewide programme absence.'))
    alias_groups = defaultdict(list)
    for s in schools:
        if s['grade_context_nces_candidate']:
            alias_groups[(s['state_code'], s['grade_context_nces_candidate'])].append(s)
    aliases = [dict(state_code=state, grade_context_nces_candidate=nces,
        school_ids=joined(s['school_id'] for s in values), school_names=joined(s['school_name'] for s in values),
        review_status='possible_alias_or_colocation_not_automatically_merged',
        outcome_join_authorized=0) for (state, nces), values in sorted(alias_groups.items()) if len(values) > 1]
    priorities = [dict(state_code=r['state_code'], selection_year=r['selection_year'], variable=r['variable'],
        applicable_programme_site_records=r['applicable_records'],
        records_needing_documentation_or_review=r['applicable_records'] - r['with_resolved_classification'] + r['applicability_unknown'],
        applicability_unknown=r['applicability_unknown'],
        not_reported=r['not_reported'], conflicting=r['conflicting'], later_only=r['later_only'],
        provisional_or_model_review=r['provisional'] + r['reported_model_requires_review'],
        resolved_classification_pct=r['resolved_classification_pct'],
        reference_year_issue=int(r['selection_year'] != target),
        ranking_basis='Descending unresolved record count; research yield and language/model representation require later review, not an invented probability score.')
        for r in audits['state'] if r['cohort'] == 'source_vintage_working_inventory']
    priorities.sort(key=lambda r: (-r['records_needing_documentation_or_review'], r['state_code'], r['variable']))
    old_coverage = {r['state_code']: r for r in prior_coverage}
    reconciled = []
    for r in coverage:
        if r['cohort'] != 'source_vintage_working_inventory':
            continue
        old = old_coverage.get(r['state_code'], {})
        previous_n = int(old['elementary_school_units']) if old else None
        previous_m = int(old['elementary_schools_with_numerical_model']) if old else None
        reconciled.append(dict(state_code=r['state_code'], selection_year=r['selection_year'],
            prior_elementary_units=previous_n, baseline_elementary_units=r['elementary_school_units'],
            prior_with_model=previous_m, baseline_with_model=r['with_reported_model'],
            denominator_delta=r['elementary_school_units'] - previous_n if old else None,
            numerator_delta=r['with_reported_model'] - previous_m if old else None,
            interpretation='Consolidation explicitly excludes later-year policy and retains campus-grade proxy/source dates. No new research or change to original reports. School-level evidence explains differences.'))
    old_units = {sid: r for r in prior_school_units for sid in r['research_school_ids'].split(' | ')}
    changes = []
    for r in coverage_schools:
        if r['cohort'] != 'source_vintage_working_inventory':
            continue
        old = next((old_units[sid] for sid in r['school_ids'].split(' | ') if sid in old_units), None)
        if old and (int(old['elementary_denominator']), int(old['has_numerical_allocation_model'])) != (r['elementary_denominator'], r['has_reported_model']):
            changes.append(dict(state_code=r['state_code'], selection_year=r['selection_year'],
                school_ids=r['school_ids'], school_names=r['school_names'],
                prior_elementary_denominator=int(old['elementary_denominator']),
                baseline_elementary_denominator=r['elementary_denominator'],
                prior_has_model=int(old['has_numerical_allocation_model']), baseline_has_model=r['has_reported_model'],
                excluded_later_model_record_ids=r['excluded_later_model_record_ids'],
                reason='Later-year evidence is retained but does not establish the earlier reference-year policy.'
                       if r['excluded_later_model_record_ids'] else 'Dated grade/source scope differs; inspect frozen evidence and the school-unit audit.'))
    contents = {'schools.csv': csv_text(schools), 'programmes.csv': csv_text(programmes),
        'source_vintage_schools.csv': csv_text(supplement_schools, list(schools[0])),
        'working_programmes_2025_26.csv': csv_text([p for p in programmes if p['in_working_cohort']], list(programmes[0])),
        'source_vintage_programmes.csv': csv_text(supplement, list(programmes[0])),
        'programme_fields.csv': csv_text(fields), 'field_evidence.csv': csv_text(evidence),
        'allocations.csv': csv_text(allocated), 'state_summary.csv': csv_text(state_rows),
        'completeness_by_state.csv': csv_text(audits['state']), 'completeness_by_language.csv': csv_text(audits['language']),
        'completeness_by_school_level.csv': csv_text(audits['level']), 'gaps_by_district.csv': csv_text(audits['district']),
        'review_queue.csv': csv_text(audits['gaps']), 'research_priorities.csv': csv_text(priorities),
        'allocation_coverage_by_state.csv': csv_text(coverage),
        'allocation_school_units.csv': csv_text(coverage_schools),
        'coverage_reconciliation.csv': csv_text(reconciled),
        'coverage_changes.csv': csv_text(changes, ['state_code', 'selection_year', 'school_ids', 'school_names',
            'prior_elementary_denominator', 'baseline_elementary_denominator', 'prior_has_model', 'baseline_has_model',
            'excluded_later_model_record_ids', 'reason']),
        'identity_review_queue.csv': csv_text(aliases, ['state_code', 'grade_context_nces_candidate', 'school_ids', 'school_names', 'review_status', 'outcome_join_authorized']),
        'screening_school_candidates.csv': csv_text([r for r in tables['schools'] if r['school_id'] not in selection.excluded_schools and r['school_id'] not in {s['school_id'] for s in schools}], list(tables['schools'][0]))}
    summary = dict(states=len(state_rows), programme_site_records=len(programmes), school_research_identities=len(schools),
        working_reference_sites=sum(p['in_working_cohort'] for p in programmes),
        confirmed_qualifying_reference_sites=sum(p['in_confirmed_qualifying_cohort'] for p in programmes),
        source_vintage_supplement_records=len(supplement), field_selection_rows=len(fields),
        identity_groups_needing_review=len(aliases), new_source_collection=False, new_proficiency_collection=False)
    summary['allocation_coverage_changed_school_units'] = len(changes)
    summary['allocation_coverage_changes_by_state'] = dict(sorted(Counter(r['state_code'] for r in changes).items()))
    contents['summary.json'] = json_text(summary)
    contents['table_contracts.json'] = json_text({name: dict(primary_key=key,
        columns=next(csv.reader(io.StringIO(contents[name]))),
        identifier_and_school_year_types='string; preserve leading zeros',
        null_encoding='empty CSV cell; JSON values retain explicit null/empty lists') for name, key in KEYS.items()})
    audit_rendered(contents, tables, rules)
    return contents, summary


def audit_rendered(contents, tables, rules):
    """Check grain, scope, provenance and balanced denominators independently."""
    parsed = {name: list(csv.DictReader(io.StringIO(contents[name]))) for name in KEYS}
    for name, keys in KEYS.items():
        seen = set()
        for row in parsed[name]:
            key = tuple(row[k] for k in keys)
            if key in seen:
                raise ValueError('Duplicate national baseline grain: ' + name + '/' + str(key))
            seen.add(key)
    from .study_scope import excluded_school_ids
    excluded=excluded_school_ids(tables)
    sites = {r['site_id']: r for r in tables['program_sites'] if r['school_id'] not in excluded}
    schools = {r['school_id'] for r in sites.values()}
    if {r['site_id'] for r in parsed['programmes.csv']} != set(sites):
        raise ValueError('National baseline lost or invented programme sites')
    if {r['school_id'] for r in parsed['schools.csv']} != schools:
        raise ValueError('National baseline lost or invented programme-host school identities')
    statuses = defaultdict(list)
    for r in tables['program_status_history']:
        statuses[(r['site_id'], r['school_year'])].append(r)
    for row in parsed['programmes.csv'] + parsed['source_vintage_programmes.csv']:
        site = sites[row['site_id']]
        if row['school_id'] != site['school_id'] or row['program_id'] != site['program_id']:
            raise ValueError('National baseline changes a programme/site/school identity link')
        if row['in_confirmed_qualifying_cohort'] == '1':
            valid = [r for r in statuses[(row['site_id'], row['selection_year'])]
                     if r['operating_status'] == 'confirmed_' + row['selection_year'].replace('-', '_')
                     and (r['eligibility_status'] or '').startswith('documented_')]
            if not valid:
                raise ValueError('National baseline invented reference-year operation/eligibility')
    field_keys = {(r['site_id'], r['selection_year'], r['variable']) for r in parsed['programme_fields.csv']}
    expected = {(r['site_id'], r['selection_year'], variable)
                for r in parsed['programmes.csv'] + parsed['source_vintage_programmes.csv'] for variable in VARIABLES}
    if field_keys != expected:
        raise ValueError('National baseline field grid is incomplete')
    canonical = {}
    for table, key in [('program_configurations', 'configuration_id'), ('program_languages', 'language_record_id'),
                       ('program_status_history', 'status_id'), ('allocation_schedules', 'schedule_id')]:
        canonical.update({(table, r[key]): r for r in tables[table]})
    sources = {r['source_id']: r for r in tables['sources']}
    selected = defaultdict(set)
    for row in parsed['field_evidence.csv']:
        key = (row['site_id'], row['selection_year'], row['variable'])
        record = canonical.get((row['evidence_table'], row['evidence_record_id']))
        if key not in field_keys or not record or record['site_id'] != row['site_id']:
            raise ValueError('National baseline evidence is missing or attributed across sites')
        if row['source_id'] != record['source_id'] or row['source_url'] != sources[record['source_id']]['source_url']:
            raise ValueError('National baseline evidence changed source attribution')
        if row['selection_role'] == 'selected':
            if later_period_mention(record, row['selection_year']):
                raise ValueError('National baseline backdates later-year evidence')
            selected[key].add(row['evidence_record_id'])
    for row in parsed['programme_fields.csv']:
        key = (row['site_id'], row['selection_year'], row['variable'])
        if selected[key] != set(filter(None, row['selected_evidence_ids'].split(' | '))):
            raise ValueError('National baseline selected-field provenance is incomplete')
        if row['value_status'].startswith('not_applicable_') and json.loads(row['value_json']):
            raise ValueError('National baseline assigned an elementary model to an inapplicable phase')
    for row in parsed['completeness_by_state.csv']:
        categories = sum(int(row[k]) for k in ['documented', 'inferred_or_mixed', 'provisional',
            'reported_model_requires_review', 'conflicting', 'later_only', 'not_reported'])
        if categories != int(row['applicable_records']) or int(row['applicable_records']) + int(row['not_applicable']) + int(row['applicability_unknown']) != int(row['total_records']):
            raise ValueError('National baseline completeness denominator is not balanced')
    if {r['state_code'] for r in parsed['state_summary.csv']} != {r['state_code'] for r in tables['states']}:
        raise ValueError('National baseline does not retain all states, including screening-only states')
    for row in parsed['allocation_coverage_by_state.csv']:
        if int(row['with_reported_model']) + int(row['without_reported_model']) != int(row['elementary_school_units']):
            raise ValueError('National baseline elementary allocation denominator is not balanced')
    for row in parsed['schools.csv'] + parsed['source_vintage_schools.csv']:
        if row['grade_context_candidate_is_automatic_outcome_join'] != '0':
            raise ValueError('National baseline promoted a grade-context match into an outcome crosswalk')


def create(root, baseline_id, rules_path):
    from .validation import validate
    root = root.resolve(); baseline_id = safe_id(baseline_id)
    rules_path = rules_path if rules_path.is_absolute() else root / rules_path
    rules = json.loads(rules_path.read_text())
    if rules['baseline_id'] != baseline_id or not academic_year(rules['target_school_year']):
        raise ValueError('Baseline ID/reference year differs from its versioned rules')
    destination = root / HOME / baseline_id
    if destination.exists():
        raise ValueError('Frozen baseline already exists; check it or choose a new version. It is never overwritten.')
    index_path = root / INDEX
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    if baseline_id in index:
        raise ValueError('Baseline index already contains this immutable version')
    validate(root)
    parent = root / HOME; parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.baseline-', dir=parent) as temporary:
        stage = Path(temporary)
        snapshots = freeze_inputs(root, stage, rules_path)
        rules = json.loads((stage / 'rules.json').read_text())
        _, tables = load_snapshot(stage)
        contents, summary = render(tables, rules, json.loads((stage / 'state_profiles.json').read_text()),
                                   read_csv(stage / 'evidence/previous_allocation_coverage.csv'),
                                   read_csv(stage / 'evidence/previous_allocation_school_units.csv'))
        for name, text in contents.items():
            (stage / name).write_text(text)
        (stage / 'README.md').write_text(readme(rules, summary))
        files = {p.relative_to(stage).as_posix(): dict(sha256=digest(p), bytes=p.stat().st_size)
                 for p in sorted(stage.rglob('*')) if p.is_file()}
        original = json.loads((root / 'data/curated/manifest.json').read_text())
        untouched = {path: info for path, info in original['outputs'].items()
                     if path not in {s['original_path'] for s in snapshots.values()} and '/coverage/' not in path}
        if len(untouched) != 12:
            raise ValueError('Expected twelve preserved assessment/context output receipts')
        manifest = dict(baseline_id=baseline_id, rules_version=rules['rules_version'],
            snapshot_date=rules['snapshot_date'], target_school_year=rules['target_school_year'],
            canonical_build_id=original['build_id'], canonical_data_base_git_revision=original['base_git_revision'],
            evidence_tables=snapshots, preserved_assessment_context_output_receipts=untouched,
            files=files, summary=summary, completeness='partial_inventory_not_a_national_census')
        (stage / 'manifest.json').write_text(json_text(manifest))
        shutil.copytree(stage, destination)
    index[baseline_id] = dict(manifest_sha256=digest(destination / 'manifest.json'),
        target_school_year=rules['target_school_year'], snapshot_date=rules['snapshot_date'])
    index_path.write_text(json_text(index))
    return dict(baseline_id=baseline_id, directory=str(destination.relative_to(root)), **summary)


def check(root, baseline_id, *, reproduce=False):
    root = root.resolve(); baseline_id = safe_id(baseline_id)
    directory = root / HOME / baseline_id
    index = json.loads((root / INDEX).read_text())
    if baseline_id not in index or digest(directory / 'manifest.json') != index[baseline_id]['manifest_sha256']:
        raise ValueError('Frozen baseline manifest differs from its registered checksum')
    manifest = json.loads((directory / 'manifest.json').read_text())
    for relative, info in manifest['files'].items():
        path = directory / relative
        if not path.is_file() or digest(path) != info['sha256']:
            raise ValueError('Frozen baseline file changed: ' + relative)
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if actual != set(manifest['files']) | {'manifest.json'}:
        raise ValueError('Frozen baseline contains an unregistered file or is incomplete')
    if reproduce:
        _, tables = load_snapshot(directory)
        contents, summary = render(tables, json.loads((directory / 'rules.json').read_text()),
                                   json.loads((directory / 'state_profiles.json').read_text()),
                                   read_csv(directory / 'evidence/previous_allocation_coverage.csv'),
                                   read_csv(directory / 'evidence/previous_allocation_school_units.csv'))
        for name, expected in contents.items():
            if (directory / name).read_text() != expected:
                raise ValueError('Frozen baseline is not reproducible with these rules: ' + name)
        if summary != manifest['summary']:
            raise ValueError('Frozen baseline summary differs from reproduced results')
    return dict(baseline_id=baseline_id, status='PASS', reproduced=reproduce, **manifest['summary'])


def check_registered(root):
    if not (root / INDEX).exists():
        return []
    return [check(root, name) for name in sorted(json.loads((root / INDEX).read_text()))]


def readme(rules, summary):
    return f'''# National structural baseline v1

Frozen {rules['snapshot_date']} for a **{rules['target_school_year']} target reference**. This is a partial research inventory covering all 50 state research passes, not a national school census or a participant dataset. It contains {summary['programme_site_records']:,} programme-site evidence groups and {summary['school_research_identities']:,} existing school research identities. These are provisional research units, not verified counts of distinct programmes.

Start with [programmes.csv](programmes.csv), [schools.csv](schools.csv) and [state_summary.csv](state_summary.csv). [working_programmes_2025_26.csv](working_programmes_2025_26.csv) contains the working reference cohort; the `in_confirmed_qualifying_cohort` flag distinguishes explicit operation/eligibility reviews from source-year listings. Candidates, future phases and historical records remain in the full inventory.

Texas's source working reference is 2023–24 and Oregon's is 2026–27. Their [{summary['source_vintage_supplement_records']:,} source-vintage rows](source_vintage_programmes.csv) are separate from the 2025–26 selections. They must not be stacked and described as a single-year census. Unknown reference-year operation is not programme absence.

Each row in [programme_fields.csv](programme_fields.csv) is **programme site × selection year × variable**. Source dates, evidence IDs, conflicts, inference and provisional classifications are explicit. [field_evidence.csv](field_evidence.csv) records selected and excluded evidence, including later-only observations. An undated or older policy compatible with programme continuity is not a newly observed annual configuration. Retrieval dates never determine policy validity. The versioned [rules](rules.json) and original source records document the choices.

[allocations.csv](allocations.csv) preserves grade/service scopes, percentage bases, source passages and all historical schedules. A programme is not reduced to a single entry ratio. Named-language percentages remain in [the original allocation-language table](evidence/instructional_allocations.csv). Campus-only policies are not silently assigned to each language strand. Secondary-only elementary entry models are not applicable; campuses serving any K–5 grade count as elementary-containing. Source model availability and a resolved, language-specific policy are separate measures.

Model notation is standardized in separate normalized columns. With two explicitly named languages including English, the normalized ratio is partner-language/English; otherwise a numeric source ratio retains an explicitly unresolved language order. The raw label and language shares remain unchanged. Core/classroom scope, annual model-only labels and unspecified instructional denominators are distinct basis classes.

School-grade context keeps its own source year. If only a later campus directory is available, it is explicitly marked as a grade-context proxy, not a reference-year configuration. Later **allocation policies** remain excluded from earlier selections. [Coverage reconciliation](coverage_reconciliation.csv) and [school-level changes](coverage_changes.csv) compare this baseline with the saved prior audit; {summary['allocation_coverage_changed_school_units']} school-unit changes are listed individually. The original evidence and earlier reports are unchanged. [Source-vintage school rows](source_vintage_schools.csv) retain the corresponding grade/identifier/membership context. Campus-level delivery reports remain school context and are not assigned to every language strand.

The [state](completeness_by_state.csv), [language](completeness_by_language.csv), [school-level](completeness_by_school_level.csv) and [district](gaps_by_district.csv) audits distinguish documented, inferred, provisional, conflicting, later-only, missing and not-applicable values. Their structural-variable denominator is programme sites. [Allocation coverage](allocation_coverage_by_state.csv) instead counts schools, grouping only by the existing grade-context audit units; that grouping does not authorize outcome joins. Language groups overlap for multilingual programmes and must not be summed as independent samples.

Unknown elementary applicability is tallied separately and does not inflate the applicable denominator. Availability of selected evidence differs from a resolved classification: provisional labels, conflicts and reported models needing review are shown separately. An inferred classification retains its inference status even when usable under the research rules.

[Research priorities](research_priorities.csv) rank unresolved record counts in the source working inventories; [review_queue.csv](review_queue.csv) lists the underlying records. Percentages describe the reviewed inventory, not completeness of statewide school lists. Zero denominators are marked explicitly, including screening-only states. No probability of research success or arbitrary confidence score is invented.

Existing canonical identities are preserved. [Native identifier records](evidence/identifiers.csv) retain source/review/year scope. Grade-context NCES candidates are **not automatic outcome crosswalks**. [Possible aliases/co-locations](identity_review_queue.csv) need review before any additional merging; no name-based merges were performed. [Screening school candidates](screening_school_candidates.csv) remain separate from programme hosts.

The [table contracts](table_contracts.json) document CSV keys and columns. The [evidence folder](evidence/) freezes all structural source records and histories, including the source catalogue and claims. Original web/PDF archives remain at the paths and hashes in that catalogue; they are not duplicated here. The [manifest](manifest.json) pins the original table paths, hashes, rules, code and provenance. The [pipeline](pipeline/dl_outcomes/) preserves the implementation. Twelve assessment/context output receipts remain unchanged; no proficiency, demographic, EL-exit or SEDA data were collected.

From the repository root, verify with:

```bash
dl-outcomes baseline check {rules['baseline_id']} --reproduce
```

The command reads the frozen evidence, not updated live tables. For future historical reproduction after the main implementation changes, use the frozen package with `PYTHONPATH=data/baselines/{rules['baseline_id']}/pipeline python -m dl_outcomes.cli baseline check {rules['baseline_id']} --reproduce`. Install this baseline's [pinned core requirements](requirements-lock.txt) first. Creating a baseline with an existing ID fails; later research belongs in a new baseline version.
'''
