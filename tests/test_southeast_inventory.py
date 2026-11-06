"""Source selections, academic language roles and date-sensitive structural decisions."""
import csv
import io
import json
from pathlib import Path
import unittest

from dl_outcomes.elementary_audit import report_rows
from dl_outcomes.northern_central_review import inputs
from dl_outcomes.southeast_review import audit_errors, render_reports
from dl_outcomes.states.southeast import BASE, STATES, AUDIT
from dl_outcomes.validation import load

ROOT=Path(__file__).resolve().parents[1]


class SoutheastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _,cls.tables=load(ROOT)
        cls.programmes,cls.sources=inputs(ROOT,base=BASE,states=STATES)
        cls.details,cls.summary=report_rows(cls.tables)
        cls.rosters=json.loads((ROOT/BASE/'extractions/roster_reconciliation.json').read_text())

    def programme(self,school,target=None):
        return next(p for p in self.programmes if p['school']==school and (target is None or p['track']==target+' immersion'))

    def school(self,school):
        sid=self.programme(school)['school_id']
        return next(r for r in self.details if r['school_id']==sid and r['audit_scope']=='reference_working_set')

    def test_sources_previous_outputs_and_research_identities_reconcile(self):
        self.assertEqual(audit_errors(ROOT,self.tables),[])
        self.assertEqual((len(self.programmes),len({p['school_id'] for p in self.programmes})),(596,552))
        audit=json.loads((ROOT/AUDIT).read_text())
        self.assertEqual((len(audit['preserved_reports']),len(audit['preserved_previous_registry']),len(audit['preserved_assessment_outputs'])),(134,649,12))

    def test_nc_actual_csv_preserves_every_field_and_source_row(self):
        doc=self.sources['se_nc_csv']
        original=list(csv.DictReader(io.StringIO((ROOT/doc['path']).read_text(encoding='utf-8-sig'))))
        selected=next(s for s in self.rosters if s['name']=='nc_state_directory')['rows']
        self.assertEqual([r['raw'] for r in selected],original)
        self.assertEqual(len(original),316)
        self.assertEqual(sum(r['disposition']=='screening_only' for r in selected),2)

    def test_nc_qualitative_full_immersion_does_not_become_100_percent(self):
        for p in self.programmes:
            for o in p['observations']:
                if o['source']=='se_nc_csv':self.assertIsNone(o['label'])
        allen=self.programme('Allen Jay Elementary School','Urdu')
        self.assertIn('Urdu',allen['observations'][0]['languages'])
        self.assertFalse(allen['allocations'])

    def test_nc_directory_chinese_label_is_preserved_without_invented_variety(self):
        observations=[o for p in self.programmes for o in p['observations'] if o['source']=='se_nc_csv' and o.get('raw',{}).get('Language')=='Chinese']
        self.assertEqual(len(observations),23)
        self.assertTrue(all('Chinese' in o['languages'] and 'Mandarin Chinese' not in o['languages'] for o in observations))
        east=self.programme('East Elementary')
        self.assertEqual(east['allocations'][0]['grade'],'1-5')
        self.assertIsNone(east['allocations'][0]['shares'])

    def test_nc_same_campus_language_rows_link_elementary_and_secondary(self):
        rows=[r for s in self.rosters if s['name']=='nc_state_directory' for r in s['rows']
              if r['raw']['School Name'].startswith('South Academy of International Languages')]
        self.assertEqual(len(rows),8)
        self.assertEqual(len({sid for r in rows for sid in r['school_ids']}),1)
        self.assertEqual(len({pid for r in rows for pid in r['program_ids']}),4)

    def test_ga_appendix_is_87_school_rows_93_language_cells_with_preschool_screening(self):
        rows=next(s for s in self.rosters if s['name']=='ga_state_school_appendix')['rows']
        self.assertEqual((len(rows),sum(len(r['raw']['languages']) for r in rows)),(87,93))
        self.assertEqual(sum(r['disposition']=='screening_only' for r in rows),5)
        self.assertEqual(self.programme('Sandra Dunagan Deal Elementary School')['reference']['status'],'reference_year_k12_scope_unconfirmed')

    def test_ga_typical_state_model_is_not_universal_and_fulton_stays_one_way(self):
        self.assertFalse(self.programme('International Charter Academy of Georgia')['allocations'])
        fulton=self.programme('Hapeville Elementary School')
        self.assertTrue(any(o['population']=='one_way' for o in fulton['observations']))
        self.assertEqual(fulton['allocations'][0]['shares'],{'Spanish':50,'English':50})
        self.assertTrue(all(a.get('review_status')=='SAME_DISTRICT_LANGUAGE_PROGRAMME_INFERENCE' for a in self.programme('Nickajack Elementary School')['allocations']))

    def test_broward_two_rosters_deduplicate_k8_and_hours_do_not_become_a_ratio(self):
        rows=[r for s in self.rosters if s['name'].startswith('se_fl_broward') for r in s['rows'] if r['raw']['school']=='Gulfstream Academy Hallandale Beach K-8']
        self.assertEqual(len(rows),4)
        self.assertEqual(len({pid for r in rows for pid in r['program_ids']}),1)
        self.assertEqual(self.school('Gulfstream Academy Hallandale Beach K-8')['elementary_denominator'],1)
        self.assertFalse(self.programme('Manatee Bay Elementary School')['allocations'])

    def test_florida_partner_languages_are_campus_specific(self):
        self.assertEqual(self.programme('Arch Creek Elementary School')['track'],'French immersion')
        self.assertEqual(self.programme('West Hialeah Gardens Elementary School')['track'],'Spanish immersion')
        ada=[p for p in self.programmes if p['school']=='Ada Merritt K-8 Center']
        self.assertEqual({p['track'] for p in ada},{'Portuguese immersion','Spanish immersion'})
        bilbao=[p for p in self.programmes if p['school']=='Dr. Toni Bilbao Preparatory Academy']
        self.assertEqual([p['track'] for p in bilbao],['Spanish immersion'])
        douglas=self.programme('Marjory Stoneman Douglas Elementary School')
        self.assertEqual(douglas['track'],'BISO partner language unresolved')
        self.assertEqual(douglas['observations'][0]['languages'],['English'])

    def test_miami_efl_scope_is_screening_not_47_unverified_immersion_programmes(self):
        rows=next(s for s in self.rosters if s['name']=='fl_miami_efl')['rows']
        self.assertEqual(len(rows),47)
        self.assertTrue(all(r['disposition']=='screening_only' and not r['program_ids'] for r in rows))

    def test_palm_creole_and_policy_vintages_remain_separate(self):
        creole=self.programme('Indian Pines Elementary School')
        self.assertEqual(creole['allocations'][0]['shares'],{'Haitian Creole':50,'English':50})
        self.assertEqual(creole['allocations'][0]['grade'],'K-2')
        spanish=self.programme('Barton Elementary School')
        self.assertTrue(all(a['period'].startswith('2026') for a in spanish['allocations']))
        self.assertTrue(any(o['source']=='se_fl_palm_guidelines25' and o['label'] is None for o in spanish['observations']))

    def test_osceola_aspirational_target_is_not_an_implemented_model(self):
        p=self.programme('Celebration K-8 School')
        self.assertFalse(p['allocations'])
        self.assertEqual(self.school(p['school'])['has_numerical_allocation_model'],0)
        self.assertEqual(self.programme('Canoe Creek K-8')['reference']['status'],'reference_year_start_unconfirmed')

    def test_secondary_hosts_stay_out_and_grade_five_middle_school_stays_in(self):
        self.assertEqual(self.school('Valley Springs Middle School')['elementary_denominator'],1)
        for name in ['ChattAcademy Community School','Hughes Academy','Sullivan Middle School']:
            self.assertEqual(self.school(name)['elementary_denominator'],0)
            self.assertFalse(self.programme(name)['allocations'])

    def test_district_policy_is_scoped_to_primary_and_intermediate_campus_grades(self):
        for name in ['East Mooresville Intermediate','Mooresville Intermediate']:
            self.assertEqual(self.programme(name)['allocations'][0]['grade'],'3-5')
        self.assertEqual(self.programme('Park View Elementary')['allocations'][0]['grade'],'K-2')

    def test_nashville_retrospective_distinguishes_k_launch_from_later_grade_expansion(self):
        p=self.programme('Paragon Mills Elementary School')
        self.assertEqual((p['observations'][0]['period'],p['observations'][0]['grade']),('2025-26','K'))
        self.assertEqual((p['observations'][1]['period'],p['observations'][1]['grade']),('2026-27','K-1'))
        self.assertEqual(p['allocations'][0]['grade'],'K')
        self.assertEqual(p['reference']['method'],'retrospective_operator_launch_confirmation')

    def test_treadwell_home_language_balance_does_not_replace_90_10_k(self):
        p=self.programme('Treadwell Elementary School')
        self.assertEqual((p['allocations'][0]['label'],p['allocations'][0]['shares']),('90/10',{'Spanish':90,'English':10}))
        self.assertFalse(self.programme('Spanish Immersion at Barksdale')['allocations'])

    def test_harnett_historical_hosts_survive_later_closures(self):
        rows=next(s for s in self.rosters if s['name']=='nc_harnett_historical_hosts')['rows']
        self.assertEqual(len(rows),14)
        h=[p for p in self.programmes if p['district']=='Harnett County Schools']
        self.assertEqual(len(h),14)
        self.assertTrue(all(p['reference']['status']=='confirmed_2025_26' for p in h))
        self.assertEqual(sum(any(e['year']=='2026-27' and e['status']=='reported_closed_after_2025_26' for e in p['events']) for p in h),12)

    def test_glenwood_move_is_2027_plan_and_language_specials_are_not_new_dl(self):
        p=self.programme('Rashkis Elementary School')
        self.assertEqual(p['reference']['status'],'planned_future')
        self.assertEqual(p['events'][0]['year'],'2027-28')
        self.assertFalse(any(p['school']=='Scroggs Elementary School' for p in self.programmes))

    def test_blythe_proposed_phaseout_was_rejected(self):
        p=self.programme('Blythe Academy','French')
        self.assertEqual(p['reference']['status'],'confirmed_2025_26')
        self.assertTrue(any(e['status']=='proposed_phaseout_rejected_by_board' for e in p['events']))
        self.assertFalse(p['allocations'])

    def test_cherokee_is_academic_tribal_funded_not_a_specials_class(self):
        p=self.programme('New Kituwah Academy')
        self.assertEqual(p['reference']['funding'],'tribal_government_budget_documented')
        self.assertEqual(p['reference']['source'],'se_nc_kituwah25')
        self.assertEqual(p['observations'][-1]['languages'],['Cherokee'])
        self.assertFalse(p['allocations'])

    def test_grade_context_and_redaction_provenance_are_explicit(self):
        rows=json.loads((ROOT/BASE/'grade_context_decisions.json').read_text())
        self.assertEqual(len(rows),473)
        ids={r['school_id'] for r in rows}
        self.assertFalse(any(r['entity_id'] in ids and r['namespace']=='NCES_school_id' for r in self.tables['identifiers']))
        redactions=json.loads((ROOT/BASE/'source_redactions.json').read_text())
        self.assertEqual([r['key'] for r in redactions],['se_nc_district_36'])
        self.assertTrue(redactions[0]['programme_text_unchanged'])
        self.assertNotEqual(redactions[0]['original_response_sha256'],redactions[0]['saved_redacted_sha256'])


if __name__=='__main__':unittest.main()
