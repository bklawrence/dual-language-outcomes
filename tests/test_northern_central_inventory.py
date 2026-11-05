"""Seven-state source, grade, language and reference-year boundaries."""
import json
from pathlib import Path
import unittest

from dl_outcomes.elementary_audit import report_rows
from dl_outcomes.io import digest
from dl_outcomes.northern_central_review import AUDIT, audit_errors, inputs
from dl_outcomes.validation import load

ROOT = Path(__file__).resolve().parents[1]


class NorthernCentralInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tables = load(ROOT)
        cls.programmes, cls.sources = inputs(ROOT)
        cls.sites = {r['program_id']: r['site_id'] for r in cls.tables['program_sites']}
        cls.details, cls.summary = report_rows(cls.tables)

    def programme(self, school, target=None):
        return next(p for p in self.programmes if p['school'] == school
                    and (target is None or p['track'] == target + ' immersion'))

    def test_seven_states_reconcile_and_preserve_prior_work(self):
        self.assertEqual(audit_errors(ROOT, self.tables), [])
        self.assertEqual(len(self.programmes), 187)
        self.assertEqual(len({p['school_id'] for p in self.programmes}), 172)
        self.assertEqual({p['state'] for p in self.programmes}, {'ND', 'SD', 'MN', 'IA', 'MO', 'AK', 'HI'})

    def test_future_starts_are_excluded_from_reference_working_set(self):
        hosts = {r['school_id'] for r in self.details if r['audit_scope'] == 'reference_working_set'}
        for name in ['Kennedy Community School', 'Prince Jonah Kūhiō Kalanianaʻole Elementary']:
            p = self.programme(name)
            self.assertEqual(p['reference']['status'], 'planned_future')
            self.assertNotIn(p['school_id'], hosts)

    def test_hawaiian_policy_is_not_assigned_to_secondary_or_english_strands(self):
        hawaiian = [p for p in self.programmes if p['state'] == 'HI' and p['track'] == 'Hawaiian immersion']
        self.assertEqual(len(hawaiian), 34)
        for p in hawaiian:
            for a in p['allocations']:
                self.assertIn(a['grade'], {'K', 'K-1', 'K-4'})
                self.assertEqual(a['shares'], {'Hawaiian': 100, 'English': 0})
        waihona = self.programme('Ka Waihona o ka Naʻauao PCS')
        self.assertEqual(waihona['observations'][0]['delivery'], 'strand')
        keonepoko = self.programme('Keonepoko Elementary')
        self.assertFalse(any('English' in o['languages'] for o in keonepoko['observations']))

    def test_fla_and_sllis_languages_are_distinct_strands(self):
        fla = [p for p in self.programmes if p['school'] == 'Foreign Language Academy']
        self.assertEqual({p['track'] for p in fla}, {'Spanish immersion', 'Mandarin Chinese immersion'})
        self.assertEqual(len({p['school_id'] for p in fla}), 1)
        sllis = [p for p in self.programmes if p['school'] == 'St. Louis Language Immersion School']
        self.assertEqual({p['track'] for p in sllis}, {'Spanish immersion', 'French immersion', 'Chinese immersion'})
        self.assertTrue(all(not p['allocations'] for p in sllis))

    def test_anchorage_directory_does_not_infer_english_or_new_planned_hosts(self):
        observations = [o for p in self.programmes if p['state'] == 'AK'
                        for o in p['observations'] if o['source'] == 'nc_ak_asd_immersion']
        self.assertEqual(len(observations), 18)
        self.assertTrue(all('English' not in o['languages'] for o in observations))
        self.assertFalse(any(p['school'] == 'Bartlett High School' for p in self.programmes))

    def test_grade_one_and_grade_five_hosts_count_without_a_k_model(self):
        for name in ['Bridgewater Elementary', 'Greenvale Park Elementary', 'Spring Creek Elementary',
                     'Horizon Middle School West', 'Westwood Intermediate School']:
            p = self.programme(name)
            row = next(r for r in self.details if r['school_id'] == p['school_id']
                       and r['audit_scope'] == 'reference_working_set')
            self.assertEqual(row['elementary_denominator'], 1)
            self.assertEqual(row['has_numerical_allocation_model'], int(name != 'Horizon Middle School West'))
            self.assertFalse(any(a['grade'] == 'K' for a in p['allocations']))

    def test_woodbury_entry_model_is_not_the_later_50_50(self):
        p = self.programme('Woodbury Elementary')
        self.assertEqual({a['grade']: a['label'] for a in p['allocations']}, {'K': '70/30', '1-4': '50/50'})
        self.assertTrue(all(a['period'] == '2018-10-13' for a in p['allocations']))

    def test_hmong_ambiguous_single_percentage_is_not_synthesized_to_50_50(self):
        p = self.programme('Hmong International Academy')
        self.assertFalse(any(a['label'] == '50/50' or a['shares'] for a in p['allocations']))
        row = next(r for r in self.details if r['school_id'] == p['school_id']
                   and r['audit_scope'] == 'reference_working_set')
        self.assertEqual(row['has_numerical_allocation_model'], 0)

    def test_nd_school_age_evidence_and_funding_are_distinct(self):
        p = self.programme('Wičhákini Owáyawa')
        self.assertEqual(p['reference']['status'], 'confirmed_2025_26')
        self.assertTrue(p['reference']['eligibility'].startswith('candidate_'))
        self.assertEqual(p['allocations'][0]['source'], 'nc_nd_nest_policy')
        self.assertIsNone(p['allocations'][0]['shares'])
        self.assertFalse(any('English' in o['languages'] for o in p['observations']))
        row = next(r for r in self.summary if r['state_code'] == 'ND' and r['audit_scope'] == 'reference_working_set')
        self.assertEqual(row['elementary_school_units'], 0)
        self.assertIsNone(row['numerical_allocation_coverage_pct'])

    def test_historical_hosts_and_renaming_do_not_duplicate_current_schools(self):
        for name in ['Gage Elementary School', 'Ellen Hopkins Elementary School']:
            p = self.programme(name)
            self.assertEqual(p['reference']['status'], 'not_offered_reference_year')
            self.assertTrue(p['events'])
        cc = [p for p in self.programmes if 'Academia' in p['school']]
        self.assertEqual(len(cc), 1)
        self.assertIn('Cesar Chavez', cc[0]['school'])

    def test_mutating_source_date_or_language_is_rejected(self):
        p = self.programme('Scenic Park Elementary School')
        site = self.sites[p['program_id']]
        rows = dict(self.tables)
        rows['program_configurations'] = [dict(r) for r in self.tables['program_configurations']]
        row = next(r for r in rows['program_configurations'] if r['site_id'] == site and r['reported_model_label'] == '50/50')
        row['school_year'] = '2025-26'
        self.assertTrue(any('source grade/model/period changed' in e for e in audit_errors(ROOT, rows, check_hashes=False)))
        rows = dict(self.tables)
        rows['program_languages'] = [dict(r) for r in self.tables['program_languages']]
        row = next(r for r in rows['program_languages'] if r['site_id'] == site and r['language_name'] == 'Mandarin Chinese')
        row['language_name'] = 'Spanish'
        self.assertTrue(any('source languages/roles/dates changed' in e for e in audit_errors(ROOT, rows, check_hashes=False)))

    def test_assessment_layers_are_byte_for_byte_preserved(self):
        audit = json.loads((ROOT / AUDIT).read_text())
        self.assertEqual(len(audit['preserved_assessment_outputs']), 12)
        for path, expected in audit['preserved_assessment_outputs'].items():
            self.assertEqual(digest(ROOT / path), expected)


if __name__ == '__main__':
    unittest.main()
