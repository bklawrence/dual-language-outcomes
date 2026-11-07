"""Conservative, field-specific selections from frozen structural observations.

Selections describe evidence for a chosen reference, not observed annual student
exposure. All input observations survive in the baseline evidence snapshot.
"""
from collections import defaultdict
import json
import re

from .elementary_audit import elementary_scope, elementary_span, numeric_model
from .policy_selection import current_policy_choices
from .evidence_scope import reference_bounds, scoped_row, within_reviewed_reference

MISSING = {'', 'unknown', 'not_reported', 'not reported', 'none', 'n/a', '.', 'other'}
REJECTED_GRADE = {'SOURCE_DOES_NOT_SUPPORT_PROGRAM_GRADE_PERIOD', 'UNRECOVERED',
                  'EARLIER_GRADE_PROXY_NOT_TARGET_QUANTIFIED'}
VARIABLES = ('instruction_languages', 'population_model', 'delivery_structure',
             'programme_grade_scope', 'elementary_allocation_model', 'reference_operation')


def joined(values):
    return ' | '.join(sorted({str(v) for v in values if v is not None and v != ''}))


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def academic_year(value):
    value = str(value or '').replace('–', '-').strip()
    if re.fullmatch(r'\d{4}-\d{2}', value) and int(value[-2:]) == (int(value[:4]) + 1) % 100:
        return value
    return None


def evidence_year(row):
    # Only a typed year or a complete raw-year value is normalized. A year
    # inside a narrative remains narrative; it cannot become annual validity.
    return row.get('school_year') or row.get('valid_from_year') or academic_year(row.get('evidence_period_raw'))


def later_period_mention(row, year):
    # A reviewed use bound is separate from a source/policy date. Newly
    # adjudicated undated evidence must not silently fill an older baseline.
    if row.get('_earliest_reviewed_selection_year', '') > year:
        return True
    if evidence_year(row):
        return evidence_year(row) > year
    text = row.get('evidence_period_raw') or ''
    # Some saved context explicitly distinguishes its undated school-grade
    # statement from a later programme-directory year. That year is not the
    # applicability of the grade statement itself.
    text = re.split(r'\bseparate from\b', text, flags=re.I)[0]
    mentioned = {academic_year(s) for s in re.findall(r'\b20\d{2}[-–]\d{2}\b', text)} - {None}
    return bool(mentioned and min(mentioned) > year)


def known(value):
    return value is not None and str(value).strip().casefold() not in MISSING


def eligible_value(row, field):
    value = row.get(field)
    if not known(value):
        return False
    if field == 'grade_scope':
        return not str(value).casefold().startswith(('not reported', 'not uniformly reported'))
    return True


def select_rows(rows, year, *, override_ids=()):
    usable = [r for r in rows if not later_period_mention(r, year) and within_reviewed_reference(r, year)]
    if override_ids:
        selected = [r for r in usable if r['_id'] in override_ids]
        if {r['_id'] for r in selected} != set(override_ids):
            raise ValueError('A baseline adjudication selects missing or later evidence')
        return selected, 'reviewed_field_adjudication'
    reviewed = [r for r in usable if r.get('program_kind') == 'reviewed_structural_selection_with_separate_source_dates']
    if reviewed:
        return reviewed, 'existing_reviewed_structural_selection'
    exact = [r for r in usable if evidence_year(r) == year]
    if exact:
        return exact, 'exact_selection_year'
    undated = [r for r in usable if not evidence_year(r)]
    earlier = [r for r in usable if evidence_year(r) and evidence_year(r) < year]
    latest = max((evidence_year(r) for r in earlier), default=None)
    selected = undated + [r for r in earlier if evidence_year(r) == latest]
    if undated and earlier:
        timing = 'undated_and_latest_earlier_not_new_annual_observations'
    elif undated:
        timing = 'undated_not_an_annual_observation'
    elif earlier:
        timing = 'earlier_source_not_an_annual_observation'
    elif rows and any(r.get('_latest_reviewed_selection_year','9999-99')<year for r in rows):
        timing = 'outside_reviewed_reference_window'
    elif rows:
        timing = 'later_only'
    else:
        timing = 'not_reported'
    return selected, timing


def grade_set(text):
    """Only simple explicit grade bands support overlap adjudication."""
    text = (text or '').strip().replace('–', '-').replace('—', '-').upper()
    match = re.fullmatch(r'(?:GRADES?\s+)?(PK|PRE-K|K|KG|\d{1,2})(?:\s*-\s*(K|\d{1,2}))?', text)
    if not match:
        return None
    def number(s):
        return -1 if s in {'PK', 'PRE-K'} else 0 if s in {'K', 'KG'} else int(s)
    low, high = number(match[1]), number(match[2] or match[1])
    return set(range(low, high + 1)) if -1 <= low <= high <= 12 else None


def model_description(row, shares, aliases):
    """Normalize notation without inferring missing instructional languages."""
    named = {}
    for value in shares:
        language = aliases.get(value['language_name'], value['language_name'])
        if language in named:
            raise ValueError('Language aliases collide within one allocation schedule')
        named[language] = value['instruction_share_pct']
    raw = row.get('reported_model_label') or ''
    normalized, order = None, 'not_established'
    if len(named) == 2 and 'English' in named:
        partner = next(k for k in named if k != 'English')
        normalized = f'{named[partner]:g}/{named["English"]:g}'
        order = 'named_partner_then_English'
    elif re.fullmatch(r'\s*\d{1,3}(?:\.\d+)?(?:\s*[/:-]\s*\d{1,3}(?:\.\d+)?){1,3}\s*', raw) and numeric_model(raw):
        normalized = '/'.join(f'{float(v):g}' for v in re.findall(r'\d+(?:\.\d+)?', raw))
        order = 'source_order_without_inferred_language_assignment'
    basis = (row.get('percentage_basis') or '').casefold()
    if 'annual_programme_model_label' in basis:
        basis_class = 'annual_programme_model_label'
    elif 'classroom' in basis:
        basis_class = 'classroom_instruction_scope'
    elif 'core' in basis or 'academic' in basis:
        basis_class = 'academic_core_instruction_scope'
    elif 'researcher_estimate' in basis:
        basis_class = 'researcher_estimated_scheduled_instruction'
    elif 'directory' in basis:
        basis_class = 'directory_reported_model'
    else:
        basis_class = 'instructional_policy_denominator_not_fully_specified'
    return dict(named_language_shares=named, model_label_normalized=normalized,
        model_label_language_order=order, percentage_basis_class=basis_class,
        schedule_status=row.get('schedule_status'))


class Selection:
    def __init__(self, tables, rules):
        self.tables, self.rules = tables, rules
        self.target = rules['target_school_year']
        self.sources = {r['source_id']: r for r in tables['sources']}
        self.programs = {r['program_id']: r for r in tables['programs']}
        self.schools = {r['school_id']: r for r in tables['schools']}
        self.configs, self.languages, self.statuses, self.allocations = [defaultdict(list) for _ in range(4)]
        self.campus_allocations, self.memberships, self.identifiers = [defaultdict(list) for _ in range(3)]
        self.grade_claims, self.school_claims = defaultdict(list), defaultdict(list)
        self.allocation_claims = {}
        self.shares = defaultdict(list)
        scopes = reference_bounds(tables)
        ceilings = reference_bounds(tables, latest=True)
        def scoped(table, key, row):
            return scoped_row(table,key,row,scopes,ceilings)
        for table, index, key in [('program_configurations', self.configs, 'configuration_id'),
                                  ('program_languages', self.languages, 'language_record_id'),
                                  ('program_status_history', self.statuses, 'status_id'),
                                  ('allocation_schedules', self.allocations, 'schedule_id')]:
            for row in tables[table]:
                value = dict(scoped(table,key,row), _id=row[key], _table=table)
                if table == 'allocation_schedules' and not row['site_id']:
                    self.campus_allocations[row['school_id']].append(value)
                else:
                    index[row['site_id']].append(value)
        for r in tables['instructional_allocations']:
            self.shares[r['schedule_id']].append(r)
        for r in tables['school_district_history']:
            self.memberships[r['school_id']].append(r)
        for r in tables['identifiers']:
            if r['entity_type'] == 'school':
                self.identifiers[r['entity_id']].append(r)
        for c in tables['evidence_claims']:
            if c['attribute'] == 'allocation_source_selection':
                self.allocation_claims[c['entity_id']] = json.loads(c['reported_value'])
            if c['entity_type'] == 'school':
                c = scoped('evidence_claims','claim_id',c)
                self.school_claims[c['entity_id']].append(c)
                if c['attribute'] == 'elementary_audit_school_grade_context':
                    self.grade_claims[c['entity_id']].append(dict(c, _id=c['claim_id'],
                        school_year=c['valid_from_year'], _table='evidence_claims'))
        self.overrides = {(r['site_id'], r['selection_year'], r['variable']): r
                          for r in rules.get('field_overrides', [])}
        for claim in tables['evidence_claims']:
            if claim['attribute'] == 'reviewed_structural_field_selection':
                review = json.loads(claim['reported_value'])
                key = (review['site_id'],review['selection_year'],review['variable'])
                if key in self.overrides and set(self.overrides[key]['evidence_ids']) != set(review['evidence_ids']):
                    raise ValueError('Conflicting explicit field adjudications')
                self.overrides[key] = review
        from .hand_coding import selection_overrides, allocation_overrides
        # Manual decisions explicitly select a field for a reference year.
        # Retain prior machine/researcher observations and all previous reviews.
        self.overrides.update(selection_overrides(tables))
        self.allocation_reviews = allocation_overrides(tables)
        self.manual_allocation_ids = {i for reviews in self.allocation_reviews.values()
                                      for review in reviews for i in review['evidence_ids']}
        from .review_events import event_index
        self.program_events = event_index(tables)
        self.policy_cache = {}

    def policy_choices(self, year):
        if year not in self.policy_cache:
            self.policy_cache[year] = current_policy_choices(self.tables, year)
        return self.policy_cache[year]

    def school_grade(self, sid, year, *, allow_later_context=False):
        rows = self.grade_claims[sid]
        selected, timing = select_rows(rows, year)
        if not selected and rows and allow_later_context:
            dated = [r for r in rows if evidence_year(r)]
            first = min((evidence_year(r) for r in dated), default=None)
            selected = [r for r in dated if evidence_year(r) == first]
            timing = 'later_campus_grade_context_proxy_not_reference_year_configuration'
        # Prefer a dated grade statement over undated material at this step;
        # preserve ambiguity instead of relying on arbitrary claim-ID order.
        dated = [r for r in selected if evidence_year(r)]
        if dated:
            latest = max(evidence_year(r) for r in dated)
            selected = [r for r in dated if evidence_year(r) == latest]
        values = [json.loads(r['reported_value']) for r in selected]
        spans = {(r.get('lowest_grade_offered'), r.get('highest_grade_offered')) for r in values}
        if len(spans) == 1:
            low, high = next(iter(spans))
            level = elementary_span(low, high)
        elif spans:
            low, high, level = None, None, 'unknown'
            timing = 'conflicting_school_grade_statements'
        else:
            low, high, level = None, None, 'unknown'
        nces = {r.get('ncessch') for r in values if r.get('ncessch')}
        return dict(school_grade_low=low, school_grade_high=high, school_level=level,
            grade_context_years=joined(evidence_year(r) for r in selected),
            grade_context_source_periods=joined(r.get('evidence_period_raw') for r in selected),
            grade_context_record_ids=joined(r['_id'] for r in selected),
            grade_context_nces_candidate=next(iter(nces)) if len(nces) == 1 else None,
            grade_context_status=timing, grade_context_is_outcome_crosswalk=0)

    def operation(self, site, year):
        rows = self.statuses[site['site_id']]
        from .review_events import event_at
        event = event_at(self.program_events.get(site['site_id'], []), year)
        if event and event['kind'] in {'ended','moved'}:
            selected = [r for r in rows if r['_id']==event['status_id']]
            return dict(operation_status='hand_coded_'+event['kind'],operation_confirmed=0,confirmed_qualifying=0,
                        operation_record_ids=joined(r['_id'] for r in selected),operating_statuses=event['kind'],
                        eligibility_statuses='not_operating_at_this_site',public_funding_statuses='',selected=selected)
        # Event corrections choose the selected current event; historical rows
        # remain in the canonical table without competing with original reviews.
        rows = [r for r in rows if not r['confirmation_method'].startswith('researcher_hand_coding_')]
        exact = [r for r in rows if evidence_year(r) == year]
        confirmed = [r for r in exact if r['operating_status'] == 'confirmed_' + year.replace('-', '_')]
        documented = [r for r in confirmed if (r['eligibility_status'] or '').startswith('documented_')]
        if documented:
            selected, status = documented, 'confirmed_qualifying_reference_year'
        elif confirmed:
            selected, status = confirmed, 'operation_confirmed_eligibility_unresolved'
        elif exact:
            selected, status = exact, 'reference_year_review_requires_filtering'
        else:
            selected, timing = select_rows(rows, year)
            status = 'no_reference_year_operation_confirmation'
            if not selected and rows and timing == 'later_only':
                status = 'later_status_only'
        return dict(operation_status=status, operation_confirmed=int(bool(confirmed)),
            confirmed_qualifying=int(bool(documented)), operation_record_ids=joined(r['_id'] for r in selected),
            operating_statuses=joined(r['operating_status'] for r in selected),
            eligibility_statuses=joined(r['eligibility_status'] for r in selected),
            public_funding_statuses=joined(r['public_funding_status'] for r in selected),
            selected=selected)

    def candidates(self, site, variable):
        sid = site['site_id']
        if variable == 'instruction_languages':
            return [dict(r, _value=self.rules['language_aliases'].get(r['language_name'], r['language_name']))
                    for r in self.languages[sid] if known(r['language_name'])]
        field = {'population_model': 'population_model', 'delivery_structure': 'delivery_structure',
                 'programme_grade_scope': 'grade_scope'}[variable]
        return [dict(r, _value=r[field]) for r in self.configs[sid] if eligible_value(r, field)
                and r['program_kind'] != 'post_immersion_language_subject_options']

    def select_field(self, site, variable, year):
        rows = self.candidates(site, variable)
        override = self.overrides.get((site['site_id'], year, variable), {})
        selected, timing = select_rows(rows, year, override_ids=override.get('evidence_ids', ()))
        values = sorted({r['_value'] for r in selected})
        if not selected:
            status = 'later_only' if rows and timing!='outside_reviewed_reference_window' else 'not_reported'
        elif variable in {'population_model', 'delivery_structure'} and len(values) > 1:
            status = 'conflicting'
        elif any(r['verification_status'] in {'provisional', 'unverified', 'district_policy_only'} for r in selected):
            status = 'provisional'
        elif variable == 'programme_grade_scope' and any(
                w in str(v).casefold() for v in values for w in ('unresolved', 'unverified', 'not uniform')):
            status = 'provisional'
        else:
            status = 'documented'
        return self.field_result(site, variable, year, values, status, timing, rows, selected,
            override.get('reason', 'Field-specific selection; dates remain evidence dates, not newly observed annual validity.'))

    def field_result(self, site, variable, year, values, status, timing, candidates, selected, reason):
        row = dict(site_id=site['site_id'], program_id=site['program_id'], school_id=site['school_id'],
            state_code=self.programs[site['program_id']]['state_code'], selection_year=year, variable=variable,
            value_json=packed(values), value_status=status, applicability='applicable', temporal_status=timing,
            source_years=joined(evidence_year(r) for r in selected),
            source_periods=joined(r.get('evidence_period_raw') for r in selected),
            selected_evidence_ids=joined(r['_id'] for r in selected),
            selected_source_ids=joined(r['source_id'] for r in selected),
            candidate_evidence_count=len(candidates), selected_evidence_count=len(selected), reason=reason)
        evidence = []
        chosen = {r['_id'] for r in selected}
        for r in sorted(candidates, key=lambda r: (r['_table'], r['_id'])):
            role = ('selected' if r['_id'] in chosen else 'excluded_later' if later_period_mention(r, year)
                    else 'excluded_outside_reference_window' if not within_reviewed_reference(r,year) else 'not_selected')
            evidence.append(dict(site_id=site['site_id'], selection_year=year, variable=variable,
                evidence_table=r['_table'], evidence_record_id=r['_id'], selection_role=role,
                value_json=packed(r.get('_value')), source_school_year=evidence_year(r),
                evidence_period_raw=r.get('evidence_period_raw'), source_id=r['source_id'],
                source_url=self.sources[r['source_id']]['source_url'], source_locator=r.get('source_locator'),
                verification_status=r.get('verification_status', r.get('schedule_status'))))
        return row, evidence

    def select_allocations(self, site, year, level, grade_scopes):
        rows = [dict(r, _value=r['reported_model_label']) for r in self.allocations[site['site_id']]
                if (numeric_model(r['reported_model_label']) or self.shares[r['_id']]) and r['grade_support_status'] not in REJECTED_GRADE
                and elementary_scope(r['grade_scope']) not in {'secondary_6_plus', 'preschool_only'}]
        override = self.overrides.get((site['site_id'],year,'elementary_allocation_model'), {})
        selected, timing = select_rows(rows, year, override_ids=override.get('evidence_ids', ()))
        choice = self.policy_choices(year).get(site['site_id'])
        if choice and not override:
            selected = [r for r in rows if r['_id'] == choice['selected_schedule_id'] and not later_period_mention(r, year)]
            timing = 'existing_reviewed_current_policy_selection'
        # An exact-year K schedule does not erase an undated, non-overlapping
        # upper-grade policy. Restore only explicit disjoint grade scopes.
        occupied = set().union(*(grade_set(r['grade_scope']) or set() for r in selected))
        if selected and not choice and not override:
            for r in rows:
                grades = grade_set(r['grade_scope'])
                if r not in selected and not later_period_mention(r, year) and grades and not grades & occupied:
                    selected.append(r); occupied.update(grades)
        if override.get('hand_coded'):
            from .allocation_selection import apply_grade_reviews
            base_rows = [r for r in rows if r['_id'] not in self.manual_allocation_ids]
            base, _ = select_rows(base_rows, year)
            if choice:
                base = [r for r in base_rows if r['_id']==choice['selected_schedule_id']
                        and not later_period_mention(r,year) and within_reviewed_reference(r,year)]
            elif base:
                covered = set().union(*(grade_set(r['grade_scope']) or set() for r in base))
                for row in base_rows:
                    grades = grade_set(row['grade_scope'])
                    if (row not in base and grades and not grades & covered
                            and not later_period_mention(row,year) and within_reviewed_reference(row,year)):
                        base.append(row); covered.update(grades)
            selected = apply_grade_reviews(rows,self.allocation_reviews[(site['site_id'],year)],base,year)
        # Published annual model labels (especially WA) remain model evidence,
        # but cannot override a grade-specific schedule or create named shares.
        model_rows = [dict(r, _value=r['reported_model_label'],
            percentage_basis='annual_programme_model_label_not_a_grade_specific_named_language_schedule',
            schedule_status='reported_policy_requires_review', evidence_review_status='ANNUAL_MODEL_LABEL_ONLY',
            grade_support_status='SOURCE_GRADE_SCOPE_NOT_REPORTED') for r in self.configs[site['site_id']]
            if numeric_model(r.get('reported_model_label'))]
        if not selected:
            model_selected, model_timing = select_rows(model_rows, year)
            if model_selected:
                selected, timing = model_selected, model_timing
        rows += model_rows
        programme_preschool = bool(grade_scopes and all(elementary_scope(s) == 'preschool_only' for s in grade_scopes))
        applicable = level not in {'secondary_6_plus', 'preschool_only'} and not programme_preschool and not (
            grade_scopes and all(elementary_scope(s) == 'secondary_6_plus' for s in grade_scopes))
        conflict = any('CONFLICT' in (r.get('evidence_review_status') or '')
                       or r['schedule_status'] == 'conflicting_documented_plan' for r in selected)
        for i, a in enumerate(selected):
            for b in selected[i + 1:]:
                ga, gb = grade_set(a['grade_scope']), grade_set(b['grade_scope'])
                sa = self.allocation_claims.get(a['_id'], {}).get('service_scope', '')
                sb = self.allocation_claims.get(b['_id'], {}).get('service_scope', '')
                if sa and sb and sa != sb:
                    continue
                if ga is not None and gb is not None and not ga & gb:
                    continue
                va = sorted((r['language_name'], r['instruction_share_pct']) for r in self.shares[a['_id']])
                vb = sorted((r['language_name'], r['instruction_share_pct']) for r in self.shares[b['_id']])
                if (va and vb and va != vb) or (not (va and vb) and a['_value'] != b['_value']):
                    conflict = True
        if not applicable:
            status = 'not_applicable_preschool_only' if level == 'preschool_only' or programme_preschool else 'not_applicable_secondary_entry'
            selected = []
        elif conflict:
            status = 'conflicting'
        elif selected:
            statuses = {r['schedule_status'] for r in selected}
            if statuses == {'inferred_plan'}:
                status = 'inferred'
            elif 'inferred_plan' in statuses:
                status = 'mixed_documented_and_inferred'
            elif any(not self.shares[r['_id']] or r['schedule_status'] == 'reported_policy_requires_review' for r in selected):
                status = 'reported_model_requires_review'
            else:
                status = 'documented'
        else:
            status = 'later_only' if rows and timing == 'later_only' else 'not_reported'
        selected.sort(key=lambda r: (min(grade_set(r['grade_scope']) or {99}), r['_table'], r['_id']))
        values = [dict(evidence_table=r['_table'], evidence_record_id=r['_id'],
            schedule_id=r['_id'] if r['_table'] == 'allocation_schedules' else None,
            grade_scope=r['grade_scope'], model_label=r['_value'],
            **({'source_grade_scope':r['_source_grade_scope']} if '_source_grade_scope' in r else {}),
            **model_description(r, self.shares[r['_id']], self.rules['language_aliases']),
            service_scope=self.allocation_claims.get(r['_id'], {}).get('service_scope'),
            percentage_basis=r['percentage_basis'], source_year=evidence_year(r)) for r in selected]
        result = self.field_result(site, 'elementary_allocation_model', year, values, status, timing, rows, selected,
            'Policies retain grade, language, service and source scope. Campus-only schedules are not assigned to language strands. Secondary-only entry allocation is not applicable.')
        result[0]['applicability'] = ('not_applicable' if not applicable else 'unknown' if level == 'unknown' else 'applicable')
        return result

    def operation_field(self, site, year):
        op = self.operation(site, year)
        rows = [dict(r, _value=r['operating_status']) for r in self.statuses[site['site_id']]]
        selected = [dict(r, _value=r['operating_status']) for r in op['selected']]
        status = 'documented' if op['operation_confirmed'] else 'not_reported' if not rows else 'requires_reference_year_review'
        return self.field_result(site, 'reference_operation', year,
            [dict(operation_status=op['operation_status'], operating_statuses=op['operating_statuses'],
                  eligibility_statuses=op['eligibility_statuses'])], status,
            'exact_selection_year' if op['operation_confirmed'] else 'reference_year_not_confirmed', rows, selected,
            'Operation and public academic eligibility are separate. Source listings and later continuations do not become annual operation certification.')
