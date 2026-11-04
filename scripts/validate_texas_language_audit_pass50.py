#!/usr/bin/env python3
"""Validate Pass 50 lineage, evidence scope, languages, dates and allocation links."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"Invalid CSV headers: {path}")
        return list(reader)


def check_rows(tracks, allocations, prior, sources):
    errors = []
    old = {r["language_track_id"]: r for r in prior}
    index = {}
    groups = collections.defaultdict(list)
    allowed_pairs = {"UNVERIFIED", "Spanish–English", "Mandarin–English", "Vietnamese–English", "French–English", "Arabic–English"}
    for row in tracks:
        tid = row["language_track_id"]
        if tid in index:
            errors.append(f"Duplicate track: {tid}")
        index[tid] = row
        groups[row["registry_record_id"]].append(row)
        if row["assessment_year"] != "2023-24":
            errors.append(f"Changed outcome year: {tid}")
        if row["campus_id"] != row["registry_record_id"].split(":")[0] or len(row["campus_id"]) != 9:
            errors.append(f"Invalid campus/parent: {tid}")
        if row["language_pair"] not in allowed_pairs:
            errors.append(f"Invalid/unparsed language pair: {tid}")
        if row["derived_from_language_track_id"] not in old:
            errors.append(f"Missing original lineage: {tid}")
        if row["previous_language_track_id"] and row["previous_language_pair"] != old[row["previous_language_track_id"]]["language_pair"]:
            errors.append(f"Altered previous label: {tid}")
        if row["language_pair"] == "UNVERIFIED":
            if row["language_pair_verified_in_source"] != "NO" or row["partner_language"] or row["instruction_languages"]:
                errors.append(f"Unknown pair silently assigned: {tid}")
        elif row["instruction_languages"] != "English;" + row["partner_language"]:
            errors.append(f"Language fields disagree: {tid}")
        ids = list(filter(None, row["audit_source_ids"].split(";")))
        if any(key not in sources for key in ids):
            errors.append(f"Unregistered source: {tid}")
        if row["language_pair_verified_in_source"] == "YES" and not ids:
            errors.append(f"Verified pair without evidence: {tid}")
        if row["language_pair_verified_in_source"] == "YES" and not any(key in sources and sources[key]["http_status"] == "200" and sources[key]["review_use"] == "USED_EVIDENCE_OR_REVIEW_CONTEXT" for key in ids):
            errors.append(f"Verified pair without retrieved reviewed source: {tid}")
        if row["language_specific_2023_24_TAPR_result_available"] != "NOT_ESTABLISHED" or row["outcome_attribution"] != "NOT_ESTABLISHED_DO_NOT_DISAGGREGATE":
            errors.append(f"Unsupported language-specific outcome: {tid}")
        if row["historical_2023_24_pair_status"] == "LATER_EVIDENCE_ONLY" and row["campus_specific_2023_24_roster_confirmed"] != "NO":
            errors.append(f"Backdated later source: {tid}")
        if row["track_identity_status"] != "PROVISIONAL_LANGUAGE_TRACK_NOT_STABLE_PROGRAM_ID" or row["study_scope"] != "multilingual_education":
            errors.append(f"Unsupported program identity or restricted language scope: {tid}")
    if set(groups) != {r["registry_record_id"] for r in prior}:
        errors.append("Original TAPR reporting groups lost or invented")
    if {r["campus_id"] for r in tracks} != {r["campus_id"] for r in prior}:
        errors.append("Original campus universe changed")
    previous_ids = [r["previous_language_track_id"] for r in tracks if r["previous_language_track_id"]]
    if set(previous_ids) != set(old) or len(previous_ids) != len(old):
        errors.append("Original language-track lineage lost or duplicated")
    for row in allocations:
        tid = row["language_track_id_if_unambiguous"]
        if row["verified_tested_cohort_exposure"] != "NO":
            errors.append("Unsupported tested-cohort exposure")
        if tid:
            linked = index.get(tid)
            if not linked or linked["registry_record_id"] != row["registry_record_id"]:
                errors.append(f"Invalid allocation link: {row['allocation_record_id']}")
            elif len(groups[row["registry_record_id"]]) != 1 or linked["language_pair"] == "UNVERIFIED" or linked["language_pair"] != linked["previous_language_pair"] or linked["language_pair_verified_in_source"] != "YES":
                errors.append(f"Ambiguous or changed-language policy link: {row['allocation_record_id']}")
    # Direct substantive guards for the errors this research pass addresses.
    expected = {"220901166": {"French–English", "Spanish–English"}, "057909147": {"Vietnamese–English", "Spanish–English"}, "101912483": {"French–English", "Spanish–English"}, "101912460": {"Mandarin–English"}, "101912478": {"Arabic–English"}, "227901138": {"Vietnamese–English"}}
    for campus, pairs in expected.items():
        if {r["language_pair"] for r in tracks if r["campus_id"] == campus} != pairs:
            errors.append(f"Collapsed or incorrect campus languages: {campus}")
    for campus in ("068901105", "071902130"):
        if {r["language_pair"] for r in tracks if r["campus_id"] == campus} != {"Spanish–English"}:
            errors.append(f"Third-language course substituted for core pair: {campus}")
    return errors


def validate(root=ROOT):
    data = root / "data/registry/texas"
    manifest = json.loads((data / "manifest_pass50.json").read_text())
    errors = []
    for section in ("files", "input_snapshots"):
        for rel, expected in manifest[section].items():
            path = root / rel
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                errors.append(f"Checksum mismatch or missing file: {rel}")
    tracks = read_csv(data / "texas_language_program_tracks_pass50.csv")
    allocations = read_csv(data / "texas_k_allocation_evidence_pass50.csv")
    prior = read_csv(root / "data/registry/texas_language_program_tracks_pass49_provisional.csv")
    sources = {r["source_id"]: r for r in read_csv(data / "pass50/source_register.csv")}
    errors.extend(check_rows(tracks, allocations, prior, sources))
    old_alloc = read_csv(data / "texas_k_allocation_evidence_pass48.csv")
    if {r["allocation_record_id"] for r in allocations} != {r["allocation_record_id"] for r in old_alloc} or len(allocations) != len(old_alloc):
        errors.append("Allocation observations lost, duplicated or invented")
    campus_table = read_csv(data / "texas_campus_language_inventory_pass50.csv")
    if len(campus_table) != len({r["campus_id"] for r in tracks}) or {r["campus_id"] for r in campus_table} != {r["campus_id"] for r in tracks}:
        errors.append("Campus view loses or duplicates campuses")
    for row, old_row in zip(allocations, old_alloc):
        for key in ("allocation_record_id", "allocation_label", "entry_school_year", "source_period", "source_url", "registry_record_id"):
            if row[key] != old_row[key]:
                errors.append(f"Altered historical allocation evidence: {row['allocation_record_id']} / {key}")
    pointer = json.loads((data / "current_inventory.json").read_text())
    if pointer["version"] != "pass50" or pointer["language_tracks"] != "data/registry/texas/texas_language_program_tracks_pass50.csv":
        errors.append("Current Texas pointer does not select the audited data")
    if errors:
        raise ValueError("\n".join(errors))
    return {"tracks": len(tracks), "reporting_groups": len({r['registry_record_id'] for r in tracks}), "campuses": len({r['campus_id'] for r in tracks}), "allocation_records": len(allocations), "status": "PASS"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(validate(args.root), indent=2))
