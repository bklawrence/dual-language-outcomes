"""School/strand identity, grade-specific models and transparent NY inference."""
import json
from pathlib import Path
import unittest

from dl_outcomes.allocation_coverage import report_rows as k_rows
from dl_outcomes.elementary_audit import report_rows
from dl_outcomes.ny_allocation_followup import AUDIT, audit_errors, inputs, render_reports
from dl_outcomes.validation import load

ROOT = Path(__file__).resolve().parents[1]


class NewYorkAllocationFollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tables = load(ROOT)
        cls.programmes, cls.sources, cls.reviews = inputs(ROOT)
        cls.details, cls.summary = report_rows(cls.tables)

    def programmes_at(self, dbn):
        return [p for p in self.programmes if p.get('nyc_dbn') == dbn]

    def programme(self, dbn):
        return self.programmes_at(dbn)[0]

    def test_all_original_primary_hosts_and_source_observations_are_preserved(self):
        self.assertEqual(audit_errors(ROOT, self.tables), [])
        self.assertEqual((len(self.reviews), sum(bool(r['dbn']) for r in self.reviews)), (200, 187))
        audit = json.loads((ROOT / AUDIT).read_text())
        self.assertEqual((len(audit['baseline_programme_ids']), len(audit['baseline_school_ids'])), (269, 255))
        self.assertEqual(len(audit['preserved_original_sources']), 198)
        verified = [p for p in self.programmes if p['district']=='Rochester City School District'
                    or p['school']=='Seymour Dual Language Academy']
        self.assertEqual(len(verified), 5)
        self.assertTrue(all(p['track']=='Spanish immersion' and p['track_label_update']['previous_label']=='dual language (partner not verified)'
                            for p in verified))

    def test_initial_report_is_frozen_as_a_baseline_not_rewritten_as_current(self):
        audit = json.loads((ROOT / AUDIT).read_text())
        self.assertEqual(audit['initial_reference_elementary'], dict(schools=200, schools_with_models=8, coverage_pct=4.0))
        _, report = render_reports(ROOT, self.tables)
        self.assertGreater(report['after_same_baseline_schools']['schools_with_models'], 170)
        self.assertEqual(report['after_same_baseline_schools']['schools'], 200)

    def test_anna_silver_ratios_apply_separately_to_both_partner_languages(self):
        ps = self.programmes_at('01M020')
        self.assertEqual({p['track'] for p in ps}, {'Chinese immersion', 'Spanish immersion'})
        self.assertTrue(all(any(a['source']=='nyf_cep_01M020' and a['grade']=='K-5' and a['label']=='50/50'
                                for a in p['allocations']) for p in ps))
        for dbn in ['03M145','15K094']:
            self.assertTrue(all(any(a['source']=='nyf_cep_'+dbn and a['grade']=='K-5' and a.get('evidence_type')=='documented_plan'
                                    for a in p['allocations']) for p in self.programmes_at(dbn)))

    def test_grade_specific_early_immersion_takes_precedence_over_generic_50_50(self):
        ps163 = self.programme('03M163')
        self.assertEqual({a['grade']:a['shares']['Spanish'] for a in ps163['allocations']}, {'K':80,'1-5':50})
        ps89 = self.programme('24Q089')
        self.assertEqual({a['grade']:a['shares']['Spanish'] for a in ps89['allocations']}, {'K':80,'1':70,'2':60,'3-5':50})

    def test_english_first_ratio_is_normalized_without_reversing_languages(self):
        p = self.programme('17K770')
        self.assertEqual(p['allocations'][0]['shares'], {'Spanish':10,'English':90})
        p = self.programme('21K101')
        self.assertEqual({a['grade']:a['shares']['Chinese'] for a in p['allocations']}, {'K-1':40,'2-5':30})
        p = self.programme('14K319')
        self.assertEqual(p['allocations'][0]['shares'], {'Spanish':40,'English':60})
        self.assertEqual(p['allocations'][0]['evidence_type'], 'researcher_inference')

    def test_subject_inference_retains_basis_and_separate_ict_model(self):
        p = self.programme('15K124')
        inferred = next(a for a in p['allocations'] if a.get('evidence_type')=='researcher_inference')
        self.assertEqual((inferred['grade'], inferred['label']), ('K','50/50'))
        self.assertEqual(inferred['subject_language_distribution']['English'], ['mathematics','science'])
        self.assertIn('social studies', inferred['subject_language_distribution']['Spanish'])
        self.assertIn('general', inferred['service_scope'])
        ict = next(a for a in p['allocations'] if a['label']=='60/40')
        self.assertIsNone(ict['shares'])
        self.assertIn('special education', ict['service_scope'])
        site = next(s['site_id'] for s in self.tables['program_sites'] if s['program_id']==p['program_id'])
        schedules = [s for s in self.tables['allocation_schedules'] if s['site_id']==site]
        self.assertTrue(any(s['schedule_status']=='inferred_plan' and s['grade_scope']=='K' for s in schedules))

    def test_inference_is_distinct_in_coverage_and_not_a_published_label(self):
        p = self.programme('27Q253')
        self.assertTrue(all(o['label'] is None for o in p['observations']))
        row = next(r for r in self.details if r['school_id']==p['school_id'] and r['audit_scope']=='reference_working_set')
        self.assertEqual(row['model_classification_bases'], 'inferred_kindergarten_subject_distribution')
        self.assertEqual(row['has_numerical_allocation_model'], 1)

    def test_conflicts_and_unordered_labels_are_not_silently_resolved(self):
        p = self.programme('07X030')
        self.assertEqual({a['label'] for a in p['allocations']}, {'50/50','40/60'})
        self.assertTrue(all('CONFLICTING' in a['review_status'] for a in p['allocations']))
        p = self.programme('14K034')
        self.assertEqual({a['label'] for a in p['allocations']}, {'70/30','80/20'})
        self.assertTrue(all(a['shares'] is None for a in p['allocations']))

    def test_subject_only_ratios_pupil_mix_and_unquantified_bilingualism_remain_missing(self):
        for dbn in ['02M347','06M048','17K249','17K316','20K503','27Q060','28Q086','75Q255','15K896']:
            self.assertFalse(self.programme(dbn)['allocations'], dbn)

    def test_non_kindergarten_programmes_do_not_gain_an_entry_allocation(self):
        details, _, _ = k_rows(self.tables)
        for dbn in ['03M180','04M206','06M153','08X152','21K090','26Q162','75Q023','75Q811']:
            pid = self.programme(dbn)['program_id']
            row = next(r for r in details if r['program_id']==pid)
            self.assertEqual(row['k_eligibility'], 'excluded_no_k', dbn)

    def test_later_southampton_policy_stays_separate_and_minimum_is_not_exact(self):
        p = next(p for p in self.programmes if p['school']=='Southampton Elementary School')
        self.assertEqual([(a['label'], a['period']=='2026-27') for a in p['allocations']], [('50/50',False),('40/60',True)])
        for name in ['Southampton Intermediate School','Southampton High School']:
            self.assertFalse(next(p for p in self.programmes if p['school']==name)['allocations'])


if __name__ == '__main__':
    unittest.main()
