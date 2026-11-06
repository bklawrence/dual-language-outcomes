"""Source conservation, entry grades, language strands and dated policy changes."""
import copy
import csv
import json
from pathlib import Path
import unittest

from dl_outcomes.allocation_coverage import report_rows as kindergarten_rows
from dl_outcomes.elementary_audit import report_rows
from dl_outcomes.new_england_review import audit_errors, render_reports
from dl_outcomes.northern_central_review import inputs
from dl_outcomes.ny_allocation_followup import audit_errors as ny_audit_errors
from dl_outcomes.policy_selection import current_policy_choices
from dl_outcomes.states.new_england import AUDIT, BASE, STATES
from dl_outcomes.validation import load

ROOT = Path(__file__).resolve().parents[1]


class NewEnglandInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tables = load(ROOT)
        cls.programmes, cls.sources = inputs(ROOT, base=BASE, states=STATES)
        cls.details, cls.summary = report_rows(cls.tables)
        cls.k_details, _, _ = kindergarten_rows(cls.tables)

    def programme(self, school, language=None):
        return next(p for p in self.programmes if p['school'] == school
                    and (language is None or p['track'] == language + ' immersion'))

    def reference_school(self, school):
        sid = self.programme(school)['school_id']
        return next(r for r in self.details if r['school_id'] == sid
                    and r['audit_scope'] == 'reference_working_set')

    def test_prior_sources_identities_reports_and_assessment_layers_are_preserved(self):
        self.assertEqual(audit_errors(ROOT, self.tables), [])
        audit = json.loads((ROOT / AUDIT).read_text())
        self.assertEqual(tuple(len(audit[k]) for k in ['preserved_reports', 'preserved_previous_registry',
            'preserved_previous_archives', 'preserved_assessment_outputs']), (212, 1415, 2300, 12))
        self.assertEqual((len(self.programmes), len({p['school_id'] for p in self.programmes})), (101, 97))

    def test_all_75_massachusetts_word_rows_have_a_conserved_disposition(self):
        roster = json.loads((ROOT / BASE / 'extractions/roster_reconciliation.json').read_text())[0]
        self.assertEqual([r['source_row'] for r in roster['rows']], list(range(1, 76)))
        unresolved = [r for r in roster['rows'] if not r['program_ids']]
        self.assertEqual([r['source_row'] for r in unresolved], [55])
        self.assertIn('Pierce', unresolved[0]['raw']['text_raw'])
        self.assertEqual(unresolved[0]['raw']['district_raw'], 'Millis')
        tables = copy.deepcopy(self.tables)
        claim = next(r for r in tables['evidence_claims'] if r['attribute'] == 'source_structural_observation'
                     and r['entity_id'].startswith('NE5-MA-') and 'raw_directory_row' in r['reported_value'])
        value = json.loads(claim['reported_value']); value.pop('raw_directory_row')
        claim['reported_value'] = json.dumps(value)
        self.assertTrue(any('canonical raw directory row' in e for e in audit_errors(ROOT, tables, check_hashes=False)))

    def test_three_brockton_languages_are_distinct_strands_at_one_school(self):
        ps = [p for p in self.programmes if p['school'] == 'Manthala George Jr. Global Studies School']
        self.assertEqual({p['track'] for p in ps}, {'Spanish immersion', 'Portuguese immersion', 'French immersion'})
        self.assertEqual(len({p['school_id'] for p in ps}), 1)
        for p in ps:
            a = p['allocations'][0]
            partner = p['track'].removesuffix(' immersion')
            self.assertEqual(a['shares'], {partner: 50, 'English': 50})
            self.assertIn('learning in ' + ('Portugese' if partner == 'Portuguese' else partner), a['source_passage'])

    def test_boston_preschool_launches_are_not_kindergarten_confirmation(self):
        for name in ['Blackstone Elementary School', 'Sarah Roberts Elementary School']:
            p = self.programme(name)
            self.assertEqual(p['reference']['status'], 'confirmed_preschool_only_2025_26')
            self.assertFalse(any(r['school_id'] == p['school_id'] and r['audit_scope'] == 'reference_working_set'
                                 for r in self.details))
        p = self.programme('Sarah Roberts Elementary School')
        self.assertEqual([(a['grade'], a['label'], a['period']) for a in p['allocations'][:2]],
                         [('PK', '90/10', '2025-26'), ('K', '80/20', '2026-27')])

    def test_everett_wrong_state_link_does_not_supply_a_massachusetts_model(self):
        for name in ['George Keverian School', 'Albert N. Parlin School']:
            p = self.programme(name)
            self.assertFalse(p['allocations'])
            self.assertEqual(p['reference']['status'], 'planned_after_reference_year')
            self.assertTrue(any(e['year'] == '2026-27' for e in p['events']))
        self.assertIn('everettsd.org', self.sources['ne5_doc_9a3d83259803489e']['url'])

    def test_grade_one_entry_is_elementary_but_excludes_kindergarten(self):
        for name in ['Clyde F. Brown Elementary School', 'Cunningham Elementary School',
                     'Glover Elementary School', 'Tucker Elementary School']:
            p = self.programme(name)
            self.assertEqual(self.reference_school(name)['elementary_denominator'], 1)
            self.assertEqual(self.reference_school(name)['has_numerical_allocation_model'], 1)
            k = next(r for r in self.k_details if r['program_id'] == p['program_id'])
            self.assertEqual(k['k_eligibility'], 'excluded_no_k')
            self.assertTrue(all(a['grade'] == '1-2' for a in p['allocations']))

    def test_fowler_grade_four_campus_is_in_elementary_denominator(self):
        row = self.reference_school('Fowler School')
        self.assertEqual((row['school_grade_low'], row['school_grade_high'], row['elementary_denominator']), (4, 8, 1))
        self.assertEqual(self.programme('Fowler School')['allocations'][0]['grade'], '4-5')

    def test_lyseth_former_model_is_retained_but_current_coverage_uses_60_40(self):
        p = self.programme('Harrison Lyseth Elementary School')
        self.assertEqual(len(p['allocations']), 2)
        self.assertIn('90/10', p['allocations'][1]['label'])
        choice = next(v for v in current_policy_choices(self.tables, '2025-26').values()
                      if v['program_id'] == p['program_id'])
        self.assertEqual(choice['model'], '60/40')
        row = self.reference_school(p['school'])
        self.assertEqual(row['numerical_model_labels'], '60/40')
        self.assertTrue(all(a['shares'] is None for a in p['allocations']))

    def test_french_new_hampshire_model_has_independent_explicit_support(self):
        p = self.programme('Weston Elementary School')
        self.assertEqual(p['allocations'][0]['shares'], {'French': 90, 'English': 10})
        self.assertEqual(p['allocations'][0]['source'], 'ne5_doc_f4e902d5f1247e57')
        self.assertEqual(p['observations'][0]['grade'], 'K')
        self.assertTrue(any('grade4' in reason or 'grade 4' in reason for reason in p['review_reasons']))

    def test_rhode_island_language_strands_and_later_models_remain_separate(self):
        ps = [p for p in self.programmes if p['school'] == 'International Charter School']
        self.assertEqual({p['track'] for p in ps}, {'Spanish immersion', 'Portuguese immersion'})
        self.assertEqual(len({p['school_id'] for p in ps}), 1)
        for p in self.programmes:
            if p['district'] == 'Providence':
                self.assertFalse(p['allocations'])
        p = self.programme('Raíces Dual Language Academy at Robertson')
        self.assertEqual(p['allocations'][0]['period'], '2026-27')
        self.assertEqual(self.reference_school(p['school'])['has_numerical_allocation_model'], 0)

    def test_vermont_2024_change_and_post_immersion_courses_are_not_conflated(self):
        for name in ['Jericho Elementary School', 'Richmond Elementary School']:
            p = self.programme(name)
            self.assertEqual({a['grade']: a['shares']['Spanish'] for a in p['allocations']}, {'K-2': 80, '3-4': 60})
            self.assertTrue(any(o.get('kind') == 'post_immersion_language_subject_options' for o in p['observations']))
            self.assertFalse(any(a['label'] == '90/10' for a in p['allocations']))
        self.assertFalse(any(p['state'] == 'VT' and 'High School' in p['school'] for p in self.programmes))

    def test_new_york_audit_is_scoped_and_new_england_inference_is_typed(self):
        self.assertEqual(ny_audit_errors(ROOT, self.tables), [])
        p = self.programme('Rafael Hernández Dual Language School')
        a = p['allocations'][0]
        self.assertEqual(a['shares'], {'Spanish': 83, 'English': 17})
        self.assertEqual(a['evidence_type'], 'researcher_inference')
        self.assertIn('220', a['source_passage'])
        tables = copy.deepcopy(self.tables)
        claim = next(r for r in tables['evidence_claims'] if r['attribute'] == 'allocation_source_selection'
                     and r['source_locator'].startswith(p['program_id'] + ':allocation:0;'))
        value = json.loads(claim['reported_value']); value.pop('classification_method')
        claim['reported_value'] = json.dumps(value)
        self.assertTrue(any('inferred allocation lost' in e for e in audit_errors(ROOT, tables, check_hashes=False)))

    def test_secondary_hosts_have_no_elementary_entry_allocation(self):
        for name in ['Burncoat Middle School', 'Burncoat High School', 'Springfield Legacy Academy',
                     'Raíces Upper Dual Language Academy', 'Hope High School']:
            self.assertFalse(self.programme(name)['allocations'])
            self.assertEqual(self.reference_school(name)['elementary_denominator'], 0)

    def test_state_csvs_and_reference_counts_are_reproducible(self):
        contents, report = render_reports(ROOT, self.tables)
        counts = {r['state']: (r['elementary_reference_schools_with_numerical_model'],
                              r['elementary_reference_school_units']) for r in report['state_summary']}
        self.assertEqual(counts, {'MA': (24, 48), 'ME': (1, 1), 'NH': (2, 2), 'RI': (3, 12), 'VT': (2, 2)})
        self.assertEqual(report['source_reconciliation_counts'], {'massachusetts_dese_dle_docx': 75})
        for state in STATES:
            for suffix in ['_schools.csv', '_programmes.csv', '_screening.csv']:
                path = BASE + '/' + state.lower() + suffix
                self.assertEqual((ROOT / path).read_text(), contents[path])
        school_rows = list(csv.DictReader(contents[BASE + '/ma_schools.csv'].splitlines()))
        self.assertEqual(len(school_rows), 76)
