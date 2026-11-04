"""Source-scope, longitudinal identity and deferred-assessment migration regressions."""
import copy
import json
from pathlib import Path
import unittest

from dl_outcomes.io import read_csv
from dl_outcomes.structural import FIVE, generate_report, migration_errors
from dl_outcomes.validation import load, validate_tables

ROOT = Path(__file__).resolve().parents[1]


class StructuralIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.definition, cls.tables = load(ROOT)
        cls.sites = {r['site_id']:r for r in cls.tables['program_sites']}
        cls.programs = {r['program_id']:r for r in cls.tables['programs']}
        cls.rows = sum((read_csv(ROOT/f'data/registry/state_dl_programs_{name}_2025_26.csv') for name in FIVE.values()), [])

    def record(self, school):
        return next(r for r in self.rows if r['school_name']==school)

    def schedules(self, pid):
        sites = {r['site_id'] for r in self.tables['program_sites'] if r['program_id']==pid}
        return [r for r in self.tables['allocation_schedules'] if r['site_id'] in sites]

    def test_review_views_and_source_preservation_audit_are_current(self):
        report = generate_report(ROOT,check=True)
        self.assertEqual(len(report['states_with_integrated_program_evidence']),9)
        self.assertEqual(len(report['other_states_without_program_evidence']),41)
        self.assertEqual(migration_errors(ROOT,self.tables),[])

    def test_original_attribute_values_and_raw_dates_are_all_retained(self):
        rows = copy.deepcopy(self.tables)
        claim = next(r for r in rows['evidence_claims'] if r['source_locator'].endswith('-25-E-1') and r['evidence_period_raw'] is None)
        claim['valid_from_year']='2025-26'
        self.assertTrue(any('Source applicability replaced' in e for e in migration_errors(ROOT,rows,check_hashes=False)))

    def test_historical_school_lead_does_not_create_an_unreviewed_program(self):
        rows=copy.deepcopy(self.tables)
        rows['programs'].append(dict(program_id='CA-test-unreviewed-lead',state_code='CA'))
        self.assertTrue(any('screening leads became programs' in e for e in migration_errors(ROOT,rows,check_hashes=False)))

    def test_operation_reference_year_cannot_date_an_undated_allocation(self):
        rows = copy.deepcopy(self.tables)
        schedule = next(r for r in rows['allocation_schedules'] if '-25-E-' in r['source_locator'] and r['school_year'] is None)
        schedule['school_year']='2025-26'
        self.assertTrue(any('Allocation source period replaced' in e for e in migration_errors(ROOT,rows,check_hashes=False)))

    def test_sfusd_50_50_policy_does_not_erase_older_80_20(self):
        record = next(r for r in self.rows if r['district_name']=='San Francisco Unified School District' and r['partner_language']=='Spanish')
        schedules = self.schedules(record['program_id'])
        self.assertTrue(any(r['reported_model_label']=='80/20' and r['school_year'] is None for r in schedules))
        self.assertTrue(any(r['reported_model_label']=='50/50' and r['school_year']=='2025-26' and r['schedule_status']=='documented_plan' for r in schedules))

    def test_yu_ming_range_and_conflicting_points_do_not_become_a_numeric_plan(self):
        pid=self.record('Yu Ming Charter School')['program_id']
        schedules=self.schedules(pid);ids={r['schedule_id'] for r in schedules}
        self.assertTrue({'85/15','90/10'} <= {r['reported_model_label'] for r in schedules})
        self.assertTrue(all(r['grade_support_status']=='CONFLICTING_SOURCE_CLAIMS' for r in schedules))
        self.assertFalse(any(r['schedule_id'] in ids for r in self.tables['instructional_allocations']))
        self.assertTrue(any(r['entity_id']==pid and r['attribute']=='kindergarten_share_ranges_json' and r['evidence_period_raw']=='2025-26' for r in self.tables['evidence_claims']))

    def test_west_portal_later_schedule_is_not_backdated(self):
        schedules=self.schedules(self.record('West Portal Elementary School')['program_id'])
        self.assertTrue(any(r['reported_model_label']=='50/50' and r['school_year']=='2026-27' for r in schedules))
        self.assertFalse(any(r['school_year']=='2025-26' for r in schedules))

    def test_continuity_confirmation_requires_its_saved_review(self):
        rows=copy.deepcopy(self.tables)
        status=next(r for r in rows['program_status_history'] if r['confirmation_method']=='continuity_no_end_indication')
        pid=self.sites[status['site_id']]['program_id']
        rows['evidence_claims']=[r for r in rows['evidence_claims'] if not (r['entity_type']=='program' and r['entity_id']==pid and r['attribute']=='continuity_review')]
        self.assertTrue(any('continuity confirmation lacks' in e for e in validate_tables(rows,self.definition)))

    def test_indigenous_operation_funding_and_intensity_remain_distinct(self):
        record=self.record('Nk̓ʷusm Salish Language School')
        status=next(r for r in self.tables['program_status_history'] if self.sites[r['site_id']]['program_id']==record['program_id'])
        self.assertEqual(status['operating_status'],'confirmed_2025_26')
        self.assertTrue(status['eligibility_status'].startswith('candidate_public_funding'))
        self.assertFalse(self.schedules(record['program_id']))
        self.assertFalse(self.schedules(self.record('Hardin Primary School')['program_id']))
        cuts={r['site_id'] for r in self.tables['program_sites'] if r['program_id']==self.record('Cuts Wood School')['program_id']}
        self.assertFalse(any(r['site_id'] in cuts and r['language_name']=='English' for r in self.tables['program_languages']))

    def test_research_name_correction_retains_both_school_aliases(self):
        aliases=[r for r in self.tables['identifiers'] if r['namespace']=='FIVE_STATE_RESEARCH_school_id' and r['native_id'] in {'MT-S-ece7683a18bf','MT-S-9f462a61e60b'}]
        self.assertEqual({r['native_id'] for r in aliases},{'MT-S-ece7683a18bf','MT-S-9f462a61e60b'})
        self.assertEqual(len({r['entity_id'] for r in aliases}),1)

    def test_directory_language_does_not_infer_english(self):
        rows=copy.deepcopy(self.tables)
        sources={r['source_id']:r for r in rows['sources']}
        record=copy.deepcopy(next(r for r in rows['program_languages'] if sources[r['source_id']]['dataset_id']=='OR_STRUCTURAL_DIRECTORY'))
        record.update(language_record_id='test-invented-English',language_name='English',language_code='en')
        rows['program_languages'].append(record)
        self.assertTrue(any('silently acquired an English' in e for e in migration_errors(ROOT,rows,check_hashes=False)))

    def test_composite_campus_policy_cannot_become_a_track_timetable(self):
        rows=copy.deepcopy(self.tables)
        schedule=next(r for r in rows['allocation_schedules'] if r['grade_support_status']=='COMPOSITE_TRACK_SCOPE_UNRESOLVED')
        schedule['site_id']=next(r['site_id'] for r in rows['program_sites'] if r['school_id']==schedule['school_id'])
        self.assertTrue(any('Composite Oregon campus model' in e for e in migration_errors(ROOT,rows,check_hashes=False)))

    def test_reconciled_oregon_aliases_keep_source_observations_and_school_units(self):
        rows=read_csv(ROOT/'data/registry/oregon_nces/reconciled/oregon_program_observations_with_nces_reconciled.csv')
        four=[r for r in rows if 'Four Rivers' in r['school_name']]
        self.assertEqual(len({r['program_identity_key'] for r in four}),3)
        school_ids={r['school_id'] for r in self.tables['program_sites'] if r['program_id'] in {x['program_identity_key'] for x in four}}
        self.assertEqual(len(school_ids),1)
        mcd=[r for r in rows if 'McDaniel' in r['school_name']]
        self.assertEqual(len(mcd),4)
        self.assertEqual(len({r['program_identity_key'] for r in mcd}),2)
        school_keys={r['school_id'] for r in self.tables['program_sites'] if r['program_id'] in {x['program_identity_key'] for x in mcd}}
        self.assertEqual(len(school_keys),1)
        nc=[r for r in self.tables['identifiers'] if r['namespace']=='NCES_school_id' and r['entity_id'] in school_ids]
        self.assertTrue(all(r['valid_from_year']=='2024-25' for r in nc))

    def test_model_only_evidence_cannot_become_an_accepted_schedule(self):
        rows=copy.deepcopy(self.tables)
        row=next(r for r in rows['allocation_schedules'] if r['grade_support_status']=='PUBLISHED_MODEL_ONLY')
        row['schedule_status']='documented_plan'
        self.assertTrue(any('unresolved grade evidence promoted' in e for e in validate_tables(rows,self.definition)))

    def test_proficiency_collection_is_deferred_and_prior_values_preserved(self):
        self.assertEqual(json.loads((ROOT/'config/project.json').read_text())['collection_phase'],'structural_inventory')
        rows=copy.deepcopy(self.tables)
        rows['datasets'].append(dict(dataset_id='NEW_PROFICIENCY',state_code='CA',layer='el_proficiency'))
        self.assertTrue(any('New non-structural dataset' in e for e in migration_errors(ROOT,rows,check_hashes=False)))


if __name__=='__main__':
    unittest.main()
