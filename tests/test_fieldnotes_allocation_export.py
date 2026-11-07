"""Allocation gaps and candidate leads stay separate from program confirmation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dl_outcomes.hand_coding import DATASET
from dl_outcomes.review_site import export, reviewable_candidate
from dl_outcomes.validation import load

ROOT=Path(__file__).resolve().parents[1]


class FieldnotesAllocationExportTests(unittest.TestCase):
    def test_export_preserves_grade_schedules_and_exposes_unconfirmed_candidates(self):
        schema,before=load(ROOT)
        manual_sources={s['source_id'] for s in before['sources'] if s['dataset_id']==DATASET}
        original={name:[r for r in rows if r.get('source_id') not in manual_sources
                        and not(name=='datasets' and r['dataset_id']==DATASET)] for name,rows in before.items()}
        with tempfile.TemporaryDirectory() as temp:
            with patch('dl_outcomes.review_site.load',return_value=(schema,original)):
                export(ROOT,Path(temp))
            data=json.loads((Path(temp)/'queue.json').read_text())
        cases={c['school_id']:c for c in data['cases']}
        white=cases['NE5-MA-S-c7cf93db6bc0']
        rows=white['sites'][0]['known']['elementary_allocation_model']['schedules']
        self.assertEqual({r['grade_scope']:r['model_label_normalized'] for r in rows},
                         {'K':'80/20','1':'70/30','2-5':'50/50'})
        kindergarten=next(r for r in rows if r['grade_scope']=='K')
        self.assertEqual(kindergarten['named_language_shares'],{'Spanish':80,'English':20})
        # A Texas funding/identity candidate is a research lead, not a new
        # confirmed DL program, even if an allocation is later hand coded.
        candidate=cases['TX-S071901104']
        self.assertEqual(candidate['dl_status'],'needs_confirmation')
        self.assertTrue(candidate['research_lead'])
        self.assertFalse(candidate['allocation_known'])
        self.assertIn('elementary_allocation_model',candidate['missing'])
        _,after=load(ROOT)
        for table in ['program_sites','program_status_history','allocation_schedules','instructional_allocations']:
            self.assertEqual(before[table],after[table],table)

    def test_explicit_future_closed_and_non_dl_leads_do_not_enter_missing_allocation_queue(self):
        row=dict(school_level='elementary',operation_status='no_reference_year_operation_confirmation',
                 programme_screening_status='candidate',operating_statuses='',eligibility_statuses='')
        self.assertTrue(reviewable_candidate(row))
        for change in [dict(operation_status='later_status_only'),dict(school_level='secondary_6_plus'),
                       dict(operating_statuses='planned_future'),dict(operating_statuses='closed_before_reference_year'),
                       dict(eligibility_statuses='not_qualifying'),dict(programme_screening_status='related_language_program')]:
            self.assertFalse(reviewable_candidate(row|change),change)
