"""Reference years, programme scope and source-specific baseline selections."""
import copy
import json
from pathlib import Path
import unittest

from dl_outcomes.baseline import load_snapshot, school_rows
from dl_outcomes.baseline_selection import Selection, evidence_year, later_period_mention, model_description, select_rows
from dl_outcomes.validation import load

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / 'data/baselines/national_structural_v1'


class TemporalSelectionTests(unittest.TestCase):
    def row(self, key, year=None, period=None):
        return dict(_id=key, school_year=year, evidence_period_raw=period)

    def test_exact_year_wins_without_retrieval_date_priority(self):
        rows = [self.row('old', '2023-24'), self.row('current', '2025-26'), self.row('future', '2026-27')]
        rows[0]['retrieved_at'] = '2026-11-06'
        selected, timing = select_rows(rows, '2025-26')
        self.assertEqual([r['_id'] for r in selected], ['current'])
        self.assertEqual(timing, 'exact_selection_year')

    def test_unknown_and_earlier_dates_are_not_redated_to_reference_year(self):
        row = self.row('undated', period='undated; retrieved November 2026')
        self.assertIsNone(evidence_year(row))
        selected, timing = select_rows([row, self.row('earlier', '2022-23')], '2025-26')
        self.assertEqual({r['_id'] for r in selected}, {'undated', 'earlier'})
        self.assertIn('not_new_annual', timing)
        self.assertIsNone(selected[0]['school_year'])

    def test_later_roster_mention_is_not_an_undated_policy(self):
        row = self.row('later', period='2026-27 roster')
        self.assertIsNone(evidence_year(row))
        self.assertTrue(later_period_mention(row, '2025-26'))
        self.assertEqual(select_rows([row], '2025-26'), ([], 'later_only'))

    def test_adjudication_cannot_backdate_a_later_observation(self):
        with self.assertRaisesRegex(ValueError, 'missing or later'):
            select_rows([self.row('later', '2026-27')], '2025-26', override_ids=['later'])

    def test_normalization_uses_named_shares_without_reversing_english_first_labels(self):
        row = dict(reported_model_label='90/10', percentage_basis='core classroom policy', schedule_status='documented_plan')
        result = model_description(row, [dict(language_name='English', instruction_share_pct=90),
            dict(language_name='Spanish', instruction_share_pct=10)], {})
        self.assertEqual(result['model_label_normalized'], '10/90')
        self.assertEqual(result['model_label_language_order'], 'named_partner_then_English')
        self.assertEqual(row['reported_model_label'], '90/10')


class NationalBaselineSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tables = load_snapshot(FROZEN) if FROZEN.exists() else load(ROOT)
        cls.rules = json.loads((ROOT / 'config/baselines/national_structural_v1.json').read_text())
        cls.selection = Selection(cls.tables, cls.rules)
        cls.schools = {r['school_id']: r for r in cls.tables['schools']}

    def site(self, school, language=None, state=None):
        schools = {r['school_id'] for r in self.tables['schools'] if r['school_name'] == school
                   and (state is None or r['state_code'] == state)}
        programs = {r['program_id']: r for r in self.tables['programs']}
        return next(r for r in self.tables['program_sites'] if r['school_id'] in schools
                    and (language is None or language in programs[r['program_id']]['program_name']))

    def field(self, school, variable, year='2025-26', state=None):
        site = self.site(school, state=state)
        if variable == 'elementary_allocation_model':
            grades, _ = self.selection.select_field(site, 'programme_grade_scope', year)
            level = self.selection.school_grade(site['school_id'], year)['school_level']
            return self.selection.select_allocations(site, year, level, json.loads(grades['value_json']))[0]
        return self.selection.select_field(site, variable, year)[0]

    def test_connery_uses_saved_district_one_way_evidence_with_directory_retained(self):
        row = self.field('Wm. P. Connery Elementary School', 'population_model')
        self.assertEqual(json.loads(row['value_json']), ['one_way'])
        self.assertEqual(row['temporal_status'], 'reviewed_field_adjudication')
        configurations = self.selection.configs[self.site('Wm. P. Connery Elementary School')['site_id']]
        self.assertEqual({r['population_model'] for r in configurations}, {'one_way', 'two_way'})

    def test_mandarin_aliases_do_not_collapse_unspecified_chinese_or_infer_english(self):
        self.assertNotIn('Chinese', self.rules['language_aliases'])
        self.assertEqual(self.rules['language_aliases']['Mandarin Chinese'], 'Mandarin')
        site = next(r for r in self.tables['program_sites'] if self.schools[r['school_id']]['state_code'] == 'OR'
                    and self.selection.languages[r['site_id']])
        row, _ = self.selection.select_field(site, 'instruction_languages', '2026-27')
        actual = set(json.loads(row['value_json']))
        source = {self.rules['language_aliases'].get(r['language_name'], r['language_name'])
                  for r in self.selection.languages[site['site_id']]}
        self.assertEqual(actual, source)
        self.assertNotIn('English', actual)

    def test_preschool_start_is_not_a_kindergarten_model(self):
        site = self.site('Sarah Roberts Elementary School')
        self.assertFalse(self.selection.operation(site, '2025-26')['confirmed_qualifying'])
        row, _ = self.selection.select_allocations(site, '2025-26', 'preschool_only', ['PK'])
        self.assertEqual(row['value_status'], 'not_applicable_preschool_only')
        self.assertEqual(json.loads(row['value_json']), [])
        row, _ = self.selection.select_allocations(site, '2026-27', 'elementary', ['K'])
        self.assertTrue(any(r['grade_scope'] == 'K' and r['model_label'] == '80/20' for r in json.loads(row['value_json'])))

    def test_grade_one_entry_keeps_its_grade_specific_policy(self):
        row = self.field('Clyde F. Brown Elementary School', 'elementary_allocation_model')
        values = json.loads(row['value_json'])
        self.assertEqual([(v['grade_scope'], v['model_label']) for v in values], [('1-2', '100/0')])

    def test_secondary_hosts_have_no_elementary_entry_model(self):
        row = self.field('Burncoat High School', 'elementary_allocation_model')
        self.assertEqual(row['value_status'], 'not_applicable_secondary_entry')
        self.assertEqual(json.loads(row['value_json']), [])

    def test_lyseth_current_choice_does_not_reselect_former_90_10(self):
        row = self.field('Harrison Lyseth Elementary School', 'elementary_allocation_model')
        values = json.loads(row['value_json'])
        self.assertEqual([v['model_label'] for v in values], ['60/40'])
        self.assertEqual(values[0]['named_language_shares'], {})
        self.assertEqual(row['value_status'], 'reported_model_requires_review')
        self.assertEqual(len(self.selection.allocations[self.site('Harrison Lyseth Elementary School')['site_id']]), 2)

    def test_wa_annual_model_is_available_without_becoming_a_k_schedule(self):
        site = next(r for r in self.tables['program_sites'] if self.schools[r['school_id']]['state_code'] == 'WA'
                    and any(c['school_year'] == '2025-26' and c['reported_model_label']
                            for c in self.selection.configs[r['site_id']]))
        row, _ = self.selection.select_allocations(site, '2025-26', 'elementary', [])
        self.assertEqual(row['value_status'], 'reported_model_requires_review')
        self.assertTrue(all(v['schedule_id'] is None and not v['named_language_shares']
                            for v in json.loads(row['value_json'])))

    def test_equal_day_named_shares_are_not_lost_for_non_numeric_labels(self):
        row = self.field('Lowell Elementary School', 'elementary_allocation_model', state='AZ')
        self.assertTrue(any(v['named_language_shares'] == {'Spanish': 50.0, 'English': 50.0}
                            for v in json.loads(row['value_json'])))

    def test_inference_keeps_its_type_and_its_source_minutes(self):
        row = self.field('Rafael Hernández Dual Language School', 'elementary_allocation_model')
        self.assertEqual(row['value_status'], 'mixed_documented_and_inferred')
        values = json.loads(row['value_json'])
        self.assertTrue(any(v['named_language_shares'] == {'Spanish': 83.0, 'English': 17.0} for v in values))

    def test_later_raices_policy_is_not_assigned_to_2025_26(self):
        row = self.field('Raíces Dual Language Academy at Robertson', 'elementary_allocation_model')
        self.assertEqual(row['value_status'], 'later_only')
        self.assertEqual(json.loads(row['value_json']), [])

    def test_explicit_primary_schedule_supplies_a_flagged_school_scope_proxy(self):
        site = self.site('Fairmount Elementary School')
        rows = school_rows(self.selection, self.tables, '2025-26', states={'CA'})
        school = next(r for r in rows if r['school_id'] == site['school_id'])
        self.assertEqual(school['school_level'], 'elementary')
        self.assertIn('proxy', school['grade_context_status'])
        self.assertIsNone(school['school_grade_low'])

    def test_later_grade_context_remains_a_proxy_not_an_outcome_crosswalk(self):
        site = self.site('Columbia Vista Intermediate')
        selection = copy.copy(self.selection)
        claim = dict(self.selection.grade_claims[site['school_id']][0], school_year='2026-27')
        selection.grade_claims = {site['school_id']: [claim]}
        grade = selection.school_grade(site['school_id'], '2025-26', allow_later_context=True)
        self.assertEqual(grade['school_grade_low'], 4)
        self.assertIn('later_campus_grade_context_proxy', grade['grade_context_status'])
        self.assertEqual(grade['grade_context_is_outcome_crosswalk'], 0)

    def test_a_separate_directory_year_does_not_date_an_undated_grade_statement(self):
        site = self.site('Columbia Vista Intermediate')
        grade = self.selection.school_grade(site['school_id'], '2025-26')
        self.assertEqual(grade['school_grade_low'], 4)
        self.assertEqual(grade['grade_context_years'], '')
        self.assertIn('separate from 2026-27', grade['grade_context_source_periods'])
