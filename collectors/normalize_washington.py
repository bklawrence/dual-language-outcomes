
#!/usr/bin/env python3
"""Normalize Washington's language-program data for all languages.

Input:
  output/washington/wa_dual_language_source_rows.csv

Outputs:
  wa_all_dl_programs.csv
  wa_all_dl_school_years.csv
  wa_all_dl_schools.csv
  wa_all_dl_model_change_candidates.csv
  wa_heritage_tribal_programs.csv
  wa_language_summary.csv
  wa_spanish_dl_school_years.csv
  wa_spanish_dl_schools.csv
  wa_model_change_candidates.csv
  wa_normalization_report.json

The program retains all instructional languages and preserves
heritage and tribal language programs separately.

It does not infer English as a partner language or construct
unverified cohort histories.

Only Python's standard library is required.
"""

import argparse
import csv
import json

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


SOURCE_URL = "https://data.wa.gov/d/d4w4-82bk"

KNOWN_MODELS = {
    "50-50",
    "70-30",
    "80-20",
    "90-10",
}

REQUIRED = {
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


def clean(value):
    """Treat the state's literal NULL as missing."""
    s = str(value or "").strip()

    if s.lower() in {"null", "none", "nan"}:
        return ""

    return s


def model(value):
    """Normalize equivalent instructional-model labels."""
    s = clean(value).replace(" ", "")

    if s == "50/50":
        return "50-50"

    return s


def join(values):
    return " | ".join(
        sorted({x for x in values if x})
    )


def save_csv(path, rows, fields):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def collect_records(source):
    dl = []
    related = []
    errors = []

    for row in source:
        if clean(
            row["organizationlevel"]
        ).lower() != "school":
            continue

        kind = clean(
            row["programdesigntype"]
        ).lower()

        if kind == "dual language program":
            category = "dual_language"

        elif kind == "heritage language program":
            category = "heritage_language"

        elif kind == "tribal language program":
            category = "tribal_language"

        else:
            errors.append({
                "rowid": clean(row["rowid"]),
                "issue": "unexpected_school_program_type",
                "value": kind,
            })
            continue

        sid = clean(
            row["schoolorganizationid"]
        )

        site = clean(
            row["programschoolorganizationid"]
        )

        year = clean(row["schoolyear"])
        school = clean(row["schoolname"])

        if not (sid and site and year and school):
            errors.append({
                "rowid": clean(row["rowid"]),
                "issue": "missing_school_identity",
            })
            continue

        if sid != site:
            errors.append({
                "rowid": clean(row["rowid"]),
                "issue": "school_program_id_mismatch",
                "school_id": sid,
                "program_site_id": site,
            })
            continue

        rec = {
            "state": "WA",
            "school_id": "WA-S" + sid,
            "state_school_id": sid,
            "school_year": year,
            "school_name": school,
            "district_name": clean(row["leaname"]),
            "instructional_language":
                clean(row["instructionallanguage"]),

            # The source does not explicitly identify
            # the second language in this table.
            "partner_language": "",
            "partner_language_status":
                "not_reported_in_source",

            "program_category": category,
            "program_design":
                clean(row["programdesign"]),
            "program_design_type_raw":
                clean(row["programdesigntype"]),
            "reported_model":
                model(row["programmodel"]),
            "reported_model_raw":
                clean(row["programmodel"]),
            "source_row_id":
                clean(row["rowid"]),
            "data_as_of":
                clean(row.get("dataasof")),
            "source_url": SOURCE_URL,
            "verification_status":
                "state_reported_program_metadata",
        }

        if category == "dual_language":
            dl.append(rec)
        else:
            related.append(rec)

    return dl, related, errors


def make_school_years(dl):
    """One row per school, school year, and language."""

    groups = defaultdict(list)

    for rec in dl:
        key = (
            rec["state_school_id"],
            rec["school_year"],
            rec["instructional_language"],
        )
        groups[key].append(rec)

    output = []

    for (sid, year, language), rows in sorted(
        groups.items()
    ):
        models = {
            r["reported_model"]
            for r in rows
            if r["reported_model"]
        }

        names = {
            r["school_name"]
            for r in rows
        }

        districts = {
            r["district_name"]
            for r in rows
        }

        designs = {
            r["program_design"]
            for r in rows
        }

        flags = []

        if len(models) > 1:
            flags.append(
                "multiple_models_same_year_language"
            )

        if len(designs) > 1:
            flags.append(
                "multiple_program_designs"
            )

        if (
            len(names) > 1
            or len(districts) > 1
        ):
            flags.append(
                "identity_label_conflict"
            )

        if not language:
            flags.append(
                "language_not_reported"
            )

        if (
            not models
            or any(
                m not in KNOWN_MODELS
                for m in models
            )
        ):
            flags.append(
                "model_unknown_or_unrecognized"
            )

        output.append({
            "school_id": "WA-S" + sid,
            "state_school_id": sid,
            "state": "WA",
            "school_year": year,
            "school_name": sorted(names)[0],
            "district_name": sorted(districts)[0],
            "instructional_language": language,
            "partner_language": "",
            "partner_language_status":
                "not_reported_in_source",
            "reported_models": join(models),
            "reported_model_labels_raw": join(
                r["reported_model_raw"]
                for r in rows
            ),
            "program_designs": join(designs),
            "program_design_count": len(designs),
            "source_rows": len(rows),
            "source_row_ids": join(
                r["source_row_id"]
                for r in rows
            ),
            "data_as_of": join(
                r["data_as_of"]
                for r in rows
            ),
            "review_flags": join(flags),
            "verification_status":
                "state_reported_program_metadata",
            "source_url": SOURCE_URL,
        })

    return output


def make_schools(school_years):
    """One row per school, combining its DL languages."""

    groups = defaultdict(list)

    for row in school_years:
        groups[
            row["state_school_id"]
        ].append(row)

    schools = []

    for sid, history in sorted(groups.items()):
        history.sort(
            key=lambda r: (
                r["school_year"],
                r["instructional_language"],
            )
        )

        last = history[-1]

        years = sorted({
            r["school_year"]
            for r in history
        })

        languages = {
            r["instructional_language"]
            for r in history
        }

        flags = []

        if any(
            r["review_flags"]
            for r in history
        ):
            flags.append(
                "school_year_record_requires_review"
            )

        schools.append({
            "school_id": "WA-S" + sid,
            "state_school_id": sid,
            "state": "WA",
            "school_name_latest":
                last["school_name"],
            "district_latest":
                last["district_name"],
            "first_observed_school_year":
                years[0],
            "last_observed_school_year":
                years[-1],
            "years_observed":
                len(years),
            "languages_reported":
                join(languages),
            "latest_reported_model": join(
                r["reported_models"]
                for r in history
                if r["school_year"] == years[-1]
            ),
            "models_reported_any_year": join(
                r["reported_models"]
                for r in history
            ),
            "designs_reported_any_year": join(
                r["program_designs"]
                for r in history
            ),
            "model_by_year": " | ".join(
                f'{r["school_year"]} '
                f'{r["instructional_language"]}: '
                f'{r["reported_models"]}'
                for r in history
            ),
            "review_flags": join(flags),
            "verification_status":
                "state_reported_program_metadata",
            "source_url": SOURCE_URL,
        })

    return schools


def model_changes(school_years):
    """Find model changes within each school and language.

    A school offering multiple languages must not be
    flagged merely because those languages use
    different instructional models.
    """

    groups = defaultdict(list)

    for r in school_years:
        key = (
            r["state_school_id"],
            r["instructional_language"],
        )
        groups[key].append(r)

    changes = []

    for (sid, language), history in sorted(
        groups.items()
    ):
        history.sort(
            key=lambda r: r["school_year"]
        )

        model_sets = {
            r["reported_models"]
            for r in history
            if r["reported_models"]
        }

        if len(model_sets) < 2:
            continue

        last = history[-1]

        changes.append({
            "school_id": "WA-S" + sid,
            "state_school_id": sid,
            "state": "WA",
            "school_name_latest":
                last["school_name"],
            "district_latest":
                last["district_name"],
            "instructional_language": language,
            "first_observed_school_year":
                history[0]["school_year"],
            "last_observed_school_year":
                last["school_year"],
            "years_observed":
                len(history),
            "models_reported_any_year": join(
                r["reported_models"]
                for r in history
            ),
            "model_by_year": " | ".join(
                f'{r["school_year"]}: '
                f'{r["reported_models"]}'
                for r in history
            ),
            "verification_status":
                "candidate_label_change_not_verified_transition",
            "source_url": SOURCE_URL,
        })

    return changes


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
        default=Path("output/washington"),
    )

    args = parser.parse_args()

    args.output.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.source.open(
        newline="",
        encoding="utf-8-sig",
    ) as f:
        reader = csv.DictReader(f)

        missing = REQUIRED - set(
            reader.fieldnames or []
        )

        if missing:
            raise RuntimeError(
                "Source schema changed; "
                f"missing {sorted(missing)}"
            )

        source = list(reader)

    if not source:
        raise RuntimeError(
            "Source file is empty"
        )

    dl, related, errors = collect_records(source)

    if errors:
        (
            args.output /
            "wa_normalization_errors.json"
        ).write_text(
            json.dumps(errors, indent=2),
            encoding="utf-8",
        )

        raise RuntimeError(
            f"{len(errors)} problematic source rows; "
            "audit saved"
        )

    if not dl:
        raise RuntimeError(
            "No state-designated dual-language "
            "programs found"
        )

    # All-language datasets
    by_language_year = make_school_years(dl)
    all_schools = make_schools(by_language_year)
    all_changes = model_changes(by_language_year)

    # Spanish-specific compatibility datasets
    spanish_rows = [
        r for r in by_language_year
        if r["instructional_language"].casefold()
        == "spanish"
    ]

    spanish_schools = make_schools(
        spanish_rows
    )

    spanish_changes = [
        r for r in all_changes
        if r["instructional_language"].casefold()
        == "spanish"
    ]

    def output(filename, rows, fields):
        save_csv(
            args.output / filename,
            rows,
            fields,
        )

    fields = list(dl[0])

    output(
        "wa_all_dl_programs.csv",
        dl,
        fields,
    )

    output(
        "wa_heritage_tribal_programs.csv",
        related,
        fields,
    )

    output(
        "wa_all_dl_school_years.csv",
        by_language_year,
        list(by_language_year[0]),
    )

    output(
        "wa_all_dl_schools.csv",
        all_schools,
        list(all_schools[0]),
    )

    change_fields = [
        "school_id",
        "state_school_id",
        "state",
        "school_name_latest",
        "district_latest",
        "instructional_language",
        "first_observed_school_year",
        "last_observed_school_year",
        "years_observed",
        "models_reported_any_year",
        "model_by_year",
        "verification_status",
        "source_url",
    ]

    output(
        "wa_all_dl_model_change_candidates.csv",
        all_changes,
        change_fields,
    )

    output(
        "wa_spanish_dl_school_years.csv",
        spanish_rows,
        list(by_language_year[0]),
    )

    output(
        "wa_spanish_dl_schools.csv",
        spanish_schools,
        list(all_schools[0]),
    )

    output(
        "wa_model_change_candidates.csv",
        spanish_changes,
        change_fields,
    )

    # Summarize every language and year.
    language_rows = []

    language_year_pairs = {
        (
            r["school_year"],
            r["instructional_language"],
        )
        for r in by_language_year
    }

    for year, language in sorted(
        language_year_pairs
    ):
        rows = [
            r for r in by_language_year
            if r["school_year"] == year
            and r["instructional_language"] == language
        ]

        language_rows.append({
            "school_year": year,
            "instructional_language": language,
            "distinct_schools": len({
                r["state_school_id"]
                for r in rows
            }),
            "school_language_year_records":
                len(rows),
            "program_source_rows": sum(
                r["source_rows"]
                for r in rows
            ),
            "reported_models": join(
                r["reported_models"]
                for r in rows
            ),
        })

    output(
        "wa_language_summary.csv",
        language_rows,
        [
            "school_year",
            "instructional_language",
            "distinct_schools",
            "school_language_year_records",
            "program_source_rows",
            "reported_models",
        ],
    )

    # Annual coverage report.
    by_year = {}

    years = sorted({
        r["school_year"]
        for r in by_language_year
    })

    for year in years:
        subset = [
            r for r in by_language_year
            if r["school_year"] == year
        ]

        spanish_subset = [
            r for r in subset
            if r["instructional_language"].casefold()
            == "spanish"
        ]

        by_year[year] = {
            "all_language_distinct_dl_schools":
                len({
                    r["state_school_id"]
                    for r in subset
                }),
            "all_language_school_language_records":
                len(subset),
            "spanish_dl_schools":
                len(spanish_subset),
            "spanish_models": dict(
                sorted(
                    Counter(
                        r["reported_models"]
                        for r in spanish_subset
                    ).items()
                )
            ),
        }

    report = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "source_url": SOURCE_URL,
        "source_rows": len(source),

        "school_level_rows": sum(
            clean(
                r["organizationlevel"]
            ).lower() == "school"
            for r in source
        ),

        "dual_language_school_source_rows_all_languages":
            len(dl),

        "related_heritage_tribal_school_source_rows":
            len(related),

        "dual_language_languages": sorted({
            r["instructional_language"]
            for r in dl
        }),

        "distinct_all_language_dl_schools":
            len(all_schools),

        "distinct_all_language_school_language_years":
            len(by_language_year),

        "distinct_spanish_dl_schools":
            len(spanish_schools),

        "distinct_spanish_dl_school_years":
            len(spanish_rows),

        "model_change_candidates_all_languages":
            len(all_changes),

        "model_change_candidates_spanish":
            len(spanish_changes),

        "by_year": by_year,

        "cautions": [
            "Heritage and tribal records are retained "
            "separately and not mislabeled as DL.",

            "Partner language is not reported and "
            "is never assumed to be English.",

            "School-year model labels are not "
            "grade-by-grade allocations.",

            "Changes in annual labels are not "
            "verified cohort transitions.",

            "These are program metadata, not "
            "DL participant assessment outcomes.",

            "No curated national registry files "
            "were modified.",
        ],
    }

    (
        args.output /
        "wa_normalization_report.json"
    ).write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "all_language_dl_schools":
                    len(all_schools),

                "all_language_school_language_years":
                    len(by_language_year),

                "spanish_dl_schools":
                    len(spanish_schools),

                "spanish_school_years":
                    len(spanish_rows),

                "model_changes_all_languages":
                    len(all_changes),

                "model_changes_spanish":
                    len(spanish_changes),

                "related_heritage_tribal_records":
                    len(related),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
