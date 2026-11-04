"""Protect the distinction between direct evidence and continuity assessments."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('inventory25',ROOT/'scripts/validate_five_state_inventory_2025_26.py')
validator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=ROOT/'data/registry/five_state_2025_26'
        cls.rows=[r for name in validator.STATES.values() for r in validator.read_csv(ROOT/f'data/registry/state_dl_programs_{name}_2025_26.csv')]
        cls.ledger=validator.read_csv(base/'evidence_ledger.csv')
        cls.sources=validator.read_csv(base/'sources.csv')
        cls.reviews=json.loads((base/'continuity_reviews.json').read_text())

    def errors(self,rows=None,ledger=None,reviews=None):
        return validator.validate_rows(rows if rows is not None else self.rows,ledger if ledger is not None else self.ledger,
                                       self.sources,reviews if reviews is not None else self.reviews)

    def test_full_collected_inventory_and_source_reconciliation(self):
        self.assertGreater(len(self.rows),314)
        self.assertEqual(validator.validate()['result'],'passed')

    def test_continuity_cannot_be_confirmed_without_a_review(self):
        rows=copy.deepcopy(self.rows)
        row=next(r for r in rows if r['confirmation_basis']=='continuity_no_end_indication')
        row['continuity_review_ids']=''
        self.assertTrue(any('eligible review' in e for e in self.errors(rows=rows)))

    def test_a_closure_indication_blocks_automatic_continuity(self):
        reviews=copy.deepcopy(self.reviews)
        row=next(r for r in self.rows if r['confirmation_basis']=='continuity_no_end_indication')
        rid=row['continuity_review_ids'].split(' | ')[0]
        next(r for r in reviews if r['review_id']==rid)['outcome']='confirmed_discontinued'
        self.assertTrue(any('eligible review' in e for e in self.errors(reviews=reviews)))

    def test_a_curriculum_share_cannot_become_a_kindergarten_language_ratio(self):
        rows=copy.deepcopy(self.rows)
        row=next(r for r in rows if 'Nk̓ʷusm' in r['school_name'])
        row.update(kindergarten_allocation='other',kindergarten_partner_language_pct='70',kindergarten_english_pct='30',
                   kindergarten_language_shares_json='{"Salish":70,"English":30}')
        self.assertTrue(any('K model lacks supporting claim' in e for e in self.errors(rows=rows)))

    def test_a_later_year_schedule_cannot_be_backdated(self):
        rows=copy.deepcopy(self.rows)
        row=next(r for r in rows if r['school_name']=='Vang Pao Elementary School')
        row.update(kindergarten_allocation='50/50',kindergarten_partner_language_pct='50',kindergarten_english_pct='50',
                   kindergarten_language_shares_json='{"Hmong":50,"English":50}')
        self.assertTrue(any('Later schedule retroactively assigned' in e for e in self.errors(rows=rows)))

    def test_a_future_opening_cannot_be_promoted_with_matching_fabricated_status(self):
        rows=copy.deepcopy(self.rows);ledger=copy.deepcopy(self.ledger)
        row=next(r for r in rows if r['operating_status_2025_26']=='planned_future')
        row.update(operating_status_2025_26='confirmed_2025_26',confirmation_basis='continuity_no_end_indication')
        c=next(c for c in ledger if c['program_id']==row['program_id'] and c['field_supported']=='operating_status_2025_26')
        c.update(recorded_value='confirmed_2025_26',evidence_classification='user_authorized_continuity_assessment')
        self.assertTrue(any('Future opening promoted' in e for e in self.errors(rows=rows,ledger=ledger)))


if __name__=='__main__':
    unittest.main()
