"""Historical source conservation and dated, language-specific policy corrections."""
import csv
import json
from pathlib import Path
import unittest

from dl_outcomes.allocation_coverage import report_rows as kindergarten_rows
from dl_outcomes.elementary_audit import report_rows as elementary_rows
from dl_outcomes.illinois_history import CONFIG, DATASET, YEAR, audit_errors, inputs
from dl_outcomes.policy_selection import ATTRIBUTE, current_policy_choices
from dl_outcomes.validation import load

ROOT = Path(__file__).resolve().parents[1]


class IllinoisHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tables = load(ROOT)
        cls.config, cls.records, cls.schools, cls.programmes, cls.decisions = inputs(ROOT)
        cls.sources = {r['source_id']:r for r in cls.tables['sources']}
        cls.raw_source = next(r['source_id'] for r in cls.tables['sources']
            if r['snapshot_path']==cls.config['raw']+'/inventory.tsv')
        cls.elementary, cls.coverage = elementary_rows(cls.tables)

    def record(self, name):
        return next(r for r in self.records if r['raw']['Name'].strip()==name)

    def test_every_source_row_and_previous_research_are_preserved(self):
        self.assertEqual(audit_errors(ROOT,self.tables), [])
        self.assertEqual((len(self.records),len(self.schools),len(self.programmes)),(144,41,42))
        self.assertEqual(len(self.config['preserved_reports']),98)
        self.assertEqual(len(self.config['preserved_assessment_outputs']),12)
        with (ROOT/self.config['raw']/'inventory.tsv').open() as stream:
            original=list(csv.DictReader(stream,delimiter='\t'))
        self.assertEqual([r['raw'] for r in self.records],original)

    def test_collection_year_is_not_substituted_for_school_year(self):
        configurations=[r for r in self.tables['program_configurations'] if r['source_id']==self.raw_source]
        schedules=[r for r in self.tables['allocation_schedules'] if r['source_id']==self.raw_source]
        self.assertEqual((len(configurations),len(schedules)),(133,86))
        self.assertTrue(all(r['school_year']==YEAR and r['evidence_period_raw']==YEAR for r in configurations+schedules))
        labels={r['schedule_id'] for r in schedules}
        self.assertFalse(any(r['schedule_id'] in labels for r in self.tables['instructional_allocations']))
        memberships=[r for r in self.tables['school_district_history'] if r['source_id']==self.raw_source]
        self.assertTrue(memberships)
        self.assertTrue(all(r['school_year']==YEAR and r['validity_status']=='source_year' for r in memberships))

    def test_historical_aliases_reuse_identities_without_duplicate_school_counts(self):
        left=self.record('Mancel Talcott Elementary');right=self.record('Talcott Fine Arts and Museum Academy')
        self.assertEqual((left['school_id'],right['school_id']),('IL-S016','IL-S016'))
        self.assertEqual(left['program_id'],right['program_id'])
        self.assertEqual(self.record('Charles R. Darwin School')['school_id'],'IL-S004')
        cook=self.record('Lincoln Elementary')
        elgin=next(r for r in self.records if r['raw']['Name']=='Lincoln Elementary' and r['raw']['District']=='Elgin Area SD U46')
        self.assertNotEqual(cook['school_id'],elgin['school_id'])
        self.assertIn(cook['school_id'],self.config['new_school_ids'])
        self.assertIn(elgin['school_id'],self.config['baseline_school_ids'])
        chicago=[r for r in self.records if r['raw']['District']=='Chicago Public Schools']
        self.assertEqual({r['district_name'] for r in chicago},{'Chicago Public Schools 299'})

    def test_composite_language_cells_do_not_become_extra_instructional_tracks(self):
        mixed=[r for r in self.records if len(r['languages_as_reported'])>1]
        self.assertEqual(len(mixed),4)
        self.assertTrue(all(r['school_id'] and not r['program_id'] for r in mixed))
        roles=[r for r in self.tables['program_languages'] if r['source_id']==self.raw_source]
        self.assertFalse({'Arabic','Mandarin Chinese','Korean','English'} & {r['language_name'] for r in roles})
        self.assertTrue(all(r['valid_from_year']==YEAR for r in roles))

    def test_countryside_spanish_history_does_not_replace_its_current_mandarin_track(self):
        record=self.record('Countryside Elementary')
        self.assertIn(record['program_id'],self.config['new_programme_ids'])
        languages={r['language_name'] for r in self.tables['program_languages'] if r['site_id']==record['site_id']}
        self.assertEqual(languages,{'Spanish'})
        other_sites={r['site_id'] for r in self.tables['program_sites'] if r['school_id']==record['school_id'] and r['site_id']!=record['site_id']}
        self.assertTrue(any(r['language_name']=='Mandarin Chinese' for r in self.tables['program_languages'] if r['site_id'] in other_sites))

    def test_enrichment_blank_languages_and_preschool_remain_screening(self):
        for name in ['Abraham Lincoln Elementary','Augustus H Burley Elementary',
                     'Belmont Cragin Early Childhood','Bardwell Elementary','Rollins Elementary','Yorkville Middle School']:
            self.assertIsNone(self.record(name)['program_id'])
        verda=self.record('Verda Dierzen Early Learning Center')
        self.assertEqual(verda['programme_grade_proxy'],'PK')
        model=next(r for r in self.tables['allocation_schedules'] if r['source_id']==self.raw_source and r['source_locator']==verda['row_id'])
        self.assertEqual(model['grade_scope'],'PK')
        whittier=self.record('Whittier Intermediate')
        self.assertEqual(whittier['level_label'],'middle')
        self.assertEqual(whittier['programme_grade_proxy'],'not_reported')

    def test_blank_sector_is_not_private_and_delivery_is_not_population_type(self):
        self.assertEqual(self.record('Timber Trails Elementary')['sector_label'],'not_reported')
        autumn=self.record('Autumn Creek Elementary')
        self.assertEqual(autumn['raw']['Private 0/Public1/Charter 2'],'0')
        self.assertTrue(any('private code' in note for note in autumn['review_notes']))
        configs=[r for r in self.tables['program_configurations'] if r['source_id']==self.raw_source]
        self.assertTrue(all(r['population_model']=='unknown' for r in configs))
        self.assertEqual(self.record('Academy for Global Citizenship')['delivery_structure'],'strand')

    def test_ipa_change_is_confirmed_without_inventing_its_first_change_year(self):
        choice=next(r for r in self.decisions if r['program_id']=='IL-P008')
        schedules={r['schedule_id']:r for r in self.tables['allocation_schedules']}
        self.assertEqual(schedules[choice['selected_schedule_id']]['school_year'],'2025-26')
        self.assertEqual(schedules[choice['selected_schedule_id']]['reported_model_label'],'90-10')
        historical=[r for r in schedules.values() if r['site_id']=='IL-PS008' and r['school_year']==YEAR]
        self.assertTrue(any(r['reported_model_label']=='50/50' for r in historical))
        interval=next(r for r in self.tables['evidence_claims'] if r['attribute']=='allocation_change_date_interval')
        self.assertIsNone(json.loads(interval['reported_value'])['effective_change_school_year'])

    def test_urbana_consolidation_has_two_predecessors_and_a_dated_spanish_change(self):
        predecessor=[p for p in self.programmes if p['closed_after_school_year']]
        self.assertEqual(len(predecessor),2)
        sites={r['site_id']:r for r in self.tables['program_sites']}
        for p in predecessor:
            self.assertEqual(sites[p['site_id']]['valid_to_year'],'2023-24')
        choice=next(d for d in self.decisions if d['decision_id']=='IL22-YANKEE-SPANISH-2024')
        model=next(r for r in self.tables['allocation_schedules'] if r['schedule_id']==choice['selected_schedule_id'])
        self.assertEqual((model['school_year'],model['reported_model_label']),('2024-25','80/20'))
        self.assertEqual({r['language_name']:r['instruction_share_pct'] for r in self.tables['instructional_allocations']
                          if r['schedule_id']==model['schedule_id']},{'Spanish':80,'English':20})
        french=next(d for d in self.decisions if d['decision_id']=='IL22-YANKEE-FRENCH-STABLE')
        self.assertIsNone(french['effective_from'])
        self.assertEqual(french['model'],'50/50')

    def test_current_policy_choices_do_not_erase_historical_descriptions(self):
        current=next(r for r in self.elementary if r['school_id']=='IL-S018' and r['audit_scope']=='reference_working_set')
        historical=next(r for r in self.elementary if r['school_id']=='IL-S018' and r['audit_scope']=='all_recorded_programme_hosts')
        self.assertEqual(set(current['numerical_model_labels'].split(' | ')),{'80/20','50/50'})
        self.assertIn('90/10',historical['numerical_model_labels'])
        rows,_,_=kindergarten_rows(self.tables)
        ipa=next(r for r in rows if r['program_id']=='IL-P008')
        choice=next(d for d in self.decisions if d['program_id']=='IL-P008')
        self.assertEqual(ipa['k_schedule_ids'],choice['selected_schedule_id'])

    def test_historical_schools_do_not_inflate_current_operation_coverage(self):
        row=next(r for r in self.coverage if r['state_code']=='IL' and r['audit_scope']=='reference_working_set')
        self.assertEqual((row['inventory_school_units'],row['elementary_school_units'],row['elementary_schools_with_numerical_model']),(123,104,64))
        own={sid for sid,r in self.sources.items() if r['dataset_id']==DATASET}
        self.assertFalse(any(r['operating_status']=='confirmed_2025_26' for r in self.tables['program_status_history'] if r['source_id'] in own))

    def test_a_current_policy_cannot_select_the_other_language_strand(self):
        tables=dict(self.tables)
        tables['evidence_claims']=[dict(r) for r in self.tables['evidence_claims']]
        spanish=next(d for d in self.decisions if d['decision_id']=='IL22-YANKEE-SPANISH-2024')
        french=next(d for d in self.decisions if d['decision_id']=='IL22-YANKEE-FRENCH-STABLE')
        claim=next(r for r in tables['evidence_claims'] if r['attribute']==ATTRIBUTE and r['entity_id']==french['program_id'])
        choice=json.loads(claim['reported_value']);choice['selected_schedule_id']=spanish['selected_schedule_id'];claim['reported_value']=json.dumps(choice)
        with self.assertRaisesRegex(ValueError,'language scope'):
            current_policy_choices(tables,'2025-26')


if __name__=='__main__':
    unittest.main()
