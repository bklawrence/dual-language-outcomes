"""Frozen dataset grain, preservation, scope and independent reproduction."""
import copy
import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from dl_outcomes.baseline import (audit_rendered, check, create, csv_text, digest,
    json_text, load_snapshot, render)
from dl_outcomes.release import release

ROOT = Path(__file__).resolve().parents[1]
ID = 'national_structural_v1'
BASE = ROOT / 'data/baselines' / ID


class NationalBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tables = load_snapshot(BASE)
        cls.rules = json.loads((BASE / 'rules.json').read_text())
        cls.profiles = json.loads((BASE / 'state_profiles.json').read_text())
        cls.prior = list(csv.DictReader(io.StringIO((BASE / 'evidence/previous_allocation_coverage.csv').read_text())))
        cls.prior_schools = list(csv.DictReader(io.StringIO((BASE / 'evidence/previous_allocation_school_units.csv').read_text())))
        cls.contents, cls.summary = render(cls.tables, cls.rules, cls.profiles, cls.prior, cls.prior_schools)

    def rows(self, name):
        return list(csv.DictReader(io.StringIO(self.contents[name])))

    def test_registered_baseline_reproduces_and_preserves_evidence_and_twelve_layers(self):
        self.assertEqual(check(ROOT, ID, reproduce=True)['status'], 'PASS')
        manifest = json.loads((BASE / 'manifest.json').read_text())
        self.assertEqual(len(manifest['preserved_assessment_context_output_receipts']), 12)
        for name, entry in manifest['evidence_tables'].items():
            self.assertEqual(digest(BASE / entry['snapshot_path']), entry['sha256'])
            self.assertEqual(len(self.tables[name]), entry['rows'])
        self.assertEqual(self.summary['programme_site_records'], 5131)
        self.assertEqual(self.summary['school_research_identities'], 4617)
        self.assertFalse(self.summary['new_source_collection'])
        self.assertFalse(self.summary['new_proficiency_collection'])

    def test_all_states_and_zero_denominators_remain_explicit(self):
        states = self.rows('state_summary.csv')
        self.assertEqual(len(states), 50)
        self.assertEqual(len(self.rows('completeness_by_state.csv')), 1200)
        for state in ['MS', 'WV']:
            row = next(r for r in states if r['state_code'] == state)
            self.assertEqual(row['programme_site_evidence_records'], '0')
            self.assertEqual(row['statewide_school_list_completeness'], 'not_established')
            self.assertIn('screened', row['research_status'])
            coverage = [r for r in self.rows('allocation_coverage_by_state.csv') if r['state_code'] == state]
            self.assertTrue(all(r['reported_model_coverage_pct'] == '' for r in coverage))

    def test_texas_and_oregon_are_not_relabelled_as_confirmed_2025_26(self):
        programmes = self.rows('programmes.csv')
        supplements = self.rows('source_vintage_programmes.csv')
        self.assertEqual(len(supplements), 2072)
        for state, year in [('TX', '2023-24'), ('OR', '2026-27')]:
            rows = [r for r in programmes if r['state_code'] == state]
            self.assertTrue(rows)
            self.assertTrue(all(r['selection_year'] == '2025-26' and r['in_confirmed_qualifying_cohort'] == '0'
                                and r['in_working_cohort'] == '0' for r in rows))
            self.assertTrue(all(r['selection_year'] == year for r in supplements if r['state_code'] == state))

    def test_coverage_changes_are_traceable_only_to_57_texas_later_policy_cases(self):
        changes = self.rows('coverage_changes.csv')
        self.assertEqual(len(changes), 57)
        self.assertEqual({r['state_code'] for r in changes}, {'TX'})
        self.assertTrue(all(r['prior_has_model'] == '1' and r['baseline_has_model'] == '0'
                            and r['excluded_later_model_record_ids'] for r in changes))
        tx = next(r for r in self.rows('coverage_reconciliation.csv') if r['state_code'] == 'TX')
        self.assertEqual((tx['prior_with_model'], tx['baseline_with_model'], tx['baseline_elementary_units']),
                         ('875', '818', '1420'))

    def test_inferred_models_remain_typed_and_not_all_evidence_is_resolved(self):
        fields = self.rows('programme_fields.csv')
        self.assertTrue(any(r['value_status'] == 'inferred' for r in fields))
        self.assertTrue(any(r['value_status'] == 'conflicting' for r in fields))
        self.assertTrue(any(r['value_status'] == 'reported_model_requires_review' for r in fields))
        for r in self.rows('completeness_by_state.csv'):
            self.assertLessEqual(int(r['with_resolved_classification']), int(r['with_selected_evidence']))

    def test_lost_field_provenance_and_false_confirmation_are_rejected(self):
        altered = dict(self.contents)
        evidence = self.rows('field_evidence.csv')
        index = next(i for i, r in enumerate(evidence) if r['selection_role'] == 'selected')
        evidence.pop(index)
        altered['field_evidence.csv'] = csv_text(evidence)
        with self.assertRaisesRegex(ValueError, 'provenance is incomplete'):
            audit_rendered(altered, self.tables, self.rules)
        altered = dict(self.contents); programmes = self.rows('programmes.csv')
        row = next(r for r in programmes if r['state_code'] == 'TX')
        row['in_confirmed_qualifying_cohort'] = '1'
        altered['programmes.csv'] = csv_text(programmes)
        with self.assertRaisesRegex(ValueError, 'invented reference-year'):
            audit_rendered(altered, self.tables, self.rules)

    def test_grade_context_matches_and_possible_aliases_do_not_authorize_outcome_joins(self):
        self.assertTrue(all(r['grade_context_candidate_is_automatic_outcome_join'] == '0' for r in self.rows('schools.csv')))
        aliases = self.rows('identity_review_queue.csv')
        self.assertEqual(len(aliases), 2)
        self.assertTrue(all(r['outcome_join_authorized'] == '0' for r in aliases))

    def test_a_frozen_version_cannot_be_overwritten(self):
        before = digest(BASE / 'manifest.json')
        with self.assertRaisesRegex(ValueError, 'never overwritten'):
            create(ROOT, ID, ROOT / 'config/baselines/national_structural_v1.json')
        self.assertEqual(digest(BASE / 'manifest.json'), before)

    def test_standalone_frozen_pipeline_ignores_absent_or_changed_live_tables(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); destination = root / 'data/baselines' / ID
            shutil.copytree(BASE, destination, ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copyfile(ROOT / 'data/baselines/index.json', root / 'data/baselines/index.json')
            (root / 'data/curated').mkdir()
            (root / 'data/curated/manifest.json').write_text('{"unrelated_future_live_data":true}')
            environment = os.environ.copy()
            environment['PYTHONPATH'] = str(destination / 'pipeline')
            result = subprocess.run([sys.executable, '-m', 'dl_outcomes.cli', '--root', str(root),
                'baseline', 'check', ID, '--reproduce'], env=environment, cwd=root,
                text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'PASS')


class BaselineIntegrityAndReleaseTests(unittest.TestCase):
    def test_checksum_detects_changes_to_a_frozen_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); base = root / 'data/baselines/sample'; base.mkdir(parents=True)
            data = base / 'sample.csv'; data.write_text('id\n001\n')
            manifest = dict(files={'sample.csv': dict(sha256=digest(data))}, summary={})
            (base / 'manifest.json').write_text(json_text(manifest))
            (base.parent / 'index.json').write_text(json_text({'sample': {'manifest_sha256': digest(base / 'manifest.json')}}))
            self.assertEqual(check(root, 'sample')['status'], 'PASS')
            data.write_text('id\n002\n')
            with self.assertRaisesRegex(ValueError, 'Frozen baseline file changed'):
                check(root, 'sample')

    def test_portable_release_includes_registered_baseline_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); base = root / 'data/baselines/sample'; base.mkdir(parents=True)
            (base / 'sample.csv').write_text('id\n001\n')
            (base / 'manifest.json').write_text(json_text({'files': {'sample.csv': {'sha256': digest(base / 'sample.csv')}}}))
            (base.parent / 'index.json').write_text(json_text({'sample': {}}))
            (root / 'data/curated').mkdir(); (root / 'pyproject.toml').write_text(''); (root / 'requirements-lock.txt').write_text('')
            (root / 'data/curated/manifest.json').write_text(json_text(dict(inputs={}, pipeline_files={}, outputs={},
                schema_version='test', build_id='test', limitations=[])))
            with patch('dl_outcomes.release.validate'):
                result = release(root, 'test-baseline-package')
            with zipfile.ZipFile(root / result['bundle']) as archive:
                self.assertIn('data/baselines/index.json', archive.namelist())
                self.assertIn('data/baselines/sample/sample.csv', archive.namelist())
                self.assertIn('data/baselines/sample/manifest.json', archive.namelist())
