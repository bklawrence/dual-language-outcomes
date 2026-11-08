"""Institutional exclusions affect live cohorts while source history remains auditable."""
import base64
import csv
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from dl_outcomes.baseline import school_rows, programme_rows
from dl_outcomes.baseline_selection import Selection
from dl_outcomes.build import Build
from dl_outcomes.hand_coding import accept_issue
from dl_outcomes.review_site import export
from dl_outcomes.study_scope import ATTRIBUTE, CONFIG, DATASET, excluded_school_ids, migrate, report, source_history_tables
from dl_outcomes.validation import load, validate_tables

ROOT=Path(__file__).resolve().parents[1]


class StudyScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema,tables=load(ROOT)
        sources={r['source_id'] for r in tables['sources'] if r['dataset_id']==DATASET}
        cls.before={k:[r for r in rows if r.get('source_id') not in sources
                      and not(k=='datasets' and r['dataset_id']==DATASET)] for k,rows in tables.items()}
        cls.policy=json.loads((ROOT/CONFIG).read_text())
        cls.excluded={r['school_id'] for r in cls.policy['schools']}
        cls.rules=json.loads((ROOT/'data/baselines/national_structural_v1/rules.json').read_text())
        cls.build=Build(ROOT)
        for name,rows in cls.before.items():
            for row in rows:cls.build.add(name,**row)
        migrate(cls.build)
        cls.after={name:cls.build.rows(name) for name in cls.build.tables}

    def test_decisions_preserve_all_original_school_program_and_assessment_observations(self):
        self.assertEqual(excluded_school_ids(self.before),set())
        self.assertEqual(excluded_school_ids(self.after),self.excluded)
        self.assertEqual(len(self.excluded),6)
        for table in self.before:
            if table not in {'datasets','sources','evidence_claims'}:
                self.assertEqual(self.before[table],self.after[table],table)
        original={r['claim_id']:r for r in self.before['evidence_claims']}
        after={r['claim_id']:r for r in self.after['evidence_claims']}
        self.assertTrue(all(after[k]==v for k,v in original.items()))
        self.assertEqual(validate_tables(self.after,self.schema),[])
        self.assertEqual(excluded_school_ids(source_history_tables(self.after)),set())
        rows=list(csv.DictReader(io.StringIO(report(self.after))))
        self.assertEqual(len(rows),6)
        self.assertEqual(sum(r['previous_inventory_role']=='program_school' for r in rows),4)
        self.assertTrue(all(r['basis'] and r['evidence_url'] and r['decision_date'] for r in rows))

    def test_live_selection_and_coverage_remove_only_the_reviewed_program_schools(self):
        from dl_outcomes.allocation_coverage import report_rows as kindergarten
        from dl_outcomes.elementary_audit import report_rows as elementary
        from dl_outcomes.structural import report_rows as national
        selection=Selection(self.after,self.rules)
        schools=[]
        for year in sorted({'2025-26',*self.rules['source_vintage_exceptions'].values()}):
            schools.extend(school_rows(selection,self.after,year))
        programmes,_,fields,_=programme_rows(selection,self.after,schools,'2025-26')
        active={r['school_id'] for r in programmes}
        expected={r['school_id'] for r in self.before['program_sites']}-self.excluded
        self.assertEqual(active,expected)
        self.assertEqual(len(programmes),len(self.before['program_sites'])-4)
        self.assertTrue(all(r['school_id'] not in self.excluded for r in schools+fields))
        for rows in [kindergarten(self.after)[0],elementary(self.after)[0],national(ROOT,self.after)[0]]:
            self.assertTrue(all(r['school_id'] not in self.excluded for r in rows))

    def test_fieldnotes_omits_excluded_schools_from_all_cases_and_move_destinations(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('dl_outcomes.review_site.load',return_value=(self.schema,self.after)):
                export(ROOT,Path(directory))
            data=json.loads((Path(directory)/'queue.json').read_text())
        for key in ['cases','destination_schools']:
            self.assertTrue(all(r['school_id'] not in self.excluded for r in data[key]),key)
        self.assertIn('NC-MN-S-b1f946c82b37',{r['school_id'] for r in data['cases']})

    def test_name_rule_prevents_reintroduction_without_excluding_asl_or_disability_support_in_general_schools(self):
        b=Build(ROOT)
        for name,rows in self.before.items():
            for row in rows:b.add(name,**row)
        for sid,name in [('special','Example School for the Deaf'),('general','Blind Brook High School'),
                         ('asl','Example ASL and English Academy')]:
            b.add('schools',school_id=sid,state_code='NY',school_name=name,identity_status='provisional',screening_status='candidate')
        migrate(b)
        excluded=excluded_school_ids({'evidence_claims':b.rows('evidence_claims')})
        self.assertIn('special',excluded)
        self.assertFalse({'general','asl'}&excluded)
        mainstream=[r['school_id'] for r in self.before['schools'] if 'Longwood Academy of Discovery' in r['school_name']]
        self.assertTrue(mainstream)
        self.assertFalse(set(mainstream)&excluded)

    def test_stale_submissions_cannot_readd_an_excluded_school_but_old_accepted_batches_remain_valid(self):
        sid='NC-HI-S-554eb837cc2e'
        site=next(r['site_id'] for r in self.after['program_sites'] if r['school_id']==sid)
        record=dict(review_id=str(uuid.uuid4()),school_id=sid,reviewer='Researcher',reference_year='2025-26',
            source_school_year=None,coding_method='explicit_source_statement',grade_scope='K',notes='A source note.',
            evidence_url='https://example.edu/source',changes={'delivery_structure':dict(value='whole_school',site_ids=[site])})
        payload=dict(version=1,batch_id=str(uuid.uuid4()),records=[record])
        token=base64.urlsafe_b64encode(gzip.compress(json.dumps(payload).encode())).decode().rstrip('=')
        event={'issue':dict(user={'login':'researcher'},number=1,html_url='https://github.com/example/repo/issues/1',
            created_at='2026-11-07T01:00:00Z',body='<!-- DL_REVIEW_V1:'+token+' -->')}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'config').mkdir();journal=root/'data/registry/hand_coded_reviews';journal.mkdir(parents=True)
            (root/'config/hand_coding.json').write_text(json.dumps({'authorized_reviewers':['researcher']}))
            with patch('dl_outcomes.validation.load',return_value=(self.schema,self.after)):
                with self.assertRaisesRegex(ValueError,'excluded from the research cohort'):accept_issue(root,event)
                self.assertEqual(list(journal.glob('*.json')),[])
                old=payload|{'submission':{'github_actor':'researcher'}}
                (journal/(payload['batch_id']+'.json')).write_text(json.dumps(old))
                self.assertEqual(accept_issue(root,event)['status'],'already_saved')
