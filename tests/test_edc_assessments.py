"""Protect school matching, source populations, suppression and transfer integrity."""
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dl_outcomes.collectors.edc import IDENTITY_FIELDS, fetch_file
from dl_outcomes.edc import (MEASURES, choose_match, count_provenance, gzip_csv,
                            nces_id, normalized_row, parse_edc_value, source_index, target_rows, unit_id)
from dl_outcomes.io import write_csv


def source(**changes):
    row = {k: "" for k in IDENTITY_FIELDS + MEASURES}
    row.update(StateAbbrev="CA", SchYear="2023-24", NCESSchoolID="62271000001", NCESDistrictID="622710",
               StateAssignedSchID="0000001", StateAssignedDistID="1964733", SchName="Example Elementary",
               DistName="Los Angeles Unified", GradeLevel="G03", DataLevel="School", Subject="ela",
               StudentGroup="All Students", StudentSubGroup="All Students", AssmtName="State Test",
               AssmtType="Regular", ProficiencyCriteria="Levels 3-4", Flag_AssmtNameChange="N",
               Flag_CutScoreChange_ELA="N", Flag_CutScoreChange_math="N")
    return row | changes


def target(**changes):
    return dict(school_id="research-school", state_code="CA", school_name="Example Elementary School",
                district_names="Los Angeles Unified School District", grade_context_nces_candidate="062271000001",
                official_identifiers_json="[]", directory_evidence_json="[]") | changes


class EDCValues(unittest.TestCase):
    def test_zero_suppressed_and_missing_are_distinct(self):
        self.assertEqual(parse_edc_value(0)["numeric"], "0")
        self.assertEqual(parse_edc_value("*")["status"], "suppressed")
        self.assertEqual(parse_edc_value("--")["status"], "not_reported")
        self.assertEqual(parse_edc_value("")["status"], "not_reported")

    def test_ranges_and_open_bounds_never_become_points(self):
        value = parse_edc_value(".35-.40", proportion=True)
        self.assertEqual((value["numeric"], value["lower_bound"], value["upper_bound"]), ("", "35.00", "40.00"))
        self.assertEqual(parse_edc_value("<.05", proportion=True)["upper_inclusive"], "0")
        self.assertEqual(parse_edc_value("<=5")["upper_inclusive"], "1")
        self.assertEqual(parse_edc_value("10-19")["status"], "bounded")

    def test_source_totals_are_not_subgroup_counts_or_enrollment(self):
        row = source(StudentGroup="EL Status", StudentSubGroup="English Learner",
                     StudentGroup_TotalTested="100", StudentSubGroup_TotalTested="12",
                     ProficientOrAbove_percent=".50")
        output = normalized_row(row, "result")
        self.assertEqual(output["StudentGroup_TotalTested_numeric"], "100")
        self.assertEqual(output["StudentSubGroup_TotalTested_numeric"], "12")
        self.assertEqual(output["ProficientOrAbove_percent_numeric"], "50.00")
        self.assertEqual(output["outcome_scope"], "schoolwide_not_DL_participants")
        self.assertEqual(output["cross_state_norming"], "none")

    def test_grade_aggregate_is_not_grade_38(self):
        self.assertEqual(normalized_row(source(GradeLevel="G38"), "r")["grade_scope"], "all_tested_grades")

    def test_proxy_counts_keep_the_documented_source_year(self):
        self.assertIn("enrollment_proxy", count_provenance("UT", 2024, "All Students")[0])
        self.assertEqual(count_provenance("KS", 2024, "EL Status")[1], "2022")
        self.assertIn("enrollment_proxy", count_provenance("KS", 2025, "EL Status")[0])
        self.assertIn("possible_EDFacts", count_provenance("AR", 2024, "EL Status")[0])
        self.assertNotIn("2022_subgroup", count_provenance("AR", 2024, "All Students")[0])

    def test_unknown_token_is_retained_for_review(self):
        value = parse_edc_value("source-specific-mask")
        self.assertEqual(value["raw"], "source-specific-mask")
        self.assertEqual(value["status"], "unrecognized_source_token")
        self.assertEqual(value["numeric"], "")


class EDCIdentity(unittest.TestCase):
    def test_candidate_id_needs_source_name_and_district_id_corroboration(self):
        self.assertEqual(choose_match(target(), [source()])[1], "matched")
        self.assertEqual(choose_match(target(), [source(SchName="Different Elementary")])[1], "review_needed")
        self.assertEqual(choose_match(target(), [source(NCESDistrictID="9999999")])[1], "review_needed")

    def test_name_and_district_alone_do_not_join(self):
        self.assertEqual(choose_match(target(grade_context_nces_candidate=""), [source()])[1], "review_needed")

    def test_multiple_corroborated_ids_remain_ambiguous(self):
        t = target(grade_context_nces_candidate="062271000001 | 062271000002")
        self.assertEqual(choose_match(t, [source(), source(NCESSchoolID="62271000002")])[1], "ambiguous")

    def test_reviews_are_year_specific(self):
        reviews = {("research-school", "2021-22"): dict(nces_school_id="062271000001", evidence="reviewed source")}
        self.assertEqual(choose_match(target(grade_context_nces_candidate=""), [source()], reviews)[1], "review_needed")

    def test_leading_zero_restoration_does_not_change_native_id(self):
        row = source()
        self.assertEqual(nces_id(row["NCESSchoolID"]), "062271000001")
        self.assertEqual(row["NCESSchoolID"], "62271000001")
        self.assertEqual(unit_id(row), unit_id(source(NCESSchoolID="062271000001")))

    def test_same_reporting_unit_has_one_id_across_languages(self):
        self.assertEqual(unit_id(source()), unit_id(source(StudentSubGroup="White")))

    def test_short_elementary_label_does_not_link_to_same_named_middle_school(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            school = target(school_name="Example", school_level="elementary")
            write_csv(root / "data/baselines/national_structural_v1/schools.csv", [school], list(school))
            write_csv(root / "data/curated/registry/states.csv", [{"state_code": "CA", "state_fips": "06"}], ["state_code", "state_fips"])
            write_csv(root / "data/curated/registry/identifier_crosswalk.csv", [], ["entity_type", "entity_id", "namespace"])
            write_csv(root / "data/curated/sources/evidence_claims.csv", [], ["entity_type", "entity_id", "attribute", "reported_value"])
            raw = root / "data/raw/ccd_example.json"
            raw.parent.mkdir(parents=True)
            raw.write_text(json.dumps({"results": [
                {"year": 2024, "fips": 6, "ncessch": "062271000001", "school_name": "Example Elementary", "lea_name": "Los Angeles Unified"},
                {"year": 2024, "fips": 6, "ncessch": "062271000002", "school_name": "Example Middle", "lea_name": "Los Angeles Unified"},
            ]}))
            enriched = target_rows(root)[0]
            self.assertEqual(choose_match(enriched, [source()])[1], "matched")
            self.assertNotEqual(choose_match(enriched, [source(NCESSchoolID="62271000002", SchName="Example Middle")])[1], "matched")


class EDCTransfer(unittest.TestCase):
    def test_small_download_flushes_before_server_hash_verification(self):
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(source()), lineterminator="\n")
        writer.writeheader()
        writer.writerow(source())
        payload = buffer.getvalue().encode()
        class Response(io.BytesIO):
            headers = {"ETag": '"' + hashlib.md5(payload).hexdigest() + '"', "Content-Length": str(len(payload))}
            url = "https://storage.googleapis.com/public-test.csv"
        with tempfile.TemporaryDirectory() as directory, patch("dl_outcomes.collectors.edc.urlopen", return_value=Response(payload)):
            receipt = fetch_file(Path(directory), "CA", 2024)
            self.assertTrue(receipt["server_md5_verified"])
            self.assertEqual((Path(directory) / "CA_2024.csv").read_bytes(), payload)

    def test_gzip_receipts_are_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / x for x in ["a.csv.gz", "b.csv.gz"]]
            for path in paths:
                with gzip_csv(path, ["raw"]) as writer:
                    writer.writerow(dict(raw="*"))
            self.assertEqual(paths[0].read_bytes(), paths[1].read_bytes())


if __name__ == "__main__":
    unittest.main()
