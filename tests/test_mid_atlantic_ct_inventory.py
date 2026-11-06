"""Six-state source conservation, service grain and dated scope regressions."""
import copy
import csv
import io
import json
from pathlib import Path
import unittest

from dl_outcomes.allocation_coverage import report_rows as kindergarten_rows
from dl_outcomes.elementary_audit import report_rows
from dl_outcomes.mid_atlantic_ct_review import audit_errors, render_reports
from dl_outcomes.northern_central_review import inputs
from dl_outcomes.states.mid_atlantic_ct import BASE, STATES, AUDIT
from dl_outcomes.validation import load

ROOT=Path(__file__).resolve().parents[1]


class MidAtlanticConnecticutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _,cls.tables=load(ROOT)
        cls.programmes,cls.sources=inputs(ROOT,base=BASE,states=STATES)
        cls.details,cls.summary=report_rows(cls.tables)
        cls.rosters=json.loads((ROOT/BASE/'extractions/roster_reconciliation.json').read_text())

    def programme(self,school,language=None):
        return next(p for p in self.programmes if p['school']==school
                    and (language is None or p['track']==language+' immersion'))

    def reference_school(self,school):
        sid=self.programme(school)['school_id']
        return next(r for r in self.details if r['school_id']==sid and r['audit_scope']=='reference_working_set')

    def test_prior_sources_identities_reports_and_assessment_layers_are_preserved(self):
        self.assertEqual(audit_errors(ROOT,self.tables),[])
        audit=json.loads((ROOT/AUDIT).read_text())
        self.assertEqual((len(audit['preserved_reports']),len(audit['preserved_previous_registry']),
                          len(audit['preserved_assessment_outputs'])),(174,1020,12))
        self.assertEqual((len(self.programmes),len({p['school_id'] for p in self.programmes}),len(self.sources)),(433,404,96))

    def test_nyc_csv_preserves_tbe_services_languages_and_school_language_grain(self):
        source=list(csv.DictReader(io.StringIO((ROOT/self.sources['m6_nyc_csv25']['path']).read_text(encoding='utf-8-sig'))))
        roster=next(r for r in self.rosters if r['name']=='nyc_2025_26_bilingual_csv')
        self.assertEqual([r['raw'] for r in roster['rows']],source)
        city=[p for p in self.programmes if p.get('nyc_dbn')]
        self.assertEqual((len(source),len(city),len({p['school_id'] for p in city})),(579,254,240))
        observations=[o for p in city for o in p['observations'] if o['source']=='m6_nyc_csv25']
        self.assertEqual(len(observations),300)
        self.assertEqual(len({o['raw']['Language'] for o in observations}),11)
        self.assertEqual(sum(not r['program_ids'] for r in roster['rows']),279)
        asl=[p for p in city if p['track']=='American Sign Language immersion']
        self.assertEqual(len(asl),1)
        self.assertEqual(len([o for o in asl[0]['observations'] if o['source']=='m6_nyc_csv25']),2)
        self.assertTrue(any(p['track']=='Chinese immersion' for p in city))
        self.assertFalse(any(p['track']=='Mandarin Chinese immersion' for p in city))

    def test_canonical_raw_service_details_cannot_be_dropped(self):
        tables=copy.deepcopy(self.tables)
        claim=next(r for r in tables['evidence_claims'] if r['entity_id'].startswith('M6-NY-P-')
                   and r['attribute']=='source_structural_observation' and 'Special Education Model' in r['reported_value'])
        value=json.loads(claim['reported_value']);value.pop('raw');claim['reported_value']=json.dumps(value)
        self.assertTrue(any('canonical raw service observation' in e for e in audit_errors(ROOT,tables,check_hashes=False)))

    def test_city_directory_membership_does_not_supply_a_numerical_model(self):
        city=[p for p in self.programmes if p.get('nyc_dbn')]
        self.assertEqual({p['nyc_dbn'] for p in city if p['allocations']},{'15K058','14K084'})
        self.assertFalse(next(p for p in city if p['nyc_dbn']=='03M163')['allocations'])
        early=[p for p in city if p['nyc_dbn']=='30Q228']
        self.assertTrue(early)
        self.assertEqual(self.reference_school(early[0]['school'])['elementary_denominator'],1)

    def test_delaware_map_multilanguage_rows_and_establishment_typo_are_conserved(self):
        roster=next(r for r in self.rosters if r['name']=='de_state_map_2021_22_hosts')
        self.assertEqual((len(roster['rows']),sum(len(r['program_ids']) for r in roster['rows'])),(57,60))
        typo=next(r for r in roster['rows'] if 'Maple Lane' in r['raw']['school'])
        self.assertEqual(typo['raw']['established_raw'],'2107')
        p=next(p for p in self.programmes if p['program_id']==typo['program_ids'][0])
        self.assertEqual(p['reference']['status'],'confirmed_2025_26')
        self.assertFalse(p['events'])

    def test_delaware_charters_require_their_own_language_and_model_evidence(self):
        alonso=self.programme('Academia Antonia Alonso Charter School')
        self.assertEqual({a['grade']:a['shares'] for a in alonso['allocations']},
                         {'K-4':{'Spanish':50,'English':50},'5':{'Spanish':20,'English':80}})
        odyssey=self.programme('Odyssey Charter School')
        self.assertEqual(odyssey['track'],'Greek immersion')
        self.assertEqual(odyssey['allocations'][0]['shares'],{'Greek':50,'English':50})
        self.assertTrue(all(o['delivery']=='strand' for o in odyssey['observations']))
        self.assertFalse(self.programme('Las Américas ASPIRA Academy')['allocations'])

    def test_delaware_reconfigured_middle_hosts_do_not_become_current_by_continuity(self):
        for school in ['Central Middle School','William Henry Middle School']:
            p=self.programme(school)
            self.assertNotEqual(p['reference']['status'],'confirmed_2025_26')
            self.assertFalse(any(r['school_id']==p['school_id'] and r['audit_scope']=='reference_working_set' for r in self.details))
        self.assertEqual(self.reference_school('East Dover Early Childhood Center')['elementary_denominator'],1)

    def test_maryland_partial_total_labels_and_unimplemented_languages_remain_distinct(self):
        for school in ['Bayard Rustin Elementary School','Maryvale Elementary School','Burnt Mills Elementary School']:
            self.assertFalse(self.programme(school)['allocations'])
        west=[p for p in self.programmes if p['school']=='Baltimore International Academy West']
        self.assertEqual({p['track'] for p in west},{'Chinese immersion','French immersion','Spanish immersion'})
        self.assertTrue(all(p['allocations'][0]['grade']=='K-1' and p['allocations'][0]['label']=='100/0' for p in west))
        for school in ['Cabin John Middle School','Takoma Park Middle School']:
            self.assertEqual(self.programme(school)['reference']['status'],'planned_future')
            self.assertEqual(self.programme(school)['events'][0]['year'],'2027-28')
        charter=self.programme('Bilingual Global Citizens Public Charter School')
        self.assertNotEqual(charter['reference']['status'],'confirmed_2025_26')
        self.assertTrue(charter['allocations'])
        self.assertFalse(any(r['school_id']==charter['school_id'] and r['audit_scope']=='reference_working_set' for r in self.details))

    def test_pennsylvania_dated_progression_and_subject_language_screening(self):
        p=self.programme('Independence Charter School')
        self.assertEqual({a['grade']:a['label'] for a in p['allocations']},{'K-1':'90/10','2':'70/30','3-5':'50/50'})
        self.assertTrue(all(a['period']=='2025-26' for a in p['allocations']))
        self.assertFalse(any(p['school']=='Independence Charter School West' for p in self.programmes))
        self.assertFalse(self.programme('Vida Charter School')['allocations'])
        sonia=self.programme('Sonia Sotomayor Dual Language Immersion Academy')
        self.assertTrue(any(o['period']=='2025-26' and o['grade']=='PK-2' for o in sonia['observations']))
        self.assertEqual(sonia['events'][0]['year'],'2026-27')

    def test_new_jersey_upper_elementary_and_proposed_policy_are_not_conflated(self):
        somerset=self.reference_school('Somerset School')
        self.assertEqual((somerset['elementary_denominator'],somerset['school_grade_low'],somerset['school_grade_high']),(1,5,6))
        self.assertEqual(self.programme('Somerset School')['allocations'][0]['grade'],'5')
        for school in ['Joseph F. Brandt Elementary School','Thomas G. Connors Elementary School','Wallace Elementary School']:
            p=self.programme(school)
            self.assertEqual({a['label'] for a in p['allocations']},{'50/50'})
        hola=self.programme('Hoboken Dual Language Charter School (HoLa)')
        self.assertEqual(hola['allocations'][0]['grade'],'elementary')
        self.assertIsNone(hola['allocations'][0]['shares'])

    def test_windham_dated_fifth_grade_move_overrides_older_ccd_context(self):
        middle=self.reference_school('Windham Middle School')
        north=self.reference_school('North Windham Elementary School')
        self.assertEqual((middle['elementary_denominator'],middle['school_grade_low'],middle['school_grade_high']),(1,5,8))
        self.assertEqual((north['school_grade_low'],north['school_grade_high']),(0,4))
        tables=copy.deepcopy(self.tables)
        claim=next(r for r in tables['evidence_claims'] if r['entity_id']==self.programme('Windham Middle School')['school_id']
                   and r['attribute']=='elementary_audit_school_grade_context')
        claim['valid_from_year']='2024-25'
        self.assertTrue(any('Windham official grade update' in e for e in audit_errors(ROOT,tables,check_hashes=False)))

    def test_minimums_aspirations_and_unquantified_alternation_do_not_become_exact_models(self):
        for school in ['North Windham Elementary School','Windham Middle School','DiLoreto Elementary and Middle School',
                       'Denton Avenue Elementary School','Regional Multicultural Magnet School']:
            self.assertFalse(self.programme(school)['allocations'])
        for p in self.programmes:
            if p['district']=='Rochester City School District':
                self.assertTrue(all(o['languages']==['English'] for o in p['observations']))

    def test_connecticut_handbook_provenance_and_unresolved_two_way_host_are_retained(self):
        meta=json.loads((ROOT/self.sources['m6_ct_bridge_doc942']['metadata_path']).read_text())
        self.assertIn('visually verified',meta['text_extraction_method'])
        self.assertTrue((ROOT/self.sources['m6_ct_bridge_doc942']['path']).read_bytes().startswith(b'%PDF'))
        lmm=self.programme('Luis Muñoz Marín School')
        self.assertEqual(lmm['reference']['status'],'confirmed_2025_26')
        self.assertTrue(lmm['review_reasons'])
        self.assertFalse(any(p['school']=='FAME' for p in self.programmes))
        leads=json.loads((ROOT/BASE/'ct_screening.json').read_text())
        self.assertTrue(any(r['school']=='FAME (K-8)' for r in leads))
        self.assertTrue(any(o['source']=='m6_ct_fairhaven' for o in self.programme('Fair Haven School')['observations']))

    def test_working_coverage_counts_only_elementary_containing_hosts(self):
        _,report=render_reports(ROOT,self.tables)
        counts={r['state']:(r['elementary_reference_schools_with_numerical_model'],r['elementary_reference_school_units']) for r in report['state_summary']}
        self.assertEqual(counts,{'PA':(2,13),'MD':(9,24),'DE':(43,44),'NJ':(13,19),'NY':(7,200),'CT':(14,18)})
        k_detail,_,_=kindergarten_rows(self.tables)
        for school in ['Somerset School','Windham Middle School']:
            pid=self.programme(school)['program_id'];row=next(r for r in k_detail if r['program_id']==pid)
            self.assertEqual(row['k_eligibility'],'excluded_no_k')
