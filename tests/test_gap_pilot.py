"""Pilot attribution, temporal bounds, core scope and immutable comparisons."""
import csv
import json
from pathlib import Path
import unittest

from dl_outcomes.baseline_selection import Selection, grade_set, select_rows
from dl_outcomes.gap_pilot import audit_errors, comparison, inputs, revise_report_paths
from dl_outcomes.io import digest
from dl_outcomes.validation import load

ROOT=Path(__file__).resolve().parents[1]


class GapPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _,cls.tables=load(ROOT)
        cls.config,cls.files=inputs(ROOT)
        cls.rules=json.loads((ROOT/'data/baselines/national_structural_v1/rules.json').read_text())
        cls.selection=Selection(cls.tables,cls.rules)
        cls.fields,cls.schools,cls.districts,cls.completeness=comparison(ROOT,cls.tables)

    def test_original_rows_sources_reports_baseline_and_twelve_layers_are_preserved(self):
        self.assertEqual(audit_errors(ROOT,self.tables),[])
        self.assertEqual(len(self.files['preservation']['preserved_assessment_context_outputs']),12)

    def test_same_sample_distinguishes_new_models_from_extra_observations(self):
        self.assertEqual((len(self.districts),len(self.schools)),(9,290))
        elementary=[r for r in self.schools if r['elementary_denominator']]
        self.assertEqual(len(elementary),222)
        self.assertEqual(sum(r['before_has_primary_model'] for r in elementary),37)
        self.assertEqual(sum(r['after_has_primary_model'] for r in elementary),59)
        self.assertEqual(len(self.files['observations']),257)
        self.assertFalse(any(r['before_has_primary_model'] and not r['after_has_primary_model'] for r in elementary))

    def test_previously_coded_alief_models_are_not_counted_as_new_availability(self):
        row=next(r for r in self.districts if r['district_key']=='tx_alief')
        self.assertEqual((row['before_with_primary_model'],row['after_with_primary_model']), (18,18))
        self.assertEqual(row['newly_with_primary_model'],0)
        resolved=next(r for r in self.completeness if r['district_key']=='tx_alief' and r['variable']=='population_model')
        self.assertGreater(resolved['newly_resolved'],0)

    def test_no_allocation_is_assigned_to_secondary_only_sites(self):
        for row in self.schools:
            if row['school_level']=='secondary_6_plus':
                self.assertEqual((row['elementary_denominator'],row['after_has_primary_model']),(0,0))

    def test_non_k_campus_does_not_inherit_a_kindergarten_schedule(self):
        facts=[f for f in self.files['observations'] if f['school_name']=='Shiloh Valley Elementary School' and f['variable']=='elementary_allocation_model']
        self.assertTrue(facts)
        self.assertEqual({f['grade_scope'] for f in facts},{'4-5'})

    def test_alief_allocation_is_bounded_by_existing_campus_grade_context(self):
        with (ROOT/'data/baselines/national_structural_v1/schools.csv').open() as stream:
            schools={r['school_id']:r for r in csv.DictReader(stream)}
        facts=[f for f in self.files['observations'] if f['district_key']=='tx_alief' and f['variable']=='elementary_allocation_model']
        self.assertEqual(len(facts),18)
        for fact in facts:
            self.assertLessEqual(max(grade_set(fact['grade_scope'])),int(schools[fact['school_id']]['school_grade_high']))

    def test_core_only_full_spanish_ratios_keep_their_scope_and_inference(self):
        facts=[f for f in self.files['observations'] if f['variable']=='elementary_allocation_model' and f['value']=='100/0']
        self.assertTrue(facts)
        for fact in facts:
            self.assertIn('core',fact['percentage_basis'].lower())
            self.assertEqual(fact['shares'],{'Spanish':100,'English':0})
            if fact['district_key']=='nc_union':
                self.assertEqual(fact['schedule_status'],'inferred_plan')
        self.assertFalse(any(f['schedule_status']=='observed_schedule' for f in facts))

    def test_student_composition_does_not_become_buncombe_time_allocation(self):
        self.assertFalse(any(f['district_key']=='nc_buncombe' and f['variable']=='elementary_allocation_model' for f in self.files['observations']))
        row=next(r for r in self.districts if r['district_key']=='nc_buncombe')
        self.assertEqual(row['after_with_primary_model'],0)

    def test_vietnamese_inference_remains_with_its_language_programme(self):
        facts=[f for f in self.files['observations'] if f['district_key']=='tx_garland' and f['variable']=='elementary_allocation_model']
        recipient=next(f for f in facts if f['school_name']=='VERNAL LISTER EL')
        self.assertEqual(recipient['shares'],{'Vietnamese':50,'English':50})
        self.assertEqual(recipient['method'],'user_authorized_same_programme_inference')
        self.assertEqual(recipient['schedule_status'],'inferred_plan')
        self.assertTrue(all('Vietnamese' in f['shares'] or f['school_name']=='CLASSICAL CENTER AT VIAL EL' for f in facts))

    def test_use_bounds_do_not_redate_undated_observations_or_fill_2023(self):
        row=dict(_id='new',school_year=None,evidence_period_raw='undated',_earliest_reviewed_selection_year='2025-26')
        self.assertEqual(select_rows([row],'2023-24'),([], 'later_only'))
        chosen,_=select_rows([row],'2025-26')
        self.assertIsNone(chosen[0]['school_year'])
        with self.assertRaisesRegex(ValueError,'missing or later'):
            select_rows([row],'2023-24',override_ids=['new'])
        for fact in self.files['observations']:
            if fact['district_key']=='tx_alief' and fact['variable']=='instruction_languages':
                site=next(s for s in self.tables['program_sites'] if s['site_id']==fact['site_id'])
                field,_=self.selection.select_field(site,'instruction_languages','2023-24')
                new_languages={r['language_record_id'] for r in self.tables['program_languages'] if r['source_locator']==fact['fact_id']}
                self.assertFalse(new_languages & set(field['selected_evidence_ids'].split(' | ')))
                break

    def test_legacy_coverage_views_also_honor_new_reference_bounds(self):
        from dl_outcomes.allocation_coverage import report_rows as kindergarten_rows
        from dl_outcomes.elementary_audit import report_rows as elementary_rows
        pilot_ids={r['schedule_id'] for r in self.tables['allocation_schedules']
            if any(f['fact_id']==r['source_locator'] and f['state']=='TX' for f in self.files['observations'])}
        details,_,_=kindergarten_rows(self.tables)
        for row in details:
            if row['state_code']=='TX':
                self.assertFalse(pilot_ids & set(row['k_schedule_ids'].split(' | ')))
        details,_=elementary_rows(self.tables)
        for row in details:
            if row['state_code']=='TX' and row['audit_scope']=='reference_working_set':
                self.assertFalse(pilot_ids & set(row['model_evidence_ids'].split(' | ')))

    def test_native_language_k_literacy_is_not_a_verified_equal_k_schedule(self):
        for name in ['Central Elementary School','Doña Ana Elementary School']:
            facts=[f for f in self.files['observations'] if f['district_key']=='nm_lcps' and f['school_name']==name and f['variable']=='elementary_allocation_model']
            generic=next(f for f in facts if f['grade_scope']=='K-5')
            upper=next(f for f in facts if f['grade_scope']=='2-5')
            self.assertEqual(generic['schedule_status'],'reported_policy_requires_review')
            self.assertFalse(generic['shares'])
            self.assertEqual(upper['shares'],{'Spanish':50,'English':50})

    def test_later_reilly_move_preserves_the_earlier_whole_school_observation(self):
        facts=[f for f in self.files['observations'] if f['school_name']=='REILLY EL']
        before=next(f for f in facts if f['variable']=='campus_delivery_structure')
        after=next(f for f in facts if f['variable']=='campus_programme_change')
        self.assertEqual(before['source_school_year'],'2025-26')
        self.assertEqual(after['reference_year'],'2026-27')
        self.assertEqual(after['earliest_reviewed_selection_year'],'2026-27')

    def test_linked_english_evidence_is_explicit_and_excludes_charter_models(self):
        facts=[f for f in self.files['observations'] if f['method']=='linked_primary_sources']
        self.assertTrue(facts)
        for fact in facts:
            self.assertIn('English and a partner language',fact['source_quote'])
            self.assertIn('prior_nm_state',fact['source_keys'])
            self.assertEqual(fact['value'],['English','Spanish'])
            self.assertNotIn('International',fact['school_name'])
            self.assertNotIn('Charter',fact['school_name'])

    def test_unresolved_candidates_and_review_cases_are_retained(self):
        self.assertEqual(len(self.files['review_cases']),9)
        self.assertFalse(any(f['district_key']=='nm_gadsden' for f in self.files['observations']))
        before={r['site_id'] for r in self.files['baseline_programme_records']}
        self.assertTrue(before<={r['site_id'] for r in self.tables['program_sites']})

    def test_changed_derived_reports_get_a_new_path_without_overwriting_milestones(self):
        old=next(iter(self.files['preservation']['preserved_prior_reports']))
        checksum=digest(ROOT/old)
        contents,aliases=revise_report_paths(ROOT,{old:'recomputed\n'})
        self.assertIn(old,aliases)
        self.assertNotEqual(old,aliases[old])
        self.assertEqual(contents[aliases[old]],'recomputed\n')
        self.assertEqual(digest(ROOT/old),checksum)
