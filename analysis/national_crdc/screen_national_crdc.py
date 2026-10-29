
#!/usr/bin/env python3
"""
National 2023-24 CRDC English Learner Screening.

Find elementary-serving schools with more than
20% English learners.

IMPORTANT:
The federal 2023-24 public-use release redacts
nonbinary enrollment fields with code -10.

Where those fields are redacted, the screening
uses male + female reported enrollment only.
These results are provisional screening estimates,
not exact all-student percentages.

No suppressed value is interpreted as zero.

The existing GitHub Action can run this script.
"""

import argparse
import csv
import io
import json
import re
import zipfile

from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


csv.field_size_limit(5_000_000)

SOURCE = "https://ocrdata.ed.gov/data"

STATES = """
AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA
KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM
NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA
WV WI WY
""".split()

STATE_NAMES = {
    name.upper(): abbreviation
    for name, abbreviation in [
        ("Alabama", "AL"),
        ("Alaska", "AK"),
        ("Arizona", "AZ"),
        ("Arkansas", "AR"),
        ("California", "CA"),
        ("Colorado", "CO"),
        ("Connecticut", "CT"),
        ("Delaware", "DE"),
        ("District of Columbia", "DC"),
        ("Florida", "FL"),
        ("Georgia", "GA"),
        ("Hawaii", "HI"),
        ("Idaho", "ID"),
        ("Illinois", "IL"),
        ("Indiana", "IN"),
        ("Iowa", "IA"),
        ("Kansas", "KS"),
        ("Kentucky", "KY"),
        ("Louisiana", "LA"),
        ("Maine", "ME"),
        ("Maryland", "MD"),
        ("Massachusetts", "MA"),
        ("Michigan", "MI"),
        ("Minnesota", "MN"),
        ("Mississippi", "MS"),
        ("Missouri", "MO"),
        ("Montana", "MT"),
        ("Nebraska", "NE"),
        ("Nevada", "NV"),
        ("New Hampshire", "NH"),
        ("New Jersey", "NJ"),
        ("New Mexico", "NM"),
        ("New York", "NY"),
        ("North Carolina", "NC"),
        ("North Dakota", "ND"),
        ("Ohio", "OH"),
        ("Oklahoma", "OK"),
        ("Oregon", "OR"),
        ("Pennsylvania", "PA"),
        ("Rhode Island", "RI"),
        ("South Carolina", "SC"),
        ("South Dakota", "SD"),
        ("Tennessee", "TN"),
        ("Texas", "TX"),
        ("Utah", "UT"),
        ("Vermont", "VT"),
        ("Virginia", "VA"),
        ("Washington", "WA"),
        ("West Virginia", "WV"),
        ("Wisconsin", "WI"),
        ("Wyoming", "WY"),
    ]
}

GRADES = ["PS", "KG"] + [
    f"G{i:02d}" for i in range(1, 13)
]

ELEMENTARY = {
    "KG", "G01", "G02",
    "G03", "G04", "G05",
}

COUNT_KEYS = [
    "all_school_records",
    "elementary_serving",
    "elementary_only",
    "flagged",
    "not_flagged",
    "unassessed",
    "no_grade_flags",
    "no_valid_nces_id",
    "not_elementary_serving",
]

OUTPUT_COLS = [
    "state",
    "school_year",
    "nces_school_id",
    "school_name",
    "district_name",
    "city",
    "grade_low",
    "grade_high",
    "grades_served",
    "elementary_only",
    "el_count",
    "total_enrollment",
    "el_percent",
    "flag_over_20",
    "status",
    "measurement_basis",
    "unassessed_reason",
    "x_total_code",
    "x_el_code",
    "data_source",
    "source_url",
]


# ========================================
# FILE HANDLING
# ========================================

@contextmanager
def open_csv(path, member=None):
    """
    Open an ordinary CSV or a CSV within a ZIP.
    """

    if path.suffix.lower() != ".zip":
        with path.open(
            "r",
            encoding="utf-8-sig",
            errors="replace",
            newline="",
        ) as f:
            yield f

        return

    with zipfile.ZipFile(path) as archive:

        members = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".csv")
        ]

        if member is None:
            if len(members) != 1:
                raise ValueError(
                    "ZIP contains multiple CSVs. "
                    "Specify --member."
                )

            member = members[0]

        if member not in members:
            raise ValueError(
                f"CSV not found: {member}"
            )

        with archive.open(member) as raw:
            with io.TextIOWrapper(
                raw,
                encoding="utf-8-sig",
                errors="replace",
                newline="",
            ) as f:
                yield f


def field(headers, name, required=True):
    lookup = {
        h.upper(): h
        for h in headers
    }

    result = lookup.get(name.upper())

    if result is None and required:
        raise ValueError(
            f"Required CRDC column missing: {name}"
        )

    return result


# ========================================
# SCHOOL IDENTIFICATION
# ========================================

def school_id(row, headers):
    """
    Return a 12-digit NCES school ID.
    """

    for name in (
        "COMBOKEY",
        "NCESSCH",
        "NCES_SCH_ID",
        "NCES_SCHOOL_ID",
    ):
        col = field(
            headers,
            name,
            required=False,
        )

        if col:
            value = str(
                row.get(col) or ""
            ).strip()

            if re.fullmatch(
                r"\d{12}",
                value,
            ):
                return value

    lea_col = field(
        headers,
        "LEAID",
        required=False,
    )

    sch_col = field(
        headers,
        "SCHID",
        required=False,
    )

    if lea_col and sch_col:

        lea = str(
            row.get(lea_col) or ""
        ).strip()

        sch = str(
            row.get(sch_col) or ""
        ).strip()

        if (
            lea.isdigit()
            and sch.isdigit()
            and len(lea) <= 7
            and len(sch) <= 5
        ):
            return (
                lea.zfill(7)
                + sch.zfill(5)
            )

    return ""


# ========================================
# NUMERIC AND MISSING VALUE HANDLING
# ========================================

def parse_count(raw):
    """
    Accept nonnegative integer counts.

    Negative reserve codes such as -2,
    -9, and -10 are not numeric counts.
    """

    value = str(
        raw if raw is not None else ""
    ).strip().replace(",", "")

    if re.fullmatch(
        r"\d+(?:\.0+)?",
        value,
    ):
        return int(float(value))

    return None


def code(raw):
    """
    Preserve reporting-code information
    for diagnostics.
    """

    value = str(
        raw if raw is not None else ""
    ).strip()

    if parse_count(value) is not None:
        return "number"

    return value or "blank"


def yes(raw):
    return str(
        raw or ""
    ).strip().upper() in {
        "YES", "Y", "TRUE", "1"
    }


# ========================================
# SCHOOL GRADE CONFIGURATIONS
# ========================================

def read_school_grades(path, member):
    """
    Read SCH/School Characteristics.csv
    and identify grades served.
    """

    result = {}

    with open_csv(
        path,
        member,
    ) as handle:

        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []

        grade_columns = {
            grade: field(
                headers,
                "SCH_GRADE_" + grade,
                required=False,
            )
            for grade in GRADES
        }

        if not any(
            grade_columns.values()
        ):
            raise ValueError(
                "No school grade columns found."
            )

        for row in reader:

            sid = school_id(
                row,
                headers,
            )

            if not sid:
                continue

            if sid in result:
                raise ValueError(
                    f"Duplicate school ID: {sid}"
                )

            offered = [
                grade
                for grade, col
                in grade_columns.items()
                if (
                    col
                    and yes(row.get(col))
                )
            ]

            result[sid] = offered

    return result


# ========================================
# ENGLISH LEARNER CALCULATION
# ========================================

def evaluate(row, columns, diagnostic):
    """
    Calculate the EL proportion.

    When X enrollment is suppressed,
    use male + female counts as a
    provisional screening denominator.

    Suppressed X counts are not zero.
    """

    values = {}

    for name in (
        "el_m",
        "el_f",
        "total_m",
        "total_f",
    ):
        raw = row.get(
            columns[name]
        )

        value = parse_count(raw)

        diagnostic[
            "core_code_counts"
        ][
            f"{name}:{code(raw)}"
        ] += 1

        values[name] = value

    # Male and female counts must be usable.

    if any(
        value is None
        for value in values.values()
    ):
        return (
            None,
            None,
            "",
            "missing_or_suppressed_male_female",
        )

    el = (
        values["el_m"]
        + values["el_f"]
    )

    total = (
        values["total_m"]
        + values["total_f"]
    )

    basis = "male_female_only"

    # ------------------------------------
    # Handle X category separately.
    # ------------------------------------

    if (
        columns["el_x"]
        and columns["total_x"]
    ):

        raw_el_x = row.get(
            columns["el_x"]
        )

        raw_total_x = row.get(
            columns["total_x"]
        )

        el_x = parse_count(
            raw_el_x
        )

        total_x = parse_count(
            raw_total_x
        )

        pattern = (
            f"el:{code(raw_el_x)}"
            f"|total:{code(raw_total_x)}"
        )

        diagnostic[
            "x_field_pairs"
        ][pattern] += 1

        if (
            el_x is not None
            and total_x is not None
        ):

            el += el_x
            total += total_x

            basis = (
                "all_reported_sex_categories"
            )

        elif (
            code(raw_el_x) in ("-9", "-9.0")
            and code(raw_total_x)
            in ("-9", "-9.0")
        ):

            basis = (
                "male_female_x_not_applicable"
            )

        elif (
            code(raw_el_x) in ("-10", "-10.0")
            or code(raw_total_x)
            in ("-10", "-10.0")
        ):

            # Federal 2023-24 release
            # redacts these fields.
            #
            # We can use M+F for screening,
            # but not claim an exact
            # all-student percentage.

            basis = (
                "male_female_only_x_redacted"
            )

        else:

            basis = (
                "male_female_only_x_unavailable"
            )

    if total <= 0:

        return (
            None,
            None,
            basis,
            "zero_total",
        )

    if el > total:

        return (
            None,
            None,
            basis,
            "el_exceeds_total",
        )

    return (
        el,
        total,
        basis,
        "",
    )


# ========================================
# NATIONAL SCREENING
# ========================================

def run(
    input_file,
    member,
    directory,
    directory_member,
    output,
):

    if directory is None:
        raise ValueError(
            "Use --directory to specify "
            "School Characteristics."
        )

    output.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "Reading national school "
        "grade configurations...",
        flush=True,
    )

    grades_by_school = read_school_grades(
        directory,
        directory_member,
    )

    print(
        f"Loaded {len(grades_by_school):,} "
        "school characteristics records.",
        flush=True,
    )

    counts = {
        state: Counter()
        for state in STATES
    }

    excluded = Counter()

    diagnostic = {
        "core_code_counts": Counter(),
        "x_field_pairs": Counter(),
        "unassessed_reasons": Counter(),
        "measurement_bases": Counter(),
    }

    seen = set()

    all_path = (
        output
        / "school_screen_all_2023_24.csv"
    )

    candidate_path = (
        output
        / "candidates_over_20_2023_24.csv"
    )

    with (
        open_csv(
            input_file,
            member,
        ) as source,
        all_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as full_file,
        candidate_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as candidate_file,
    ):

        reader = csv.DictReader(
            source
        )

        headers = reader.fieldnames or []

        columns = {
            "state": field(
                headers, "LEA_STATE"
            ),
            "school": field(
                headers, "SCH_NAME"
            ),
            "district": field(
                headers, "LEA_NAME"
            ),
            "el_m": field(
                headers, "SCH_ENR_EL_M"
            ),
            "el_f": field(
                headers, "SCH_ENR_EL_F"
            ),
            "total_m": field(
                headers, "TOT_ENR_M"
            ),
            "total_f": field(
                headers, "TOT_ENR_F"
            ),
            "el_x": field(
                headers,
                "SCH_ENR_EL_X",
                required=False,
            ),
            "total_x": field(
                headers,
                "TOT_ENR_X",
                required=False,
            ),
        }

        full_writer = csv.DictWriter(
            full_file,
            fieldnames=OUTPUT_COLS,
        )

        candidate_writer = csv.DictWriter(
            candidate_file,
            fieldnames=OUTPUT_COLS,
        )

        full_writer.writeheader()
        candidate_writer.writeheader()

        print(
            "Screening national enrollment...",
            flush=True,
        )

        for row in reader:

            raw_state = str(
                row.get(
                    columns["state"]
                ) or ""
            ).strip().upper()

            state = STATE_NAMES.get(
                raw_state,
                raw_state,
            )

            if state not in counts:

                excluded[
                    "outside_50_states_dc"
                ] += 1

                continue

            count = counts[state]

            count[
                "all_school_records"
            ] += 1

            sid = school_id(
                row,
                headers,
            )

            if not sid:

                count[
                    "no_valid_nces_id"
                ] += 1

                continue

            if sid in seen:
                raise ValueError(
                    f"Duplicate school record: {sid}"
                )

            seen.add(sid)

            grades = (
                grades_by_school.get(
                    sid, []
                )
            )

            if not grades:

                count[
                    "no_grade_flags"
                ] += 1

                continue

            if not ELEMENTARY.intersection(
                grades
            ):

                count[
                    "not_elementary_serving"
                ] += 1

                continue

            count[
                "elementary_serving"
            ] += 1

            numeric_grades = [
                int(grade[1:])
                for grade in grades
                if re.fullmatch(
                    r"G\d{2}",
                    grade,
                )
            ]

            highest = max(
                numeric_grades,
                default=0,
            )

            lowest = min(
                numeric_grades,
                default=0,
            )

            elementary_only = (
                highest <= 5
            )

            if elementary_only:

                count[
                    "elementary_only"
                ] += 1

            # ----------------------------
            # Calculate EL share.
            # ----------------------------

            (
                el,
                total,
                basis,
                reason,
            ) = evaluate(
                row,
                columns,
                diagnostic,
            )

            diagnostic[
                "measurement_bases"
            ][
                basis or "unavailable"
            ] += 1

            flag = None
            percent = None

            if reason:

                count[
                    "unassessed"
                ] += 1

                diagnostic[
                    "unassessed_reasons"
                ][reason] += 1

                status = "unassessed"

            else:

                percent = round(
                    100 * el / total,
                    6,
                )

                # Strictly greater than 20%.
                # No rounding ambiguity.

                flag = (
                    5 * el > total
                )

                count[
                    "flagged"
                    if flag
                    else "not_flagged"
                ] += 1

                status = (
                    "candidate_over_20"
                    if flag
                    else "at_or_below_20"
                )

            # ----------------------------
            # Record each school.
            # ----------------------------

            record = {
                "state": state,

                "school_year": "2023-24",

                "nces_school_id": sid,

                "school_name": row.get(
                    columns["school"], ""
                ),

                "district_name": row.get(
                    columns["district"], ""
                ),

                "city": "",

                "grade_low": (
                    lowest
                    if lowest
                    else (
                        "KG"
                        if "KG" in grades
                        else "PS"
                    )
                ),

                "grade_high": (
                    highest
                    if highest
                    else (
                        "KG"
                        if "KG" in grades
                        else "PS"
                    )
                ),

                "grades_served": (
                    ";".join(grades)
                ),

                "elementary_only": (
                    str(
                        elementary_only
                    ).lower()
                ),

                "el_count": (
                    el
                    if el is not None
                    else ""
                ),

                "total_enrollment": (
                    total
                    if total is not None
                    else ""
                ),

                "el_percent": (
                    percent
                    if percent is not None
                    else ""
                ),

                "flag_over_20": (
                    str(flag).lower()
                    if flag is not None
                    else ""
                ),

                "status": status,

                "measurement_basis": basis,

                "unassessed_reason": reason,

                "x_total_code": (
                    code(
                        row.get(
                            columns["total_x"]
                        )
                    )
                    if columns["total_x"]
                    else "absent"
                ),

                "x_el_code": (
                    code(
                        row.get(
                            columns["el_x"]
                        )
                    )
                    if columns["el_x"]
                    else "absent"
                ),

                "data_source": (
                    "US DOE CRDC 2023-24"
                ),

                "source_url": SOURCE,
            }

            full_writer.writerow(
                record
            )

            if flag:
                candidate_writer.writerow(
                    record
                )

    # ====================================
    # STATE SUMMARY
    # ====================================

    state_path = (
        output
        / "state_summary_2023_24.csv"
    )

    with state_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "state",
                *COUNT_KEYS,
            ],
        )

        writer.writeheader()

        for state in STATES:

            writer.writerow({
                "state": state,

                **{
                    key: counts[state][key]
                    for key in COUNT_KEYS
                },
            })

    # ====================================
    # NATIONAL SUMMARY
    # ====================================

    national = {
        key: sum(
            counts[state][key]
            for state in STATES
        )
        for key in COUNT_KEYS
    }

    result = {
        "dataset": (
            "US DOE CRDC 2023-24 "
            "school-level, 50 states and DC"
        ),

        "generated_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),

        "screening_threshold": (
            "Strictly greater than 20%"
        ),

        "screening_note": (
            "Uses M+F reported counts "
            "where X is redacted; "
            "not necessarily full-population "
            "EL percentage."
        ),

        "not_a_dual_language_classifier":
            True,

        "national": national,

        "measurement_bases": dict(
            diagnostic[
                "measurement_bases"
            ]
        ),

        "unassessed_reasons": dict(
            diagnostic[
                "unassessed_reasons"
            ]
        ),

        "x_field_pairs": dict(
            diagnostic[
                "x_field_pairs"
            ]
        ),

        "core_code_counts": dict(
            diagnostic[
                "core_code_counts"
            ]
        ),

        "outside_50_states_dc": dict(
            excluded
        ),
    }

    (
        output
        / "national_summary.json"
    ).write_text(
        json.dumps(
            result,
            indent=2,
        ),
        encoding="utf-8",
    )

    (
        output
        / "source_schema.json"
    ).write_text(
        json.dumps(
            {
                "columns_used": columns,
                "members": [
                    member,
                    directory_member,
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # ====================================
    # VALIDATION
    # ====================================

    evaluated = (
        national["flagged"]
        + national["not_flagged"]
    )

    if (
        evaluated
        + national["unassessed"]
        != national["elementary_serving"]
    ):
        raise AssertionError(
            "National school counts "
            "did not reconcile."
        )

    # Print diagnostics BEFORE raising
    # so the cause is visible in Actions.

    print(
        json.dumps(
            {
                "national": national,

                "measurement_bases":
                    result["measurement_bases"],

                "unassessed_reasons":
                    result["unassessed_reasons"],

                "x_field_pairs":
                    result["x_field_pairs"],
            },
            indent=2,
        ),
        flush=True,
    )

    if evaluated == 0:
        raise RuntimeError(
            "No schools evaluated. "
            "Inspect national_summary.json "
            "and reporting-code diagnostics."
        )

    print(
        f"Completed: "
        f"{national['flagged']:,} candidates "
        f"from {evaluated:,} evaluated schools.",
        flush=True,
    )

    return result


# ========================================
# COMMAND-LINE INTERFACE
# ========================================

def main():

    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "file",
        type=Path,
    )

    parser.add_argument(
        "--member",
    )

    parser.add_argument(
        "--directory",
        type=Path,
    )

    parser.add_argument(
        "--directory-member",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "national_crdc_results"
        ),
    )

    parser.add_argument(
        "--list-members",
        action="store_true",
    )

    args = parser.parse_args()

    if args.list_members:

        with zipfile.ZipFile(
            args.file
        ) as archive:

            for name in archive.namelist():

                if name.lower().endswith(
                    ".csv"
                ):
                    print(name)

        return

    run(
        args.file,
        args.member,
        args.directory,
        args.directory_member,
        args.output,
    )


if __name__ == "__main__":
    main()
