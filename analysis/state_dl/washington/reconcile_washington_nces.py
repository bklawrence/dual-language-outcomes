
#!/usr/bin/env python3
"""Apply two independently verified WA-NCES reconciliation decisions.

Run after analysis/state_dl/washington/match_washington_nces.py.

Input:
  output/washington/nces/wa_nces_school_crosswalk.csv
  output/washington/nces/wa_all_program_observations_with_nces.csv

Output:
  output/washington/nces/reconciled/*

Preserves original files; fails rather than silently overriding
unexpected data.
"""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


# Official NCES identifiers and documented school-name evidence.
DECISIONS = {
    "103208": {
        "name": "East Valley High School",
        "district": "East Valley School District (Yakima)",
        "nces": "530537000805",
        "lea": "5305370",
        "status": "reconciled_district_disambiguation",
        "method": "manual_verified_district_disambiguation",
        "nces_2024_25_name": "East Valley High School",
        "note": (
            "Separate from East Valley High School in the Spokane "
            "district; Yakima district 5305370."
        ),
        "evidence": (
            "https://nces.ed.gov/ccd/districtsearch/"
            "district_detail.asp?DistrictID=5305370"
            "&ID2=5305370&Search=2&details="
        ),
    },
    "100527": {
        "name": "Edgewood Elementary School",
        "district": "Vancouver School District",
        "nces": "530927001564",
        "lea": "5309270",
        "status": "reconciled_historical_school_alias",
        "method": "manual_verified_school_rename",
        "nces_2024_25_name": "Harney Elementary School",
        "note": (
            "Formerly Harney Elementary; Vancouver district "
            "renamed it Edgewood in April 2025."
        ),
        "evidence": "https://edgewood.vansd.org/about/",
    },
}


def load(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError(f"No CSV headers: {path}")

        return list(reader), list(reader.fieldnames)


def write(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--base",
        type=Path,
        default=Path("output/washington"),
    )

    args = parser.parse_args()

    nces_dir = args.base / "nces"

    crosswalk_path = (
        nces_dir / "wa_nces_school_crosswalk.csv"
    )

    programs_path = (
        nces_dir / "wa_all_program_observations_with_nces.csv"
    )

    out = nces_dir / "reconciled"

    schools, school_fields = load(crosswalk_path)
    observations, obs_fields = load(programs_path)

    if len(schools) != 177 or len(observations) != 510:
        raise ValueError(
            f"Unexpected input sizes: {len(schools)} schools, "
            f"{len(observations)} observations"
        )

    by_state = {
        r["state_school_id"]: r
        for r in schools
    }

    if len(by_state) != len(schools):
        raise ValueError(
            "Duplicate state school identifiers"
        )

    # Verify each manual decision against the input identity.
    for sid, decision in DECISIONS.items():
        row = by_state.get(sid)

        if (
            row is None
            or row["school_name"] != decision["name"]
            or row["district_name"] != decision["district"]
        ):
            raise ValueError(
                f"Unexpected source identity for {sid}: {row}"
            )

        if (
            row["nces_school_id"]
            and row["nces_school_id"] != decision["nces"]
        ):
            raise ValueError(
                f"Conflicting pre-existing NCES ID for {sid}"
            )

        if (
            row["nces_lea_id"]
            and row["nces_lea_id"] != decision["lea"]
        ):
            raise ValueError(
                f"Conflicting pre-existing LEA ID for {sid}"
            )

    audit = []

    added_fields = [
        "nces_2024_25_school_name",
        "reconciliation_note",
        "reconciliation_evidence_url",
        "previous_suggested_nces_school_id",
    ]

    # Apply verified school identity corrections.
    for row in schools:
        for field in added_fields:
            if field in row:
                raise ValueError(
                    f"Unexpected input column {field}"
                )
            row[field] = ""

        sid = row["state_school_id"]

        if sid not in DECISIONS:
            continue

        decision = DECISIONS[sid]

        before = {
            k: row[k]
            for k in (
                "nces_school_id",
                "match_status",
                "suggested_nces_school_id",
            )
        }

        row["nces_school_id"] = decision["nces"]
        row["nces_lea_id"] = decision["lea"]
        row["match_status"] = decision["status"]
        row["verification_method"] = decision["method"]

        row["nces_2024_25_school_name"] = (
            decision["nces_2024_25_name"]
        )

        row["reconciliation_note"] = decision["note"]

        row["reconciliation_evidence_url"] = (
            decision["evidence"]
        )

        row["previous_suggested_nces_school_id"] = (
            before["suggested_nces_school_id"]
        )

        # Retire the earlier fuzzy suggestion.
        row["suggested_nces_school_id"] = ""
        row["suggested_nces_school_name"] = ""
        row["suggested_nces_district"] = ""

        audit.append({
            "state_school_id": sid,
            "school_name": row["school_name"],
            "district_name": row["district_name"],
            "previous_match_status":
                before["match_status"],
            "previous_suggested_nces_school_id":
                before["suggested_nces_school_id"],
            "assigned_nces_school_id":
                decision["nces"],
            "assigned_nces_lea_id":
                decision["lea"],
            "nces_2024_25_school_name":
                decision["nces_2024_25_name"],
            "reconciliation_status":
                decision["status"],
            "evidence_url":
                decision["evidence"],
            "notes":
                decision["note"],
        })

    # Validate the final crosswalk.
    ids = [
        row["nces_school_id"]
        for row in schools
    ]

    if any(
        not school_id
        or len(school_id) != 12
        or not school_id.isdigit()
        for school_id in ids
    ):
        raise ValueError(
            "Empty or invalid NCES school IDs remain"
        )

    if len(set(ids)) != len(ids):
        duplicates = [
            school_id
            for school_id, n in Counter(ids).items()
            if n > 1
        ]
        raise ValueError(
            f"NCES school ID collision: {duplicates}"
        )

    if any(
        row["nces_school_id"][:7] != row["nces_lea_id"]
        for row in schools
    ):
        raise ValueError(
            "NCES district prefix mismatch"
        )

    # Update program observations without losing records.
    seen = set()

    for obs in observations:
        sid = obs["state_school_id"]

        if sid not in by_state:
            raise ValueError(
                f"Unknown school ID in program records: {sid}"
            )

        key = (
            sid,
            obs["school_year"],
            obs["instructional_language"],
        )

        if key in seen:
            raise ValueError(
                f"Duplicate program-language-year observation: {key}"
            )

        seen.add(key)

        matched = by_state[sid]

        if (
            sid in DECISIONS
            and obs["nces_school_id"]
            not in ("", matched["nces_school_id"])
        ):
            raise ValueError(
                f"Conflicting program NCES ID: {sid}"
            )

        if (
            sid not in DECISIONS
            and obs["nces_school_id"]
            != matched["nces_school_id"]
        ):
            raise ValueError(
                f"Mismatch between school and program NCES ID: {sid}"
            )

        obs["nces_school_id"] = (
            matched["nces_school_id"]
        )

        obs["nces_match_status"] = (
            matched["match_status"]
        )

    # Write new reconciled files.
    school_file = (
        out / "wa_nces_school_crosswalk_reconciled.csv"
    )

    observation_file = (
        out / "wa_all_program_observations_with_nces_reconciled.csv"
    )

    audit_file = (
        out / "wa_nces_reconciliation_audit.csv"
    )

    write(
        school_file,
        schools,
        school_fields + added_fields,
    )

    write(
        observation_file,
        observations,
        obs_fields,
    )

    write(
        audit_file,
        audit,
        list(audit[0]),
    )

    summary = {
        "nces_reference_year": "2024-25",
        "washington_schools": len(schools),
        "matched_schools": sum(
            bool(r["nces_school_id"])
            for r in schools
        ),
        "distinct_nces_school_ids": len(set(ids)),
        "program_language_year_observations":
            len(observations),
        "program_observations_with_nces": sum(
            bool(r["nces_school_id"])
            for r in observations
        ),
        "manual_reconciliations_applied": len(audit),
        "match_status_counts": dict(
            Counter(
                r["match_status"]
                for r in schools
            )
        ),
        "source_sha256": {
            crosswalk_path.name: sha256(crosswalk_path),
            programs_path.name: sha256(programs_path),
        },
        "source_files_unchanged": True,
        "caveat": (
            "School identity matches do not verify DLI "
            "enrollment, strand vs whole school, "
            "or cohort instructional model."
        ),
    }

    summary_file = (
        out / "wa_nces_reconciliation_summary.json"
    )

    summary_file.write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
