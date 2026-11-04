"""Behavioral regression tests for language attribution, not just snapshot counts."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("texas50_validate", ROOT / "scripts/validate_texas_language_audit_pass50.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
build_spec = importlib.util.spec_from_file_location("texas50_build", ROOT / "scripts/build_texas_language_audit_pass50.py")
build = importlib.util.module_from_spec(build_spec)
build_spec.loader.exec_module(build)


class TexasLanguageAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = ROOT / "data/registry/texas"
        cls.tracks = audit.read_csv(data / "texas_language_program_tracks_pass50.csv")
        cls.allocations = audit.read_csv(data / "texas_k_allocation_evidence_pass50.csv")
        cls.prior = audit.read_csv(ROOT / "data/registry/texas_language_program_tracks_pass49_provisional.csv")
        cls.sources = {r["source_id"]: r for r in audit.read_csv(data / "pass50/source_register.csv")}

    def errors(self, tracks=None, allocations=None):
        return audit.check_rows(tracks if tracks is not None else self.tracks, allocations if allocations is not None else self.allocations, self.prior, self.sources)

    def test_complete_audit_is_valid(self):
        self.assertEqual(self.errors(), [])

    def test_unknown_pair_cannot_default_to_spanish(self):
        rows = copy.deepcopy(self.tracks)
        row = next(r for r in rows if r["language_pair"] == "UNVERIFIED")
        row["partner_language"] = "Spanish"
        self.assertTrue(any("silently assigned" in e for e in self.errors(rows)))

    def test_district_spanish_policy_cannot_fill_an_unknown_campus(self):
        row = copy.deepcopy(next(r for r in self.prior if r["language_pair"] == "UNVERIFIED"))
        row["district"] = "DALLAS ISD"
        rules = {"DALLAS ISD": {"district": "DALLAS ISD", "language_pair": "Spanish–English", "source_id": "tx50_policy_dallas_isd", "scope": "district_model", "note": ""}}
        result = build.make_tracks([row], {}, rules, self.sources, [])
        self.assertEqual(result[0]["language_pair"], "UNVERIFIED")
        self.assertEqual(result[0]["language_pair_verified_in_source"], "NO")

    def test_missing_french_track_is_rejected(self):
        rows = [r for r in self.tracks if not (r["campus_id"] == "220901166" and r["language_pair"] == "French–English")]
        self.assertTrue(any("Collapsed or incorrect" in e for e in self.errors(rows)))

    def test_mandarin_elective_cannot_replace_mesita_core_pair(self):
        rows = copy.deepcopy(self.tracks)
        row = next(r for r in rows if r["campus_id"] == "071902130")
        row.update(language_pair="Mandarin–English", partner_language="Mandarin", instruction_languages="English;Mandarin")
        self.assertTrue(any("Third-language course" in e for e in self.errors(rows)))

    def test_later_wooten_evidence_cannot_be_backdated(self):
        rows = copy.deepcopy(self.tracks)
        row = next(r for r in rows if r["campus_id"] == "227901144")
        row["campus_specific_2023_24_roster_confirmed"] = "YES"
        self.assertTrue(any("Backdated" in e for e in self.errors(rows)))

    def test_french_track_cannot_inherit_combined_campus_policy_link(self):
        rows = copy.deepcopy(self.allocations)
        row = next(r for r in rows if r["campus_id"] == "220901166")
        row["language_track_id_if_unambiguous"] = next(r["language_track_id"] for r in self.tracks if r["campus_id"] == "220901166" and r["partner_language"] == "French")
        self.assertTrue(any("Ambiguous or changed-language" in e for e in self.errors(allocations=rows)))

    def test_language_evidence_cannot_create_language_specific_outcome(self):
        rows = copy.deepcopy(self.tracks)
        rows[0]["language_specific_2023_24_TAPR_result_available"] = "YES"
        self.assertTrue(any("Unsupported language-specific outcome" in e for e in self.errors(rows)))


if __name__ == "__main__":
    unittest.main()
