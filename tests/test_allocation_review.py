"""Research inference must respect programme type, language and source quality."""
import copy
import csv
import json
from pathlib import Path
import unittest

from dl_outcomes.allocation_review import (
    CONFIG, DIRECTIVE, INFERRED, audit_errors, inputs, validate_matches,
)
from dl_outcomes.elementary_audit import report_rows
from dl_outcomes.io import digest
from dl_outcomes.validation import load

ROOT = Path(__file__).resolve().parents[1]


class AllocationReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tables = load(ROOT)
        cls.config, cls.sources, cls.decisions, cls.resolutions = inputs(ROOT)
        source_ids = {r['source_id'] for r in cls.tables['sources']
                      if r['dataset_id'] == cls.config['dataset_id']}
        cls.additions = [r for r in cls.tables['allocation_schedules'] if r['source_id'] in source_ids]

    def test_denton_directive_applies_to_all_four_elementary_two_way_sites(self):
        row = next(d for d in self.decisions if d['decision_id'] == 'TXR_DENTON_TWOWAY')
        self.assertEqual({m['school_id'] for m in row['sites']},
                         {'TX-S061901105', 'TX-S061901109', 'TX-S061901111', 'TX-S061901116'})
        schedules = [r for r in self.additions if r['evidence_review_status'] == DIRECTIVE]
        self.assertEqual(len(schedules), 4)
        self.assertTrue(all(r['reported_model_label'] == '50/50' for r in schedules))

    def test_legacy_donor_inferences_keep_unreviewed_source_status(self):
        rows = [r for r in self.decisions if r['legacy_donor']]
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row['legacy_donor']['pass51_review_status'], 'NOT_REVIEWED')
            self.assertEqual(row['source_quote_kind'], 'preserved_legacy_registry_claim_not_primary_source_quote')
            self.assertIn('404', row['limitations'])
        self.assertTrue(any(r['evidence_review_status'] == INFERRED for r in self.additions))

    def test_red_oak_type_is_confirmed_without_filling_an_allocation(self):
        school_ids = {'TX-S070911102', 'TX-S070911107'}
        self.assertFalse(any(r['school_id'] in school_ids for r in self.additions))
        sites = {r['site_id']:r for r in self.tables['program_sites']}
        programs = {s['program_id'] for s in sites.values() if s['school_id'] in school_ids}
        claims = [r for r in self.tables['evidence_claims']
                  if r['entity_id'] in programs and r['attribute'] == 'reviewed_population_model']
        self.assertEqual(len(claims), 2)
        self.assertEqual({r['reported_value'] for r in claims}, {'one_way'})

    def test_mixed_school_does_not_inherit_a_model_on_the_wrong_strand(self):
        row = next(d for d in self.decisions if d['decision_id'] == 'TXR_WALLACE_TWOWAY')
        assigned = {m['site_id'] for m in row['sites']}
        self.assertEqual(len(assigned), 1)
        self.assertTrue(all(r['population_model'] == 'two_way'
                            for r in self.tables['program_configurations'] if r['site_id'] in assigned))
        self.assertTrue(all(r['site_id'] for r in self.additions))

    def test_type_mismatch_is_rejected(self):
        decision = copy.deepcopy(next(d for d in self.decisions if d['decision_id'] == 'TXR_DENTON_TWOWAY'))
        oneway = next(d for d in self.decisions if d['decision_id'] == 'TXR_DENTON_ONEWAY')
        decision['sites'] = [copy.deepcopy(oneway['sites'][0])]
        with self.assertRaisesRegex(ValueError, 'One-way and two-way'):
            validate_matches(self.tables, [decision])

    def test_mandarin_cannot_inherit_a_spanish_model(self):
        decision = copy.deepcopy(next(d for d in self.decisions if d['decision_id'] == 'TXR_IRVING_TWOWAY'))
        decision['district_id'] = '227901'
        site_id = next(r['site_id'] for r in self.tables['program_languages']
                       if r['language_name'] == 'Mandarin'
                       and any(s['site_id'] == r['site_id'] and s['school_id'] == 'TX-S227901198'
                               for s in self.tables['program_sites']))
        site = next(r for r in self.tables['program_sites'] if r['site_id'] == site_id)
        decision['sites'] = [dict(site_id=site_id, school_id=site['school_id'], program_id=site['program_id'],
                                  language_match_basis='existing_site_language_evidence')]
        with self.assertRaisesRegex(ValueError, 'instructional languages'):
            validate_matches(self.tables, [decision])

    def test_unmatched_or_conflicting_groups_remain_unclassified(self):
        for district in ['227901', '101921', '068901', '094902', '057910', '101911']:
            self.assertFalse(any(r['school_id'].startswith('TX-S' + district) for r in self.additions))
        row = next(r for r in self.resolutions if r['case_id'] == 'TX52-R07-AUSTIN')
        self.assertEqual(row['resolution_status'], 'held_conflicting_models_within_language_type')

    def test_review_assignments_cannot_become_observed_k_or_cohort_schedules(self):
        ids = {r['schedule_id'] for r in self.additions}
        for row in self.additions:
            self.assertIsNone(row['school_year'])
            self.assertEqual(row['grade_support_status'], 'PUBLISHED_MODEL_ONLY')
            self.assertEqual(row['tested_cohort_exposure'], 'not_established')
        self.assertFalse(any(r['schedule_id'] in ids for r in self.tables['instructional_allocations']))
        self.assertEqual(audit_errors(ROOT, self.tables), [])

    def test_old_checkpoints_are_frozen_and_recorded_gains_match_saved_evidence(self):
        for path, expected in self.config['frozen_checkpoint_files'].items():
            self.assertEqual(digest(ROOT / path), expected, path)
        with (ROOT / 'data/reports/elementary_allocation_coverage_2026_11_05_all_records_by_state.csv').open() as stream:
            old = next(r for r in csv.DictReader(stream) if r['state_code'] == 'TX')
        from dl_outcomes.baseline import load_snapshot
        _, checkpoint = load_snapshot(ROOT / 'data/baselines/national_structural_v1')
        _, summary = report_rows(checkpoint)
        new = next(r for r in summary if r['state_code'] == 'TX' and r['audit_scope'] == 'all_recorded_programme_hosts')
        results = json.loads((ROOT / (self.config['report_prefix'] + '_summary.json')).read_text())
        self.assertEqual(new['elementary_schools_with_numerical_model'] - int(old['elementary_schools_with_numerical_model']),
                         results['newly_classified_campuses'])
        self.assertEqual(results['cumulative_model_additions'] + results['remaining_without_model'], 598)
        self.assertGreater(new['elementary_schools_with_only_inferred_models'], 0)
        _, live = report_rows(self.tables)
        current = next(r for r in live if r['state_code']=='TX' and r['audit_scope']=='all_recorded_programme_hosts')
        self.assertGreaterEqual(current['elementary_schools_with_numerical_model'],new['elementary_schools_with_numerical_model'])

    def test_all_cases_have_current_outcomes_and_legacy_pending_requests_are_historical(self):
        self.assertEqual(len(self.resolutions), 14)
        claims = [r for r in self.tables['evidence_claims'] if r['attribute'] == 'allocation_review_case_resolution']
        self.assertEqual({r['source_locator'] for r in claims}, {r['case_id'] for r in self.resolutions})
