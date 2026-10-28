
#!/usr/bin/env python3
"""Collect Washington academic outcomes for DL schools.

Source:
Washington OSPI Report Card Assessment
School Years 2021-22 Through Present

Uses the existing all-language DL inventory.

Produces:
- wa_academic_source_rows.csv
- wa_academic_outcomes.csv
- wa_academic_dl_join.csv
- wa_academic_coverage.csv
- wa_academic_report.json

Results remain school-level outcomes, not necessarily
outcomes of students enrolled in dual language.
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


DATASET = "9fjj-2374"

SOURCE = (
    f"https://data.wa.gov/d/{DATASET}"
)

ENDPOINT = (
    f"https://data.wa.gov/resource/{DATASET}.json"
)

PAGE_SIZE = 5000
SCHOOL_CHUNK = 20
MAX_PER_CHUNK = 200000


def read_csv(path):
    with path.open(
        encoding="utf-8-sig",
        newline=""
    ) as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, columns):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=columns,
            extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def norm(text):
    return re.sub(
        r"[^a-z0-9]",
        "",
        str(text or "").lower()
    )


def find_col(columns, *names):
    lookup = {
        norm(s): s
        for s in columns
    }

    for name in names:
        if norm(name) in lookup:
            return lookup[norm(name)]

    return None


def api_get(url):
    for attempt in range(6):
        try:
            request = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent":
                        "DualLanguageOutcomesResearch/0.2",
                }
            )

            with urlopen(
                request,
                timeout=95
            ) as response:
                result = json.load(response)

            if (
                not isinstance(result, list)
                or any(
                    not isinstance(x, dict)
                    for x in result
                )
            ):
                raise ValueError(
                    "Unexpected assessment API format"
                )

            return result

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
        "Washington API retry limit exceeded"
    )


def get_rows(registry, fixture=None):
    """Download academic rows for DL schools and years."""

    ids = sorted({
        r["state_school_id"].strip()
        for r in registry
    })

    years = sorted({
        r["school_year"].strip()
        for r in registry
    })

    if any(
        not re.fullmatch(r"[0-9]+", x)
        for x in ids
    ):
        raise ValueError(
            "Invalid school identifier"
        )

    if any(
        not re.fullmatch(
            r"20[0-9]{2}-[0-9]{2}", y
        )
        for y in years
    ):
        raise ValueError(
            "Unexpected school-year format"
        )

    if fixture:
        obj = json.loads(
            fixture.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(obj, list) or not obj:
            raise ValueError(
                "Fixture must be a nonempty JSON list"
            )

        return obj

    result = []

    years_condition = ",".join(
        "'" + y + "'"
        for y in years
    )

    for start in range(
        0, len(ids), SCHOOL_CHUNK
    ):
        part = ids[
            start:start + SCHOOL_CHUNK
        ]

        ids_condition = ",".join(
            "'" + x + "'"
            for x in part
        )

        where = (
            f"schoolorganizationid in "
            f"({ids_condition}) "
            f"and schoolyear in "
            f"({years_condition})"
        )

        print(
            f"Collecting schools "
            f"{start + 1}-"
            f"{start + len(part)} "
            f"of {len(ids)}",
            flush=True
        )

        offset = 0

        while True:
            url = ENDPOINT + "?" + urlencode({
                "$where": where,
                "$limit": PAGE_SIZE,
                "$offset": offset,
                "$order": ":id",
            })

            page = api_get(url)

            if not page:
                break

            if (
                offset + len(page)
                > MAX_PER_CHUNK
            ):
                raise RuntimeError(
                    "Pagination safety limit reached"
                )

            result.extend(page)
            offset += len(page)

            print(
                f"Downloaded {len(result)} rows",
                flush=True
            )

            if len(page) < PAGE_SIZE:
                break

    if not result:
        raise RuntimeError(
            "No academic results returned "
            "for the DL school identifiers"
        )

    return result


def subject_label(value):
    x = norm(value)

    if x in (
        "ela",
        "englishlanguagearts",
        "englishlanguageartsliteracy"
    ):
        return "ELA"

    if x in (
        "math",
        "mathematics"
    ):
        return "Math"

    return ""


def grade_label(value):
    x = str(
        value or ""
    ).strip().lower()

    m = re.fullmatch(
        r"(?:grade\s*)?(0?[3-8])",
        x
    )

    return (
        str(int(m.group(1)))
        if m else ""
    )


def group_label(value):
    x = norm(value)

    if x in (
        "allstudents",
        "all"
    ):
        return "all_students"

    if x in (
        "englishlearners",
        "englishlearner",
        "englishlanguagelearners",
        "currentenglishlearners",
        "currentenglishlanguagelearners",
        "currentel",
        "currentell"
    ):
        return "reported_english_learners"

    return "other_reported_group"


def percent_status(raw):
    x = str(
        raw or ""
    ).strip()

    if (
        not x
        or norm(x) in {
            "null", "na", "suppressed",
            "nlt10", "none"
        }
        or x in {
            "*", "--", "—", "-"
        }
    ):
        return "not_reported", ""

    try:
        value = float(
            x.replace(",", "")
            .removesuffix("%")
        )

    except ValueError:
        return "non_numeric", ""

    if not 0 <= value <= 100:
        return "out_of_range", ""

    return "numeric_published", value


def process(registry, raw, output):
    lookup = defaultdict(list)

    for r in registry:
        key = (
            r["state_school_id"].strip(),
            r["school_year"].strip()
        )
        lookup[key].append(r)

    cols = sorted(
        set().union(
            *(r.keys() for r in raw)
        )
    )

    mapping = {
        "school_id": find_col(
            cols, "schoolorganizationid"
        ),
        "school_year": find_col(
            cols, "schoolyear"
        ),
        "level": find_col(
            cols, "organizationlevel"
        ),
        "name": find_col(
            cols, "schoolname"
        ),
        "district": find_col(
            cols, "districtname"
        ),
        "subject": find_col(
            cols, "testsubject"
        ),
        "grade": find_col(
            cols, "gradelevel"
        ),
        "group": find_col(
            cols, "studentgroup"
        ),
        "group_type": find_col(
            cols, "studentgrouptype"
        ),
        "pct_met": find_col(
            cols, "percentmetstandard"
        ),
        "administration": find_col(
            cols,
            "testadministration",
            "assessmenttype"
        ),
        "n_tested": find_col(
            cols,
            "numbertested",
            "counttested"
        ),
        "pct_tested": find_col(
            cols, "percenttested"
        ),
    }

    required = [
        "school_id",
        "school_year",
        "level",
        "subject",
        "grade",
        "group",
        "pct_met"
    ]

    missing = [
        x for x in required
        if not mapping[x]
    ]

    if missing:
        raise RuntimeError(
            "Assessment API schema mismatch: "
            + str(missing)
            + "; source fields: "
            + ", ".join(cols)
        )

    write_csv(
        output / "wa_academic_source_rows.csv",
        raw,
        cols
    )

    def field(row, key):
        col = mapping[key]

        return str(
            row.get(col, "")
            if col else ""
        ).strip()

    stats = Counter()
    values = Counter()
    normalized = []
    joined = []
    duplicate_check = Counter()

    for r in raw:
        sid = field(r, "school_id")
        yr = field(r, "school_year")

        if (
            field(r, "level").casefold()
            != "school"
        ):
            stats["not_school_level"] += 1
            continue

        program_rows = lookup.get(
            (sid, yr), []
        )

        if not program_rows:
            stats[
                "not_in_dl_registry_year"
            ] += 1
            continue

        subject = subject_label(
            field(r, "subject")
        )

        grade = grade_label(
            field(r, "grade")
        )

        if not subject or not grade:
            stats[
                "not_grade_3_8_ela_math"
            ] += 1
            continue

        raw_rate = field(r, "pct_met")

        status, rate = percent_status(
            raw_rate
        )

        group = field(r, "group")

        stats[
            "academic_source_rows"
        ] += 1

        values[status] += 1

        rec = {
            "state": "WA",
            "state_school_id": sid,
            "school_year": yr,
            "school_name": field(r, "name"),
            "district_name": field(
                r, "district"
            ),
            "grade": grade,
            "subject": subject,
            "test_administration_raw": field(
                r, "administration"
            ),
            "student_group": group,
            "student_group_type": field(
                r, "group_type"
            ),
            "student_group_bucket":
                group_label(group),
            "percent_met_standard_raw":
                raw_rate,
            "percent_met_standard":
                rate,
            "percent_value_status":
                status,
            "number_tested_raw": field(
                r, "n_tested"
            ),
            "percent_tested_raw": field(
                r, "pct_tested"
            ),
            "outcome_scope":
                "school_reported_student_group_NOT_DL_participants",
            "source_dataset_id": DATASET,
            "source_url": SOURCE,
        }

        normalized.append(rec)

        key = (
            sid,
            yr,
            grade,
            subject,
            group,
            rec["test_administration_raw"]
        )

        duplicate_check[key] += 1

        for p in program_rows:
            joined.append({
                **rec,
                "dl_school_id":
                    p["school_id"],
                "dl_language":
                    p["instructional_language"],
                "dl_model_reported":
                    p["reported_models"],
                "dl_program_design":
                    p["program_designs"],
                "dl_review_flags":
                    p["review_flags"],
                "join_scope":
                    "school_id_and_school_year_only_not_program_participants",
                "multiple_dl_languages_at_school":
                    "yes"
                    if len(program_rows) > 1
                    else "no",
            })

    if not normalized:
        raise RuntimeError(
            "No grade 3-8 ELA/Math observations. "
            "Inspect published categories."
        )

    write_csv(
        output / "wa_academic_outcomes.csv",
        normalized,
        list(normalized[0])
    )

    write_csv(
        output / "wa_academic_dl_join.csv",
        joined,
        list(joined[0])
    )

    groups = defaultdict(list)

    for r in joined:
        key = (
            r["state_school_id"],
            r["school_year"],
            r["dl_language"]
        )
        groups[key].append(r)

    coverage = []

    for p in registry:
        key = (
            p["state_school_id"],
            p["school_year"],
            p["instructional_language"]
        )

        rows = groups[key]

        selected = [
            r for r in rows
            if r["percent_value_status"]
            == "numeric_published"
        ]

        coverage.append({
            "state_school_id": key[0],
            "school_year": key[1],
            "instructional_language":
                key[2],
            "school_name":
                p["school_name"],
            "reported_model":
                p["reported_models"],
            "reported_design":
                p["program_designs"],
            "academic_rows":
                len(rows),
            "numeric_percent_rows":
                len(selected),
            "all_students_numeric_rows":
                sum(
                    r["student_group_bucket"]
                    == "all_students"
                    for r in selected
                ),
            "english_learner_numeric_rows":
                sum(
                    r["student_group_bucket"]
                    == "reported_english_learners"
                    for r in selected
                ),
            "ela_numeric_rows":
                sum(
                    r["subject"] == "ELA"
                    for r in selected
                ),
            "math_numeric_rows":
                sum(
                    r["subject"] == "Math"
                    for r in selected
                ),
            "join_status":
                "academic_rows_found"
                if rows else
                "no_matching_academic_rows",
            "outcome_scope":
                "school_reported_not_dl_participants",
        })

    write_csv(
        output / "wa_academic_coverage.csv",
        coverage,
        list(coverage[0])
    )

    duplicate_examples = [
        list(k) + [n]
        for k, n in duplicate_check.items()
        if n > 1
    ]

    report = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "source_url": SOURCE,
        "source_dataset_id": DATASET,

        "source_rows_downloaded": len(raw),

        "distinct_school_ids_in_registry":
            len({
                r["state_school_id"]
                for r in registry
            }),

        "registry_school_language_year_rows":
            len(registry),

        "academic_rows_grade_3_8":
            len(normalized),

        "academic_rows_joined_school_language":
            len(joined),

        "program_language_years_with_academics":
            sum(
                bool(x["academic_rows"])
                for x in coverage
            ),

        "program_language_years_without_academics":
            sum(
                not bool(x["academic_rows"])
                for x in coverage
            ),

        "distinct_schools_with_grade_3_8_academics":
            len({
                r["state_school_id"]
                for r in normalized
            }),

        "field_mapping": mapping,

        "numeric_values_by_status":
            dict(values),

        "excluded_source_rows":
            dict(stats),

        "reported_student_groups_sample":
            Counter(
                r["student_group"]
                for r in normalized
            ).most_common(30),

        "reported_test_administrations":
            dict(
                Counter(
                    r["test_administration_raw"]
                    for r in normalized
                )
            ),

        "duplicate_assessment_keys":
            len(duplicate_examples),

        "duplicate_key_examples":
            duplicate_examples[:15],

        "cautions": [
            "Results are school-level subgroup rates, not DL-participant outcomes.",
            "Schoolwide results are repeated for each DL language at multi-language schools.",
            "Test-administration variants are preserved separately.",
            "No averages across schools, subjects, grades or models are calculated.",
            "Numeric/range checks are not independent source-cell verification.",
            "The 2026 revision changed tested-student denominator reporting and corrected some 2022-23 data.",
            "Suppressed and missing values are not zero."
        ],
    }

    (
        output / "wa_academic_report.json"
    ).write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "source_rows_downloaded":
                    len(raw),
                "academic_rows":
                    len(normalized),
                "joined_rows":
                    len(joined),
                "school_language_years_with_academics":
                    report[
                        "program_language_years_with_academics"
                    ]
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
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/washington"),
    )

    parser.add_argument(
        "--input-json",
        type=Path,
        help="Optional local test fixture"
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

        if not registry:
            raise ValueError(
                "No DL schools in normalized registry"
            )

        required = (
            "state_school_id",
            "school_year",
            "instructional_language",
            "school_id",
            "school_name",
            "reported_models",
            "program_designs",
            "review_flags"
        )

        for key in required:
            if key not in registry[0]:
                raise ValueError(
                    f"DL registry missing: {key}"
                )

        raw = get_rows(
            registry,
            args.input_json
        )

        process(
            registry,
            raw,
            args.output
        )

    except Exception as exc:
        (
            args.output /
            "wa_academic_error.txt"
        ).write_text(
            str(exc) + "\n",
            encoding="utf-8"
        )

        print(
            f"ACADEMIC COLLECTION FAILED: {exc}",
            file=sys.stderr
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()
