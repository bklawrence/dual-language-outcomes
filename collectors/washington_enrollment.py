
#!/usr/bin/env python3
"""Washington enrollment demographics for all DL schools.

Uses Washington OSPI Report Card Enrollment (rxjk-6ieq).

Creates schoolwide and grade 3-5 demographic measures.
Joins them to the existing all-language DL inventory.

Does not modify the curated national registry.
Python standard library only.
"""

import argparse
import csv
import json
import re
import sys
import time

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DATASET = "rxjk-6ieq"
URL = f"https://data.wa.gov/d/{DATASET}"
ENDPOINT = f"https://data.wa.gov/resource/{DATASET}.json"
META = f"https://data.wa.gov/api/views/{DATASET}.json"

PAGE_SIZE = 5000
CHUNK_SIZE = 20
MAX_CHUNK = 50000

ALIASES = {
    "schoolyear": ["schoolyear"],
    "organizationlevel": ["organizationlevel"],
    "schoolorganizationid": ["schoolorganizationid"],
    "gradelevel": ["gradelevel"],
    "all_students": ["all_students", "allstudents"],
    "low_income": ["low_income", "lowincome"],
    "english_language_learners": [
        "english_language_learners",
        "englishlanguagelearners",
    ],
    "hispanic_latino": [
        "hispanic_latino_of_any_race",
        "hispanic_latino_of_any_race_s",
        "hispanic_latino",
    ],
    "schoolname": ["schoolname"],
    "districtname": ["districtname", "leaname"],
    "dat": ["dat"],
    "dataasof": ["dataasof"],
}

REQUIRED = [
    "schoolyear",
    "organizationlevel",
    "schoolorganizationid",
    "gradelevel",
    "all_students",
    "low_income",
    "english_language_learners",
    "hispanic_latino",
]

COUNT_LABELS = [
    "all_students",
    "low_income",
    "english_language_learners",
    "hispanic_latino",
]


def canon(value):
    return re.sub(
        r"[^a-z0-9]",
        "",
        str(value or "").lower()
    )


def read_csv(path):
    with path.open(
        newline="",
        encoding="utf-8-sig"
    ) as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, columns):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def save_json(path, value):
    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def get_json(url):
    for attempt in range(6):
        try:
            req = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent":
                        "DualLanguageOutcomesResearch/0.4",
                }
            )

            with urlopen(
                req,
                timeout=90
            ) as response:
                return json.load(response)

        except HTTPError as exc:
            if (
                exc.code not in (
                    429, 500, 502, 503, 504
                )
                or attempt == 5
            ):
                raise

        except (
            URLError,
            TimeoutError,
            ConnectionError
        ):
            if attempt == 5:
                raise

        time.sleep(
            min(30, 2 ** attempt)
        )

    raise RuntimeError(
        "API retry limit exceeded"
    )


def field_mapping(fields):
    available = {
        canon(x): x for x in fields
    }

    mapped = {}

    for label, possibilities in ALIASES.items():
        mapped[label] = next(
            (
                available[canon(p)]
                for p in possibilities
                if canon(p) in available
            ),
            None
        )

    missing = [
        key for key in REQUIRED
        if not mapped[key]
    ]

    if missing:
        raise RuntimeError(
            f"Missing required enrollment fields: "
            f"{missing}; available: {sorted(fields)}"
        )

    return mapped


def schema_fields(meta):
    if (
        not isinstance(meta, dict)
        or not isinstance(
            meta.get("columns"), list
        )
    ):
        raise RuntimeError(
            "Unexpected Washington metadata response"
        )

    return sorted({
        col["fieldName"]
        for col in meta["columns"]
        if col.get("fieldName")
        and not col["fieldName"].startswith(":")
    })


def download(registry, mapping):
    ids = sorted({
        r["state_school_id"].strip()
        for r in registry
    })

    years = sorted({
        r["school_year"].strip()
        for r in registry
    })

    if (
        not ids
        or not all(
            re.fullmatch(r"\d+", sid)
            for sid in ids
        )
    ):
        raise RuntimeError(
            "Unexpected or missing WA school IDs"
        )

    if not all(
        re.fullmatch(
            r"20\d{2}-\d{2}", year
        )
        for year in years
    ):
        raise RuntimeError(
            "Unexpected school-year labels"
        )

    selected = sorted(set(
        x for x in mapping.values()
        if x
    ))

    rows = []

    for pos in range(
        0, len(ids), CHUNK_SIZE
    ):
        chunk = ids[
            pos:pos + CHUNK_SIZE
        ]

        quoted_ids = ",".join(
            "'" + x + "'"
            for x in chunk
        )

        quoted_years = ",".join(
            "'" + y + "'"
            for y in years
        )

        where = (
            f"{mapping['schoolorganizationid']} "
            f"in ({quoted_ids}) "
            f"and {mapping['schoolyear']} "
            f"in ({quoted_years}) "
            f"and {mapping['organizationlevel']} "
            f"= 'School'"
        )

        offset = 0

        while True:
            url = ENDPOINT + "?" + urlencode({
                "$where": where,
                "$select": ",".join(selected),
                "$limit": PAGE_SIZE,
                "$offset": offset,
                "$order": ":id",
            })

            page = get_json(url)

            if (
                not isinstance(page, list)
                or any(
                    not isinstance(r, dict)
                    for r in page
                )
            ):
                raise RuntimeError(
                    "Unexpected data page"
                )

            if offset + len(page) > MAX_CHUNK:
                raise RuntimeError(
                    "Pagination limit reached; "
                    "do not treat as complete"
                )

            rows.extend(page)
            offset += len(page)

            if len(page) < PAGE_SIZE:
                break

        print(
            f"Enrollment downloaded: {len(rows)} "
            f"rows, schools through "
            f"{pos + len(chunk)} / {len(ids)}",
            flush=True
        )

    if not rows:
        raise RuntimeError(
            "No school-level enrollment results found"
        )

    return rows


def count(raw):
    val = str(
        raw if raw is not None else ""
    ).strip()

    if (
        not val
        or val.lower() in (
            "null", "none", "n/a",
            "na", "suppressed"
        )
        or val in (
            "*", "—", "-", "--"
        )
    ):
        return None, "not_reported"

    try:
        number = float(
            val.replace(",", "")
        )

        if (
            not number.is_integer()
            or number < 0
        ):
            return None, "invalid"

        return int(number), "numeric"

    except ValueError:
        return None, "non_numeric"


def extract(row, mapping):
    def val(name):
        field = mapping.get(name)

        return str(
            row.get(field, "")
            if field else ""
        ).strip()

    amounts = {}
    states = {}

    for label in COUNT_LABELS:
        amounts[label], states[label] = count(
            val(label)
        )

    return amounts, states


def shares(amounts, prefix):
    total = amounts.get("all_students")

    result = {
        f"{prefix}_enrollment_n":
            "" if total is None else total
    }

    for label in (
        "low_income",
        "english_language_learners",
        "hispanic_latino"
    ):
        n = amounts.get(label)

        usable = (
            total is not None
            and total > 0
            and n is not None
            and 0 <= n <= total
        )

        result[
            f"{prefix}_{label}_n"
        ] = "" if n is None else n

        result[
            f"{prefix}_{label}_pct"
        ] = (
            round(100 * n / total, 4)
            if usable else ""
        )

        if usable:
            status = "usable"

        elif (
            total is not None
            and n is not None
            and n > total
        ):
            status = "count_exceeds_total"

        elif total == 0:
            status = "zero_denominator"

        else:
            status = "missing_or_suppressed"

        result[
            f"{prefix}_{label}_status"
        ] = status

    return result


def process(registry, raw, mapping, output):
    keys = {
        (
            r["state_school_id"].strip(),
            r["school_year"].strip()
        )
        for r in registry
    }

    columns = sorted(
        set(mapping.values()) - {None}
    )

    write_csv(
        output / "wa_enrollment_source_rows.csv",
        raw,
        columns
    )

    grouped = defaultdict(list)
    skipped = Counter()
    grade_labels = Counter()

    for row in raw:
        org = str(
            row.get(
                mapping["organizationlevel"], ""
            )
        ).strip()

        sid = str(
            row.get(
                mapping["schoolorganizationid"], ""
            )
        ).strip()

        year = str(
            row.get(
                mapping["schoolyear"], ""
            )
        ).strip()

        grade = str(
            row.get(
                mapping["gradelevel"], ""
            )
        ).strip()

        if (
            canon(org) != "school"
            or (sid, year) not in keys
        ):
            skipped[
                "not_matching_school_year"
            ] += 1
            continue

        grouped[(sid, year)].append(row)
        grade_labels[grade] += 1

    results = []

    for sid, year in sorted(keys):
        rows = grouped.get(
            (sid, year), []
        )

        full = [
            r for r in rows
            if canon(
                r.get(mapping["gradelevel"])
            ) in ("allgrades", "allgrade")
        ]

        grade_rows = {}

        for grade in (3, 4, 5):
            grade_rows[grade] = [
                r for r in rows
                if canon(
                    r.get(mapping["gradelevel"])
                ) in (
                    str(grade),
                    f"grade{grade}"
                )
            ]

        record = {
            "state": "WA",
            "state_school_id": sid,
            "school_year": year,
            "source_dataset_id": DATASET,
            "source_url": URL,
            "source_rows": len(rows),
            "all_grades_row_count": len(full),
            "grade3_5_rows_present": sum(
                bool(grade_rows[g])
                for g in (3, 4, 5)
            ),
            "grade3_5_complete": (
                "yes"
                if all(
                    len(grade_rows[g]) == 1
                    for g in (3, 4, 5)
                )
                else "no"
            )
        }

        for name in (
            "schoolname",
            "districtname",
            "dat",
            "dataasof"
        ):
            record[name] = str(
                full[0].get(
                    mapping[name], ""
                )
                if len(full) == 1
                and mapping.get(name)
                else ""
            )

        flags = []

        if len(full) != 1:
            flags.append(
                "all_grades_missing"
                if not full
                else "all_grades_duplicate"
            )

        if len(full) == 1:
            amounts, status = extract(
                full[0], mapping
            )

            record.update(
                shares(amounts, "whole_school")
            )

            for label in COUNT_LABELS:
                record[
                    f"whole_school_{label}_raw_status"
                ] = status[label]

        else:
            record.update(
                shares({}, "whole_school")
            )

            for label in COUNT_LABELS:
                record[
                    f"whole_school_{label}_raw_status"
                ] = "no_unique_all_grades_row"

        counts_3_5 = {}

        if record[
            "grade3_5_complete"
        ] == "yes":
            parts = [
                extract(
                    grade_rows[g][0],
                    mapping
                )[0]
                for g in (3, 4, 5)
            ]

            for label in COUNT_LABELS:
                values = [
                    p[label]
                    for p in parts
                ]

                counts_3_5[label] = (
                    sum(values)
                    if all(
                        v is not None
                        for v in values
                    )
                    else None
                )

        record.update(
            shares(counts_3_5, "grade3_5")
        )

        if record[
            "grade3_5_complete"
        ] != "yes":
            flags.append(
                "grade3_5_incomplete_or_not_offered"
            )

        if any(
            record[
                f"whole_school_{label}_status"
            ] == "count_exceeds_total"
            for label in (
                "low_income",
                "english_language_learners",
                "hispanic_latino"
            )
        ):
            flags.append(
                "subgroup_exceeds_school_enrollment"
            )

        record["review_flags"] = (
            " | ".join(flags)
        )

        record["outcome_scope"] = (
            "schoolwide_enrollment_not_"
            "DL_program_enrollment"
        )

        results.append(record)

    write_csv(
        output / "wa_enrollment_school_years.csv",
        results,
        list(results[0])
    )

    by_key = {
        (
            r["state_school_id"],
            r["school_year"]
        ): r
        for r in results
    }

    joined = []

    for p in registry:
        row = by_key[
            (
                p["state_school_id"].strip(),
                p["school_year"].strip()
            )
        ]

        joined.append({
            **row,
            "dl_school_id": p["school_id"],
            "dl_language":
                p["instructional_language"],
            "dl_model_reported":
                p["reported_models"],
            "dl_program_design":
                p["program_designs"],
            "dl_review_flags":
                p["review_flags"],
            "join_scope":
                "school_and_year_only_not_DL_participants"
        })

    write_csv(
        output / "wa_enrollment_dl_join.csv",
        joined,
        list(joined[0])
    )

    academic_path = (
        output / "wa_academic_coverage.csv"
    )

    academic_join = []

    if academic_path.exists():
        academic = read_csv(
            academic_path
        )

        a_lookup = {
            (
                r.get("state_school_id", ""),
                r.get("school_year", ""),
                r.get(
                    "instructional_language", ""
                )
            ): r
            for r in academic
        }

        for row in joined:
            a = a_lookup.get(
                (
                    row["state_school_id"],
                    row["school_year"],
                    row["dl_language"]
                ),
                {}
            )

            academic_join.append({
                **row,
                "academic_rows": a.get(
                    "academic_rows", ""
                ),
                "academic_numeric_primary_rows":
                    a.get(
                        "numeric_primary_proficiency_rows",
                        ""
                    ),
                "academic_all_students_rows":
                    a.get(
                        "all_students_primary_proficiency_rows",
                        ""
                    ),
                "academic_english_learner_rows":
                    a.get(
                        "english_learner_primary_proficiency_rows",
                        ""
                    )
            })

        write_csv(
            output /
            "wa_academic_enrollment_coverage.csv",
            academic_join,
            list(academic_join[0])
        )

    report = {
        "created_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "source": URL,

        "downloaded_enrollment_rows":
            len(raw),

        "dl_registry_school_language_years":
            len(registry),

        "unique_school_years":
            len(results),

        "school_years_with_unique_all_grades_row":
            sum(
                r["all_grades_row_count"] == 1
                for r in results
            ),

        "school_years_with_all_three_whole_school_shares":
            sum(
                all(
                    r[
                        f"whole_school_{name}_status"
                    ] == "usable"
                    for name in (
                        "low_income",
                        "english_language_learners",
                        "hispanic_latino"
                    )
                )
                for r in results
            ),

        "school_years_with_complete_grade3_5_counts":
            sum(
                all(
                    r[
                        f"grade3_5_{name}_status"
                    ] == "usable"
                    for name in (
                        "low_income",
                        "english_language_learners",
                        "hispanic_latino"
                    )
                )
                for r in results
            ),

        "source_grade_labels":
            dict(grade_labels),

        "unmatched_source_rows":
            dict(skipped),

        "field_mapping":
            mapping,

        "academic_coverage_joined":
            bool(academic_join),

        "warnings": [
            "Schoolwide shares do not identify "
            "DL-program participation or entering "
            "home language.",

            "All Grades and grade 3-5 results "
            "are separate; do not add them.",

            "Suppression and absent counts "
            "are not zero.",

            "Grade 3-5 shares require all three "
            "grades; missing grades are flagged.",

            "No causal model comparison or "
            "imputation performed."
        ]
    }

    save_json(
        output / "wa_enrollment_report.json",
        report
    )

    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "downloaded_enrollment_rows",
                    "unique_school_years",
                    "school_years_with_unique_all_grades_row",
                    "school_years_with_all_three_whole_school_shares",
                    "school_years_with_complete_grade3_5_counts"
                )
            },
            indent=2
        ),
        flush=True
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--registry",
        type=Path,
        default=Path(
            "output/washington/"
            "wa_all_dl_school_years.csv"
        )
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/washington")
    )

    parser.add_argument(
        "--input-json",
        type=Path,
        help="Offline fixture for testing"
    )

    args = parser.parse_args()

    args.output.mkdir(
        parents=True,
        exist_ok=True
    )

    try:
        registry = read_csv(
            args.registry
        )

        required = {
            "state_school_id",
            "school_year",
            "school_id",
            "instructional_language",
            "reported_models",
            "program_designs",
            "review_flags"
        }

        if (
            not registry
            or not required.issubset(registry[0])
        ):
            raise RuntimeError(
                "Missing normalized all-language "
                "Washington registry"
            )

        if args.input_json:
            raw = json.loads(
                args.input_json.read_text(
                    encoding="utf-8"
                )
            )

            if (
                not isinstance(raw, list)
                or not raw
            ):
                raise RuntimeError(
                    "Invalid local fixture"
                )

            fields = set().union(
                *(r.keys() for r in raw)
            )

        else:
            metadata = get_json(META)

            fields = schema_fields(
                metadata
            )

        # Check fields before downloading the dataset.
        mapping = field_mapping(fields)

        raw = (
            raw
            if args.input_json
            else download(registry, mapping)
        )

        if (
            not isinstance(raw, list)
            or not raw
        ):
            raise RuntimeError(
                "No enrollment rows"
            )

        process(
            registry,
            raw,
            mapping,
            args.output
        )

    except Exception as exc:
        (
            args.output /
            "wa_enrollment_error.txt"
        ).write_text(
            str(exc) + "\n",
            encoding="utf-8"
        )

        print(
            f"ENROLLMENT COLLECTION FAILED: {exc}",
            file=sys.stderr
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()
