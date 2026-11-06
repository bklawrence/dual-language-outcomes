"""Elementary denominator, model-availability and dated grade-context safeguards."""
from pathlib import Path
import unittest

from dl_outcomes.elementary_audit import elementary_scope, elementary_span, grade_matches, numeric_model, report_rows
from dl_outcomes.validation import load

ROOT = Path(__file__).resolve().parents[1]


class ElementaryDefinitionTests(unittest.TestCase):
    def test_primary_grades_count_even_without_kindergarten(self):
        for low,high in [(0,8),(0,12),(3,6),(1,5),(5,12),(-1,5)]:
            self.assertEqual(elementary_span(low,high),'elementary')
        for low,high in [(6,6),(6,8),(7,12)]:
            self.assertEqual(elementary_span(low,high),'secondary_6_plus')
        self.assertEqual(elementary_span(-1,-1),'preschool_only')
        for low,high in [(None,8),(-2,8),(15,15),(8,6)]:
            self.assertEqual(elementary_span(low,high),'unknown')

    def test_grade_six_only_is_excluded_despite_an_elementary_label(self):
        self.assertEqual(elementary_scope('elementary grades 6-6'),'secondary_6_plus')
        self.assertEqual(elementary_scope('3-6'),'elementary')
        self.assertEqual(elementary_scope('elementary; starts grade 1'),'elementary')
        self.assertEqual(elementary_scope('K-8 pathway; campus grade band unresolved'),'unknown')

    def test_models_require_an_instructional_allocation_combination(self):
        for label in ['90-10','80/20','70:30','45/45/10','K-1:90/10; 2-5:50/50',
                      'English 50%; Spanish 50%','100% target-language immersion']:
            with self.subTest(label=label):self.assertTrue(numeric_model(label))
        for label in ['Other','school year 2025-26','grades 3-6','80/10','50/50 student population',
                      '50% English speakers; 50% Spanish speakers','80% target language']:
            with self.subTest(label=label):self.assertFalse(numeric_model(label))


class ElementaryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _,cls.tables=load(ROOT)
        cls.details,cls.summary=report_rows(cls.tables)
        cls.working=[r for r in cls.details if r['audit_scope']=='reference_working_set']

    def school(self,state,name):
        return next(r for r in self.working if r['state_code']==state and r['school_name']==name)

    def test_all_covered_states_have_auditable_balanced_denominators(self):
        self.assertEqual(len(self.summary),74)
        self.assertEqual(len({r['state_code'] for r in self.summary}),37)
        self.assertEqual(len({(r['audit_scope'],r['school_id']) for r in self.details}),len(self.details))
        self.assertEqual(len({(r['audit_scope'],r['audit_school_id']) for r in self.details}),len(self.details))
        self.assertTrue(any(' | ' in r['research_school_ids'] for r in self.details if r['audit_scope']=='all_recorded_programme_hosts'))
        for row in self.summary:
            self.assertEqual(row['inventory_school_units'],sum(row[k] for k in ['elementary_school_units',
                'secondary_6_plus_school_units_excluded','preschool_only_school_units_excluded','unresolved_grade_school_units']))
            self.assertEqual(row['elementary_school_units'],row['elementary_schools_with_numerical_model']+row['elementary_schools_missing_numerical_model'])
            self.assertEqual(row['statewide_completeness'],'not_established')

    def test_wa_elementary_models_and_secondary_records_remain_distinct(self):
        row=next(r for r in self.summary if r['audit_scope']=='reference_working_set' and r['state_code']=='WA')
        self.assertEqual((row['elementary_school_units'],row['elementary_schools_with_numerical_model'],row['secondary_6_plus_school_units_excluded']),(126,126,49))
        secondary=[r for r in self.working if r['state_code']=='WA' and r['elementary_classification']=='secondary_6_plus']
        self.assertTrue(all(r['allocation_status']=='not_applicable_secondary' and not r['has_numerical_allocation_model'] for r in secondary))
        self.assertTrue(any(r['numerical_model_labels'] for r in secondary))
        self.assertEqual(len([r for r in self.working if r['state_code']=='WA' and r['school_name']=='Beacon Hill International School']),1)

    def test_upper_elementary_and_mixed_schools_are_included(self):
        for state,name in [('OR','Columbia Vista Intermediate'),('KS','Valley Park Elementary'),('CO','Denver Language School')]:
            row=self.school(state,name)
            self.assertEqual(row['elementary_classification'],'elementary')
            self.assertEqual(row['elementary_denominator'],1)
        self.assertEqual(self.school('OR','Columbia Vista Intermediate')['school_grade_low'],4)
        self.assertEqual(self.school('CO','Denver Language School')['school_grade_high'],8)

    def test_equal_minutes_and_half_day_plans_count_as_quantified_models(self):
        for name in ['Lowell Elementary School','San Tan Elementary School']:
            row=self.school('AZ',name)
            self.assertEqual(row['has_numerical_allocation_model'],1)
            self.assertIn('50',row['numerical_model_labels'])
        self.assertEqual(self.school('KS','Black Bob Elementary School')['has_numerical_allocation_model'],1)

    def test_qualitative_subject_language_descriptions_do_not_supply_ratios(self):
        row=self.school('KS','Scott Dual Language Magnet Elementary School')
        self.assertEqual(row['elementary_denominator'],1)
        self.assertEqual(row['has_numerical_allocation_model'],0)

    def test_official_school_grades_do_not_impute_a_programme_allocation(self):
        row=self.school('MT','Pretty Eagle Catholic Academy')
        self.assertEqual((row['school_grade_low'],row['school_grade_high']),(0,8))
        self.assertEqual(row['has_numerical_allocation_model'],0)
        self.assertEqual(row['grade_classification_basis'],'official_named_school_grade_statement')

    def test_old_grade_fallback_keeps_its_own_school_year(self):
        rows=[r for r in self.working if r['state_code']=='TX' and r['school_grade_reference_year']=='2023-24']
        self.assertTrue(rows)
        self.assertTrue(all(r['grade_evidence_ids'] for r in rows))

    def test_counted_models_retain_source_and_record_references(self):
        sources={r['source_id'] for r in self.tables['sources']}
        for row in self.details:
            if row['has_numerical_allocation_model']:
                self.assertTrue(row['model_evidence_ids'])
                self.assertTrue(set(row['model_source_ids'].split(' | '))<=sources)
                self.assertEqual(row['elementary_classification'],'elementary')


class GradeContextMatchingTests(unittest.TestCase):
    def tables(self):
        return dict(states=[dict(state_fips='53',state_code='WA')],
            schools=[dict(school_id='s',state_code='WA',school_name='Campus')],
            program_sites=[dict(school_id='s',program_id='p')],
            identifiers=[dict(entity_type='school',entity_id='s',namespace='WA_OSPI_school_code',native_id='1234')],
            evidence_claims=[],districts=[],school_district_history=[])

    def row(self,year,low,high):
        return dict(fips=53,ncessch='530000001234',seasch='00100-1234',year=year,
            school_name='Campus',lea_name='District',lowest_grade_offered=low,highest_grade_offered=high)

    def test_older_complete_grades_only_fill_a_missing_current_range(self):
        t=self.tables()
        rows=[self.row(2023,0,5),self.row(2024,None,None)]
        self.assertEqual(grade_matches(t,rows)['s']['year'],2023)
        rows[1]=self.row(2024,6,8)
        self.assertEqual(grade_matches(t,rows)['s']['year'],2024)

    def test_reviewed_alias_cannot_override_an_existing_native_identifier(self):
        alias=dict(school_id='s',ncessch='another-id',rationale='bad mapping')
        with self.assertRaisesRegex(ValueError,'contradicts'):
            grade_matches(self.tables(),[self.row(2024,0,5)],[alias])


if __name__=='__main__':
    unittest.main()
