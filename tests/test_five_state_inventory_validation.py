"""Regression checks against realistic corruptions of the collected inventory."""
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('five_state_validation', ROOT / 'scripts/validate_five_state_inventory_2026_27.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class InventoryValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = ROOT / 'data/registry/five_state_2026_27'
        cls.records = [r for name in validator.STATES.values()
                       for r in validator.csv_rows(ROOT / f'data/registry/state_dl_programs_{name}_2026_27.csv')]
        cls.ledger = validator.csv_rows(base / 'evidence_ledger.csv')
        cls.sources = validator.csv_rows(base / 'sources.csv')

    def errors(self, records=None, ledger=None):
        return validator.validate_rows(records if records is not None else self.records,
                                       ledger if ledger is not None else self.ledger, self.sources)

    def test_collected_data_are_nonempty_and_consistent(self):
        self.assertGreater(len(self.records), 250)
        self.assertEqual(self.errors(), [])

    def test_duplicate_school_program_is_rejected_even_with_new_id(self):
        rows = copy.deepcopy(self.records)
        extra = dict(rows[0], program_id='DUPLICATE-WITH-DIFFERENT-ID')
        rows.append(extra)
        self.assertTrue(any('Duplicate school–program' in e for e in self.errors(rows)))

    def test_language_shares_cannot_silently_stop_summing_to_100(self):
        rows = copy.deepcopy(self.records)
        row = next(r for r in rows if r['kindergarten_allocation'] == '50/50')
        row['kindergarten_language_shares_json'] = '{"Spanish": 50, "English": 30}'
        self.assertTrue(any('percentages/sum' in e for e in self.errors(rows)))

    def test_historical_program_cannot_be_promoted_without_year_evidence(self):
        rows = copy.deepcopy(self.records)
        row = next(r for r in rows if r['operating_status_2026_27'] == 'historical_status_unknown')
        row['operating_status_2026_27'] = 'confirmed_2026_27'
        self.assertTrue(any('lacks applicable 2026' in e for e in self.errors(rows)))

    def test_published_model_cannot_be_dropped_without_documented_conflict(self):
        rows = copy.deepcopy(self.records)
        row = next(r for r in rows if r['published_model_label'] == '90/10' and not r['allocation_conflict_notes'])
        row.update(kindergarten_allocation='unknown', kindergarten_partner_language_pct='',
                   kindergarten_english_pct='', kindergarten_language_shares_json='{}')
        self.assertTrue(any('conventional model incorrectly left unknown' in e for e in self.errors(rows)))

    def test_source_identity_cannot_point_at_another_document(self):
        ledger = copy.deepcopy(self.ledger)
        ledger[0]['source_url'] = 'https://example.org/unrelated-document'
        self.assertTrue(any('registry disagree' in e for e in self.errors(ledger=ledger)))


if __name__ == '__main__':
    unittest.main()
