"""Partner-language pathways do not by themselves establish campus strand delivery."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from dl_outcomes.baseline_selection import Selection
from dl_outcomes.build import Build
from dl_outcomes.delivery_review import inputs, migrate
from dl_outcomes.io import record_id
from dl_outcomes.validation import load, validate_tables

ROOT = Path(__file__).resolve().parents[1]
CONFIG = 'config/research_migrations/named_school_delivery_review_2026_11_07.json'
DATASET = 'NAMED_SCHOOL_DELIVERY_REVIEW_2026_11_07'


class NamedSchoolDeliveryReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema, tables = load(ROOT)
        cls.config, cls.files = inputs(ROOT, CONFIG)
        cls.rules = json.loads((ROOT/'data/baselines/national_structural_v1/rules.json').read_text())
        configurations = {record_id('configuration', DATASET, f['fact_id']) for f in cls.files['observations']}
        claims = set()
        sources = {s['key']:s['reuse_source_id'] for s in cls.files['sources']}
        for f in cls.files['observations']:
            for attribute, locator in [
                ('reviewed_record_reference_scope', f['fact_id']+':reference_scope'),
                ('delivery_scope_review_observation', f['fact_id']+':review'),
                ('reviewed_structural_field_selection', f['site_id']+':'+f['reference_year']+':delivery_structure'),
            ]:
                claims.add(record_id('claim','program',f['program_id'],attribute,sources[f['source_keys'][0]],locator))
        cls.before = {name:[r for r in rows if not (
            name=='datasets' and r['dataset_id']==DATASET or
            name=='program_configurations' and r['configuration_id'] in configurations or
            name=='evidence_claims' and r['claim_id'] in claims)] for name,rows in tables.items()}
        build = cls.fresh_build()
        migrate(build, config_path=CONFIG, dataset_id=DATASET)
        cls.after = {name:build.rows(name) for name in build.tables}

    @classmethod
    def fresh_build(cls):
        build = Build(ROOT)
        for name, rows in cls.before.items():
            for row in rows:
                build.add(name, **row)
        return build

    def test_language_pathways_share_a_whole_school_model_without_changing_other_fields(self):
        before, after = Selection(self.before,self.rules), Selection(self.after,self.rules)
        sites = {s['site_id']:s for s in self.before['program_sites']}
        for fact in self.files['observations']:
            site = sites[fact['site_id']]
            field,_ = after.select_field(site,'delivery_structure','2025-26')
            self.assertEqual(json.loads(field['value_json']),['whole_school'])
            self.assertEqual(field['value_status'],'provisional')
            for year in ['2024-25','2026-27']:
                old,_ = before.select_field(site,'delivery_structure',year)
                new,_ = after.select_field(site,'delivery_structure',year)
                for key in ['value_json','value_status','selected_evidence_ids','selected_source_ids','temporal_status']:
                    self.assertEqual(old[key],new[key],(year,key))
            for variable in ['population_model','instruction_languages','programme_grade_scope']:
                self.assertEqual(before.select_field(site,variable,'2025-26'),
                                 after.select_field(site,variable,'2025-26'))
        for name in self.before:
            if name not in {'datasets','program_configurations','evidence_claims'}:
                self.assertEqual(self.before[name],self.after[name],name)
        existing = {r['configuration_id']:r for r in self.after['program_configurations']}
        self.assertTrue(all(existing[r['configuration_id']]==r for r in self.before['program_configurations']))
        self.assertEqual(validate_tables(self.after,self.schema),[])

    def test_suggestive_names_do_not_automatically_reclassify_other_schools(self):
        before,after = Selection(self.before,self.rules),Selection(self.after,self.rules)
        for school in ['WP-AZ-S-38fdf8b4080e','IL-S006','M6-DE-S-0fed95439ac8']:
            for site in self.before['program_sites']:
                if site['school_id']==school:
                    self.assertEqual(before.select_field(site,'delivery_structure','2025-26'),
                                     after.select_field(site,'delivery_structure','2025-26'))

    def test_followup_rejects_cross_campus_and_future_source_assignments(self):
        for change, error in [('school_id','crosses'),('source_school_year','source date')]:
            files=copy.deepcopy(self.files)
            files['observations'][0][change]='IL-S006' if change=='school_id' else '2026-27'
            with patch('dl_outcomes.delivery_review.inputs',return_value=(self.config,files)):
                with self.assertRaisesRegex(ValueError,error):
                    migrate(self.fresh_build(),config_path=CONFIG,dataset_id=DATASET)
