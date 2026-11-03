
#!/usr/bin/env python3
"""Validate the Texas Pass 48 research checkpoint.

Run from repository root:
    python3 scripts/validate_texas_pass48.py
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import sys


DATA = Path("data/registry/texas")
TRACK = "texas_language_program_tracks_pass48.csv"
ALLOC = "texas_k_allocation_evidence_pass48.csv"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(data: bytes) -> bytes:
    """Normalize line endings and trailing newlines."""
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data.rstrip(b"\n") + b"\n"


def csv_rows(path: Path):
    with path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        reader = csv.DictReader(f)

        if (
            not reader.fieldnames
            or len(reader.fieldnames) != len(set(reader.fieldnames))
        ):
            raise ValueError(
                f"Invalid or duplicate CSV headers: {path}"
            )

        return list(reader)


def validate(root: Path):
    d = root / DATA

    manifest_path = d / "manifest_pass48.json"
    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    problems = []

    # Check files and verify CSV content.
    # Markdown files must exist, but their hashes are
    # not enforced because GitHub editing can change
    # whitespace and formatting.

    for rel, meta in manifest["files"].items():
        target = root / rel

        if not target.is_file():
            problems.append(f"Missing file: {rel}")
            continue

        if target.suffix.lower() == ".csv":
            data = target.read_bytes()

            actual = digest(canonical_bytes(data))
            expected = meta["sha256_canonical_text"]

            if actual != expected:
                problems.append(
                    f"CSV checksum mismatch: {rel}"
                )

    if problems:
        raise ValueError("\n".join(problems))

    tracks = csv_rows(d / TRACK)
    allocations = csv_rows(d / ALLOC)

    track_index = {}
    groups = collections.defaultdict(list)

    # Validate language tracks.

    for lineno, row in enumerate(tracks, 2):
        tid = row["language_track_id"]
        rid = row["registry_record_id"]

        if not tid or tid in track_index:
            problems.append(
                f"Track row {lineno}: blank/duplicate track ID"
            )
        else:
            track_index[tid] = row

        if (
            not rid
            or row["campus_id"] != rid.split(":", 1)[0]
        ):
            problems.append(
                f"Track row {lineno}: invalid parent/campus ID"
            )

        if row["TAPR_program_group"] not in {
            "one_way", "two_way"
        }:
            problems.append(
                f"Track row {lineno}: invalid TAPR group"
            )

        if (
            row["language_pair"] == "UNVERIFIED"
            and row["language_evidence_level"]
            != "unverified_default"
        ):
            problems.append(
                f"Track row {lineno}: unverified language "
                "not flagged correctly"
            )

        if (
            row["track_identity_status"]
            != "PROVISIONAL_LANGUAGE_TRACK_NOT_STABLE_PROGRAM_ID"
        ):
            problems.append(
                f"Track row {lineno}: claims stable program ID"
            )

        groups[rid].append(row)

    # Multiple language tracks within one reporting
    # group are allowed, but IDs must be distinct.

    for rid, siblings in groups.items():
        ids = {
            r["language_track_id"]
            for r in siblings
        }

        if len(ids) != len(siblings):
            problems.append(
                f"Duplicate track ID within TAPR group {rid}"
            )

    # Validate historical kindergarten allocations.

    allocation_ids = set()
    linked = 0
    unlinked = 0

    for lineno, row in enumerate(allocations, 2):
        aid = row["allocation_record_id"]
        rid = row["registry_record_id"]

        if not aid or aid in allocation_ids:
            problems.append(
                f"Allocation row {lineno}: "
                "blank/duplicate allocation ID"
            )

        allocation_ids.add(aid)

        if rid not in groups:
            problems.append(
                f"Allocation row {lineno}: "
                "unknown reporting group"
            )
        elif (
            row["campus_id"]
            != groups[rid][0]["campus_id"]
        ):
            problems.append(
                f"Allocation row {lineno}: campus mismatch"
            )

        if row["TAPR_program_group"] not in {
            "one_way", "two_way"
        }:
            problems.append(
                f"Allocation row {lineno}: invalid TAPR group"
            )

        if row["grade"] != "K":
            problems.append(
                f"Allocation row {lineno}: "
                "unexpected grade"
            )

        if (
            row["verified_tested_cohort_exposure"]
            .casefold() == "yes"
        ):
            problems.append(
                f"Allocation row {lineno}: "
                "unverified cohort exposure"
            )

        tid = row["language_track_id_if_unambiguous"]

        if tid:
            linked += 1

            if tid not in track_index:
                problems.append(
                    f"Allocation row {lineno}: unknown track"
                )

            elif (
                track_index[tid]["registry_record_id"]
                != rid
            ):
                problems.append(
                    f"Allocation row {lineno}: "
                    "track belongs to another reporting group"
                )

            elif (
                track_index[tid]["language_pair"]
                == "UNVERIFIED"
            ):
                problems.append(
                    f"Allocation row {lineno}: "
                    "linked to unverified language"
                )

        else:
            unlinked += 1

            if (
                row["partner_language_attribution"]
                != "REQUIRES_REVIEW"
            ):
                problems.append(
                    f"Allocation row {lineno}: "
                    "unresolved language not flagged"
                )

    # Calculate summary statistics.

    result = {
        "campuses": len({
            r["campus_id"] for r in tracks
        }),
        "registry_groups": len(groups),
        "language_tracks": len(tracks),
        "reporting_groups_with_multiple_tracks": sum(
            len(v) > 1 for v in groups.values()
        ),
        "unverified_language_tracks": sum(
            r["language_pair"] == "UNVERIFIED"
            for r in tracks
        ),
        "allocation_observations": len(allocations),
        "allocations_linked_to_track": linked,
        "allocations_without_unambiguous_track_link": unlinked,
        "verified_tested_cohort_exposures": sum(
            r["verified_tested_cohort_exposure"]
            .casefold() == "yes"
            for r in allocations
        ),
    }

    # Compare against the Pass 48 manifest.

    for key, expected in manifest[
        "expected_counts"
    ].items():
        actual = result.get(key)

        if actual != expected:
            problems.append(
                f"Unexpected {key}: "
                f"{actual} (expected {expected})"
            )

    if problems:
        raise ValueError("\n".join(problems))

    return result


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )

    args = parser.parse_args()

    try:
        results = validate(args.root.resolve())

    except (
        OSError,
        KeyError,
        ValueError,
        csv.Error,
    ) as err:
        print(f"FAIL: {err}", file=sys.stderr)
        return 1

    print(
        "PASS: Texas Pass 48 snapshot "
        "and linkage checks"
    )
    print(json.dumps(results, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
