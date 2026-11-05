"""School identities, programme languages, source periods and screened-only coverage."""
import json
from pathlib import Path
import unittest

from dl_outcomes.elementary_audit import report_rows
from dl_outcomes.northern_central_review import inputs
from dl_outcomes.south_central_review import audit_errors, render_reports
from dl_outcomes.states.south_central import BASE, STATES, AUDIT
from dl_outcomes.validation import load

ROOT = Path(__file__).resolve().parents[1]


class SouthCentralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tables = load(ROOT)
        cls.programmes, cls.sources = inputs(ROOT, base=BASE, states=STATES)
        cls.details, cls.summary = report_rows(cls.tables)

    def programme(self, school, target=None):
        return next(p for p in self.programmes if p['school']==school
                    and (target is None or p['track']==target+' immersion'))

    def school(self, school):
        sid=self.programme(school)['school_id']
        return next(r for r in self.details if r['school_id']==sid and r['audit_scope']=='reference_working_set')

    def test_sources_and_previous_research_reconcile(self):
        self.assertEqual(audit_errors(ROOT,self.tables),[])
        self.assertEqual((len(self.programmes),len({p['school_id'] for p in self.programmes})),(101,86))
        audit=json.loads((ROOT/AUDIT).read_text())
        self.assertEqual(len(audit['preserved_reports']),114)
        self.assertEqual(len(audit['preserved_assessment_outputs']),12)

    def test_public_snapshot_redactions_retain_acquisition_and_saved_checksums(self):
        rows=json.loads((ROOT/BASE/'source_redactions.json').read_text())
        self.assertEqual(len(rows),4)
        for row in rows:
            source=self.sources[row['key']]
            self.assertNotEqual(source['sha256'],row['original_response_sha256'])
            self.assertEqual(source['sha256'],row['saved_redacted_sha256'])
            self.assertTrue(row['programme_text_unchanged'])
            self.assertIn(b'[REDACTED_EMBEDDED_MAP_SERVICE_TOKEN]',(ROOT/source['path']).read_bytes())
            self.assertFalse((ROOT/row['original_path']).exists())

    def test_mississippi_is_screened_with_no_fabricated_programme_or_zero_percent(self):
        self.assertFalse(any(p['state']=='MS' for p in self.programmes))
        contents, report=render_reports(ROOT,self.tables)
        row=next(r for r in report['state_summary'] if r['state']=='MS')
        self.assertEqual(row['confirmed_qualifying_reference_school_units'],0)
        self.assertIsNone(row['elementary_reference_model_coverage_pct'])
        self.assertEqual(report['screened_only_states'],['MS'])
        self.assertEqual(contents[BASE+'/ms_programmes.csv'].count('\n'),1)
        leads=json.loads((ROOT/BASE/'ms_screening.json').read_text())
        self.assertEqual(sum(r['source']=='sc_ms_choctaw' for r in leads),8)

    def test_arkansas_later_launch_keeps_distinct_population_models(self):
        watson=self.programme('Watson Elementary School');chicot=self.programme('Chicot Elementary School')
        self.assertEqual(watson['observations'][0]['population'],'one_way')
        self.assertEqual(chicot['observations'][0]['population'],'two_way')
        for p in [watson,chicot]:
            self.assertEqual((p['reference']['status'],p['observations'][0]['period']),('planned_future','2026-27'))
            self.assertFalse(p['allocations'])
        self.assertFalse(any(p['school']=='Lacey K-8 Academy' for p in self.programmes))

    def test_birmingham_pupil_balance_and_k8_name_do_not_become_a_day_model(self):
        p=self.programme('Booker T. Washington K-8 School')
        self.assertEqual((p['observations'][0]['population'],p['observations'][0]['delivery']),('two_way','strand'))
        self.assertEqual(p['observations'][0]['grade'],'PK-1; includes K')
        self.assertFalse(p['allocations'])
        self.assertEqual(self.school(p['school'])['has_numerical_allocation_model'],0)

    def test_tulsa_immersion_models_do_not_transfer_to_literacy_only_ratios(self):
        eis=[p for p in self.programmes if p['school']=='Eisenhower International School']
        self.assertEqual({p['track'] for p in eis},{'French immersion','Spanish immersion'})
        self.assertEqual(len({p['school_id'] for p in eis}),1)
        for p in eis:
            self.assertEqual(p['allocations'][0]['grade'],'K-2')
            self.assertEqual(p['allocations'][0]['label'],'90/10')
        for p in self.programmes:
            if p['district']=='Tulsa Public Schools' and 'dual language' in p['track']:
                self.assertFalse(p['allocations'])
        self.assertEqual(len([p for p in self.programmes if p['school']=='Kendall-Whittier Elementary School']),2)

    def test_norman_republished_article_names_truman_not_monroe(self):
        p=self.programme('Truman Primary School')
        self.assertEqual((p['observations'][0]['period'],p['allocations'][0]['shares']),('2025-26',{'Spanish':50,'English':50}))
        self.assertFalse(any(p['school']=='Monroe Elementary School' for p in self.programmes))
        self.assertEqual(self.programme('Adelaide Lee Elementary School')['reference']['status'],'planned_future')

    def test_cherokee_actual_greasy_kindergarten_and_later_charter_exit_are_distinct(self):
        tahlequah=self.programme('Cherokee Nation Immersion School – Tahlequah')
        greasy=self.programme('Cherokee Immersion School – Greasy')
        self.assertEqual(greasy['observations'][0]['grade'],'K')
        self.assertEqual(greasy['reference']['status'],'confirmed_2025_26')
        self.assertEqual(greasy['observations'][0]['languages'],['Cherokee'])
        self.assertTrue(any(e['year']=='2026-27' and 'charter' in e['status'] for e in tahlequah['events']))
        self.assertFalse(any('Kenwood' in p['school'] for p in self.programmes))
        self.assertFalse(tahlequah['allocations'])

    def test_osage_later_closure_and_reopening_appropriation_do_not_erase_reference_operation(self):
        p=self.programme('Daposka Ahnkodapi School')
        self.assertEqual(p['reference']['status'],'confirmed_2025_26')
        self.assertIn('tribal_government',p['reference']['eligibility'])
        self.assertEqual({e['year'] for e in p['events']},{'2026-27'})
        self.assertTrue(any('implementation_unverified' in e['status'] for e in p['events']))
        yuchi=self.programme('Yuchi Immersion School')
        self.assertFalse(yuchi['reference']['eligibility'].startswith('documented_'))

    def test_mamou_grade_five_and_teche_grade_three_are_elementary_but_cecilia_junior_is_secondary(self):
        for school in ['Mamou Junior High School','Teche Elementary School','Ruston Elementary School']:
            self.assertEqual(self.school(school)['elementary_denominator'],1)
        self.assertEqual(self.school('Cecilia Junior High School')['elementary_denominator'],0)
        self.assertEqual(self.school('Evangeline Reimagine Academy')['elementary_denominator'],0)

    def test_new_grade_context_is_dated_metadata_not_a_durable_identifier_crosswalk(self):
        rows=json.loads((ROOT/BASE/'grade_context_decisions.json').read_text())
        self.assertEqual(len(rows),68)
        ids={r['school_id'] for r in rows}
        claims=[r for r in self.tables['evidence_claims'] if r['entity_id'] in ids and r['attribute']=='elementary_audit_school_grade_context']
        self.assertEqual(len(claims),68)
        self.assertTrue(all(r['valid_from_year']=='2024-25' for r in claims))
        self.assertFalse(any(r['entity_id'] in ids and r['namespace']=='NCES_school_id' for r in self.tables['identifiers']))

    def test_louisiana_extra_language_classes_do_not_create_extra_immersion_strands(self):
        self.assertFalse(any('ASL' in p['track'] for p in self.programmes))
        self.assertFalse(any('Mandarin' in p['track'] for p in self.programmes if 'Audubon' in p['school']))
        self.assertFalse(any(p['school']=='Ruppel Academie Francaise' for p in self.programmes))
        self.assertFalse(any(p['school']=='Hynes Parkview' for p in self.programmes))
        flaim=[p for p in self.programmes if p['school']=='Baton Rouge FLAIM']
        self.assertEqual({p['track'] for p in flaim},{'French immersion','Spanish immersion','Mandarin Chinese immersion'})
        self.assertTrue(all(not a['shares'] and 'range' in a['label'] for p in flaim for a in p['allocations']))

    def test_jefferson_named_two_way_policy_and_ellis_phaseout_keep_scope(self):
        rows=json.loads((ROOT/BASE/'extractions/la_jefferson_two_way_rows.json').read_text())
        for row in rows:
            p=next(p for p in self.programmes if p['program_id']==row['program_id'])
            self.assertEqual((p['observations'][0]['population'],p['allocations'][0]['shares']),('two_way',{'Spanish':90,'English':10}))
        ellis=self.programme('J. C. Ellis Elementary School','French')
        self.assertEqual(ellis['reference']['status'],'uncertain_2025_26')
        self.assertFalse(ellis['allocations'])

    def test_older_mandarin_closure_is_not_a_spanish_programme_or_a_closed_school(self):
        p=self.programme('Cpl. Michael Middlebrook Elementary School')
        self.assertEqual(p['observations'][0]['languages'],['Mandarin Chinese','English'])
        self.assertEqual(p['reference']['status'],'closed_before_reference_year')
        self.assertEqual(p['events'][0]['year'],'2024-25')
        for target in ['French','Spanish']:
            self.assertEqual(self.programme('Paul Breaux Middle School',target)['reference']['status'],'historical_relocated')
            self.assertEqual(self.programme('Scott Middle School',target)['reference']['status'],'confirmed_2025_26')

    def test_later_brochure_year_and_secondary_continuations_do_not_acquire_k_models(self):
        p=self.programme('LeBlanc Elementary School')
        self.assertEqual(p['allocations'][0]['period'],'2026-27')
        self.assertEqual(self.school(p['school'])['has_numerical_allocation_model'],0)
        for school in ['Westdale Middle School','Lafayette High School','Lycée Français – Priestley Secondary Campus']:
            self.assertTrue(all(not p['allocations'] for p in self.programmes if p['school']==school))

    def test_complement_labels_do_not_manufacture_named_english_shares(self):
        for school in ['Glen View Elementary School','Fairfield Elementary Magnet School','Hynes Charter School – UNO Campus']:
            p=self.programme(school)
            self.assertTrue(p['allocations'])
            self.assertTrue(all(a['shares'] is None for a in p['allocations']))
            self.assertEqual(self.school(school)['has_numerical_allocation_model'],1)

    def test_older_operator_description_with_no_end_indication_keeps_continuity_confirmation(self):
        p=self.programme('Rougon Elementary School')
        self.assertEqual(p['reference']['status'],'confirmed_2025_26')
        self.assertEqual(p['reference']['method'],'continuity_no_end_indication')
        self.assertNotEqual(p['observations'][0]['period'],'2025-26')
        self.assertFalse(p['allocations'])
        reviews=json.loads((ROOT/BASE/'reviews.json').read_text())
        review=next(r for r in reviews if r['review_id']==p['continuity_review'])
        self.assertIn('sc_la_rougon_current',review['source_keys'])
        self.assertEqual(review['decision'],'no_end_indication_in_checked_sources')

    def test_backdated_or_fabricated_models_are_rejected_by_source_audit(self):
        tables=dict(self.tables)
        al=self.programme('Booker T. Washington K-8 School')
        site=next(r['site_id'] for r in self.tables['program_sites'] if r['program_id']==al['program_id'])
        tables['program_configurations']=[dict(r,reported_model_label='50/50') if r['site_id']==site else r for r in self.tables['program_configurations']]
        self.assertTrue(any('source grade/model/period changed' in e for e in audit_errors(ROOT,tables,check_hashes=False)))


if __name__=='__main__':
    unittest.main()
