"""Great Lakes source boundaries, school denominators and append-only IL expansion."""
import json
from pathlib import Path
import tempfile
import unittest

from dl_outcomes.elementary_audit import report_rows
from dl_outcomes.great_lakes_review import AUDIT, BASE, STATES, audit_errors
from dl_outcomes.identity_audit import EXPANSION, fingerprint, preserved_identity_fingerprint
from dl_outcomes.northern_central_review import inputs
from dl_outcomes.validation import load

ROOT = Path(__file__).resolve().parents[1]


class GreatLakesInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tables = load(ROOT)
        cls.programmes, cls.sources = inputs(ROOT, base=BASE, states=STATES)
        cls.details, cls.summary = report_rows(cls.tables)

    def programme(self, school, target=None, *, state=None):
        return next(p for p in self.programmes if p['school'] == school
                    and (state is None or p['state'] == state)
                    and (target is None or p['track'] == target + ' immersion'))

    def school(self, school, *, state=None):
        sid = self.programme(school, state=state)['school_id']
        return next(r for r in self.details if r['school_id'] == sid
                    and r['audit_scope'] == 'reference_working_set')

    def test_all_four_states_reconcile_and_preserve_previous_work(self):
        self.assertEqual(audit_errors(ROOT, self.tables), [])
        self.assertEqual(len(self.programmes), 306)
        self.assertEqual(len({p['school_id'] for p in self.programmes}), 294)
        self.assertEqual({p['state'] for p in self.programmes}, STATES)

    def test_existing_illinois_rows_cannot_be_replaced_or_silently_dropped(self):
        tables = dict(self.tables)
        tables['schools'] = [dict(r, school_name='replacement') if r['school_id'] == 'IL-S001'
                             else r for r in tables['schools']]
        self.assertTrue(any('Original Illinois registry/evidence row replaced: schools' in e
                            for e in audit_errors(ROOT, tables, check_hashes=False)))
        tables['schools'] = [r for r in self.tables['schools'] if r['school_id'] != 'IL-S001']
        self.assertTrue(any('prior identities' in e for e in audit_errors(ROOT, tables, check_hashes=False)))

    def test_expansion_does_not_allow_unreviewed_extra_school_or_programme_ids(self):
        tables = dict(self.tables)
        tables['schools'] = self.tables['schools'] + [dict(school_id='IL-unreviewed', state_code='IL')]
        tables['programs'] = self.tables['programs'] + [dict(program_id='IL-unreviewed', state_code='IL')]
        errors = audit_errors(ROOT, tables, check_hashes=False)
        self.assertTrue(any('programme set changed: IL' in e for e in errors))
        self.assertTrue(any('school identities lost, invented or duplicated: IL' in e for e in errors))

    def test_cps_roster_keeps_preschool_and_later_starts_separate(self):
        rows = json.loads((ROOT / BASE / 'extractions/il_cps_roster_rows.json').read_text())
        self.assertEqual(len(rows), 49)
        self.assertEqual(len({r['cps_native_code'] for r in rows}), 49)
        self.assertEqual(sum(r['reference_status'] == 'confirmed_2025_26' for r in rows), 45)
        self.assertEqual([r['reported_school'] for r in rows if r['program_id'] is None], ['THOMAS'])
        self.assertEqual({r['reported_school'] for r in rows if r['reference_status'] == 'planned_future'},
                         {'ALBANY PARK', 'BURBANK', 'HERNANDEZ'})
        for name, sid in [('Darwin Elementary School', 'IL-S004'),
                          ('Talcott Fine Arts and Museum Academy', 'IL-S016')]:
            self.assertEqual(self.programme(name)['school_id'], sid)

    def test_u46_entry_chart_is_not_the_older_feeder_diagram(self):
        rows = [p for p in self.programmes if p['district'] == 'School District U-46']
        self.assertEqual(len(rows), 27)
        self.assertIn('Creekside Elementary School', {p['school'] for p in rows})
        self.assertNotIn('Bartlett Elementary School', {p['school'] for p in rows})
        for p in rows:
            self.assertEqual(p['reference']['period'], '2025-26')
            self.assertEqual(p['observations'][0]['population'], 'unknown')
            self.assertEqual(p['allocations'][0]['shares'], {'Spanish': 80, 'English': 20})

    def test_indiana_state_rows_preserve_target_only_and_stale_enrolment_cells(self):
        observations = [o for p in self.programmes if p['state'] == 'IN'
                        for o in p['observations'] if o['source'] == 'gl_in_state']
        self.assertEqual(len(observations), 44)
        self.assertTrue(all(len(o['languages']) == 1 and 'English' not in o['languages']
                            for o in observations))
        harrison = self.programme('Benjamin Harrison Elementary School')
        self.assertEqual(harrison['reference']['status'], 'uncertain_2025_26')
        self.assertIn('2023-2024', harrison['observations'][0]['raw']['grade_cell'])
        self.assertFalse(self.programme('Thompson Crossing Elementary')['allocations'])

    def test_wisconsin_age_codes_are_not_numeric_school_grades(self):
        p = self.programme('Allen-Field School')
        self.assertEqual(p['observations'][0]['grade'], 'PK-5; includes K')
        self.assertEqual(p['allocations'][0]['grade'], 'K')
        self.assertEqual(p['allocations'][0]['shares'], {'Spanish': 90, 'English': 10})
        self.assertEqual(self.school('Allen-Field School')['elementary_denominator'], 1)
        self.assertFalse(any(p['school'] == 'Bull Early Education Center' for p in self.programmes))

    def test_lower_primary_and_grade_five_hosts_count_but_six_plus_does_not(self):
        for name, state in [('Lincoln Elementary School', 'WI'), ('Northern Trails 5/6 School', 'MI'),
                            ('Stonybrook Intermediate and Middle School', 'IN'), ('Verda Dierzen Early Learning Center', 'IL')]:
            self.assertEqual(self.school(name, state=state)['elementary_denominator'], 1)
        for name in ['Westlane Middle School', 'Dr. Bessie Rhodes School of Global Studies',
                     'Milwaukee School of Languages']:
            row = self.school(name)
            self.assertEqual(row['elementary_classification'], 'secondary_6_plus')
            self.assertEqual(row['elementary_denominator'], 0)

    def test_languages_are_separate_tracks_and_do_not_share_unrelated_models(self):
        flics = [p for p in self.programmes if p['school'].startswith('Foreign Language Immersion')]
        self.assertEqual(len({p['school_id'] for p in flics}), 1)
        self.assertEqual({p['track'] for p in flics},
                         {'Mandarin Chinese immersion', 'French immersion', 'Japanese immersion', 'Spanish immersion'})
        self.assertEqual(self.programme('Meadow Brook Elementary School')['allocations'][0]['shares'],
                         {'Mandarin Chinese': 50, 'English': 50})
        self.assertFalse(self.programme('Ada Vista Elementary School')['allocations'])
        self.assertFalse(self.programme('Dooley Elementary School')['allocations'])
        self.assertEqual(self.programme('Yankee Ridge Multilingual School', 'Spanish')['school_id'], 'IL-S018')
        self.assertEqual(self.programme('Yankee Ridge Multilingual School', 'French')['school_id'], 'IL-S018')

    def test_student_background_ratios_and_english_specials_do_not_become_day_shares(self):
        for name in ['Leopold Elementary School', 'Sheridan Elementary School',
                     'MacArthur International Spanish Academy', 'Canterbury Elementary School',
                     'El Puente Elementary School']:
            self.assertFalse(self.programme(name)['allocations'])
            if name in {'MacArthur International Spanish Academy','Canterbury Elementary School'}:
                # Later historical research supplies a dated model, independent
                # of the original pupil/literacy-only percentages.
                self.assertIn('2021-22',self.school(name)['model_source_periods'])
            else:
                self.assertEqual(self.school(name)['has_numerical_allocation_model'], 0)

    def test_same_programme_inferences_keep_explicit_donors_and_review_flag(self):
        by_id = {p['program_id']: p for p in self.programmes}
        for name in ['ELC Brook Park', 'ELC Winding Ridge']:
            p = self.programme(name)
            a = p['allocations'][0]
            self.assertEqual(a['review_status'], 'USER_AUTHORIZED_SAME_PROGRAMME_INFERENCE')
            self.assertEqual(len(a['inference']['donor_program_ids']), 3)
            for pid in a['inference']['donor_program_ids']:
                donor = by_id[pid]
                self.assertEqual(donor['district'], p['district'])
                self.assertTrue(any(o['population'] == 'one_way' for o in donor['observations']))
                self.assertTrue(any(x['shares'] == a['shares'] for x in donor['allocations']))

    def test_endings_proposals_and_reference_years_remain_distinct(self):
        hosts = {r['school_id'] for r in self.details if r['audit_scope'] == 'reference_working_set'}
        victory = self.programme('Victory School / former Italian Immersion')
        self.assertEqual(victory['reference']['status'], 'ended_before_2025_26')
        self.assertNotIn(victory['school_id'], hosts)
        for name in ['Hi-Mount Community School', 'Central Heights Middle School', 'Doty Elementary School']:
            p = self.programme(name)
            self.assertEqual(p['reference']['status'], 'planned_future')
            self.assertNotIn(p['school_id'], hosts)
        self.assertIn(self.programme('Red Oak Elementary School')['school_id'], hosts)

    def test_supporting_sources_are_in_portable_inputs_and_assessments_are_unchanged(self):
        manifest = json.loads((ROOT / 'data/curated/manifest.json').read_text())
        for doc in self.sources.values():
            self.assertIn(doc['path'], manifest['inputs'])
            self.assertIn(doc['metadata_path'], manifest['inputs'])
        audit = json.loads((ROOT / AUDIT).read_text())
        self.assertEqual(len(audit['preserved_assessment_outputs']), 12)
        self.assertEqual(len(audit['preserved_reports']), 78)


class HistoricalIdentityFingerprintTests(unittest.TestCase):
    def test_narrowing_requires_the_independently_frozen_original_checksum(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / EXPANSION
            path.parent.mkdir(parents=True)
            expected = fingerprint(['old'])
            path.write_text(json.dumps({'expanded_state_original_ids': {'schools': {'IL': ['old']}}}))
            self.assertEqual(preserved_identity_fingerprint(root, 'schools', 'IL', ['old', 'new'], expected), expected)
            self.assertNotEqual(preserved_identity_fingerprint(root, 'schools', 'IL', ['new'], expected), expected)
            path.write_text(json.dumps({'expanded_state_original_ids': {'schools': {'IL': ['different']}}}))
            self.assertNotEqual(preserved_identity_fingerprint(root, 'schools', 'IL', ['old', 'new'], expected), expected)


if __name__ == '__main__':
    unittest.main()
