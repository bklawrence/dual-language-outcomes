"""Source dates, programme languages and scope decisions for OH/KY/WV/VA."""
import copy
import csv
import io
import json
from pathlib import Path
import unittest

from dl_outcomes.elementary_audit import report_rows
from dl_outcomes.northern_central_review import inputs
from dl_outcomes.oh_ky_wv_va_review import audit_errors, render_reports
from dl_outcomes.states.oh_ky_wv_va import BASE, STATES, AUDIT
from dl_outcomes.validation import load

ROOT = Path(__file__).resolve().parents[1]


class EasternFourStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tables = load(ROOT)
        cls.programmes, cls.sources = inputs(ROOT, base=BASE, states=STATES)
        cls.details, cls.summary = report_rows(cls.tables)
        cls.rosters = json.loads((ROOT/BASE/'extractions/roster_reconciliation.json').read_text())

    def programme(self, school, target=None):
        return next(p for p in self.programmes if p['school']==school
                    and (target is None or p['track']==target+' immersion'))

    def reference_school(self, school):
        sid = self.programme(school)['school_id']
        return next(r for r in self.details if r['school_id']==sid and r['audit_scope']=='reference_working_set')

    def test_archived_sources_and_all_previous_research_are_preserved(self):
        self.assertEqual(audit_errors(ROOT, self.tables), [])
        self.assertEqual((len(self.programmes), len({p['school_id'] for p in self.programmes})), (110,108))
        audit = json.loads((ROOT/AUDIT).read_text())
        self.assertEqual((len(audit['preserved_reports']), len(audit['preserved_previous_registry']),
                          len(audit['preserved_assessment_outputs'])), (154,859,12))
        self.assertEqual(len(self.sources), 105)

    def test_west_virginia_scope_leads_remain_screening_with_na_coverage(self):
        self.assertFalse(any(p['state']=='WV' for p in self.programmes))
        contents, report = render_reports(ROOT, self.tables)
        row = next(r for r in report['state_summary'] if r['state']=='WV')
        self.assertIsNone(row['elementary_reference_model_coverage_pct'])
        self.assertEqual(contents[BASE+'/wv_programmes.csv'].count('\n'), 1)
        leads = json.loads((ROOT/BASE/'wv_screening.json').read_text())
        self.assertEqual({r['disposition'] for r in leads}, {'screened_no_verified_academic_dli',
            'academic_immersion_scope_unconfirmed', 'summer_enrichment_not_school_year_dli',
            'asl_bilingual_academic_programme_scope_unconfirmed'})

    def test_fairfax_languages_entry_expansion_and_upper_elementary_scope(self):
        rows = next(r for r in self.rosters if r['name']=='va_fairfax_current_elementary_table')['rows']
        self.assertEqual(len(rows),17)
        self.assertEqual({r['raw']['language'] for r in rows}, {'Spanish','French','German','Japanese','Korean'})
        raven = self.programme('Ravensworth Elementary School')
        self.assertEqual(raven['track'],'Spanish immersion')
        self.assertTrue(any(o['period']=='2025-26' and o['grade']=='1 entry' for o in raven['observations']))
        self.assertEqual(raven['events'][0]['year'],'2026-27')
        upper = self.reference_school('Bailey’s Upper Elementary School for the Arts and Sciences')
        self.assertEqual((upper['elementary_denominator'],upper['school_grade_low']), (1,3))
        self.assertEqual(self.programme('Bailey’s Upper Elementary School for the Arts and Sciences')['allocations'][0]['grade'],'3-5')

    def test_arlington_rollout_is_grade_and_year_specific(self):
        for school in ['Escuela Key Elementary School','Claremont Immersion Elementary School']:
            p = self.programme(school)
            current = [a for a in p['allocations'] if a['period']=='2025-26']
            self.assertEqual({a['grade']:a['shares'] for a in current},
                {'K-2':{'Spanish':80,'English':20}, '3':{'Spanish':70,'English':30},
                 '4-5':{'Spanish':50,'English':50}})
            self.assertTrue(any(a['label']=='50/50' and a['period']!='2025-26' for a in p['allocations']))
        for key in ['e4_va_arlington_chart','e4_va_arlington_rollout25']:
            meta = json.loads((ROOT/self.sources[key]['metadata_path']).read_text())
            self.assertIn('visually verified',meta['text_extraction_method'])
            self.assertTrue((ROOT/self.sources[key]['path']).read_bytes().startswith(b'\x89PNG'))

    def test_columbus_official_model_conflict_is_retained_without_annual_backdating(self):
        p = self.programme('Columbus Spanish Immersion Academy')
        self.assertEqual({a['label'] for a in p['allocations']},{'50/50','60/40','70/30','80/20'})
        self.assertTrue(all(a['review_status']=='CONFLICTING_UNDATED_OFFICIAL_MODELS' for a in p['allocations']))
        self.assertTrue(all(a['period']!='2025-26' for a in p['allocations']))
        tables = copy.deepcopy(self.tables)
        site = next(r['site_id'] for r in tables['program_sites'] if r['program_id']==p['program_id'])
        schedule = next(r for r in tables['allocation_schedules'] if r['site_id']==site)
        schedule['school_year'] = '2025-26'
        self.assertTrue(any('allocation source scope changed' in e for e in audit_errors(ROOT,tables,check_hashes=False)))

    def test_academic_scope_is_not_inferred_from_bilingual_name_or_daily_spanish(self):
        leads = json.loads((ROOT/BASE/'oh_screening.json').read_text())
        self.assertTrue(any(r['school']=='Fairview-Clifton German Language School'
                            and r['disposition']=='intensive_fles_not_core_academic_immersion' for r in leads))
        for school in ['Fairview-Clifton German Language School','Columbus Bilingual West','Escuela SMART Academy']:
            self.assertFalse(any(p['school']==school for p in self.programmes))
        north = self.programme('Columbus Bilingual Academy North')
        self.assertEqual(north['reference']['eligibility'],'academic_immersion_scope_unconfirmed')
        self.assertFalse(any(r['school_id']==north['school_id'] and r['audit_scope']=='reference_working_set' for r in self.details))
        gala = [p for p in self.programmes if p['school']=='Global Ambassadors Language Academy']
        self.assertEqual({p['track'] for p in gala},{'Spanish immersion','Mandarin Chinese immersion'})
        self.assertEqual(len({p['school_id'] for p in gala}),1)

    def test_kentucky_historical_models_continuity_and_course_cut_remain_distinct(self):
        for school in ['Northern Elementary School','Goldsmith Elementary School']:
            p = self.programme(school)
            self.assertEqual(p['reference']['status'],'confirmed_2025_26')
            self.assertTrue(p['continuity_review'])
            self.assertTrue(p['review_reasons'])
            self.assertTrue(all('2018' in a['period'] for a in p['allocations']))
        highland = self.programme('Highland Middle School')
        self.assertNotEqual(highland['reference']['status'],'confirmed_2025_26')
        self.assertEqual(highland['events'][0]['year'],'2024-25')
        self.assertFalse(any(r['school_id']==highland['school_id'] and r['audit_scope']=='reference_working_set' for r in self.details))

    def test_explicit_later_prince_william_policy_does_not_fill_reference_gap(self):
        contents, report = render_reports(ROOT,self.tables)
        backlog = list(csv.DictReader(io.StringIO(contents['data/reports/oh_ky_wv_va_2026_11_05_backlog.csv'])))
        for school in ['Bel Air Elementary School','Chris Yung Elementary School','Featherstone Elementary School','Minnieville Elementary School']:
            p = self.programme(school)
            self.assertTrue(p['allocations'])
            self.assertTrue(all(a['period']=='2026-27' for a in p['allocations']))
            self.assertEqual(self.reference_school(school)['has_numerical_allocation_model'],0)
            self.assertTrue(any(r['program_id']==p['program_id'] and 'later_policy_only' in r['gaps'] for r in backlog))
        row = next(r for r in report['state_summary'] if r['state']=='VA')
        self.assertEqual((row['elementary_reference_school_units'],row['elementary_reference_schools_with_numerical_model']),(51,42))

    def test_future_and_historical_hosts_do_not_become_current_campuses(self):
        for school in ['Mountain View Upper Elementary School','John Kerr Elementary School','Bayside Middle School','Virginia Beach Middle School','Palmer Elementary School']:
            p = self.programme(school)
            self.assertNotEqual(p['reference']['status'],'confirmed_2025_26')
            self.assertFalse(any(r['school_id']==p['school_id'] and r['audit_scope']=='reference_working_set' for r in self.details))
        intermediate = self.reference_school('Daniel Morgan Intermediate School')
        self.assertEqual((intermediate['elementary_denominator'],intermediate['school_grade_low'],intermediate['school_grade_high']), (1,5,6))
        self.assertEqual(self.programme('Daniel Morgan Intermediate School')['allocations'][0]['grade'],'5')
        for p in self.programmes:
            if p['observations'][0]['grade'] in {'6-8','7-8','9-12','6','6 entry'}:
                self.assertFalse(p['allocations'],p['school'])

    def test_alexandria_current_and_2022_models_preserve_source_vintages(self):
        p = self.programme('Mount Vernon Community School')
        self.assertTrue(any(a['source']=='e4_va_alexandria_handbook22' and a['grade']=='K-5' and a['label']=='50/50' for a in p['allocations']))
        self.assertTrue(any(a['source']=='e4_va_alexandria_current_handbook' and a['grade']=='K-1' and a['label']=='70/30' for a in p['allocations']))
        self.assertTrue(any(a['source']=='e4_va_alexandria_current_handbook' and a['grade']=='2-5' and a['label']=='50/50' for a in p['allocations']))
        self.assertTrue(p['review_reasons'])
        self.assertFalse(any('90/30' in a['label'] or '90/10' in a['label'] for a in p['allocations']))

    def test_mansfield_in_year_operation_survives_reported_budget_cuts(self):
        p = self.programme('Mansfield Spanish Immersion School')
        self.assertEqual(p['reference']['status'],'confirmed_2025_26')
        self.assertEqual((p['allocations'][0]['period'],p['allocations'][0]['grade']),('2025-26','K-2'))
        self.assertEqual(p['allocations'][0]['shares'],{'Spanish':100,'English':0})
        self.assertFalse(p['events'])
