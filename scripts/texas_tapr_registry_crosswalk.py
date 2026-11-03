
#!/usr/bin/env python3
"""Join Texas historical program records to statewide TAPR by campus ID.

This is a campus/program crosswalk, NOT a kindergarten-cohort
outcome join. DQ and DT do not identify kindergarten allocations.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data/registry/texas"
RESULTS = ROOT / "results/texas/tapr_public"

CROSSWALK_COLS = [
    "registry_record_id", "campus_id", "district", "campus",
    "registry_source", "entry_year", "tested_year",
    "tested_grade", "kindergarten_ratio",
    "kindergarten_policy_status", "historical_program_type",
    "program_code_expected", "tapr_campus_match",
    "tapr_campus", "tapr_district",
    "tapr_two_way_numeric_cells",
    "tapr_one_way_numeric_cells",
    "tapr_trans_early_numeric_cells",
    "tapr_trans_late_numeric_cells",
    "tapr_named_program_outcome_present",
    "kindergarten_cohort_outcome_join",
    "linkage_scope", "policy_source_url",
]

AUDIT_COLS = [
    "registry_record_id", "campus_id", "kindergarten_ratio",
    "entry_year", "historical_program_type",
    "observed_tapr_program_code", "subject",
    "tests_numeric", "meets_n_numeric", "meets_pct_numeric",
    "comparison_eligible_for_review",
    "evidence_scope", "caution",
]


def campus_id(value):
    value = str(value or "").strip().lstrip("'")
    if value.endswith(".0"):
        value = value[:-2]
    return (
        value.zfill(9)
        if re.fullmatch(r"\d{1,9}", value)
        else ""
    )


def read_csv(path):
    with path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows, headers):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(
        "w", encoding="utf-8", newline=""
    ) as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=headers,
            extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def choose_registry(explicit):
    if explicit:
        if not explicit.is_file():
            raise FileNotFoundError(explicit)
        return explicit, "requested_registry"

    master = BASE / "texas_master_pass44.csv"

    if master.is_file():
        return master, "statewide_historical_master"

    pilot = BASE / "tapr_pilot_join_pass45.csv"

    if pilot.is_file():
        return pilot, "134_row_historical_pilot_ONLY"

    raise FileNotFoundError(
        "Neither Texas master nor historical pilot is present"
    )


def historic_program(row):
    value = (
        row.get("assessment_student_group")
        or row.get("program_type")
        or ""
    ).strip().lower()

    if value in {
        "two_way", "two-way", "two_way_dual_language"
    }:
        return "two_way", "DQ"

    if value in {
        "one_way", "one-way", "one_way_dual_language"
    }:
        return "one_way", "DT"

    return value or "UNKNOWN", ""


def metric_is_numeric(text):
    try:
        if text is None or str(text).strip() == "":
            return False
        return float(str(text).strip()) >= 0
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--registry",
        type=Path,
        default=None
    )

    parser.add_argument(
        "--campuses",
        type=Path,
        default=RESULTS / "statewide_campus_index.csv"
    )

    parser.add_argument(
        "--program-meets",
        type=Path,
        default=RESULTS / "statewide_program_meets.csv"
    )

    parser.add_argument(
        "--outdir",
        type=Path,
        default=RESULTS
    )

    args = parser.parse_args()

    registry_path, registry_scope = choose_registry(
        args.registry
    )

    for path in (args.campuses, args.program_meets):
        if not path.is_file():
            parser.error(
                f"Required statewide TAPR output missing: {path}"
            )

    historic = read_csv(registry_path)

    campuses = {
        campus_id(r.get("campus_id")): r
        for r in read_csv(args.campuses)
    }
    campuses.pop("", None)

    by_campus_program = defaultdict(list)

    for row in read_csv(args.program_meets):
        cid = campus_id(row.get("campus_id"))

        if (
            cid
            and row.get("program_code")
            in {"DQ", "DT", "DJ", "DK"}
        ):
            by_campus_program[
                (cid, row["program_code"])
            ].append(row)

    matches = []
    audit = []
    unmatched = {}

    ratios_by_campus = defaultdict(set)
    counts = Counter()

    distinct_registry = set()
    matched_campuses = set()
    numeric_program_campuses = set()

    for number, row in enumerate(historic, 1):
        cid = campus_id(
            row.get("campus_id")
            or row.get("texas_campus_id")
        )

        if not cid:
            counts[
                "records_without_valid_campus_id"
            ] += 1
            continue

        distinct_registry.add(cid)
        c = campuses.get(cid, {})

        if c:
            matched_campuses.add(cid)
        else:
            unmatched.setdefault(cid, row)

        ratio = (
            row.get("analysis_K_ratio")
            or row.get("K_ratio")
            or ""
        ).strip()

        if ratio in {
            "90/10", "80/20", "70/30", "50/50"
        }:
            ratios_by_campus[cid].add(ratio)

        historical_type, expected_code = (
            historic_program(row)
        )

        candidate = (
            by_campus_program.get(
                (cid, expected_code), []
            )
            if expected_code
            else []
        )

        valid_candidate = any(
            metric_is_numeric(
                x.get("meets_pct_numeric")
            )
            for x in candidate
        )

        if valid_candidate:
            numeric_program_campuses.add(cid)

        counts[
            "records_with_TAPR_campus_match"
            if c
            else "records_without_TAPR_campus_match"
        ] += 1

        if valid_candidate:
            counts[
                "records_with_same_named_program_outcomes"
            ] += 1

        if ratio:
            counts[
                f"historical_K_ratio_{ratio}"
            ] += 1

        rec_id = (
            row.get("record_id")
            or f"pilot_row_{number:04d}"
        )

        matches.append({
            "registry_record_id": rec_id,
            "campus_id": cid,
            "district": row.get("district", ""),
            "campus": row.get("campus", ""),
            "registry_source": registry_scope,
            "entry_year": row.get(
                "expected_k_entry_year", ""
            ),
            "tested_year": (
                row.get("tested_year")
                or row.get("assessment_year", "")
            ),
            "tested_grade": row.get(
                "tested_grade", ""
            ),
            "kindergarten_ratio": ratio,
            "kindergarten_policy_status": (
                row.get("analysis_K_ratio_status")
                or row.get("policy_status", "")
            ),
            "historical_program_type":
                historical_type,
            "program_code_expected":
                expected_code,
            "tapr_campus_match":
                "YES" if c else "NO",
            "tapr_campus": c.get(
                "campus", ""
            ),
            "tapr_district": c.get(
                "district", ""
            ),
            "tapr_two_way_numeric_cells": c.get(
                "two_way_numeric_cells", ""
            ),
            "tapr_one_way_numeric_cells": c.get(
                "one_way_numeric_cells", ""
            ),
            "tapr_trans_early_numeric_cells": c.get(
                "trans_early_numeric_cells", ""
            ),
            "tapr_trans_late_numeric_cells": c.get(
                "trans_late_numeric_cells", ""
            ),
            "tapr_named_program_outcome_present":
                "YES" if valid_candidate else "NO",
            "kindergarten_cohort_outcome_join":
                "NO",
            "linkage_scope": (
                "campus_and_named_program_only"
                if valid_candidate
                else "campus_only"
            ),
            "policy_source_url": (
                row.get("row_policy_source_url")
                or row.get("policy_source_url")
                or row.get("source_url", "")
            ),
        })

        for metric in candidate:
            audit.append({
                "registry_record_id": rec_id,
                "campus_id": cid,
                "kindergarten_ratio": ratio,
                "entry_year": row.get(
                    "expected_k_entry_year", ""
                ),
                "historical_program_type":
                    historical_type,
                "observed_tapr_program_code":
                    expected_code,
                "subject": metric.get(
                    "subject", ""
                ),
                "tests_numeric": metric.get(
                    "tests_numeric", ""
                ),
                "meets_n_numeric": metric.get(
                    "meets_n_numeric", ""
                ),
                "meets_pct_numeric": metric.get(
                    "meets_pct_numeric", ""
                ),
                "comparison_eligible_for_review":
                    metric.get(
                        "comparison_eligible_for_review",
                        ""
                    ),
                "evidence_scope": (
                    "2023-24 campus named-program "
                    "all-tested-grades"
                ),
                "caution": (
                    "NOT a K-entry cohort or "
                    "grade-specific program score"
                ),
            })

    out = args.outdir

    write_csv(
        out / "texas_registry_tapr_crosswalk.csv",
        matches,
        CROSSWALK_COLS
    )

    write_csv(
        out / "texas_registry_program_match_audit.csv",
        audit,
        AUDIT_COLS
    )

    write_csv(
        out / "texas_unmatched_registry_campuses.csv",
        [
            {
                "campus_id": campus_id(
                    r.get("campus_id")
                    or r.get("texas_campus_id")
                ),
                "district": r.get(
                    "district", ""
                ),
                "campus": r.get(
                    "campus", ""
                ),
            }
            for r in unmatched.values()
        ],
        ["campus_id", "district", "campus"]
    )

    summary = {
        "registry_file": str(registry_path),
        "registry_scope": registry_scope,
        "historical_records": len(historic),
        "distinct_historical_campuses":
            len(distinct_registry),
        "statewide_TAPR_campuses":
            len(campuses),
        "matched_distinct_historical_campuses":
            len(matched_campuses),
        "distinct_historical_campuses_with_same_named_program_numeric_meets":
            len(numeric_program_campuses),
        "campuses_with_multiple_historical_K_ratios":
            sum(
                len(v) > 1
                for v in ratios_by_campus.values()
            ),
        "counts": dict(
            sorted(counts.items())
        ),
        "confirmed_grade_specific_program_cohort_outcomes":
            0,
        "cautions": [
            "Campus ID match does not establish student participation.",
            "DQ/DT indicates program type, not starting kindergarten allocation.",
            "TAPR program scores aggregate tested grades and cannot be assigned to individual K-entry cohorts.",
            "Missing outcome cells do not establish program absence.",
        ],
    }

    out.mkdir(
        parents=True,
        exist_ok=True
    )

    (
        out / "texas_registry_tapr_summary.json"
    ).write_text(
        json.dumps(
            summary,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    print(
        json.dumps(
            summary,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
