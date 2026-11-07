"""Staff-role evidence must preserve campus, reference-year and program scope."""
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from dl_outcomes.baseline_selection import Selection
from dl_outcomes.build import Build
from dl_outcomes.delivery_review import inputs, migrate
from dl_outcomes.io import record_id
from dl_outcomes.review_site import export
from dl_outcomes.validation import load, validate_tables

ROOT = Path(__file__).resolve().parents[1]
CONFIG = 'config/research_migrations/tx_staff_delivery_review_2026_11_07.json'
DATASET = 'TX_STAFF_DELIVERY_REVIEW_2026_11_07'
BASE = ROOT / 'data/registry/tx_staff_delivery_review_2026_11_07'


class TexasStaffDeliveryReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema, tables = load(ROOT)
        cls.config, cls.files = inputs(ROOT, CONFIG)
        cls.rules = json.loads((ROOT/'data/baselines/national_structural_v1/rules.json').read_text())
        source_ids = {r['source_id'] for r in tables['sources'] if r['dataset_id'] == DATASET}
        configuration_ids = {record_id('configuration', DATASET, f['fact_id']) for f in cls.files['observations']}
        cls.before = {name: [r for r in rows if not (
            name == 'datasets' and r['dataset_id'] == DATASET or
            name == 'sources' and r['source_id'] in source_ids or
            name == 'program_configurations' and r['configuration_id'] in configuration_ids or
            name == 'evidence_claims' and r['source_id'] in source_ids)]
            for name, rows in tables.items()}
        build = Build(ROOT)
        for name, rows in cls.before.items():
            for row in rows:
                build.add(name, **row)
        migrate(build, config_path=CONFIG, dataset_id=DATASET)
        cls.after = {name: build.rows(name) for name in build.tables}

    def test_every_inventory_campus_has_an_honest_non_exhaustive_audit_outcome(self):
        targets = self.files['campus_targets']
        with (BASE/'campus_audit.csv').open() as stream:
            audit = list(csv.DictReader(stream))
        self.assertEqual(len(targets), 1610)
        self.assertEqual(len({s['district_id'] for s in targets}), 196)
        self.assertEqual(sum(len(s['program_site_ids']) for s in targets), 1863)
        self.assertEqual({s['school_id'] for s in targets}, {r['school_id'] for r in audit})
        self.assertEqual(len(audit), len({r['school_id'] for r in audit}))
        self.assertTrue(all(r['audit_outcome'] and r['notes'] for r in audit))
        self.assertTrue(all(r['staff_entries_exhaustively_reviewed'] == '0' for r in audit))
        decisions = {f['school_id']:f['value'] for f in self.files['observations']}
        self.assertEqual({r['school_id']:r['new_delivery_structure'] for r in audit if r['new_delivery_structure']}, decisions)
        self.assertEqual(set(decisions.values()), {'strand'})

    def test_source_fragments_are_in_the_archived_staff_material(self):
        sources = {s['key']:s for s in self.files['sources']}
        spec = importlib.util.spec_from_file_location('staff_extraction', ROOT/'scripts/collect_texas_staff_directories.py')
        extraction = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(extraction)
        original_text = {}
        for source in sources.values():
            data = (ROOT/source['path']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), source['sha256'])
            raw = gzip.decompress(data)
            self.assertTrue(raw)
            metadata = json.loads((ROOT/source['metadata_path']).read_text())
            self.assertEqual(metadata['status'], 'retrieved')
            self.assertEqual(metadata['url'], source['url'])
            if source.get('extraction_path'):
                original_text[source['key']] = extraction.extract(raw, metadata['content_type'], source['url'])['text']
        for fact in self.files['observations']:
            self.assertGreaterEqual(len(fact['source_quote_fragments']), 2)
            for fragment in fact['source_quote_fragments']:
                text = (ROOT/sources[fragment['source_key']]['extraction_path']).read_text()
                self.assertIn(' '.join(fragment['quote'].split()), ' '.join(text.split()))
                self.assertIn(' '.join(fragment['quote'].split()), ' '.join(original_text[fragment['source_key']].split()))
            self.assertTrue(fact['campus_identity_basis'])
            self.assertEqual(fact['verification_status'], 'provisional')
            self.assertIsNone(fact['source_school_year'])
            self.assertTrue(fact['source_capture_date'].startswith('2026-11-07'))

    def test_review_is_delivery_only_and_does_not_rewrite_other_reference_years(self):
        before, after = Selection(self.before, self.rules), Selection(self.after, self.rules)
        sites = {s['site_id']:s for s in self.after['program_sites']}
        for fact in self.files['observations']:
            site = sites[fact['site_id']]
            self.assertEqual(site['school_id'], fact['school_id'])
            self.assertEqual(site['program_id'], fact['program_id'])
            self.assertEqual(fact['earliest_reviewed_selection_year'], '2025-26')
            self.assertEqual(fact['latest_reviewed_selection_year'], '2025-26')
            field, _ = after.select_field(site, 'delivery_structure', '2025-26')
            if (site['site_id'], '2025-26', 'delivery_structure') not in after.overrides:
                self.assertEqual(json.loads(field['value_json']), ['strand'])
                self.assertEqual(field['value_status'], 'provisional')
            for year in ['2021-22', '2024-25', '2026-27', '2027-28']:
                old, _ = before.select_field(site, 'delivery_structure', year)
                new, _ = after.select_field(site, 'delivery_structure', year)
                # New, explicitly bounded evidence can change an empty period's
                # missingness label from not_reported to later_only. It must
                # never fill that period or replace its selected evidence.
                for key in ['value_json', 'selected_evidence_ids', 'selected_source_ids']:
                    self.assertEqual(old[key], new[key], (fact['school_name'], year, key))
                if json.loads(old['value_json']):
                    self.assertEqual(old['value_status'], new['value_status'])
            for variable in ['population_model', 'instruction_languages', 'programme_grade_scope']:
                self.assertEqual(before.select_field(site, variable, '2025-26'), after.select_field(site, variable, '2025-26'))
            self.assertEqual(before.operation_field(site, '2025-26'), after.operation_field(site, '2025-26'))
            grade, _ = before.select_field(site, 'programme_grade_scope', '2025-26')
            self.assertEqual(before.select_allocations(site, '2025-26', 'elementary', json.loads(grade['value_json'])),
                             after.select_allocations(site, '2025-26', 'elementary', json.loads(grade['value_json'])))
        for name in self.before:
            if name not in {'datasets', 'sources', 'program_configurations', 'evidence_claims'}:
                self.assertEqual(self.before[name], self.after[name], name)
        existing = {r['configuration_id']:r for r in self.after['program_configurations']}
        self.assertTrue(all(existing[r['configuration_id']] == r for r in self.before['program_configurations']))
        self.assertEqual(validate_tables(self.after, self.schema), [])

    def test_preschool_and_english_partner_cases_are_not_automatically_strands(self):
        decisions = {f['school_id'] for f in self.files['observations']}
        cases = {c['school_id']:c for c in self.files['review_cases']}
        for sid in ['TX-S071901105', 'TX-S246906103', 'TX-S057905239']:
            self.assertIn(sid, cases)
            self.assertNotIn(sid, decisions)
            self.assertIsNone(cases[sid]['assigned_delivery_structure'])

    def test_vetted_staff_leads_reach_fieldnotes_without_creating_reviewer_credits(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            export(ROOT, destination)
            queue = json.loads((destination/'queue.json').read_text())
        by_school = {c['school_id']:c for c in queue['cases']}
        sanger = by_school['TX-S057905206']
        references = {r['url']:r for r in sanger['references']}
        self.assertIn('https://sanger.dallasisd.org/faculty-team/staff-directory', references)
        self.assertEqual(references['https://sanger.dallasisd.org/faculty-team/staff-directory']['label'], 'Staff directory')
        for case in queue['cases']:
            self.assertTrue(all(not r['review_id'].startswith('tx-staff') for r in case['hand_coded_reviews']))


if __name__ == '__main__':
    unittest.main()
