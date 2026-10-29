
#!/usr/bin/env python3
"""
Screen the 2023-24 national CRDC for elementary
schools with more than 20% English learners.

Usage (from repository root):

python3 analysis/national_crdc/screen_national_crdc.py \
    /tmp/crdc/2023-24-crdc-data.zip \
    --member 'SCH/Enrollment.csv' \
    --directory /tmp/crdc/2023-24-crdc-data.zip \
    --directory-member 'SCH/School Characteristics.csv' \
    --output output/national_crdc/2023_24

A high-EL flag identifies a school to investigate.
It does not establish that the school offers
dual-language instruction.
"""

import argparse
import csv
import io
import json
import re
import zipfile

from collections import Counter
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
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
}

GRADES = ["PS", "KG"] + [
    f"G{i:02d}" for i in range(1, 13)
]

ELEMENTARY = {
    "KG", "G01", "G02",
    "G03", "G04", "G05",
}

SUMMARY_KEYS = [
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
    "unassessed_reason",
    "sex_x_handling",
    "data_source",
    "source_url",
]


# ========================================
# FILE HANDLING
# ========================================

def open_csv(path, member=None):
    """
    Open a CSV on disk or a CSV inside a ZIP.
    Return the file handle and ZIP archive.
    """

    if path.suffix.lower() != ".zip":
        handle = path.open(
            "r",
            encoding="utf-8-sig",
            errors="replace",
            newline="",
        )
        return handle, None

    archive = zipfile.ZipFile(path)

    names = [
        name
        for name in archive.namelist()
        if name.lower().endswith(".csv")
    ]

    if not member:
        if len(names) != 1:
            archive.close()
            raise ValueError(
                "Specify a CSV member with "
                "--member or --directory-member"
            )
        member = names[0]

    if member not in names:
        archive.close()
        raise ValueError(
            f"CSV not found in ZIP: {member}"
        )

    handle = io.TextIOWrapper(
        archive.open(member),
        encoding="utf-8-sig",
        errors="replace",
        newline="",
    )

    return handle, archive


def get_column(
    headers,
    *candidates,
    required=False,
):
    names = {
        name.strip().upper(): name
        for name in headers
    }

    for candidate in candidates:
        if candidate.upper() in names:
            return names[candidate.upper()]

    if required:
        raise ValueError(
            "Missing required column: "
            f"one of {candidates}"
        )

    return None


# ========================================
# COUNT AND CODE HANDLING
# ========================================

def int_count(raw):
    """
    Accept nonnegative integer counts only.

    Missing, suppressed, and negative CRDC
    reserve codes return None, never zero.
    """

    raw = str(
        raw if raw is not None else ""
    ).strip().replace(",", "")

    if not re.fullmatch(
        r"\d+(?:\.0+)?",
        raw,
    ):
        return None

    return int(float(raw))


def reserve_label(raw):
    """
    Record the kinds of reporting codes
    encountered, for auditing.
    """

    raw = str(
        raw if raw is not None else ""
    ).strip()

    if int_count(raw) is not None:
        return "numeric"

    if not raw:
        return "blank"

    return raw


def is_not_applicable(raw):
    """
    CRDC reserve code -9 indicates
    not applicable or skipped.
    """

    value = str(
        raw if raw is not None else ""
    ).strip()

    return value in ("-9", "-9.0")


def is_yes(raw):
    return str(raw or "").strip().upper() in (
        "YES", "Y", "TRUE", "1"
    )


# ========================================
# SCHOOL IDENTIFIERS
# ========================================

def id_columns(headers):
    return {
        name: get_column(headers, name)
        for name in (
            "NCESSCH",
            "NCES_SCH_ID",
            "NCES_SCHOOL_ID",
            "COMBOKEY",
            "SCH_ID",
            "LEAID",
            "SCHID",
        )
    }


def school_id(row, columns):
    """
    Prefer a 12-digit NCES school ID.
    Otherwise construct from LEAID/SCHID.
    """

    for key in (
        "NCESSCH",
        "NCES_SCH_ID",
        "NCES_SCHOOL_ID",
        "COMBOKEY",
        "SCH_ID",
    ):
        field = columns.get(key)

        value = (
            str(row.get(field, "") or "").strip()
            if field else ""
        )

        if (
            len(value) == 12
            and value.isdigit()
        ):
            return value

    lea_field = columns.get("LEAID")
    sch_field = columns.get("SCHID")

    lea = (
        str(
            row.get(lea_field, "") or ""
        ).strip()
        if lea_field else ""
    )

    sch = (
        str(
            row.get(sch_field, "") or ""
        ).strip()
        if sch_field else ""
    )

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
# SCHOOL GRADE DIRECTORY
# ========================================

def read_grade_directory(path, member):
    """
    Read grades offered by each school
    from SCH/School Characteristics.csv.
    """

    grades_by_school = {}

    handle, archive = open_csv(
        path, member
    )

    try:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []

        keys = id_columns(headers)

        grade_fields = {
            grade: get_column(
                headers,
                f"SCH_GRADE_{grade}",
            )
            for grade in GRADES
        }

        if not any(
            grade_fields.values()
        ):
            raise ValueError(
                "No SCH_GRADE_* columns "
                "in School Characteristics"
            )

        for row in reader:
            sid = school_id(row, keys)

            if not sid:
                continue

            if sid in grades_by_school:
                raise ValueError(
                    "Duplicate school in "
                    f"characteristics: {sid}"
                )

            grades_by_school[sid] = [
                grade
                for grade, field
                in grade_fields.items()
                if (
                    field
                    and is_yes(row.get(field))
                )
            ]

    finally:
        handle.close()

        if archive:
            archive.close()

    return grades_by_school


# ========================================
# ENROLLMENT COLUMNS
# ========================================

def enrollment_columns(headers):
    result = id_columns(headers)

    choices = {
        "state": (
            "LEA_STATE", "STATE"
        ),
        "school": (
            "SCH_NAME", "SCHOOL_NAME"
        ),
        "district": (
            "LEA_NAME", "DISTRICT_NAME"
        ),
        "city": (
            "SCH_CITY", "LEA_CITY"
        ),
        "el_m": (
            "SCH_ENR_EL_M",
        ),
        "el_f": (
            "SCH_ENR_EL_F",
        ),
        "el_x": (
            "SCH_ENR_EL_X",
        ),
        "tot_m": (
            "TOT_ENR_M",
        ),
        "tot_f": (
            "TOT_ENR_F",
        ),
        "tot_x": (
            "TOT_ENR_X",
        ),
    }

    required = {
        "state",
        "el_m",
        "el_f",
        "tot_m",
        "tot_f",
    }

    for key, names in choices.items():
        result[key] = get_column(
            headers,
            *names,
            required=key in required,
        )

    if bool(result["el_x"]) != bool(
        result["tot_x"]
    ):
        raise ValueError(
            "Only one of the paired X-category "
            "enrollment fields exists"
        )

    return result


# ========================================
# ENGLISH LEARNER CALCULATION
# ========================================

def evaluate_counts(
    row,
    columns,
    diagnostic_pairs,
):
    """
    Calculate EL enrollment and total
    enrollment.

    Male and female counts are required.

    Additional sex-category X counts:
      - Include when numeric.
      - Exclude if both fields are -9.
      - Do not convert suppressed or
        missing values to zero.

    Returns:
      el, total, status, reason, x_handling
    """

    em = int_count(
        row.get(columns["el_m"])
    )

    ef = int_count(
        row.get(columns["el_f"])
    )

    tm = int_count(
        row.get(columns["tot_m"])
    )

    tf = int_count(
        row.get(columns["tot_f"])
    )

    if None in (em, ef, tm, tf):
        return (
            None,
            None,
            "unassessed",
            "missing_or_suppressed_male_female",
            "not_evaluated",
        )

    el = em + ef
    total = tm + tf

    x_handling = "no_x_columns"

    if columns["el_x"]:
        el_raw = row.get(
            columns["el_x"]
        )

        tot_raw = row.get(
            columns["tot_x"]
        )

        ex = int_count(el_raw)
        tx = int_count(tot_raw)

        pattern = (
            f"EL_X={reserve_label(el_raw)};"
            f"TOT_X={reserve_label(tot_raw)}"
        )

        diagnostic_pairs[pattern] += 1

        if (
            ex is not None
            and tx is not None
        ):
            el += ex
            total += tx

            x_handling = (
                "included_reported_x"
            )

        elif (
            is_not_applicable(el_raw)
            and is_not_applicable(tot_raw)
        ):
            # Both fields are explicitly
            # not applicable.
            # Use the male/female totals.

            x_handling = (
                "x_not_applicable_both_minus9"
            )

        elif (
            tx == 0
            and is_not_applicable(el_raw)
        ):
            # A reported total of zero in
            # this category implies zero
            # English learners in it.

            x_handling = (
                "x_zero_total_el_not_applicable"
            )

        else:
            # Suppressed or inconsistent X
            # values cannot safely be
            # assumed to equal zero.

            return (
                None,
                None,
                "unassessed",
                "missing_or_suppressed_x",
                "x_unusable",
            )

    if total <= 0:
        return (
            None,
            None,
            "unassessed",
            "zero_or_invalid_total",
            x_handling,
        )

    if el > total:
        return (
            None,
            None,
            "unassessed",
            "el_greater_than_total",
            x_handling,
        )

    return (
        el,
        total,
        "assessed",
        "",
        x_handling,
    )


# ========================================
# NATIONAL SCREEN
# ========================================

def screen(
    input_file,
    output_dir,
    member,
    directory,
    directory_member,
):

    if directory is None:
        raise ValueError(
            "--directory must point to "
            "the CRDC school-characteristics "
            "CSV or ZIP"
        )

    print(
        "Reading national school "
        "grade configurations..."
    )

    grade_directory = read_grade_directory(
        directory,
        directory_member,
    )

    print(
        f"Loaded {len(grade_directory):,} "
        "school identities."
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    counts = {
        state: Counter()
        for state in STATES
    }

    other = Counter()
    reasons = Counter()
    x_pairs = Counter()

    seen = set()

    handle, archive = open_csv(
        input_file,
        member,
    )

    try:
        reader = csv.DictReader(handle)

        headers = reader.fieldnames or []

        cols = enrollment_columns(headers)

        schema = {
            "columns_used": cols,
            "input": str(input_file),
            "enrollment_member": member,
            "characteristics_member":
                directory_member,
        }

        all_path = (
            output_dir
            / "school_screen_all_2023_24.csv"
        )

        candidate_path = (
            output_dir
            / "candidates_over_20_2023_24.csv"
        )

        with (
            all_path.open(
                "w",
                newline="",
                encoding="utf-8",
            ) as fullfile,
            candidate_path.open(
                "w",
                newline="",
                encoding="utf-8",
            ) as candidatefile,
        ):

            full_writer = csv.DictWriter(
                fullfile,
                fieldnames=OUTPUT_COLS,
            )

            candidate_writer = csv.DictWriter(
                candidatefile,
                fieldnames=OUTPUT_COLS,
            )

            full_writer.writeheader()
            candidate_writer.writeheader()

            print(
                "Screening national "
                "enrollment records..."
            )

            for row in reader:

                raw_state = str(
                    row.get(
                        cols["state"], ""
                    ) or ""
                ).strip().upper()

                state = STATE_NAMES.get(
                    raw_state,
                    raw_state,
                )

                if state not in STATES:
                    other[
                        "outside_50_states_dc"
                    ] += 1
                    continue

                count = counts[state]

                count[
                    "all_school_records"
                ] += 1

                sid = school_id(
                    row,
                    cols,
                )

                if not sid:
                    count[
                        "no_valid_nces_id"
                    ] += 1
                    continue

                if (state, sid) in seen:
                    raise ValueError(
                        "Duplicate school record: "
                        f"{state} {sid}"
                    )

                seen.add((state, sid))

                grades = grade_directory.get(
                    sid, []
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

                number_grades = [
                    int(g[1:])
                    for g in grades
                    if re.fullmatch(
                        r"G\d{2}",
                        g,
                    )
                ]

                high = max(
                    number_grades,
                    default=0,
                )

                low = min(
                    number_grades,
                    default=0,
                )

                elementary_only = (
                    high <= 5
                )

                if elementary_only:
                    count[
                        "elementary_only"
                    ] += 1

                (
                    el,
                    total,
                    status,
                    reason,
                    x_handling,
                ) = evaluate_counts(
                    row,
                    cols,
                    x_pairs,
                )

                if status == "unassessed":

                    count[
                        "unassessed"
                    ] += 1

                    reasons[reason] += 1

                    pct = None
                    flag = None

                    status = (
                        "unassessed_missing_or_invalid"
                    )

                else:
                    pct = round(
                        100 * el / total,
                        6,
                    )

                    # Strictly greater than 20%.
                    # Integer arithmetic avoids
                    # rounding errors.

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

                record = {
                    "state": state,
                    "school_year": "2023-24",
                    "nces_school_id": sid,

                    "school_name": (
                        row.get(
                            cols["school"], ""
                        )
                        if cols["school"]
                        else ""
                    ),

                    "district_name": (
                        row.get(
                            cols["district"], ""
                        )
                        if cols["district"]
                        else ""
                    ),

                    "city": (
                        row.get(
                            cols["city"], ""
                        )
                        if cols["city"]
                        else ""
                    ),

                    "grade_low": (
                        low
                        if low
                        else (
                            "KG"
                            if "KG" in grades
                            else "PS"
                        )
                    ),

                    "grade_high": high,

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
                        pct
                        if pct is not None
                        else ""
                    ),

                    "flag_over_20": (
                        str(flag).lower()
                        if flag is not None
                        else ""
                    ),

                    "status": status,

                    "unassessed_reason": (
                        reason
                    ),

                    "sex_x_handling": (
                        x_handling
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

    finally:
        handle.close()

        if archive:
            archive.close()

    # ====================================
    # STATE SUMMARY
    # ====================================

    state_path = (
        output_dir
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
                *SUMMARY_KEYS,
            ],
        )

        writer.writeheader()

        for state in STATES:
            writer.writerow({
                "state": state,
                **{
                    key: counts[state][key]
                    for key in SUMMARY_KEYS
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
        for key in SUMMARY_KEYS
    }

    result = {
        "dataset": (
            "2023-24 CRDC school-level, "
            "50 states and DC"
        ),

        "generated_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),

        "strict_threshold": (
            ">20% EL of total reported "
            "school enrollment"
        ),

        "not_a_dual_language_program_classifier":
            True,

        "national": national,

        "unassessed_reasons": (
            dict(reasons)
        ),

        "x_category_reporting_patterns": (
            dict(x_pairs)
        ),

        "other_records": (
            dict(other)
        ),
    }

    summary_path = (
        output_dir
        / "national_summary.json"
    )

    summary_path.write_text(
        json.dumps(
            result,
            indent=2,
        ),
        encoding="utf-8",
    )

    schema_path = (
        output_dir
        / "source_schema.json"
    )

    schema_path.write_text(
        json.dumps(
            schema,
            indent=2,
        ),
        encoding="utf-8",
    )

    # ====================================
    # VALIDATION
    # ====================================

    assessed = (
        national["flagged"]
        + national["not_flagged"]
    )

    if assessed == 0:
        raise RuntimeError(
            "Zero elementary schools evaluated. "
            "See national_summary.json for "
            "missing-value diagnostics. "
            "Do not interpret zero as no "
            "candidate schools."
        )

    if (
        assessed
        + national["unassessed"]
        != national["elementary_serving"]
    ):
        raise AssertionError(
            "Screening count "
            "reconciliation failed"
        )

    print(
        "\nNational screening completed."
    )

    print(
        f"Elementary-serving schools: "
        f"{national['elementary_serving']:,}"
    )

    print(
        f"Above 20% ELL: "
        f"{national['flagged']:,}"
    )

    print(
        f"At or below 20%: "
        f"{national['not_flagged']:,}"
    )

    print(
        f"Unassessed: "
        f"{national['unassessed']:,}"
    )

    print(
        f"\nResults saved to {output_dir}"
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
        help=(
            "Enrollment CSV "
            "inside the source ZIP"
        ),
    )

    parser.add_argument(
        "--directory",
        type=Path,
        help=(
            "Characteristics CSV or ZIP"
        ),
    )

    parser.add_argument(
        "--directory-member",
        help=(
            "Characteristics CSV "
            "inside ZIP"
        ),
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

            for member in archive.infolist():

                if member.filename.lower().endswith(
                    ".csv"
                ):
                    print(
                        member.filename,
                        member.file_size,
                    )

        return

    result = screen(
        args.file,
        args.output,
        args.member,
        args.directory,
        args.directory_member,
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
