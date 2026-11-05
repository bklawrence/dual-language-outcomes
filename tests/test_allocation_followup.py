"""Prevent policy evidence from becoming an invented campus-year timetable."""
import copy
import csv
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from dl_outcomes.allocation_enrichment import (
    REPORT, audit_errors, inputs, validate_decisions,
)
from dl_outcomes.elementary_audit import report_rows
from dl_outcomes.io import digest
from dl_outcomes.page_payloads import embedded_page_text
from dl_outcomes.validation import load

ROOT = Path(__file__).resolve().parents[1]


class AllocationFollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tables = load(ROOT)
        cls.config, cls.sources, cls.targets, cls.decisions, cls.reviews = inputs(ROOT)
        source_ids = {
            r['source_id'] for r in cls.tables['sources']
            if r['dataset_id'] in {
                'UT_ALLOCATION_FOLLOWUP_2026_11_05',
                'TX_ALLOCATION_FOLLOWUP_2026_11_05',
            }
        }
        cls.additions = [
            r for r in cls.tables['allocation_schedules'] if r['source_id'] in source_ids
        ]

    def test_all_identified_utah_elementary_hosts_have_traced_policy(self):
        details, summary = report_rows(self.tables)
        utah = [r for r in summary if r['state_code'] == 'UT']
        for row in utah:
            self.assertEqual(row['elementary_school_units'],
                             row['elementary_schools_with_numerical_model'])
            self.assertEqual(row['statewide_completeness'], 'not_established')
        all_utah = next(r for r in utah if r['audit_scope'] == 'all_recorded_programme_hosts')
        self.assertEqual(all_utah['elementary_school_units'], 127)
        elementary = {
            r['school_id'] for r in details if r['state_code'] == 'UT'
            and r['audit_scope'] == 'all_recorded_programme_hosts' and r['elementary_denominator']
        }
        school_states = {r['school_id']: r['state_code'] for r in self.tables['schools']}
        assigned = [r for r in self.additions if school_states[r['school_id']] == 'UT']
        self.assertEqual({r['school_id'] for r in assigned}, elementary)
        for row in assigned:
            self.assertEqual(row['reported_model_label'], '50/50')
            self.assertIsNone(row['site_id'])
            self.assertIsNone(row['school_year'])
            self.assertEqual(row['grade_support_status'], 'PUBLISHED_MODEL_ONLY')
            self.assertEqual(row['evidence_review_status'], 'USER_AUTHORIZED_STATEWIDE_ELEMENTARY_MODEL')
            self.assertEqual(row['tested_cohort_exposure'], 'not_established')

    def test_roster_matches_preserve_separate_language_cells_and_year(self):
        with (ROOT / (REPORT + '_utah_roster_reconciliation.csv')).open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 348)
        self.assertEqual(len({(r['pdf_page'], r['pdf_text_block'], r['school']) for r in rows}), 280)
        self.assertEqual({r['roster_school_year'] for r in rows}, {'2026-27'})
        self.assertTrue(all(r['status'] == 'matched_existing_record' and r['program_id'] for r in rows))
        self.assertGreater(len(rows), len({r['school'] for r in rows}))

    def test_changed_roster_cannot_reuse_the_old_reconciliation(self):
        def changed_roster(path):
            return 'changed' if path.name == 'ut_roster27.pdf' else digest(path)

        with patch('dl_outcomes.allocation_enrichment.digest', side_effect=changed_roster):
            with self.assertRaisesRegex(ValueError, 're-extract'):
                inputs(ROOT)

    def test_archives_match_saved_checksums_and_retrieval_methods(self):
        for source in self.sources:
            metadata = json.loads((ROOT / source['metadata_path']).read_text())
            self.assertEqual(digest(ROOT / source['path']), source['sha256'])
            self.assertEqual(metadata['sha256'], source['sha256'])
            self.assertEqual(metadata['http_status'], 200)
            self.assertIn(metadata['capture_method'],
                          {'original_public_HTTP_response', 'public_browser_rendered_DOM'})
            if metadata['capture_method'] == 'public_browser_rendered_DOM':
                self.assertIn('not_original_HTTP_body', metadata['archive_kind'])
            if source.get('derived_text_path'):
                derived = ROOT / source['derived_text_path']
                self.assertEqual(digest(derived), source['derived_text_sha256'])
                self.assertEqual(derived.read_text().rstrip('\n'),
                                 embedded_page_text((ROOT / source['path']).read_bytes()))

    def test_texas_fixed_starting_universe_and_decision_boundaries(self):
        self.assertEqual(len(self.targets), 598)
        self.assertEqual(len({r['district_id'] for r in self.targets}), 162)
        self.assertEqual({r['baseline_model_status'] for r in self.targets}, {'no_allocation_observation'})
        expected = {'TX-S' + cid for d in self.decisions for cid in d['campus_ids']}
        actual = {r['school_id'] for r in self.additions if r['school_id'].startswith('TX-')}
        self.assertEqual(actual, expected)
        self.assertEqual(audit_errors(ROOT, self.tables), [])

    def test_summary_counts_only_campuses_with_actual_model_decisions(self):
        summary = json.loads((ROOT / (REPORT + '_summary.json')).read_text())
        accepted = {cid for row in self.decisions for cid in row['campus_ids']}
        pending = {cid for row in self.reviews for cid in row['campus_ids']}
        self.assertEqual(summary['campuses_with_model_added'], len(accepted))
        self.assertEqual(summary['remaining_without_model'], 598 - len(accepted))
        self.assertEqual(summary['unfilled_campuses_pending_user_review'], len(pending - accepted))
        self.assertEqual(sum(summary['unfilled_status_counts'].values()), 598 - len(accepted))

    def test_policy_cannot_cross_district_boundaries(self):
        decisions = copy.deepcopy(self.decisions)
        row = decisions[0]
        row['campus_ids'] = [next(r['campus_id'] for r in self.targets
                                 if r['district_id'] != row['district_id'])]
        with self.assertRaisesRegex(ValueError, 'LEA boundaries'):
            validate_decisions(self.targets, decisions, self.sources, self.reviews)

    def test_literacy_and_population_splits_do_not_fill_total_day_models(self):
        # Denton/Red Oak quantify language arts; Gainesville quantifies student mix.
        unfilled = {r['school_id'] for r in self.additions}
        for district in ['061901', '070911', '049901']:
            for target in self.targets:
                if target['district_id'] == district:
                    self.assertNotIn(target['school_id'], unfilled)

    def test_unresolved_scope_is_retained_without_applying_two_way_models(self):
        for district in ['057912', '101921']:
            assigned = [r for r in self.additions if r['school_id'].startswith('TX-S' + district)]
            self.assertFalse(assigned)
        claims = [r for r in self.tables['evidence_claims']
                  if r['attribute'] == 'allocation_followup_pending_review']
        self.assertTrue(any('TX52-R03-IRVING_SCOPE' in r['source_locator'] for r in claims))

    def test_later_plans_are_not_backdated_to_reporting_or_reference_year(self):
        for district in ['246911', '170903', '020908']:
            assigned = [r for r in self.additions if r['school_id'].startswith('TX-S' + district)]
            self.assertTrue(assigned)
            self.assertTrue(all(r['school_year'] == '2026-27' for r in assigned))

    def test_model_labels_do_not_invent_language_specific_shares(self):
        schedule_ids = {r['schedule_id'] for r in self.additions}
        self.assertFalse(any(r['schedule_id'] in schedule_ids
                             for r in self.tables['instructional_allocations']))
        midlothian = [r for r in self.additions if r['school_id'].startswith('TX-S070908')]
        self.assertEqual(len(midlothian), 1)
        self.assertEqual(midlothian[0]['reported_model_label'], '70/30 (language ordering not stated)')

    def test_automatic_audit_rejects_a_backdated_utah_assignment(self):
        tables = copy.deepcopy(self.tables)
        row = next(r for r in tables['allocation_schedules']
                   if r['evidence_review_status'] == 'USER_AUTHORIZED_STATEWIDE_ELEMENTARY_MODEL')
        row['school_year'] = '2025-26'
        self.assertTrue(any('Utah policy assignment scope changed' in error
                            for error in audit_errors(ROOT, tables)))


if __name__ == '__main__':
    unittest.main()
