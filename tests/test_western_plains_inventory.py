"""Regressions for actual source grades, language roles, vintages and programme changes."""
import copy
import json
from pathlib import Path
import unittest

from dl_outcomes.io import digest
from dl_outcomes.validation import load, validate_tables
from dl_outcomes.states.western_plains import CODES
from dl_outcomes.western_plains_review import AUDIT, audit_errors, inputs, source_id

ROOT = Path(__file__).resolve().parents[1]


class WesternPlainsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.definition, cls.tables = load(ROOT)
        cls.programmes, cls.sources = inputs(ROOT)
        cls.sites = {r['program_id']: r['site_id'] for r in cls.tables['program_sites']}

    def record(self, state, school, track=None, district=None):
        rows = [p for p in self.programmes if p['state'] == state and p['school'].startswith(school)
                and (track is None or p['track'] == track) and (district is None or p['district'] == district)]
        self.assertEqual(len(rows), 1, [(r['school'], r['track']) for r in rows])
        return rows[0]

    def test_source_reconciliation_and_prior_preservation(self):
        self.assertEqual(len(self.programmes), 650)
        self.assertEqual(len(self.sources), 96)
        self.assertEqual(len({p['school_id'] for p in self.programmes}), 568)
        self.assertEqual(audit_errors(ROOT, self.tables), [])

    def test_later_utah_roster_does_not_backdate_its_languages(self):
        ids = {source_id('UT', 'wp_ut_roster26', self.sources)}
        rows = [r for r in self.tables['program_languages'] if r['source_id'] in ids]
        self.assertEqual(len(rows), 348)
        self.assertTrue(all(r['valid_from_year'] == r['valid_to_year'] == '2026-27' for r in rows))
        self.assertFalse(any(r['language_name'] == 'English' for r in rows))
        self.assertIn('Russian', {r['language_name'] for r in rows})

    def test_utah_first_grade_models_are_not_kindergarten_models(self):
        source_keys = {'wp_ut_cache_form25', 'wp_ut_cache_main', 'wp_ut_davis', 'wp_ut_tooele', 'wp_ut_parkcity'}
        plans = [a for p in self.programmes if p['state'] == 'UT' for a in p['allocations'] if a['source'] in source_keys]
        self.assertTrue(plans)
        self.assertFalse(any('K' in a['grade'] for a in plans))
        cache = self.record('UT', 'Sunrise', 'Portuguese', 'Cache District')
        self.assertEqual(cache['reference']['status'], 'confirmed_2025_26')
        self.assertEqual(cache['reference']['locator'], 'Named school selector; Parent Commitment Form')
        self.assertEqual(cache['allocations'][0]['grade'], '1')
        self.assertEqual(cache['allocations'][0]['period'], '2025-26')

    def test_cache_magnet_relocation_is_not_backfilled_into_2025(self):
        incoming = self.record('UT', 'Cedar Ridge', 'Portuguese', 'Cache District')
        self.assertEqual(incoming['reference']['status'], 'planned_future')
        self.assertTrue(all(a['period'] == '2026-27' for a in incoming['allocations']))
        mountain = self.record('UT', 'Mountain Crest', 'Spanish', 'Cache District')
        self.assertEqual(mountain['reference']['status'], 'not_offered_reference_year')

    def test_reference_year_programmes_survive_a_later_adopted_end(self):
        south = self.record('UT', 'South Davis', 'French')
        stetson = self.record('CO', 'Stetson')
        for p in [south, stetson]:
            self.assertEqual(p['reference']['status'], 'confirmed_2025_26')
            self.assertTrue(any(e['year'] == '2026-27' and e['status'] in {'closed', 'closed_or_consolidated'} for e in p['events']))
        self.assertTrue(all(a['shares'] == {'Spanish':80, 'English':20} for a in stetson['allocations']))

    def test_new_mexico_composite_cells_do_not_create_every_language_track(self):
        observations = [o for p in self.programmes if p['state'] == 'NM' for o in p['observations'] if o['source'] == 'wp_nm_eric_pdf']
        self.assertEqual(len(observations), 137)
        composite = [o for o in observations if ',' in o['raw']['language']]
        self.assertTrue(composite)
        self.assertTrue(all(o['languages'] == [] for o in composite))
        self.assertFalse(any('English' in o['languages'] for o in observations))
        # The merged-cell extraction repair is checked against every printed district total.
        bernalillo = [o for o in composite if o['raw']['district'] == 'Bernalillo']
        self.assertEqual(len(bernalillo), 4)

    def test_navajo_school_name_is_not_a_language_or_identity_match(self):
        p = self.record('NM', 'Navajo Elementary', 'Spanish', 'Albuquerque')
        self.assertTrue(any(o['source'] == 'wp_nm_features' and o['raw']['ObjectId'] == 16 and o['languages'] == ['Spanish'] for o in p['observations']))
        # The different Gallup Navajo Elementary remains a non-DL source school row.
        rows = json.loads((ROOT/'data/registry/western_plains_2026_11_04/extractions/nm_report_rows.json').read_text())
        self.assertEqual(next(r['DL'] for r in rows if r['district'] == 'Gallup' and r['school'] == 'Navajo Elementary School'), '')

    def test_farmington_immersion_grades_are_separate_from_pull_out_grades(self):
        apache = self.record('NM', 'Apache Elementary')
        obs = next(o for o in apache['observations'] if o['source'] == 'wp_nm_farmington')
        self.assertEqual(obs['grade'], 'K-1')
        self.assertEqual(obs['languages'], ['English', 'Navajo'])
        self.assertFalse(apache['allocations'])
        asl = self.record('NM', 'Albuquerque Sign Language')
        self.assertTrue(any(o['languages'] == ['English', 'American Sign Language'] for o in asl['observations']))
        self.assertIsNone(CODES.get('Keres'))
        self.assertIsNone(CODES.get('Tiwa'))

    def test_model_ordering_and_primary_corrections_remain_visible(self):
        armijo = self.record('NM', 'Armijo')
        self.assertTrue(all(a['shares'] is None for a in armijo['allocations'] if a['grade'] in {'K', '1', '2'}))
        corrales = self.record('NM', 'Corrales International')
        primary = [a for a in corrales['allocations'] if a['source'] == 'wp_nm_corrales']
        self.assertEqual(primary[0]['shares'], {'Spanish':90,'English':10})
        self.assertEqual(primary[1]['shares'], {'Spanish':50,'English':50})
        self.assertEqual(primary[1]['grade'], '2-5')
        self.assertTrue(all(a['period'] == 'undated' for a in primary))

    def test_colorado_aliases_and_population_models(self):
        pioneer = self.record('CO', 'Escuela Bilingüe Pioneer')
        self.assertEqual(len([p for p in self.programmes if p['state']=='CO' and 'Pioneer' in p['school']]), 1)
        self.assertTrue(any(o['delivery'] == 'whole_school' for o in pioneer['observations']))
        lasley = self.record('CO', 'Lasley')
        lumberg = self.record('CO', 'Lumberg')
        self.assertTrue(any(o['population'] == 'two_way' for o in lasley['observations']))
        self.assertTrue(any(o['population'] == 'one_way' for o in lumberg['observations']))
        boltz = self.record('CO', 'Boltz')
        self.assertEqual(boltz['reference']['status'], 'confirmed_2025_26')
        self.assertEqual(boltz['reference']['method'], 'continuity_no_end_indication')
        self.assertIn('2018',boltz['reference']['period'])
        french = self.record('CO', 'Denver Language School', 'French')
        self.assertTrue(all(o['grade'] in {'not_reported','6-8'} for o in french['observations']))
        self.assertTrue(all(a['grade'] == '6-8' for a in french['allocations']))

    def test_flagstaff_tracks_and_approximate_points_are_not_collapsed(self):
        dine = self.record('AZ', 'Puente de Hózhó', 'Navajo')
        spanish = self.record('AZ', 'Puente de Hózhó', 'Spanish')
        self.assertEqual(dine['school_id'], spanish['school_id'])
        self.assertNotEqual(dine['program_id'], spanish['program_id'])
        self.assertTrue(all(o['grade'] == 'K-5' for o in dine['observations']))
        self.assertTrue(all(a['shares'] is None for a in dine['allocations'] if a['grade'] in {'K','1'}))
        self.assertEqual(next(a['shares'] for a in dine['allocations'] if a['grade']=='2-5'), {'English':50,'Navajo':50})

    def test_arizona_partner_languages_and_denominators(self):
        tarwater = self.record('AZ', 'Tarwater', 'Mandarin Chinese')
        self.assertFalse(any('Spanish' in o['languages'] for o in tarwater['observations']))
        coronado = self.record('AZ', 'Coronado', 'Mandarin Chinese')
        self.assertFalse(any(a['shares'] for a in coronado['allocations']))
        saguaro = self.record('AZ', 'Saguaro')
        self.assertTrue(all(o['languages'] == ['Spanish'] and o['language_role'] == 'elective' for o in saguaro['observations']))
        lowell = self.record('AZ', 'Lowell')
        self.assertEqual(lowell['allocations'][0]['grade'], 'K-1')
        self.assertIn('320 core instructional minutes', lowell['allocations'][0]['basis'])
        bloom = self.record('AZ', 'Bloom')
        self.assertEqual(bloom['allocations'][0]['shares'], {'Spanish':90,'English':10})
        self.assertTrue(all(a['period'] != '2025-26' for a in bloom['allocations']))

    def test_kansas_mandarin_phase_out_and_future_relocation(self):
        valley = self.record('KS', 'Valley Park')
        self.assertEqual(valley['track'], 'Mandarin Chinese')
        self.assertEqual(valley['observations'][0]['grade'], '3-5')
        self.assertTrue(all(a['grade'] == '3-5' for a in valley['allocations']))
        self.assertTrue(any(e['year'] is None and e['status']=='announced_future_end' for e in valley['events']))
        arbor = self.record('KS', 'Arbor Creek')
        self.assertEqual(arbor['reference']['status'], 'planned_future')

    def test_kansas_proposals_and_host_websites_are_not_implementation(self):
        frances = self.record('KS', 'Frances Willard')
        new_stanley = self.record('KS', 'New Stanley')
        self.assertEqual(frances['reference']['status'], 'planned_reference_year_offering')
        self.assertEqual(new_stanley['reference']['status'], 'confirmed_2025_26')
        self.assertTrue(any(e['status']=='closure_proposal_reversed' for e in new_stanley['events']))
        self.assertFalse(any('Morse' in p['school'] or 'Carver' in p['school'] for p in self.programmes if p['state']=='KS'))

    def test_nebraska_funding_and_pupil_mix_are_not_immersion_time(self):
        washington = self.record('NE', 'Washington')
        self.assertFalse(washington['allocations'])
        scott = self.record('KS', 'Scott Dual')
        self.assertFalse(any(a['shares'] for a in scott['allocations']))
        for school in ['Friedel', 'Connely', 'Dual Language Academy']:
            p = self.record('NE', school)
            self.assertTrue(p['reference']['eligibility'].startswith('candidate_'))
            self.assertIn('not_established', p['reference']['funding'])

    def test_source_scope_mutations_are_detected(self):
        rows = copy.deepcopy(self.tables)
        source = source_id('UT', 'wp_ut_roster26', self.sources)
        row = next(r for r in rows['program_configurations'] if r['source_id']==source)
        row['school_year'] = '2025-26'
        self.assertTrue(any('grade/model/year scope changed' in e for e in audit_errors(ROOT,rows,check_hashes=False)))
        rows = copy.deepcopy(self.tables)
        row = next(r for r in rows['program_languages'] if r['source_id']==source)
        row['language_name'] = 'English'
        self.assertTrue(any('language inferred' in e for e in audit_errors(ROOT,rows,check_hashes=False)))

    def test_state_screening_can_be_retained_without_fake_schools_or_LEAs(self):
        rows = [r for r in self.tables['evidence_claims'] if r['attribute']=='western_plains_screening_observation' and r['entity_type']=='state']
        self.assertEqual(len(rows), 591)  # CO 52 + university NM 398 + AZ 140 + KS 1
        self.assertFalse(any(r['district_name']=='State Charter Schools' for r in self.tables['districts']))
        bad = copy.deepcopy(self.tables)
        next(r for r in bad['evidence_claims'] if r['entity_type']=='state')['entity_id']='ZZ'
        self.assertTrue(any('unknown polymorphic entity' in e for e in validate_tables(bad,self.definition)))

    def test_assessment_outputs_unchanged_and_public_excerpt_is_precise(self):
        audit = json.loads((ROOT/AUDIT).read_text())
        self.assertTrue(all(digest(ROOT/path)==expected for path,expected in audit['preserved_assessment_outputs'].items()))
        doc = self.sources['wp_az_navegante_js']
        raw = (ROOT/doc['path']).read_bytes()
        metadata = json.loads((ROOT/doc['metadata_path']).read_text())
        self.assertTrue(raw.startswith(b'[') and raw.endswith(b']'))
        self.assertNotIn(b'supabase',raw)
        self.assertNotEqual(metadata['sha256'],metadata['full_response_sha256'])
        self.assertIn('excerpt',metadata['archive_kind'])
        for doc in self.sources.values():
            meta = json.loads((ROOT/doc['metadata_path']).read_text())
            if meta['capture_method'] == 'public_browser_rendered_html':
                self.assertIn('rendered',meta['archive_kind'])
                self.assertIsNone(meta['full_response_sha256'])
                self.assertEqual(meta['full_capture_sha256'],meta['sha256'])


if __name__ == '__main__':
    unittest.main()
