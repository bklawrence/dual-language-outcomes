
#!/usr/bin/env python3
"""Normalize Washington's downloaded dual-language report-card rows.

Input: output/washington/wa_dual_language_source_rows.csv
Output: Spanish DL school-year registry candidates, one row per school,
        model-change audit, and quality-control JSON.

Does NOT update curated registry CSVs or infer cohort histories.
Standard library only.
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://data.wa.gov/d/d4w4-82bk"
ALLOWED_MODELS = {"50-50", "80-20", "90-10", "70-30"}


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def normalize_model(value):
    text = value.strip().replace(" ", "")
    return {"50/50": "50-50"}.get(text, text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(
            "output/washington/"
            "wa_dual_language_source_rows.csv"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/washington")
    )
    args = parser.parse_args()
    args.output.mkdir(
        parents=True, exist_ok=True
    )

    with args.source.open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        source = list(csv.DictReader(handle))

    if not source:
        raise RuntimeError(
            "Washington raw source is empty"
        )

    required = {
        "organizationlevel",
        "schoolyear",
        "schoolorganizationid",
        "schoolname",
        "leaname",
        "instructionallanguage",
        "programdesigntype",
        "programdesign",
        "programmodel",
        "rowid",
        "programschoolorganizationid",
    }

    missing = sorted(
        required - source[0].keys()
    )

    if missing:
        raise RuntimeError(
            f"Washington source schema missing: {missing}"
        )

    school_rows = [
        r for r in source
        if r["organizationlevel"].strip().lower()
        == "school"
    ]

    dl_rows = [
        r for r in school_rows
        if r["programdesigntype"].strip().lower()
        == "dual language program"
    ]

    spanish_rows = [
        r for r in dl_rows
        if r["instructionallanguage"].strip().lower()
        == "spanish"
    ]

    errors = []
    grouped = defaultdict(list)

    for r in spanish_rows:
        state_id = r[
            "schoolorganizationid"
        ].strip()

        site_id = r[
            "programschoolorganizationid"
        ].strip()

        year = r["schoolyear"].strip()

        if (
            not state_id
            or not year
            or not r["schoolname"].strip()
        ):
            errors.append({
                "rowid": r["rowid"],
                "issue": "missing_school_identity",
            })
            continue

        if site_id and site_id != state_id:
            errors.append({
                "rowid": r["rowid"],
                "issue": "program_school_id_mismatch",
            })
            continue

        grouped[(state_id, year)].append(r)

    if errors:
        (
            args.output /
            "wa_normalization_errors.json"
        ).write_text(
            json.dumps(errors, indent=2),
            encoding="utf-8"
        )

        raise RuntimeError(
            f"{len(errors)} source identity errors; "
            "see audit"
        )

    if not grouped:
        raise RuntimeError(
            "No Spanish DL school-year records "
            "were identified"
        )

    school_years = []

    for (state_id, year), rows in sorted(
        grouped.items(),
        key=lambda x: (
            x[0][1],
            x[0][0]
        )
    ):
        labels = sorted({
            normalize_model(r["programmodel"])
            for r in rows
        })

        raw_labels = sorted({
            r["programmodel"].strip()
            for r in rows
        })

        designs = sorted({
            r["programdesign"].strip()
            for r in rows
        })

        districts = sorted({
            r["leaname"].strip()
            for r in rows
        })

        names = sorted({
            r["schoolname"].strip()
            for r in rows
        })

        unknown = [
            m for m in labels
            if m not in ALLOWED_MODELS
        ]

        flags = []

        if len(labels) > 1:
            flags.append(
                "multiple_models_same_year"
            )

        if len(designs) > 1:
            flags.append(
                "multiple_program_designs"
            )

        if (
            len(districts) > 1
            or len(names) > 1
        ):
            flags.append(
                "identity_label_conflict"
            )

        if unknown:
            flags.append(
                "unrecognized_model"
            )

        school_years.append({
            "school_id": f"WA-S{state_id}",
            "state_school_id": state_id,
            "state": "WA",
            "school_year": year,
            "school_name": names[0],
            "district_name": districts[0],
            "instructional_language": "Spanish",
            "english_partner_language": "English",
            "reported_models": " | ".join(labels),
            "reported_model_labels_raw":
                " | ".join(raw_labels),
            "program_designs":
                " | ".join(designs),
            "program_design_count": len(designs),
            "source_rows": len(rows),
            "source_row_ids": " | ".join(
                sorted({
                    r["rowid"].strip()
                    for r in rows
                })
            ),
            "data_as_of": " | ".join(
                sorted({
                    r.get("dataasof", "").strip()
                    for r in rows
                })
            ),
            "review_flags": " | ".join(flags),
            "verification_status":
                "state_reported_program_metadata",
            "source_url": SOURCE_URL,
        })

    per_school = defaultdict(list)

    for r in school_years:
        per_school[
            r["state_school_id"]
        ].append(r)

    schools = []
    changes = []

    for sid, history in sorted(
        per_school.items()
    ):
        history.sort(
            key=lambda r: r["school_year"]
        )

        last = history[-1]

        distinct_models = sorted({
            m
            for r in history
            for m in r[
                "reported_models"
            ].split(" | ")
            if m
        })

        distinct_designs = sorted({
            d
            for r in history
            for d in r[
                "program_designs"
            ].split(" | ")
            if d
        })

        flags = []

        if len(distinct_models) > 1:
            flags.append(
                "reported_model_varies_by_year"
            )

        if any(
            r["review_flags"]
            for r in history
        ):
            flags.append(
                "school_year_record_requires_review"
            )

        record = {
            "school_id": f"WA-S{sid}",
            "state_school_id": sid,
            "state": "WA",
            "school_name_latest":
                last["school_name"],
            "district_latest":
                last["district_name"],
            "first_observed_school_year":
                history[0]["school_year"],
            "last_observed_school_year":
                last["school_year"],
            "years_observed":
                len(history),
            "latest_reported_model":
                last["reported_models"],
            "models_reported_any_year":
                " | ".join(distinct_models),
            "designs_reported_any_year":
                " | ".join(distinct_designs),
            "model_by_year": " | ".join(
                f'{r["school_year"]}:'
                f'{r["reported_models"]}'
                for r in history
            ),
            "review_flags": " | ".join(flags),
            "verification_status":
                "state_reported_program_metadata",
            "source_url": SOURCE_URL,
        }

        schools.append(record)

        if len(distinct_models) > 1:
            changes.append(record)

    write_csv(
        args.output /
        "wa_spanish_dl_school_years.csv",
        school_years,
        list(school_years[0])
    )

    write_csv(
        args.output /
        "wa_spanish_dl_schools.csv",
        schools,
        list(schools[0])
    )

    write_csv(
        args.output /
        "wa_model_change_candidates.csv",
        changes,
        list(schools[0])
    )

    by_year = {}

    for year in sorted({
        r["school_year"]
        for r in school_years
    }):
        subset = [
            r for r in school_years
            if r["school_year"] == year
        ]

        counts = Counter(
            r["reported_models"]
            for r in subset
        )

        by_year[year] = {
            "spanish_dl_schools":
                len(subset),
            "models":
                dict(sorted(counts.items())),
        }

    report = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "source_url": SOURCE_URL,
        "source_rows": len(source),
        "school_level_rows":
            len(school_rows),
        "dual_language_school_rows_all_languages":
            len(dl_rows),
        "spanish_dual_language_source_rows":
            len(spanish_rows),
        "distinct_spanish_dl_schools":
            len(schools),
        "distinct_spanish_dl_school_years":
            len(school_years),
        "distinct_districts_latest": len({
            r["district_latest"]
            for r in schools
        }),
        "multiple_program_design_school_years":
            sum(
                "multiple_program_designs"
                in r["review_flags"]
                for r in school_years
            ),
        "model_change_candidates":
            len(changes),
        "by_year": by_year,
        "limitations": [
            "Source program model is a school-year "
            "program label, not a measured "
            "grade-by-grade allocation.",
            "Changes between annual labels do not "
            "establish cohort transition dates.",
            "Schoolwide assessment results are not "
            "DL participant outcomes.",
            "State program metadata are not "
            "independently verified classroom observations.",
            "Do not import these rows over curated "
            "registry records without review.",
        ],
    }

    (
        args.output /
        "wa_normalization_report.json"
    ).write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "spanish_dl_schools": len(schools),
                "school_years": len(school_years),
                "model_changes": len(changes),
                "by_year": by_year,
            },
            indent=2
        )
    )


if __name__ == "__main__":
    main()
