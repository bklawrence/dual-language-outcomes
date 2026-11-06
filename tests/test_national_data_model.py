"""Substantive regression tests for longitudinal grain, population and provenance."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from dl_outcomes.build import Build, build
from dl_outcomes.collectors.washington import capture
from dl_outcomes.contracts import catalog
from dl_outcomes.io import digest, grade_scope, read_csv
from dl_outcomes.measurements import parse_value, ratio
from dl_outcomes.registry import IdentityResolver
from dl_outcomes.release import release
from dl_outcomes.validation import load, validate, validate_tables

ROOT = Path(__file__).resolve().parents[1]


def closed_fixture(tables, definitions):
    """Small transitive slice of real pilot records, including a multilingual school."""
    selected = {name: {} for name in tables}
    indices = {name: {tuple(row[k] for k in definitions[name]["x-primary-key"]): row for row in rows} for name, rows in tables.items()}

    def add(name, row):
        key = tuple(row[k] for k in definitions[name]["x-primary-key"])
        selected[name][key] = row

    for row in tables["states"]:
        add("states", row)
    for kind in ["school", "district"]:
        add("dl_participant_outcomes", next(r for r in tables["dl_participant_outcomes"] if indices["reporting_units"][(r["reporting_unit_id"],)]["entity_type"] == kind))
    seen = set()
    for row in tables["state_assessments"]:
        pop = indices["populations"][(row["population_id"],)]
        if row["value_status"] == "observed" and row["source_value_unit"] == "proportion" and row["value_numeric"] and pop["population_scope"] == "all_students" and row["reporting_unit_id"] not in seen:
            add("state_assessments", row)
            seen.add(row["reporting_unit_id"])
    add("demographics", next(r for r in tables["demographics"] if r["value_status"] == "derived"))
    for row in tables["observation_program_links"]:
        if (row["observation_id"],) in selected[row["observation_table"]]:
            add("observation_program_links", row)
    # Keep one complete two-language plan in the small fixture. New state
    # schedules must not make its percentage tests edit unrelated schedules.
    pairs = {}
    for row in tables["instructional_allocations"]:
        pairs.setdefault(row["schedule_id"], []).append(row)
    pair = next(rows for rows in pairs.values() if {r["language_name"] for r in rows} == {"English", "Spanish"} and len(rows) == 2)
    for row in pair:
        add("instructional_allocations", row)
    for row in tables["program_languages"]:
        if row["valid_from_year"] == "2026-27" and "roster" in (row["evidence_period_raw"] or ""):
            add("program_languages", row)
            break
    add("identifiers", next(r for r in tables["identifiers"] if r["namespace"] == "WA_OSPI_school_organization_id"))
    entity_tables = {"school": "schools", "district": "districts", "program": "programs", "site": "program_sites", "schedule": "allocation_schedules", "state": "states"}
    before = -1
    while before != sum(map(len, selected.values())):
        before = sum(map(len, selected.values()))
        for name, rows in list(selected.items()):
            for row in list(rows.values()):
                for field, reference in definitions[name]["x-foreign-keys"].items():
                    if row[field] is not None:
                        target = reference["table"]
                        add(target, indices[target][(row[field],)])
                if name in {"identifiers", "evidence_claims", "reporting_units"}:
                    target = entity_tables[row["entity_type"]]
                    add(target, indices[target][(row["entity_id"],)])
    return {name: copy.deepcopy(list(rows.values())) for name, rows in selected.items()}


class NationalModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.definition, cls.tables = load(ROOT)
        cls.fixture = closed_fixture(cls.tables, cls.definition["$defs"])
        assert not validate_tables(cls.fixture, cls.definition)

    def errors(self, tables):
        return validate_tables(tables, self.definition)

    def test_complete_saved_dataset_and_manifest(self):
        self.assertEqual(validate(ROOT)["status"], "PASS")

    def test_all_observation_layers_have_the_same_contract(self):
        names = ["dl_participant_outcomes", "state_assessments", "demographics", "el_proficiency", "el_exit_outcomes", "seda"]
        expected = self.definition["$defs"][names[0]]["properties"]
        for name in names:
            self.assertEqual(self.definition["$defs"][name]["properties"], expected)

    def test_original_seed_bytes_and_records_are_preserved(self):
        manifest = json.loads((ROOT / "data/raw/legacy_registry/pre_schema_v1/manifest.json").read_text())
        for path, info in manifest["files"].items():
            original = ROOT / info["original_snapshot"]
            self.assertEqual(digest(original), info["original_sha256"])
            self.assertEqual(digest(ROOT / path), info["normalized_sha256"])
            normalized = read_csv(ROOT / path)
            lines = [line for line in original.read_text().splitlines() if line.strip()]
            if Path(path).name == "sources.csv":
                lines.insert(0, ",".join(normalized[0]))
            self.assertEqual(list(csv.DictReader(lines)), normalized)

    def test_district_result_does_not_become_school_result(self):
        rows = copy.deepcopy(self.fixture)
        obs = next(r for r in rows["dl_participant_outcomes"] if next(u for u in rows["reporting_units"] if u["reporting_unit_id"] == r["reporting_unit_id"])["entity_type"] == "district")
        link = copy.deepcopy(rows["observation_program_links"][0])
        link.update(link_id="test-district-link", observation_table="dl_participant_outcomes", observation_id=obs["observation_id"])
        rows["observation_program_links"].append(link)
        self.assertTrue(any("below/across" in e for e in self.errors(rows)))

    def test_all_tested_grades_cannot_be_relabelled_grade_three(self):
        rows = copy.deepcopy(self.fixture)
        rows["dl_participant_outcomes"][0]["grade_scope"] = "3"
        self.assertTrue(any("grade scope" in e for e in self.errors(rows)))

    def test_current_els_are_not_automatically_dl_participants(self):
        rows = copy.deepcopy(self.fixture)
        pid = rows["dl_participant_outcomes"][0]["population_id"]
        next(p for p in rows["populations"] if p["population_id"] == pid)["population_scope"] = "current_el"
        self.assertTrue(any("non-DL population" in e for e in self.errors(rows)))

    def test_schoolwide_outcome_cannot_be_promoted_to_program(self):
        rows = copy.deepcopy(self.fixture)
        next(r for r in rows["observation_program_links"] if r["observation_table"] == "state_assessments")["attribution_status"] = "direct_program"
        self.assertTrue(any("non-DL outcome promoted" in e for e in self.errors(rows)))

    def test_one_observation_cannot_be_disaggregated_across_tracks(self):
        rows = copy.deepcopy(self.fixture)
        oid = rows["state_assessments"][0]["observation_id"]
        links = [r for r in rows["observation_program_links"] if r["observation_id"] == oid]
        self.assertGreaterEqual(len(links), 2)
        for link in links:
            link["attribution_status"] = "direct_program"
        self.assertTrue(any("disaggregated across programs" in e for e in self.errors(rows)))

    def test_duplicate_grain_is_rejected_even_with_another_id(self):
        rows = copy.deepcopy(self.fixture)
        duplicate = copy.deepcopy(rows["state_assessments"][0])
        duplicate["observation_id"] = "another-record-id"
        rows["state_assessments"].append(duplicate)
        self.assertTrue(any("duplicate reporting grain" in e for e in self.errors(rows)))

    def test_distinct_source_vintages_can_retain_same_year_result(self):
        rows = copy.deepcopy(self.fixture)
        original = rows["state_assessments"][0]
        source = copy.deepcopy(next(r for r in rows["sources"] if r["source_id"] == original["source_id"]))
        source.update(source_id="test-later-vintage", version_label="test-only-revision")
        rows["sources"].append(source)
        revised = {**original, "source_id": source["source_id"], "observation_id": "test-revised-observation"}
        rows["state_assessments"].append(revised)
        self.assertEqual(self.errors(rows), [])

    def test_suppression_cannot_become_zero(self):
        rows = copy.deepcopy(self.fixture)
        rows["state_assessments"][0].update(value_status="suppressed", value_numeric=0)
        self.assertTrue(any("became a point estimate" in e for e in self.errors(rows)))

    def test_fraction_must_be_converted_to_percent(self):
        rows = copy.deepcopy(self.fixture)
        rows["state_assessments"][0]["value_numeric"] /= 100
        self.assertTrue(any("not converted to percent" in e for e in self.errors(rows)))

    def test_derived_rate_requires_matching_counts(self):
        rows = copy.deepcopy(self.fixture)
        rows["demographics"][0]["denominator"] = None
        self.assertTrue(any("lacks observed matching counts" in e for e in self.errors(rows)))

    def test_later_program_roster_cannot_be_backdated(self):
        rows = copy.deepcopy(self.fixture)
        rows["program_languages"][0]["valid_from_year"] = "2023-24"
        self.assertTrue(any("later roster backdated" in e for e in self.errors(rows)))

    def test_policy_does_not_verify_tested_cohort_exposure(self):
        rows = copy.deepcopy(self.fixture)
        rows["allocation_schedules"][0]["tested_cohort_exposure"] = "verified"
        self.assertTrue(any("policy promoted to tested-cohort" in e for e in self.errors(rows)))

    def test_repeated_cross_sections_are_not_identified_cohorts(self):
        rows = copy.deepcopy(self.fixture)
        rows["state_assessments"][0]["cohort_status"] = "identified_cohort"
        self.assertTrue(any("no identified cohort" in e for e in self.errors(rows)))

    def test_pooled_school_year_ranges_do_not_require_invented_dates(self):
        rows = copy.deepcopy(self.fixture)
        row = rows["state_assessments"][0]
        row.update(school_year=None, period_start="2009-10", period_end="2018-19", period_basis="school_year")
        self.assertEqual(self.errors(rows), [])

    def test_period_basis_cannot_silently_change(self):
        rows = copy.deepcopy(self.fixture)
        row = rows["state_assessments"][0]
        row.update(school_year=None, period_start="2009-10", period_end="2018-19", period_basis="calendar_date")
        self.assertTrue(any("time basis" in e for e in self.errors(rows)))

    def test_three_named_instruction_languages_are_supported(self):
        rows = copy.deepcopy(self.fixture)
        rows["instructional_allocations"][0]["instruction_share_pct"] = 50
        rows["instructional_allocations"][1]["instruction_share_pct"] = 30
        third = {**rows["instructional_allocations"][0], "allocation_id": "test-third-language", "language_name": "French", "language_code": "fr", "instruction_share_pct": 20}
        rows["instructional_allocations"].append(third)
        self.assertEqual(self.errors(rows), [])

    def test_instruction_language_totals_must_be_complete(self):
        rows = copy.deepcopy(self.fixture)
        rows["instructional_allocations"][0]["instruction_share_pct"] = 95
        self.assertTrue(any("do not sum to 100" in e for e in self.errors(rows)))

    def test_no_inferred_english_partner_in_washington(self):
        sources = {r["source_id"]: r for r in self.tables["sources"]}
        cached = {}
        for row in self.tables["program_languages"]:
            source = sources[row["source_id"]]
            if source["dataset_id"] == "WA_PROGRAMS":
                if row["source_id"] not in cached:
                    raw = json.loads((ROOT / source["snapshot_path"]).read_text())
                    cached[row["source_id"]] = {"rowid=" + r["rowid"]: r for r in raw}
                original = cached[row["source_id"]][row["source_locator"]]
                self.assertEqual(row["language_name"], original["instructionallanguage"])
                self.assertEqual(row["language_role"], "reported_instruction_language")

    def test_texas_unknown_pair_has_no_invented_named_languages(self):
        programs = {r["entity_id"] for r in self.tables["evidence_claims"] if r["attribute"] == "language_pair" and r["reported_value"] == "UNVERIFIED"}
        sites = {r["site_id"] for r in self.tables["program_sites"] if r["program_id"] in programs}
        from dl_outcomes.evidence_scope import reference_bounds
        bounds = reference_bounds(self.tables)
        reviewed = {}
        for claim in self.tables['evidence_claims']:
            if claim['attribute'] != 'structural_gap_pilot_observation':
                continue
            observation = json.loads(claim['reported_value'])
            if observation['variable'] == 'instruction_languages':
                for key in observation['canonical_evidence_ids']:
                    reviewed[key] = observation
        for row in self.tables['program_languages']:
            if row['site_id'] not in sites:
                continue
            # An older unknown remains intact. Later named languages need
            # source-backed field review and cannot silently fill that year.
            review = reviewed[row['language_record_id']]
            self.assertIn(row['language_name'], review['value'])
            self.assertIn(row['source_id'], review['supporting_source_ids'])
            self.assertTrue(review['source_quote'])
            self.assertGreater(bounds[('program_languages',row['language_record_id'])], '2023-24')

    def test_uncollected_layers_do_not_claim_no_public_data(self):
        for row in self.tables["coverage"]:
            if row["layer"] in {"el_proficiency", "el_exit_policy", "el_exit_outcomes", "seda"}:
                self.assertEqual(row["collection_status"], "not_collected")

    def test_identifier_strings_preserve_leading_zeros(self):
        identifiers = [r for r in self.tables["identifiers"] if r["namespace"] == "TX_TEA_campus_id"]
        self.assertTrue(any(r["native_id"].startswith("0") for r in identifiers))
        self.assertTrue(all(isinstance(r["native_id"], str) and len(r["native_id"]) == 9 for r in identifiers))

    def test_population_group_types_remain_distinct(self):
        b = Build(ROOT)
        left = b.population("WA", "Same label", "all_students", "test-source", group_type="type-a")
        right = b.population("WA", "Same label", "all_students", "test-source", group_type="type-b")
        self.assertNotEqual(left, right)

    def test_offline_build_is_reproducible_and_release_is_immutable(self):
        expected = json.loads((ROOT / "data/curated/manifest.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in set(expected["inputs"]) | set(expected["pipeline_files"]):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            result = build(root)
            actual = json.loads((root / "data/curated/manifest.json").read_text())
            self.assertEqual(result["build_id"], expected["build_id"])
            self.assertEqual(actual["outputs"], expected["outputs"])
            self.assertEqual(actual.get("reports"), expected.get("reports"))
            validate(root)
            info = release(root, "test-only-local-release")
            with zipfile.ZipFile(root / info["bundle"]) as archive:
                self.assertIn("data/curated/dl_participant_outcomes/observations.csv", archive.namelist())
                self.assertIn("src/dl_outcomes/schemas/catalog.json", archive.namelist())
            with self.assertRaisesRegex(ValueError, "never overwritten"):
                release(root, "test-only-local-release")


class MeasurementAndIdentityTests(unittest.TestCase):
    def test_zero_and_missing_are_distinct(self):
        self.assertEqual(parse_value("0")["value_numeric"], 0)
        self.assertEqual(parse_value("")["value_status"], "not_reported")
        self.assertIsNone(parse_value("*")["value_numeric"])
        self.assertEqual(parse_value("<5")["value_upper_bound"], 5)
        self.assertIsNone(parse_value("<5")["value_numeric"])

    def test_rate_does_not_infer_suppressed_counts_or_zero_denominator(self):
        self.assertIsNone(ratio("*", "100")["value_numeric"])
        self.assertEqual(ratio("0", "0")["value_status"], "not_applicable")
        self.assertEqual(ratio("0", "100")["value_numeric"], 0)
        with self.assertRaises(ValueError):
            ratio("101", "100")

    def test_native_grade_labels_are_preserved_but_normalized(self):
        self.assertEqual(grade_scope("03"), grade_scope("3rd Grade"))
        self.assertEqual(grade_scope("All Grades"), "all_grades")
        with self.assertRaises(ValueError):
            grade_scope("unmapped grade code")

    def test_identity_overrides_are_reviewed_and_time_limited(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "identities.csv"
            path.write_text("entity_type,namespace,native_id,valid_from_year,valid_to_year,research_entity_id,review_status,evidence_url\nschool,test,001,2023-24,2023-24,stable-school,accepted,repo:test-evidence\nschool,test,002,,,pending-school,pending,\n")
            resolver = IdentityResolver(path)
            self.assertEqual(resolver.resolve("school", "test", "001", "2023-24", "fallback"), "stable-school")
            self.assertEqual(resolver.resolve("school", "test", "001", "2024-25", "fallback"), "fallback")
            self.assertEqual(resolver.resolve("school", "test", "001", None, "fallback"), "fallback")
            self.assertEqual(resolver.resolve("school", "test", "002", "2023-24", "fallback"), "fallback")

    def test_cached_selection_changes_require_new_vintage(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            raw = b'[{"schoolyear":"2023-24"}]'
            (path / "test.json").write_bytes(raw)
            (path / "test.metadata.json").write_text(json.dumps({"dataset_id": "test", "sha256": hashlib.sha256(raw).hexdigest(), "selection": {"$limit": 5}}))
            with self.assertRaisesRegex(ValueError, "Cached selection differs"):
                capture(path, "test", "test", {"$limit": 10})
            self.assertEqual((path / "test.json").read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
