"""Regressions for grade, program, date and language scope in Texas source repairs."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

from dl_outcomes.validation import load, validate_tables

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tx51_validation', ROOT / 'scripts/validate_texas_cleanup_pass51.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class TexasCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = ROOT / 'data/registry/texas'
        inputs = data / 'pass51'
        cls.tracks = audit.read_csv(data / 'texas_language_program_tracks_pass51.csv')
        cls.allocations = audit.read_csv(data / 'texas_k_allocation_evidence_pass51.csv')
        cls.prior_tracks = audit.read_csv(data / 'texas_language_program_tracks_pass50.csv')
        cls.prior_allocations = audit.read_csv(data / 'texas_k_allocation_evidence_pass50.csv')
        cls.decisions = json.loads((inputs / 'language_decisions.json').read_text())
        cls.reviews = json.loads((inputs / 'allocation_reviews.json').read_text())
        cls.additions = json.loads((inputs / 'allocation_additions.json').read_text())
        cls.sources = {r['source_id']: r for r in audit.read_csv(inputs / 'source_register.csv')}

    def errors(self, tracks=None, allocations=None):
        return audit.check_rows(self.tracks if tracks is None else tracks,
            self.allocations if allocations is None else allocations,
            self.prior_tracks, self.prior_allocations, self.decisions, self.reviews,
            self.additions, self.sources)

    def test_saved_cleanup_and_archived_public_evidence_validate(self):
        self.assertEqual(audit.validate(ROOT)['status'], 'PASS')

    def test_district_policy_does_not_confirm_a_campus_in_2023_24(self):
        rows = copy.deepcopy(self.tracks)
        row = next(r for r in rows if r['district']=='SPRING ISD' and r['TAPR_program_group']=='one_way')
        row.update(campus_specific_2023_24_roster_confirmed='YES', historical_2023_24_pair_status='YES')
        self.assertTrue(any('backdated' in e for e in self.errors(tracks=rows)))

    def test_elementary_model_does_not_resolve_a_secondary_language_pair(self):
        rows = copy.deepcopy(self.tracks)
        row = next(r for r in rows if r['campus_id']=='071905001')
        row.update(language_pair='Spanish–English', partner_language='Spanish', instruction_languages='English;Spanish')
        self.assertTrue(any('secondary reporting group' in e for e in self.errors(tracks=rows)))

    def test_undated_campus_handbook_does_not_confirm_a_historical_year(self):
        rows = copy.deepcopy(self.tracks)
        row = next(r for r in rows if r['campus_id']=='227901158')
        row.update(campus_specific_2023_24_roster_confirmed='YES', historical_2023_24_pair_status='YES')
        self.assertTrue(any('unsupported historical year' in e for e in self.errors(tracks=rows)))

    def test_numeric_model_does_not_establish_lajoya_partner_language(self):
        rows = copy.deepcopy(self.tracks)
        row = next(r for r in rows if r['district']=='LA JOYA ISD')
        row['language_pair']='Spanish–English'
        self.assertTrue(any('La Joya numeric model' in e for e in self.errors(tracks=rows)))

    def test_pre_k_proxy_cannot_become_a_linked_kindergarten_schedule(self):
        rows = copy.deepcopy(self.allocations)
        row = next(r for r in rows if r['pass51_k_support']=='PREK_PROXY_NOT_K_QUANTIFIED')
        row['language_track_id_if_unambiguous']=next(r['language_track_id'] for r in self.tracks if r['registry_record_id']==row['registry_record_id'])
        self.assertTrue(any('Unsupported K proxy' in e for e in self.errors(allocations=rows)))

    def test_ysleta_narrative_label_is_not_an_exact_numeric_timetable(self):
        rows = copy.deepcopy(self.allocations)
        row = next(r for r in rows if r['campus_id'].startswith('071905'))
        row['pass51_k_support']='EXPLICIT_K'
        self.assertTrue(any('exact K timetable' in e for e in self.errors(allocations=rows)))

    def test_reilly_mandarin_policy_cannot_be_assigned_to_spanish_track(self):
        rows = copy.deepcopy(self.allocations)
        row = next(r for r in rows if r['campus_id']=='227901132')
        row['language_track_id_if_unambiguous']=next(r['language_track_id'] for r in self.tracks if r['campus_id']=='227901132' and r['partner_language']=='Spanish')
        self.assertTrue(any('assigned to Spanish' in e for e in self.errors(allocations=rows)))

    def test_current_spring_policy_cannot_replace_the_rejected_old_observation(self):
        old = [r for r in self.allocations if r['pass51_review_status']=='HISTORICAL_CITATION_REJECTED_CURRENT_OBSERVATION_ADDED']
        new = [r for r in self.allocations if r['pass51_observation_origin']=='ADDED_PASS51']
        self.assertEqual({r['registry_record_id'] for r in old}, {r['registry_record_id'] for r in new})
        self.assertTrue(all('2021-22' in r['source_period'] and not r['language_track_id_if_unambiguous'] for r in old))
        self.assertTrue(all('2026-11-04' in r['source_period'] for r in new))
        rows = [r for r in self.allocations if r not in old]
        self.assertTrue(any('Allocation identity lost' in e for e in self.errors(allocations=rows)))

    def test_shared_tables_expose_qualifications_as_filterable_fields(self):
        definition, tables = load(ROOT)
        texas_schools = {r['school_id'] for r in tables['schools'] if r['state_code']=='TX'}
        texas_schedules = [r for r in tables['allocation_schedules'] if r['school_id'] in texas_schools]
        proxy = next(r for r in texas_schedules if r['grade_support_status']=='EARLIER_GRADE_PROXY_NOT_TARGET_QUANTIFIED')
        self.assertEqual(proxy['evidence_review_status'], 'RETAINED_PROXY_REQUIRES_K_SCHEDULE')
        rejected = [r for r in texas_schedules if r['grade_support_status']=='SOURCE_DOES_NOT_SUPPORT_PROGRAM_GRADE_PERIOD']
        self.assertEqual(len(rejected), 23)
        self.assertTrue(all(r['site_id'] is None for r in rejected))
        proxy['schedule_status']='observed_schedule'
        self.assertTrue(any('unresolved grade evidence promoted' in e for e in validate_tables(tables, definition)))


if __name__=='__main__':
    unittest.main()
