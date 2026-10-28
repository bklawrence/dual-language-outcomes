
#!/usr/bin/env python3
"""Collect Washington academic results for DL schools.

Uses the existing all-language Washington DL registry.
Preserves source records, reported performance levels,
student groups, school-year joins, and coverage audits.

School results are NOT necessarily DL-participant results.
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


DATASET = "9fjj-2374"
SOURCE = f"https://data.wa.gov/d/{DATASET}"
ENDPOINT = f"https://data.wa.gov/resource/{DATASET}.json"

PAGE_SIZE = 5000
SCHOOL_CHUNK = 20
MAX_PER_CHUNK = 200000

PREFLIGHT_FIELDS = (
    "organizationlevel",
    "schoolyear",
    "schoolorganizationid",
    "testsubject",
    "gradelevel",
    "studentgroup",
    "percent_consistent_grade",
)

METRICS = (
    ("percent_consistent_grade",
     "pct_consistent_grade_or_above"),
    ("percent_foundational_grade",
     "pct_foundational_grade_or_above"),
    ("percentlevel1_including",
     "pct_level_1_including"),
    ("percentlevel2_including",
     "pct_level_2_including"),
    ("percentlevel3_including",
     "pct_level_3_including"),
    ("percentlevel4_including",
     "pct_level_4_including"),
    ("percent_participation",
     "pct_participation"),
    ("percent_no_score",
     "pct_no_score"),
    ("percent_taking_alternative",
     "pct_alternate_assessment"),
)

COUNTS = (
    ("count_of_students_tested", "count_tested"),
    ("count_of_students_expected", "count_expected"),
    ("count_consistent_grade_level",
     "count_consistent_grade_or_above"),
    ("count_foundational_grade",
     "count_foundational_grade_or_above"),
)


def read_csv(path):
    with path.open(
        newline="",
        encoding="utf-8-sig"
    ) as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def api_get(url):
    for attempt in range(6):
        try:
            request = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent":
                        "DualLanguageOutcomesResearch/0.3"
                }
            )

            with urlopen(
                request,
                timeout=95
            ) as response:
                result = json.load(response)

            if (
                not isinstance(result, list)
                or not all(
                    isinstance(r, dict)
                    for r in result
                )
            ):
                raise ValueError(
                    "Unexpected API response format"
                )

            return result

        except HTTPError as exc:
            if (
                exc.code not in
                (429, 500, 502, 503, 504)
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


def preflight():
    """Check actual published field names before download."""

    url = ENDPOINT + "?" + urlencode({
        "$select": ",".join(PREFLIGHT_FIELDS),
        "$limit": 1
    })

    rows = api_get(url)

    if not rows:
        raise RuntimeError(
            "Assessment API preflight returned no rows"
        )

    print(
        "Assessment API preflight passed",
        flush=True
    )


def collect(registry, fixture=None):
    if fixture:
        result = json.loads(
            fixture.read_text(encoding="utf-8")
        )
        if (
            not isinstance(result, list)
            or not result
            or not all(
                isinstance(r, dict)
                for r in result
            )
        ):
            raise ValueError(
                "Fixture must contain JSON records"
            )
        return result

    ids = sorted({
        r["state_school_id"].strip()
        for r in registry
    })

    years = sorted({
        r["school_year"].strip()
        for r in registry
    })

    if any(
        not re.fullmatch(r"\d+", x)
        for x in ids
    ):
        raise ValueError(
            "Invalid school identifier"
        )

    if any(
        not re.fullmatch(
            r"20\d\d-\d\d", y
        )
        for y in years
    ):
        raise ValueError(
            "Unexpected school-year format"
        )

    preflight()

    result = []

    for start in range(
        0, len(ids), SCHOOL_CHUNK
    ):
        subset = ids[
            start:start + SCHOOL_CHUNK
        ]

        quoted_ids = ",".join(
            "'" + x + "'"
            for x in subset
        )

        quoted_years = ",".join(
            "'" + y + "'"
            for y in years
        )

        where = (
            f"schoolorganizationid in "
            f"({quoted_ids}) "
            f"and schoolyear in "
            f"({quoted_years})"
        )

        print(
            f"Collecting schools "
            f"{start + 1}-"
            f"{start + len(subset)} "
            f"of {len(ids)}",
            flush=True
        )

        offset = 0

        while True:
            url = ENDPOINT + "?" + urlencode({
                "$where": where,
                "$limit": PAGE_SIZE,
                "$offset": offset,
                "$order": ":id"
            })

            page = api_get(url)

            if (
                offset + len(page)
                > MAX_PER_CHUNK
            ):
                raise RuntimeError(
                    "Pagination safety limit exceeded"
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
            "No academic records downloaded"
        )

    return result


def field(row, name):
    return str(
        row.get(name) or ""
    ).strip()


def number_status(raw):
    raw = str(raw or "").strip()

    if (
        not raw
        or raw.lower() in (
            "null", "none", "n/a",
            "na", "suppressed"
        )
        or raw in (
            "*", "—", "-", "--"
        )
    ):
        return "not_reported", ""

    try:
        num = float(
            raw.rstrip("%").replace(",", "")
        )
    except ValueError:
        return "non_numeric", ""

    if not 0 <= num <= 100:
        return "out_of_range", ""

    return "numeric_unverified", num


def count_status(raw):
    raw = str(raw or "").strip()

    if (
        not raw
        or raw.lower() in (
            "null", "none", "n/a",
            "na", "suppressed"
        )
        or raw in (
            "*", "—", "-", "--"
        )
    ):
        return "not_reported", ""

    try:
        num = float(
            raw.replace(",", "")
        )

        if num < 0 or int(num) != num:
            return "out_of_range", ""

        return "numeric_unverified", int(num)

    except ValueError:
        return "non_numeric", ""


def subject_label(raw):
    text = re.sub(
        r"[^a-z]", "",
        str(raw).lower()
    )

    if text in (
        "ela",
        "englishlanguagearts",
        "englishlanguageartsliteracy"
    ):
        return "ELA"

    if text in (
        "math",
        "mathematics"
    ):
        return "Math"

    return ""


def grade_label(raw):
    text = str(raw or "").strip().lower()

    match = re.fullmatch(
        r"(?:grade\s*)?0?([3-8])"
        r"(?:st|nd|rd|th)?"
        r"(?:\s*grade)?",
        text
    )

    return match.group(1) if match else ""


def group_label(raw):
    text = re.sub(
        r"[^a-z]", "",
        str(raw).lower()
    )

    if text in (
        "all",
        "allstudents"
    ):
        return "all_students"

    if text in (
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


def process(registry, raw, output):
    fields = sorted(
        set().union(
            *(r.keys() for r in raw)
        )
    )

    # Save original source before validation.
    write_csv(
        output / "wa_academic_source_rows.csv",
        raw,
        fields
    )

    required = (
        "schoolorganizationid",
        "schoolyear",
        "organizationlevel",
        "testsubject",
        "gradelevel",
        "studentgroup",
        "percent_consistent_grade"
    )

    missing = [
        x for x in required
        if x not in fields
    ]

    if missing:
        raise ValueError(
            f"Missing fields: {missing}. "
            f"Available: {fields}"
        )

    lookup = defaultdict(list)

    for p in registry:
        key = (
            p["state_school_id"].strip(),
            p["school_year"].strip()
        )
        lookup[key].append(p)

    stats = Counter()
    statuses = Counter()
    assessment = []
    joined = []
    duplicates = Counter()
    matched_keys = set()
    year_counts = Counter()

    for r in raw:
        sid = field(
            r, "schoolorganizationid"
        )
        year = field(r, "schoolyear")

        if (
            field(
                r, "organizationlevel"
            ).casefold() != "school"
        ):
            stats["non_school_rows"] += 1
            continue

        programs = lookup.get(
            (sid, year), []
        )

        if not programs:
            stats["unmatched_school_year"] += 1
            continue

        subject = subject_label(
            field(r, "testsubject")
        )

        grade = grade_label(
            field(r, "gradelevel")
        )

        if not subject or not grade:
            stats["not_grade_3_8_ela_math"] += 1
            continue

        group = field(r, "studentgroup")

        rec = {
            "state": "WA",
            "state_school_id": sid,
            "school_year": year,
            "school_name": field(
                r, "schoolname"
            ),
            "district_name": field(
                r, "districtname"
            ),
            "grade": grade,
            "subject": subject,
            "student_group": group,
            "student_group_type": field(
                r, "studentgrouptype"
            ),
            "student_group_bucket":
                group_label(group),
            "testadministration": field(
                r, "testadministration"
            ),
            "test_administration_group": field(
                r, "test_administration_group"
            ),
            "outcome_scope":
                "school_level_group_not_DL_participants",
            "source_dataset_id": DATASET,
            "source_url": SOURCE
        }

        for source_name, target in METRICS:
            raw_value = field(
                r, source_name
            )

            status, value = number_status(
                raw_value
            )

            rec[target + "_raw"] = raw_value
            rec[target] = value
            rec[target + "_status"] = status

            statuses[(target, status)] += 1

        for source_name, target in COUNTS:
            raw_value = field(
                r, source_name
            )

            status, value = count_status(
                raw_value
            )

            rec[target + "_raw"] = raw_value
            rec[target] = value
            rec[target + "_status"] = status

        rec["percentage_definition_note"] = (
            "OSPI 2026 republished assessment data; "
            "see official data notes"
        )

        assessment.append(rec)
        matched_keys.add((sid, year))
        year_counts[year] += 1

        duplicate_key = (
            sid,
            year,
            grade,
            subject,
            rec["student_group_type"],
            group,
            rec["testadministration"],
            rec["test_administration_group"]
        )

        duplicates[duplicate_key] += 1

        for p in programs:
            joined.append({
                **rec,
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
                    "school_year_only_not_DL_participants",
                "multiple_dl_languages_at_school":
                    "yes" if len(programs) > 1
                    else "no"
            })

        stats[
            "grade_3_8_ela_math_rows"
        ] += 1

    if not assessment:
        raise ValueError(
            "No school-level grade 3-8 ELA/Math "
            "records identified"
        )

    write_csv(
        output / "wa_academic_outcomes.csv",
        assessment,
        list(assessment[0])
    )

    write_csv(
        output / "wa_academic_dl_join.csv",
        joined,
        list(joined[0])
    )

    grouped = defaultdict(list)

    for r in joined:
        key = (
            r["state_school_id"],
            r["school_year"],
            r["dl_language"]
        )
        grouped[key].append(r)

    coverage = []

    for p in registry:
        key = (
            p["state_school_id"],
            p["school_year"],
            p["instructional_language"]
        )

        rows = grouped[key]

        def numeric(row):
            return (
                row[
                    "pct_consistent_grade_or_above_status"
                ] == "numeric_unverified"
            )

        coverage.append({
            "state_school_id": key[0],
            "school_year": key[1],
            "instructional_language": key[2],
            "school_name": p["school_name"],
            "reported_model":
                p["reported_models"],
            "reported_design":
                p["program_designs"],
            "academic_rows": len(rows),
            "numeric_primary_proficiency_rows":
                sum(numeric(r) for r in rows),
            "all_students_primary_proficiency_rows":
                sum(
                    numeric(r)
                    and r["student_group_bucket"]
                    == "all_students"
                    for r in rows
                ),
            "english_learner_primary_proficiency_rows":
                sum(
                    numeric(r)
                    and r["student_group_bucket"]
                    == "reported_english_learners"
                    for r in rows
                ),
            "ela_primary_proficiency_rows":
                sum(
                    numeric(r)
                    and r["subject"] == "ELA"
                    for r in rows
                ),
            "math_primary_proficiency_rows":
                sum(
                    numeric(r)
                    and r["subject"] == "Math"
                    for r in rows
                ),
            "coverage_status":
                "academic_rows_found"
                if rows else
                "no_matching_academic_rows",
            "outcome_scope":
                "school_not_DL_participants"
        })

    write_csv(
        output / "wa_academic_coverage.csv",
        coverage,
        list(coverage[0])
    )

    report = {
        "generated_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "source_dataset": DATASET,
        "source_url": SOURCE,
        "source_rows_downloaded": len(raw),
        "registry_school_language_years":
            len(registry),
        "school_years_matched":
            len(matched_keys),
        "grade_3_8_ela_math_source_rows":
            len(assessment),
        "school_language_year_joined_rows":
            len(joined),
        "distinct_schools_with_ela_math":
            len({
                r["state_school_id"]
                for r in assessment
            }),
        "program_language_years_with_results":
            sum(
                r["academic_rows"] > 0
                for r in coverage
            ),
        "program_language_years_without_results":
            sum(
                r["academic_rows"] == 0
                for r in coverage
            ),
        "primary_proficiency_rows_numeric":
            sum(
                r[
                    "pct_consistent_grade_or_above_status"
                ] == "numeric_unverified"
                for r in assessment
            ),
        "english_learner_primary_proficiency_rows_numeric":
            sum(
                r["student_group_bucket"]
                == "reported_english_learners"
                and r[
                    "pct_consistent_grade_or_above_status"
                ] == "numeric_unverified"
                for r in assessment
            ),
        "year_rows":
            dict(sorted(year_counts.items())),
        "test_administrations":
            dict(Counter(
                r["testadministration"]
                for r in assessment
            )),
        "test_administration_groups":
            dict(Counter(
                r["test_administration_group"]
                for r in assessment
            )),
        "student_groups_top_30":
            Counter(
                r["student_group"]
                for r in assessment
            ).most_common(30),
        "field_value_statuses": {
            metric: {
                status: count
                for (name, status), count
                in statuses.items()
                if name == metric
            }
            for _, metric in METRICS
        },
        "duplicate_assessment_keys":
            sum(
                count > 1
                for count in duplicates.values()
            ),
        "duplicate_key_examples": [
            list(key) + [count]
            for key, count in duplicates.items()
            if count > 1
        ][:20],
        "metric_definitions": {
            "pct_consistent_grade_or_above":
                "Levels 3-4; primary proficiency candidate",
            "pct_foundational_grade_or_above":
                "Levels 2-4; broader achievement measure",
            "individual_levels":
                "Source percentages preserved independently"
        },
        "warnings": [
            "School results are not verified DL-participant outcomes.",
            "Schoolwide results appear once per reported DL language in the joined file.",
            "Suppressed and nonreported values are not zeros.",
            "Published numeric percentages need independent verification.",
            "OSPI revised reporting denominators in 2026.",
            "OSPI corrected some historical level distributions in October 2026."
        ]
    }

    (
        output / "wa_academic_report.json"
    ).write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(
        json.dumps({
            "downloaded": len(raw),
            "academic_rows": len(assessment),
            "joined_rows": len(joined),
            "school_language_years_with_academics":
                report[
                    "program_language_years_with_results"
                ],
            "numeric_primary_proficiency":
                report[
                    "primary_proficiency_rows_numeric"
                ]
        }, indent=2),
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
        help="Optional local testing data"
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
                "Empty DL registry"
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

        if any(
            k not in registry[0]
            for k in required
        ):
            raise ValueError(
                "DL registry missing required fields"
            )

        raw = collect(
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
            args.output / "wa_academic_error.txt"
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
