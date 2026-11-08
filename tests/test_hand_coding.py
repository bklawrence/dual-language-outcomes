"""Hand-coded provenance, trusted intake, identity scope and chronological selection."""
import base64
import copy
import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import uuid

from dl_outcomes.baseline_selection import Selection
from dl_outcomes.build import Build
from dl_outcomes.hand_coding import DATASET, accept_issue, decode_submission, migrate, validate_record
from dl_outcomes.validation import load, validate_tables

ROOT=Path(__file__).resolve().parents[1]


class HandCodingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema,cls.tables=load(ROOT)
        # Tests exercise a fresh synthetic review, independently of future
        # real reviews accumulated through the production website.
        manual_sources={s['source_id'] for s in cls.tables['sources'] if s['dataset_id']==DATASET}
        cls.tables={name:[r for r in rows if r.get('source_id') not in manual_sources
                          and not (name=='datasets' and r['dataset_id']==DATASET)] for name,rows in cls.tables.items()}
        cls.sites={s['site_id']:s for s in cls.tables['program_sites']}
        cls.schools={s['school_id']:s for s in cls.tables['schools']}
        cls.rules=json.loads((ROOT/'data/baselines/national_structural_v1/rules.json').read_text())
        cls.site=next(s for s in cls.tables['program_sites'] if s['school_id']=='TX-S057905101')

    def record(self,**changes):
        record=dict(review_id=str(uuid.uuid4()),school_id=self.site['school_id'],reviewer='Researcher',
                    reference_year='2025-26',source_school_year=None,coding_method='explicit_source_statement',
                    evidence_url='https://example.edu/dual-language',notes='All pupils participate in academic DL.',
                    source_quote='Every pupil learns academic content in both languages.',grade_scope='K-5',
                    changes={'delivery_structure':dict(value='whole_school',site_ids=[self.site['site_id']])})
        return record|changes

    def payload(self,records):
        return dict(version=1,batch_id=str(uuid.uuid4()),records=records)

    def body(self,payload):
        token=base64.urlsafe_b64encode(gzip.compress(json.dumps(payload,ensure_ascii=False).encode())).decode().rstrip('=')
        return '<!-- DL_REVIEW_V1:'+token+' -->'

    def event(self,payload,actor='bklawrence'):
        return {'issue':dict(user={'login':actor},number=12,html_url='https://github.com/bklawrence/dual-language-outcomes/issues/12',
                             created_at='2026-11-07T01:00:00Z',body=self.body(payload))}

    def setup_root(self,root):
        (root/'config').mkdir();(root/'data/registry/hand_coded_reviews').mkdir(parents=True)
        (root/'config/hand_coding.json').write_text(json.dumps(dict(authorized_reviewers=['bklawrence'],repository='bklawrence/dual-language-outcomes',preserved_reports={})))
        shutil.copyfile(ROOT/'config/identity_mappings.csv',root/'config/identity_mappings.csv')

    def reviewed_tables(self,records,*,legacy=False):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.setup_root(root);payload=self.payload(records);event=self.event(payload)
            if legacy:
                # Simulate an immutable journal accepted before the K-only menu.
                path=root/'data/registry/hand_coded_reviews'/(payload['batch_id']+'.json')
                payload['submission']=dict(github_actor='bklawrence',issue_number=12,
                    issue_url=event['issue']['html_url'],submitted_at=event['issue']['created_at'],
                    received_at=event['issue']['created_at'],hand_coded=True)
                path.write_text(json.dumps(payload))
                receipt=dict(status='saved',path=str(path.relative_to(root)))
            else:
                with patch('dl_outcomes.validation.load',return_value=(self.schema,self.tables)):
                    receipt=accept_issue(root,event)
            b=Build(root)
            for name,rows in self.tables.items():
                for row in rows:b.add(name,**row)
            migrate(b)
            return {name:b.rows(name) for name in b.tables},receipt

    def test_unicode_batch_roundtrip_and_bounded_decompression(self):
        payload=self.payload([self.record(notes='Español, ʻŌlelo Hawaiʻi; "whole school" — notes retained.')])
        self.assertEqual(decode_submission(self.body(payload)),payload)
        with self.assertRaises(ValueError):decode_submission(self.body({'x':'a'*1000000}))
        with self.assertRaises(ValueError):decode_submission(self.body(payload)+self.body(payload))

    def test_only_an_authenticated_allowed_account_can_create_a_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.setup_root(root);payload=self.payload([self.record()])
            with self.assertRaisesRegex(ValueError,'authorized'):accept_issue(root,self.event(payload,actor='another-account'))
            self.assertEqual(list((root/'data/registry/hand_coded_reviews').glob('*.json')),[])
            with patch('dl_outcomes.validation.load',return_value=(self.schema,self.tables)):
                first=accept_issue(root,self.event(payload));second=accept_issue(root,self.event(payload))
            self.assertEqual(first['status'],'saved');self.assertEqual(second['status'],'already_saved')
            saved=json.loads((root/first['path']).read_text())
            self.assertEqual(saved['submission']['github_actor'],'bklawrence')
            self.assertTrue(saved['submission']['hand_coded']);self.assertTrue(saved['submission']['received_at'])
            self.assertEqual(saved['records'],payload['records'])

    def test_cross_campus_ids_invalid_urls_and_future_source_years_are_rejected(self):
        other=next(s for s in self.sites.values() if s['school_id']!=self.site['school_id'])
        for record in [self.record(evidence_url='javascript:alert(1)'),self.record(evidence_url='https://user:pass@example.edu'),
                       self.record(source_school_year='2026-27'),self.record(changes={'delivery_structure':dict(value='whole_school',site_ids=[other['site_id']])}),
                       self.record(changes={'delivery_structure':dict(value='mixed',site_ids=[self.site['site_id']])},notes='')]:
            with self.assertRaises(ValueError):validate_record(record,self.sites,self.schools)

    def test_delivery_only_review_preserves_original_rows_other_fields_and_other_years(self):
        after,_=self.reviewed_tables([self.record()]);before=Selection(self.tables,self.rules);selected=Selection(after,self.rules)
        for name in ['schools','programs','program_sites','allocation_schedules','instructional_allocations','program_languages',
                     'program_status_history','state_assessments','demographics']:
            self.assertEqual(after[name],self.tables[name])
        for year in ['2024-25','2026-27']:
            a,_=before.select_field(self.site,'delivery_structure',year);b,_=selected.select_field(self.site,'delivery_structure',year)
            self.assertEqual(a['value_json'],b['value_json']);self.assertEqual(a['selected_evidence_ids'],b['selected_evidence_ids'])
        for variable in ['population_model','instruction_languages','programme_grade_scope']:
            self.assertEqual(before.select_field(self.site,variable,'2025-26'),selected.select_field(self.site,variable,'2025-26'))
        value,_=selected.select_field(self.site,'delivery_structure','2025-26');self.assertEqual(json.loads(value['value_json']),['whole_school'])
        self.assertEqual(value['value_status'],'documented')
        claim=next(c for c in after['evidence_claims'] if c['attribute']=='hand_coded_review')
        metadata=json.loads(claim['reported_value']);self.assertTrue(metadata['hand_coded']);self.assertEqual(metadata['entry_method'],'hand_coded')
        self.assertEqual(metadata['evidence_url'],'https://example.edu/dual-language')

    def test_last_decision_in_one_batch_wins_regardless_of_uuid_order(self):
        older=self.record(review_id='ffffffff-ffff-4fff-8fff-ffffffffffff',changes={'delivery_structure':dict(value='strand',site_ids=[self.site['site_id']])})
        newer=self.record(review_id='00000000-0000-4000-8000-000000000000')
        tables,_=self.reviewed_tables([older,newer]);selection=Selection(tables,self.rules)
        field,_=selection.select_field(self.site,'delivery_structure','2025-26')
        self.assertEqual(json.loads(field['value_json']),['whole_school'])
        self.assertEqual(sum(c['attribute']=='hand_coded_review' for c in tables['evidence_claims']),2)

    def test_interpretations_stay_provisional_and_allocations_do_not_invent_shares(self):
        record=self.record(coding_method='researcher_interpretation',grade_scope='K',changes={
            'delivery_structure':dict(value='strand',site_ids=[self.site['site_id']]),
            'elementary_allocation_model':dict(value='80/20',site_ids=[self.site['site_id']]),
            'population_model':dict(value='two_way',site_ids=[self.site['site_id']]),
            'instruction_languages':dict(value=['English','Mandarin'],site_ids=[self.site['site_id']])})
        tables,_=self.reviewed_tables([record]);selection=Selection(tables,self.rules)
        value,_=selection.select_field(self.site,'delivery_structure','2025-26');self.assertEqual(value['value_status'],'provisional')
        self.assertEqual(tables['instructional_allocations'],self.tables['instructional_allocations'])
        new=next(r for r in tables['allocation_schedules'] if r['schedule_id'] not in {r['schedule_id'] for r in self.tables['allocation_schedules']})
        self.assertEqual(new['grade_scope'],'K');self.assertEqual(new['schedule_status'],'reported_policy_requires_review')
        self.assertIn('language_order',new['percentage_basis'])
        self.assertEqual(validate_tables(tables,self.schema),[])

    def test_new_allocation_intake_requires_kindergarten_whole_percentages(self):
        def allocation(scope,value,**extra):
            return self.record(grade_scope=scope,changes={'elementary_allocation_model':
                dict(value=value,site_ids=[self.site['site_id']],**extra)})
        for scope,value in [('1','50/50'),('K-5','80/20'),('K','80.5/19.5'),('K','80/30')]:
            with self.subTest(scope=scope,value=value),self.assertRaises(ValueError):
                validate_record(allocation(scope,value),self.sites,self.schools,kindergarten_only=True)
        for percentage in [0,50,85,100]:
            record=allocation('K',f'{percentage}/{100-percentage}',kindergarten_partner_language_pct=percentage)
            self.assertEqual(validate_record(record,self.sites,self.schools,kindergarten_only=True),record)
        for percentage in [True,'80',80.5,101,20,None]:
            with self.subTest(percentage=percentage),self.assertRaisesRegex(ValueError,'kindergarten percentage'):
                validate_record(allocation('K','80/20',kindergarten_partner_language_pct=percentage),self.sites,self.schools)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.setup_root(root)
            payload=self.payload([allocation('K-5','80/20')])
            with patch('dl_outcomes.validation.load',return_value=(self.schema,self.tables)):
                with self.assertRaisesRegex(ValueError,'kindergarten only'):
                    accept_issue(root,self.event(payload))
            self.assertEqual(list((root/'data/registry/hand_coded_reviews').glob('*.json')),[])

    def test_kindergarten_menu_preserves_explicit_direction_without_inventing_named_shares(self):
        record=self.record(grade_scope='K',changes={'elementary_allocation_model':
            dict(value='80/20',kindergarten_partner_language_pct=80,site_ids=[self.site['site_id']])})
        tables,_=self.reviewed_tables([record])
        field,_=Selection(tables,self.rules).select_allocations(self.site,'2025-26','elementary',['K-5'])
        kindergarten=next(v for v in json.loads(field['value_json']) if v['grade_scope']=='K')
        self.assertEqual(kindergarten['model_label_normalized'],'80/20')
        self.assertEqual(kindergarten['model_label_language_order'],'partner_then_English_from_kindergarten_menu')
        self.assertEqual(kindergarten['named_language_shares'],{})
        self.assertEqual(tables['instructional_allocations'],self.tables['instructional_allocations'])
        claim=next(c for c in tables['evidence_claims'] if c['attribute']=='hand_coded_review')
        self.assertEqual(json.loads(claim['reported_value'])['changes']['elementary_allocation_model']['kindergarten_partner_language_pct'],80)
        self.assertEqual(validate_tables(tables,self.schema),[])

    def test_existing_upper_grade_batch_remains_valid_and_idempotent(self):
        record=self.record(grade_scope='1-5',changes={'elementary_allocation_model':
            dict(value='50/50',site_ids=[self.site['site_id']])})
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.setup_root(root);payload=self.payload([record]);event=self.event(payload)
            archived=payload|{'submission':{'github_actor':'bklawrence'}}
            (root/'data/registry/hand_coded_reviews'/(payload['batch_id']+'.json')).write_text(json.dumps(archived))
            with patch('dl_outcomes.validation.load',return_value=(self.schema,self.tables)):
                self.assertEqual(accept_issue(root,event)['status'],'already_saved')
                with self.assertRaisesRegex(ValueError,'kindergarten only'):
                    accept_issue(root,self.event(self.payload([record])))

    def test_allocation_corrections_keep_other_grades_and_earlier_years(self):
        from dl_outcomes.baseline_selection import grade_set
        site=next(s for s in self.sites.values() if s['school_id']=='NE5-MA-S-c7cf93db6bc0')
        reviews=[self.record(school_id=site['school_id'],grade_scope=grades,changes={
            'elementary_allocation_model':dict(value=value,site_ids=[site['site_id']])})
            for grades,value in [('K','90/10'),('1','60/40'),('Kindergarten','85/15')]]
        tables,_=self.reviewed_tables(reviews,legacy=True)
        before,after=Selection(self.tables,self.rules),Selection(tables,self.rules)
        field,_=after.select_allocations(site,'2025-26','elementary',['PK-5'])
        values=json.loads(field['value_json'])
        self.assertEqual({tuple(sorted(grade_set(v['grade_scope']))):v['model_label_normalized'] for v in values},
                         {(0,):'85/15',(1,):'60/40',(2,3,4,5):'50/50'})
        self.assertEqual(tables['instructional_allocations'],self.tables['instructional_allocations'])
        original={r['schedule_id']:r for r in tables['allocation_schedules']}
        self.assertTrue(all(original[r['schedule_id']]==r for r in self.tables['allocation_schedules']))
        for year in ['2024-25','2026-27']:
            old,_=before.select_allocations(site,year,'elementary',['PK-5'])
            new,_=after.select_allocations(site,year,'elementary',['PK-5'])
            for key in ['value_json','selected_evidence_ids','selected_source_ids']:
                self.assertEqual(old[key],new[key],(year,key))

    def test_grade_correction_can_replace_part_of_a_broader_source_scope(self):
        from dl_outcomes.allocation_selection import apply_grade_reviews
        source=dict(_id='source-plan',_table='allocation_schedules',grade_scope='K-5',
                    school_year=None,evidence_period_raw='undated',_value='50/50')
        new=dict(_id='review-k',_table='allocation_schedules',grade_scope='K',
                 school_year=None,evidence_period_raw='undated',_value='80/20')
        selected=apply_grade_reviews([source,new],[dict(evidence_ids=['review-k'])],[source],'2025-26')
        self.assertEqual([(r['grade_scope'],r['_value']) for r in selected],[('K','80/20'),('1-5','50/50')])
        self.assertEqual(selected[1]['_source_grade_scope'],'K-5')
        self.assertEqual(source['grade_scope'],'K-5')
        # A newer broad correction also supersedes only the overlapping grades
        # of an older manual review, preserving the remaining original source.
        older=dict(new,_id='review-older',grade_scope='K-2',_value='90/10')
        selected=apply_grade_reviews([source,new,older],[dict(evidence_ids=['review-k']),dict(evidence_ids=['review-older'])],[source],'2025-26')
        self.assertEqual([(r['grade_scope'],r['_value']) for r in selected],
                         [('K','80/20'),('1-2','90/10'),('3-5','50/50')])

    def test_cleared_basis_is_retained_without_asserting_interpretation_or_documentation(self):
        original=self.record()
        cleared=self.record(coding_method='not_recorded',supersedes_review_id=original['review_id'])
        tables,_=self.reviewed_tables([original,cleared])
        field,_=Selection(tables,self.rules).select_field(self.site,'delivery_structure','2025-26')
        self.assertEqual(json.loads(field['value_json']),['whole_school'])
        self.assertEqual(field['value_status'],'provisional')
        reviews=[json.loads(c['reported_value']) for c in tables['evidence_claims'] if c['attribute']=='hand_coded_review']
        self.assertEqual([r['coding_method'] for r in reviews],['explicit_source_statement','not_recorded'])
        self.assertEqual(reviews[-1]['evidence_url'],cleared['evidence_url'])
        self.assertEqual(reviews[-1]['supersedes_review_id'],original['review_id'])
        self.assertEqual(validate_tables(tables,self.schema),[])

    def test_parked_case_creates_no_structural_value(self):
        with self.assertRaisesRegex(ValueError,'parked case'):
            validate_record(self.record(disposition='needs_review'),self.sites,self.schools)
        tables,_=self.reviewed_tables([self.record(disposition='needs_review',evidence_url='',changes={},notes='Could not establish campus scope.')])
        self.assertEqual(tables['program_configurations'],self.tables['program_configurations'])
        self.assertEqual(tables['allocation_schedules'],self.tables['allocation_schedules'])

    def event_record(self,kind='ended',first='2024-25',**changes):
        return self.record(changes={},program_event=dict(kind=kind,first_school_year=first,site_ids=[self.site['site_id']],
            destination_school_id=None,destination_school_name='',destination_url=''),**changes)

    def test_ended_program_is_dated_and_does_not_erase_earlier_history(self):
        record=self.event_record();tables,_=self.reviewed_tables([record]);selection=Selection(tables,self.rules)
        before=Selection(self.tables,self.rules)
        self.assertEqual(selection.operation(self.site,'2023-24'),before.operation(self.site,'2023-24'))
        self.assertEqual(selection.operation(self.site,'2024-25')['operation_status'],'hand_coded_ended')
        self.assertEqual(selection.operation(self.site,'2025-26')['confirmed_qualifying'],0)
        self.assertEqual(len(tables['program_status_history']),len(self.tables['program_status_history'])+1)
        for name in ['program_sites','program_languages','allocation_schedules','program_configurations']:
            self.assertEqual(tables[name],self.tables[name])
        self.assertEqual(validate_tables(tables,self.schema),[])

    def test_move_keeps_destination_identity_and_does_not_copy_configuration(self):
        record=self.event_record('moved');other=next(s for s in self.schools.values() if s['school_id']!=self.site['school_id'])
        record['program_event'].update(destination_school_id=other['school_id'],destination_school_name=other['school_name'])
        tables,_=self.reviewed_tables([record]);selection=Selection(tables,self.rules)
        self.assertEqual(selection.operation(self.site,'2025-26')['operation_status'],'hand_coded_moved')
        claim=next(c for c in tables['evidence_claims'] if c['attribute']=='hand_coded_program_event')
        self.assertEqual(json.loads(claim['reported_value'])['destination_school_id'],other['school_id'])
        self.assertEqual(tables['program_sites'],self.tables['program_sites'])
        self.assertEqual(tables['allocation_schedules'],self.tables['allocation_schedules'])
        self.assertEqual(validate_tables(tables,self.schema),[])

    def test_program_events_require_a_source_and_cannot_cross_campuses_or_backfill_future_status(self):
        other=next(s for s in self.sites.values() if s['school_id']!=self.site['school_id'])
        invalid=[self.event_record(evidence_url=''),self.event_record(first='2026-27'),self.event_record(kind=['ended'])]
        cross=self.event_record();cross['program_event']['site_ids']=[other['site_id']];invalid.append(cross)
        destination=self.event_record('moved');destination['program_event']['destination_school_id']=self.site['school_id'];invalid.append(destination)
        for record in invalid:
            with self.assertRaises(ValueError):validate_record(record,self.sites,self.schools)

    def test_status_correction_and_reopening_have_separate_temporal_effects(self):
        old=self.event_record(first='2024-25')
        corrected=self.event_record(first='2025-26',supersedes_review_id=old['review_id'])
        tables,_=self.reviewed_tables([old,corrected]);selection=Selection(tables,self.rules)
        self.assertEqual(selection.operation(self.site,'2024-25'),Selection(self.tables,self.rules).operation(self.site,'2024-25'))
        reopening=self.event_record('operating',first='2025-26')
        tables,_=self.reviewed_tables([old,reopening]);selection=Selection(tables,self.rules)
        self.assertEqual(selection.operation(self.site,'2024-25')['operation_status'],'hand_coded_ended')
        self.assertNotEqual(selection.operation(self.site,'2025-26')['operation_status'],'hand_coded_ended')
        self.assertEqual(validate_tables(tables,self.schema),[])


if __name__=='__main__':unittest.main()
