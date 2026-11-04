"""K-denominator, secondary retention and WA source-row export regressions."""
import csv
import io
import json
from pathlib import Path
import unittest

from dl_outcomes.allocation_coverage import (
    grade_eligibility, merge_eligibility, report_rows, select_grade_rows, washington_exports,
)
from dl_outcomes.validation import load

ROOT = Path(__file__).resolve().parents[1]


class AllocationCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tables = load(ROOT)
        cls.details, cls.schools, summary = report_rows(cls.tables)
        cls.summary = {r['state_code']:r for r in summary}

    def test_secondary_and_grade_one_programmes_are_not_missing_k_models(self):
        for scope in ['6-8', 'Grades 9-12', 'middle', 'secondary']:
            with self.subTest(scope=scope):
                self.assertEqual(grade_eligibility(scope), 'excluded_secondary')
        for scope in ['1-6', '3-5', 'elementary; starts grade 1', 'Pre-K', 'TK']:
            with self.subTest(scope=scope):
                self.assertEqual(grade_eligibility(scope), 'excluded_no_k')
        self.assertEqual(grade_eligibility('elementary; most start grade 1'), 'unknown')

    def test_mixed_k_secondary_campuses_still_count_the_k_programme(self):
        for scope in ['K-8', 'K-12', 'TK-5 | 6-8', 'Pre-K–6', 'K intake documented; full program grade span unverified']:
            with self.subTest(scope=scope):
                self.assertEqual(grade_eligibility(scope), 'eligible_k')
        self.assertEqual(merge_eligibility(['eligible_k','excluded_secondary']), 'eligible_k')
        self.assertEqual(grade_eligibility('K-8 pathway; campus grade band unresolved'), 'unknown')

    def test_directory_disjoint_bands_do_not_invent_kindergarten(self):
        for scope in ["'EE-05", "'KG-08", "'EE KG-05"]:
            self.assertEqual(grade_eligibility(scope, directory=True), 'eligible_k')
        for scope in ["'PK 01-08", "'EE 01-05", "'01-05"]:
            self.assertEqual(grade_eligibility(scope, directory=True), 'excluded_no_k')
        self.assertEqual(grade_eligibility("'09-12", directory=True), 'excluded_secondary')

    def test_current_grade_scope_takes_precedence_over_old_and_future_plans(self):
        def config(year, grade):
            return dict(school_year=year,grade_scope=grade,program_kind='source_structural_observation')
        chosen = select_grade_rows([config('2024-25','K-5'),config('2025-26','3-5'),config('2026-27','K-8')], 'KS')
        self.assertEqual([r['grade_scope'] for r in chosen], ['3-5'])
        self.assertEqual(select_grade_rows([config('2026-27','K-5')], 'AZ'), [])

    def test_texas_secondary_policies_are_retained_but_not_counted_as_k(self):
        secondary = [r for r in self.details if r['state_code']=='TX' and r['k_eligibility']=='excluded_secondary']
        self.assertTrue(secondary)
        self.assertTrue(all(r['k_allocation_status']=='not_applicable_secondary' for r in secondary))
        self.assertTrue(all(r['has_cited_k_model']==r['has_grade_supported_k_model']==r['has_named_language_k_plan']==0 for r in secondary))
        schools = {r['school_id'] for r in secondary}
        self.assertTrue(any(r['school_id'] in schools and r['grade_scope']=='K' for r in self.tables['allocation_schedules']))

    def test_texas_directory_context_remains_a_dated_proxy(self):
        claims = [r for r in self.tables['evidence_claims'] if r['attribute']=='campus_grade_range_context']
        self.assertEqual(len(claims),1586)
        self.assertTrue(all(r['valid_from_year']==r['valid_to_year']=='2024-25' for r in claims))
        self.assertGreater(self.summary['TX']['k_campus_proxy_school_units'], 0)
        self.assertEqual(self.summary['TX']['denominator_status'],'partial_grades_need_review')
        self.assertGreater(self.summary['TX']['k_eligibility_unknown_school_units'],0)

    def test_washington_has_model_labels_but_no_established_k_denominator(self):
        row = self.summary['WA']
        self.assertEqual(row['working_set_school_units'],175)
        self.assertEqual(row['k_denominator_school_units'],0)
        self.assertEqual(row['k_eligibility_unknown_school_units'],175)
        self.assertIsNone(row['cited_k_model_pct_among_identified_k_schools'])
        self.assertEqual(row['denominator_status'],'not_established')
        self.assertTrue(all(r['k_allocation_status']=='k_eligibility_needs_review' for r in self.details if r['state_code']=='WA' and r['in_reference_working_set']))

    def test_school_denominators_balance_without_counting_unknowns_as_missing(self):
        for row in self.summary.values():
            self.assertEqual(row['working_set_school_units'],sum(row[field] for field in [
                'k_denominator_school_units','secondary_school_units_excluded',
                'other_non_k_school_units_excluded','k_eligibility_unknown_school_units']))
            self.assertLessEqual(row['schools_with_named_language_k_plan'],row['schools_with_grade_supported_k_model'])
            self.assertLessEqual(row['schools_with_grade_supported_k_model'],row['schools_with_cited_k_model'])
            self.assertLessEqual(row['schools_with_cited_k_model'],row['k_denominator_school_units'])
        self.assertEqual(len({(r['state_code'],r['school_id']) for r in self.schools}),len(self.schools))

    def test_phaseout_school_without_k_is_retained(self):
        row = next(r for r in self.details if r['state_code']=='KS' and 'Valley Park' in r['school_name'])
        self.assertEqual(row['reported_programme_grades'],'3-5')
        self.assertEqual(row['k_allocation_status'],'not_applicable_no_k')
        self.assertTrue(row['in_reference_working_set'])

    def test_named_language_percentage_labels_are_not_lost_for_lack_of_slash(self):
        self.assertEqual(self.summary['AZ']['schools_with_named_language_k_plan'],5)
        self.assertTrue(any(r['state_code']=='AZ' and r['has_named_language_k_plan'] and '50%' in r['retained_source_model_labels'] for r in self.details))

    def test_washington_csv_preserves_all_native_fields_and_source_years(self):
        exports = washington_exports(ROOT,self.tables)
        rows = list(csv.DictReader(io.StringIO(exports['data/registry/washington/wa_programs.csv'])))
        native = json.loads((ROOT/'data/raw/wa/pilot_2026_11_04/programs.json').read_text())
        self.assertEqual(len(rows),1002)
        self.assertTrue(all(r['school_id'] for r in rows))
        by_key = {(r['source_snapshot_path'],r['rowid']):r for r in rows}
        for original in native:
            exported = by_key[('data/raw/wa/pilot_2026_11_04/programs.json', original['rowid'])]
            for key,value in original.items():
                self.assertEqual(exported[key],str(value) if value is not None else '')
            self.assertTrue(exported['source_snapshot_sha256'])
        self.assertEqual({r['schoolyear'] for r in rows},{'2023-24','2024-25','2025-26'})
        self.assertTrue(any(r['programdesigntype']=='Tribal Language Program' and r['is_state_reported_dl']=='0' for r in rows))

    def test_washington_current_dl_csv_includes_case_variant_without_inventing_shares(self):
        exports = washington_exports(ROOT,self.tables)
        rows = list(csv.DictReader(io.StringIO(exports['data/registry/washington/wa_dl_programs_2025_26.csv'])))
        self.assertEqual(len(rows),195)
        self.assertEqual(len({r['schoolorganizationid'] for r in rows}),175)
        self.assertTrue(all(r['program_id'] and r['site_id'] and r['schoolyear']=='2025-26' for r in rows))
        self.assertTrue(all(r['programme_grade_scope']=='not_reported' and r['kindergarten_allocation_status']=='not_established_source_has_no_grade_scope' for r in rows))
        wa_schedules = {r['schedule_id'] for r in self.tables['allocation_schedules'] if r['school_id'].startswith('WA-')}
        self.assertFalse(any(r['schedule_id'] in wa_schedules for r in self.tables['instructional_allocations']))


if __name__ == '__main__':
    unittest.main()
