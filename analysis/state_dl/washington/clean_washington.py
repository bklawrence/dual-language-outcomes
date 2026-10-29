
#!/usr/bin/env python3
"""Audit Washington's Spanish dual-language registry.

Inputs are produced by collectors/normalize_washington.py.
Original source files are never modified.
"""

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

TWO = "Two-Way Dual Language Program"
ONE = "One-Way Dual Language Program"
WORLD = "World Language Immersion Program"

ALLOWED_MODELS = {
    "50-50", "80-20", "90-10", "70-30"
}

REQUIRED_YEAR = {
    "school_id", "state_school_id", "state",
    "school_year", "school_name", "district_name",
    "instructional_language", "reported_models",
    "program_designs", "source_rows", "source_row_ids",
    "review_flags", "verification_status", "source_url",
}

REQUIRED_SCHOOL = {
    "school_id", "state_school_id", "school_name_latest",
    "district_latest", "first_observed_school_year",
    "last_observed_school_year", "latest_reported_model",
}


def read(path, required):
    with open(
        path, encoding="utf-8-sig", newline=""
    ) as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []

        if len(fields) != len(set(fields)):
            raise ValueError(
                f"Repeated column header in {path}"
            )

        missing = required - set(fields)

        if missing:
            raise ValueError(
                f"Missing columns: {sorted(missing)}"
            )

        rows = list(reader)

    if not rows:
        raise ValueError(f"Empty source: {path}")

    return rows


def write(path, rows, fields):
    with open(
        path, "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def classify_design(value):
    labels = {
        v.strip()
        for v in value.split("|")
        if v.strip()
    }

    if labels == {TWO}:
        return "two_way_only"

    if labels == {ONE}:
        return "one_way_only"

    if labels == {TWO, ONE}:
        return "mixed_one_way_two_way"

    if labels == {WORLD}:
        return "world_language_immersion"

    return "review_other_design"


def clean_year(row):
    design = classify_design(
        row["program_designs"]
    )

    ratios = {
        x.strip()
        for x in row["reported_models"].split("|")
        if x.strip()
    }

    issues = []

    if (
        len(ratios) != 1
        or not ratios.issubset(ALLOWED_MODELS)
    ):
        issues.append("review_allocation_label")

    if design in {
        "mixed_one_way_two_way",
        "review_other_design",
    }:
        issues.append("review_population_model")

    return {
        "state": "WA",
        "state_school_id": row["state_school_id"],
        "school_id": row["school_id"],
        "school_year": row["school_year"],
        "school_name": row["school_name"],
        "district_name": row["district_name"],
        "reported_instructional_language":
            row["instructional_language"],
        "english_partner_language_reported": "",
        "instructional_allocation_label":
            row["reported_models"],
        "population_program_design": design,
        "source_program_design_labels":
            row["program_designs"],
        "program_structure": "unknown",
        "cohort_model_status": "not_verified",
        "study_group": (
            "two_way_candidate"
            if design == "two_way_only"
            else "not_in_strict_two_way_group"
        ),
        "source_rows": row["source_rows"],
        "source_row_ids": row["source_row_ids"],
        "source_review_flags": row["review_flags"],
        "cleanup_flags": " | ".join(issues),
        "source_url": row["source_url"],
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--school-years",
        type=Path,
        default=Path(
            "output/washington/"
            "wa_spanish_dl_school_years.csv"
        ),
    )

    parser.add_argument(
        "--schools",
        type=Path,
        default=Path(
            "output/washington/"
            "wa_spanish_dl_schools.csv"
        ),
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=Path(
            "output/washington/cleaned"
        ),
    )

    args = parser.parse_args()

    years = read(
        args.school_years, REQUIRED_YEAR
    )

    schools = read(
        args.schools, REQUIRED_SCHOOL
    )

    year_keys = set()
    by_id = defaultdict(list)

    for row in years:
        sid = row["state_school_id"].strip()
        yr = row["school_year"].strip()

        if (sid, yr) in year_keys:
            raise ValueError(
                f"Duplicate school-year: {sid} {yr}"
            )

        year_keys.add((sid, yr))

        if (
            not re.fullmatch(r"\d+", sid)
            or row["school_id"] != "WA-S" + sid
        ):
            raise ValueError(
                f"Invalid school ID: {sid}"
            )

        if (
            row["state"] != "WA"
            or row["instructional_language"] != "Spanish"
        ):
            raise ValueError(
                f"Unexpected state/language: {sid}"
            )

        if not re.fullmatch(
            r"20\d{2}-\d{2}", yr
        ):
            raise ValueError(
                f"Invalid school year: {yr}"
            )

        if (
            not row["school_name"].strip()
            or not row["district_name"].strip()
        ):
            raise ValueError(
                f"Missing school or district: {sid}"
            )

        by_id[sid].append(row)

    roster = {
        r["state_school_id"]: r
        for r in schools
    }

    if (
        len(roster) != len(schools)
        or set(roster) != set(by_id)
    ):
        raise ValueError(
            "School roster and school-year "
            "inventory have different IDs"
        )

    cleaned_years = [
        clean_year(r) for r in years
    ]

    cleaned_schools = []
    review_queue = []
    history_audit = []

    for sid, raw in sorted(by_id.items()):
        raw = sorted(
            raw,
            key=lambda r: r["school_year"]
        )

        ref = roster[sid]

        if (
            ref["last_observed_school_year"]
                != raw[-1]["school_year"]
            or ref["first_observed_school_year"]
                != raw[0]["school_year"]
            or ref["latest_reported_model"]
                != raw[-1]["reported_models"]
            or ref["school_name_latest"]
                != raw[-1]["school_name"]
            or ref["district_latest"]
                != raw[-1]["district_name"]
        ):
            raise ValueError(
                f"Roster/history mismatch: {sid}"
            )

        if (
            len({
                r["school_name"] for r in raw
            }) > 1
            or len({
                r["district_name"] for r in raw
            }) > 1
        ):
            raise ValueError(
                f"School name changed: {sid}"
            )

        models = [
            r["reported_models"] for r in raw
        ]

        designs = sorted({
            classify_design(r["program_designs"])
            for r in raw
        })

        changed = len(set(models)) > 1
        review = []

        if changed:
            review.append(
                "reported_allocation_changed;"
                "verify_cohort_exposure"
            )

        if "mixed_one_way_two_way" in designs:
            review.append(
                "one_way_and_two_way_at_same_school"
            )

        if "world_language_immersion" in designs:
            review.append(
                "verify_world_immersion_program_population"
            )

        if "review_other_design" in designs:
            review.append(
                "unclassified_program_design"
            )

        if any(
            len({
                p.strip()
                for p in r["reported_models"].split("|")
            }) != 1
            for r in raw
        ):
            review.append(
                "multiple_models_in_same_year"
            )

        history = " | ".join(
            f'{r["school_year"]}:{r["reported_models"]}'
            for r in raw
        )

        last_design = classify_design(
            raw[-1]["program_designs"]
        )

        cleaned_schools.append({
            "state": "WA",
            "school_id": ref["school_id"],
            "state_school_id": sid,
            "school_name":
                ref["school_name_latest"],
            "district_name":
                ref["district_latest"],
            "first_observed_school_year":
                raw[0]["school_year"],
            "last_observed_school_year":
                raw[-1]["school_year"],
            "years_observed": str(len(raw)),
            "reported_model_history": history,
            "latest_reported_model": models[-1],
            "latest_population_design": last_design,
            "historical_population_designs":
                " | ".join(designs),
            "model_change_reported":
                str(changed).lower(),
            "whole_school_or_strand": "unknown",
            "strict_two_way_every_observed_year":
                str(all(
                    classify_design(
                        r["program_designs"]
                    ) == "two_way_only"
                    for r in raw
                )).lower(),
            "review_reasons": " | ".join(review),
            "nces_school_id": "",
            "nces_match_status": "not_yet_matched",
            "source_url": raw[-1]["source_url"],
        })

        if review:
            review_queue.append({
                "state_school_id": sid,
                "school_name":
                    ref["school_name_latest"],
                "district_name":
                    ref["district_latest"],
                "model_history": history,
                "program_designs": " | ".join(
                    designs
                ),
                "review_reasons":
                    " | ".join(review),
            })

        for r in raw:
            history_audit.append({
                "state_school_id": sid,
                "school_name": r["school_name"],
                "school_year": r["school_year"],
                "model_label": r["reported_models"],
                "population_design": classify_design(
                    r["program_designs"]
                ),
                "model_changed_at_school":
                    str(changed).lower(),
                "source_row_ids":
                    r["source_row_ids"],
            })

    args.out.mkdir(
        parents=True,
        exist_ok=True
    )

    write(
        args.out / "wa_clean_school_years.csv",
        cleaned_years,
        list(cleaned_years[0]),
    )

    write(
        args.out / "wa_clean_schools.csv",
        cleaned_schools,
        list(cleaned_schools[0]),
    )

    write(
        args.out / "wa_review_queue.csv",
        review_queue,
        [
            "state_school_id",
            "school_name",
            "district_name",
            "model_history",
            "program_designs",
            "review_reasons",
        ],
    )

    write(
        args.out / "wa_model_history_audit.csv",
        history_audit,
        list(history_audit[0]),
    )

    by_year = {}

    for year in sorted({
        r["school_year"] for r in cleaned_years
    }):
        subset = [
            r for r in cleaned_years
            if r["school_year"] == year
        ]

        by_year[year] = dict(Counter(
            r["population_program_design"]
            for r in subset
        ))

    report = {
        "source_school_year_records": len(years),
        "distinct_spanish_dl_schools": len(schools),
        "duplicate_school_year_keys": 0,
        "schools_with_reported_model_changes":
            sum(
                r["model_change_reported"] == "true"
                for r in cleaned_schools
            ),
        "schools_with_manual_review_reason":
            len(review_queue),
        "program_design_by_year": by_year,
        "unverified_strand_or_whole_school":
            len(schools),
        "verified_nces_school_ids": 0,
        "cautions": [
            "English partner language is not "
            "explicitly reported in the input source.",
            "First observed year is not "
            "program establishment year.",
            "Model labels do not establish "
            "allocation by grade or cohort.",
            "One-way, mixed, and world immersion "
            "are not silently treated as two-way.",
            "No NCES IDs or whole-school "
            "participation proportions were inferred.",
        ],
    }

    (
        args.out / "wa_cleanup_summary.json"
    ).write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
