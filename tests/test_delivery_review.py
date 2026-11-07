"""Campus scope, chronology and preservation for the delivery cleanup."""
import json
from pathlib import Path
import unittest

from dl_outcomes.baseline_selection import Selection, select_rows
from dl_outcomes.delivery_review import (
    added_ids, audit_errors, inputs, prior_tables, render_reports,
)
from dl_outcomes.validation import load

ROOT = Path(__file__).resolve().parents[1]


class DeliveryReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema, cls.tables = load(ROOT)
        cls.config, cls.files = inputs(ROOT)
        cls.rules = json.loads((ROOT/'data/baselines/national_structural_v1/rules.json').read_text())
        cls.selection = Selection(cls.tables, cls.rules)
        cls.prior = prior_tables(cls.tables, cls.files, cls.schema)
        cls.previous_selection = Selection(cls.prior, cls.rules)
        cls.sites = {r['site_id']: r for r in cls.tables['program_sites']}

    def test_review_window_is_not_a_permanent_policy_or_a_closure_date(self):
        row = dict(_id='review', school_year=None, evidence_period_raw='undated',
                   _earliest_reviewed_selection_year='2025-26',
                   _latest_reviewed_selection_year='2025-26')
        selected, _ = select_rows([row], '2025-26')
        self.assertEqual([r['_id'] for r in selected], ['review'])
        for year in ['2024-25', '2026-27']:
            selected, _ = select_rows([row], year)
            self.assertEqual(selected, [])
        with self.assertRaises(ValueError):
            select_rows([row], '2026-27', override_ids=['review'])

    def test_original_evidence_identities_assessments_and_frozen_outputs_survive(self):
        self.assertEqual(audit_errors(ROOT, self.tables), [])
        added = added_ids(self.files)
        self.assertEqual(set(added) - {'datasets', 'sources', 'program_configurations', 'evidence_claims'}, set())
        for name in ['schools', 'programs', 'program_sites', 'allocation_schedules',
                     'instructional_allocations', 'program_languages', 'program_status_history']:
            self.assertEqual(self.tables[name], self.prior[name])

    def test_current_evidence_does_not_change_any_earlier_delivery_selection(self):
        reviewed_ids = added_ids(self.files)['program_configurations']
        for fact in self.files['observations']:
            site = self.sites[fact['site_id']]
            for year in ['2021-22', '2023-24', '2024-25', '2026-27', '2027-28']:
                before, _ = self.previous_selection.select_field(site, 'delivery_structure', year)
                after, _ = self.selection.select_field(site, 'delivery_structure', year)
                for key in ['value_json', 'selected_evidence_ids', 'selected_source_ids']:
                    self.assertEqual(before[key], after[key], (fact['school_name'], year, key))
                self.assertFalse(reviewed_ids & set(after['selected_evidence_ids'].split(' | ')))

    def test_delivery_only_configuration_cannot_replace_other_structural_fields(self):
        ids = added_ids(self.files)['program_configurations']
        rows = [r for r in self.tables['program_configurations'] if r['configuration_id'] in ids]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row['grade_scope'], 'not_reported')
            self.assertEqual(row['population_model'], 'unknown')
            self.assertIsNone(row['reported_model_label'])
            self.assertIsNone(row['entry_cohort_year'])

    def test_alternative_dl_languages_can_be_collectively_whole_school(self):
        for school in ['WA-S101042', 'WA-S105166']:
            facts = [f for f in self.files['observations'] if f['school_id']==school]
            self.assertEqual(len(facts), 2)
            self.assertEqual({f['value'] for f in facts}, {'whole_school'})
            for fact in facts:
                field, _ = self.selection.select_field(self.sites[fact['site_id']], 'delivery_structure', '2025-26')
                self.assertEqual(json.loads(field['value_json']), ['whole_school'])

    def test_agc_current_whole_school_does_not_erase_historical_strand_report(self):
        site = self.sites['IL-PS001']
        before, _ = self.selection.select_field(site, 'delivery_structure', '2021-22')
        current, _ = self.selection.select_field(site, 'delivery_structure', '2025-26')
        self.assertEqual(json.loads(before['value_json']), ['strand'])
        self.assertEqual(json.loads(current['value_json']), ['whole_school'])
        self.assertEqual(current['value_status'], 'documented')

    def test_nyc_whole_school_and_parallel_monolingual_classes_have_distinct_codes(self):
        by_school = {f['school_id']: f for f in self.files['observations']}
        self.assertEqual(by_school['M6-NY-S-b00ace1072f1']['value'], 'whole_school')
        bilingual_center = [f for f in self.files['observations'] if f['school_id']=='M6-NY-S-3f6d8e4d7561']
        self.assertEqual(len(bilingual_center), 2)
        self.assertEqual({f['value'] for f in bilingual_center}, {'strand'})
        self.assertTrue(all('monolingual classes' in f['source_quote'] for f in bilingual_center))

    def test_summary_uses_unique_schools_and_fixed_allocation_bearing_denominator(self):
        _, summary = render_reports(ROOT, self.tables)
        self.assertEqual(summary['allocated_programme_sites'], 1906)
        self.assertEqual(summary['allocated_schools'], 1742)
        self.assertEqual(summary['programme_site_decisions'], 42)
        self.assertEqual(summary['school_decisions'], 35)
        self.assertEqual(summary['school_decisions_by_value'], {'whole_school': 11, 'strand': 24})
        self.assertEqual(summary['after_schools_all_allocated_sites_documented'] - summary['before_schools_all_allocated_sites_documented'], 35)


if __name__ == '__main__':
    unittest.main()
