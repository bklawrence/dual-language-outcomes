
#!/usr/bin/env python3
"""
National CRDC 2023-24 English Learner Screening

Find elementary-serving public schools with more than
20% English learners.

Usage:
    python3 screen_national_crdc.py data.csv

    python3 screen_national_crdc.py data.zip \
        --list-members

    python3 screen_national_crdc.py data.zip \
        --member school_file.csv

The national CRDC source archive must be supplied
separately. This program does not download it.

Source: https://ocrdata.ed.gov/data
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

STATES = (
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL "
    "IN IA KS KY LA ME MD MA MI MN MS MO MT "
    "NE NV NH NJ NM NY NC ND OH OK OR PA RI "
    "SC SD TN TX UT VT VA WA WV WI WY"
).split()

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
    "data_source",
    "source_url",
]


def csv_stream(path, member=None):
    if path.suffix.lower() == ".zip":
        archive = zipfile.ZipFile(path)

        members = [
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
            and not name.startswith("__MACOSX/")
        ]

        if member is None:
            if len(members) != 1:
                archive.close()
                raise ValueError(
                    "Multiple CSVs in archive. "
                    "Use --list-members and --member."
                )
            member = members[0]

        if member not in members:
            archive.close()
            raise ValueError(
                f"CSV not found in archive: {member}"
            )

        handle = io.TextIOWrapper(
            archive.open(member),
            encoding="utf-8-sig",
            errors="replace",
            newline="",
        )

        return handle, archive

    handle = path.open(
        "r",
        encoding="utf-8-sig",
        errors="replace",
        newline="",
    )

    return handle, None


def column(headers, *names, required=False):
    index = {
        name.upper().strip(): name
        for name in headers
    }

    for name in names:
        if name.upper() in index:
            return index[name.upper()]

    if required:
        raise ValueError(
            "Missing column. Expected one of: "
            + ", ".join(names)
            + "\nAvailable headers: "
            + ", ".join(headers[:80])
        )

    return None


def num(value):
    value = str(
        value if value is not None else ""
    ).strip().replace(",", "")

    if not re.fullmatch(
        r"\d+(?:\.0+)?",
        value,
    ):
        return None

    return int(float(value))


def yes(value):
    return str(value or "").strip().upper() in (
        "YES", "Y", "TRUE", "1"
    )


def nces_id(row, cols):
    for key in (
        "NCESSCH",
        "NCES_SCH_ID",
        "NCES_SCHOOL_ID",
        "COMBOKEY",
        "SCH_ID",
    ):
        field = cols.get(key)
        value = (
            str(row.get(field, "")).strip()
            if field else ""
        )

        if len(value) == 12 and value.isdigit():
            return value

    lea = str(
        row.get(cols.get("LEAID"), "") or ""
    ).strip()

    sch = str(
        row.get(cols.get("SCHID"), "") or ""
    ).strip()

    if lea.isdigit() and sch.isdigit():
        return lea.zfill(7) + sch.zfill(5)

    return ""


def read_schema(headers, external_grades=False):
    cols = {}

    for name in (
        "NCESSCH",
        "NCES_SCH_ID",
        "NCES_SCHOOL_ID",
        "COMBOKEY",
        "SCH_ID",
        "LEAID",
        "SCHID",
    ):
        cols[name] = column(headers, name)

    if not any(cols.values()):
        raise ValueError(
            "No NCES school identifier fields"
        )

    fields = {
        "state": [
            "LEA_STATE", "STATE",
            "SCH_STATE", "ST"
        ],
        "school": [
            "SCH_NAME", "SCH_NAME_CRDC",
            "SCHOOL_NAME"
        ],
        "district": [
            "LEA_NAME", "DISTRICT_NAME"
        ],
        "city": [
            "SCH_CITY", "LEA_CITY"
        ],
        "elm": [
            "SCH_ENR_EL_M", "SCH_ENR_LEP_M"
        ],
        "elf": [
            "SCH_ENR_EL_F", "SCH_ENR_LEP_F"
        ],
        "totm": [
            "TOT_ENR_M", "SCH_ENR_M"
        ],
        "totf": [
            "TOT_ENR_F", "SCH_ENR_F"
        ],
    }

    for key, names in fields.items():
        cols[key] = column(
            headers,
            *names,
            required=key in (
                "state", "elm", "elf",
                "totm", "totf"
            ),
        )

    grades = [
        "PS", "KG"
    ] + [
        f"G{i:02}" for i in range(1, 13)
    ]

    cols["grades"] = {
        grade: column(
            headers,
            f"SCH_GRADE_{grade}",
        )
        for grade in grades
    }

    elementary = (
        "KG", "G01", "G02",
        "G03", "G04", "G05"
    )

    if (
        not external_grades
        and not any(
            cols["grades"][g]
            for g in elementary
        )
    ):
        raise ValueError(
            "Missing grade-offering columns. "
            "Use a school characteristics file "
            "with --directory."
        )

    for suffix in ("X", "NB", "N"):
        elname = (
            cols["elm"].removesuffix("_M")
            + "_" + suffix
        )
        toname = (
            cols["totm"].removesuffix("_M")
            + "_" + suffix
        )

        cols["el" + suffix] = column(
            headers, elname
        )
        cols["tot" + suffix] = column(
            headers, toname
        )

        if bool(cols["el" + suffix]) != bool(
            cols["tot" + suffix]
        ):
            raise ValueError(
                "Unpaired nonbinary fields: "
                + elname + ", " + toname
            )

    return cols


def screen(
    input_file,
    output_dir,
    member=None,
    directory=None,
    directory_member=None,
):
    grade_by_id = {}

    # Optional separate school-characteristics CSV
    if directory:
        directory_handle, dz = csv_stream(
            directory,
            directory_member,
        )

        try:
            reader = csv.DictReader(
                directory_handle
            )
            headers = reader.fieldnames or []

            dc = {
                name: column(headers, name)
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

            grades = [
                "PS", "KG"
            ] + [
                f"G{i:02}"
                for i in range(1, 13)
            ]

            grade_cols = {
                g: column(
                    headers,
                    f"SCH_GRADE_{g}"
                )
                for g in grades
            }

            if not any(grade_cols.values()):
                raise ValueError(
                    "No grade flags in directory"
                )

            for row in reader:
                sid = nces_id(row, dc)

                if sid:
                    grade_by_id[sid] = [
                        g for g, field
                        in grade_cols.items()
                        if field and yes(
                            row.get(field)
                        )
                    ]

        finally:
            directory_handle.close()
            if dz:
                dz.close()

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    handle, archive = csv_stream(
        input_file,
        member,
    )

    counters = {
        state: Counter()
        for state in STATES
    }

    discarded = Counter()
    seen = set()

    try:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []

        cols = read_schema(
            headers,
            external_grades=bool(directory),
        )

        schema_info = {
            "columns_used": {
                k: v for k, v in cols.items()
                if k != "grades"
            },
            "grade_columns": cols["grades"],
            "input": str(input_file),
            "archive_member": member,
            "headers": headers,
        }

        all_path = (
            output_dir /
            "school_screen_all_2023_24.csv"
        )

        candidate_path = (
            output_dir /
            "candidates_over_20_2023_24.csv"
        )

        with (
            all_path.open(
                "w",
                encoding="utf-8",
                newline="",
            ) as all_file,
            candidate_path.open(
                "w",
                encoding="utf-8",
                newline="",
            ) as candidate_file,
        ):
            writer = csv.DictWriter(
                all_file, OUTPUT_COLS
            )

            candidate_writer = csv.DictWriter(
                candidate_file, OUTPUT_COLS
            )

            writer.writeheader()
            candidate_writer.writeheader()

            for row in reader:
                raw_state = str(
                    row.get(cols["state"]) or ""
                ).strip().upper()

                state = STATE_NAMES.get(
                    raw_state, raw_state
                )

                if state not in STATES:
                    discarded[
                        "outside_50_states_dc"
                    ] += 1
                    continue

                counts = counters[state]
                counts["all_school_records"] += 1

                school = nces_id(
                    row, cols
                )

                if not school:
                    counts[
                        "no_valid_nces_id"
                    ] += 1
                    continue

                if (state, school) in seen:
                    raise ValueError(
                        "Duplicate school ID: "
                        + state + " " + school
                    )

                seen.add((state, school))

                if directory:
                    offered = grade_by_id.get(
                        school, []
                    )
                else:
                    offered = [
                        grade
                        for grade, field
                        in cols["grades"].items()
                        if field and yes(
                            row.get(field)
                        )
                    ]

                if not offered:
                    counts[
                        "no_grade_flags"
                    ] += 1
                    continue

                elementary = (
                    "KG", "G01", "G02",
                    "G03", "G04", "G05"
                )

                if not any(
                    g in offered
                    for g in elementary
                ):
                    counts[
                        "not_elementary_serving"
                    ] += 1
                    continue

                counts[
                    "elementary_serving"
                ] += 1

                numeric_grades = [
                    int(g[1:])
                    for g in offered
                    if re.fullmatch(
                        r"G\d\d", g
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
                    counts[
                        "elementary_only"
                    ] += 1

                totals = [
                    num(row.get(cols["totm"])),
                    num(row.get(cols["totf"])),
                ]

                els = [
                    num(row.get(cols["elm"])),
                    num(row.get(cols["elf"])),
                ]

                # Include additional reported sex
                # categories when matching fields exist.
                for suffix in ("X", "NB", "N"):
                    if cols.get("el" + suffix):
                        totals.append(
                            num(row.get(
                                cols["tot" + suffix]
                            ))
                        )
                        els.append(
                            num(row.get(
                                cols["el" + suffix]
                            ))
                        )

                den = (
                    sum(totals)
                    if all(
                        x is not None
                        for x in totals
                    )
                    else None
                )

                el = (
                    sum(els)
                    if all(
                        x is not None
                        for x in els
                    )
                    else None
                )

                if (
                    den is None
                    or el is None
                    or den <= 0
                    or el > den
                ):
                    status = (
                        "unassessed_missing_or_invalid"
                    )
                    pct = None
                    flag = False
                    counts["unassessed"] += 1

                else:
                    pct = round(
                        100 * el / den, 6
                    )

                    flag = (
                        100 * el > 20 * den
                    )

                    status = (
                        "candidate_over_20"
                        if flag
                        else "at_or_below_20"
                    )

                    counts[
                        "flagged"
                        if flag
                        else "not_flagged"
                    ] += 1

                item = {
                    "state": state,
                    "school_year": "2023-24",
                    "nces_school_id": school,
                    "school_name": (
                        row.get(cols["school"], "")
                        if cols["school"] else ""
                    ),
                    "district_name": (
                        row.get(cols["district"], "")
                        if cols["district"] else ""
                    ),
                    "city": (
                        row.get(cols["city"], "")
                        if cols["city"] else ""
                    ),
                    "grade_low": (
                        lowest if lowest
                        else (
                            "KG" if "KG" in offered
                            else "PS"
                        )
                    ),
                    "grade_high": highest,
                    "grades_served": ";".join(
                        offered
                    ),
                    "elementary_only": str(
                        elementary_only
                    ).lower(),
                    "el_count": (
                        el if el is not None
                        else ""
                    ),
                    "total_enrollment": (
                        den if den is not None
                        else ""
                    ),
                    "el_percent": (
                        pct if pct is not None
                        else ""
                    ),
                    "flag_over_20": (
                        str(flag).lower()
                        if pct is not None
                        else ""
                    ),
                    "status": status,
                    "data_source": (
                        "US DOE CRDC 2023-24"
                    ),
                    "source_url": SOURCE,
                }

                writer.writerow(item)

                if flag:
                    candidate_writer.writerow(
                        item
                    )

    finally:
        handle.close()
        if archive:
            archive.close()

    fields = [
        "state",
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

    with (
        output_dir /
        "state_summary_2023_24.csv"
    ).open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file, fields
        )
        writer.writeheader()

        for state in STATES:
            writer.writerow({
                "state": state,
                **{
                    k: counters[state][k]
                    for k in fields
                    if k != "state"
                },
            })

    national = {
        key: sum(
            counters[s][key]
            for s in STATES
        )
        for key in fields
        if key != "state"
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
            "> 20% EL / total school enrollment"
        ),
        "not_a_dual_language_program_classifier":
            True,
        "national": national,
        "other_records": dict(discarded),
    }

    (
        output_dir / "national_summary.json"
    ).write_text(
        json.dumps(
            result, indent=2
        ),
        encoding="utf-8",
    )

    (
        output_dir / "source_schema.json"
    ).write_text(
        json.dumps(
            schema_info, indent=2
        ),
        encoding="utf-8",
    )

    return result


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "file",
        type=Path,
    )

    parser.add_argument(
        "--list-members",
        action="store_true",
    )

    parser.add_argument(
        "--member",
        help="CSV member name in ZIP",
    )

    parser.add_argument(
        "--directory",
        type=Path,
        help="Separate CRDC characteristics file",
    )

    parser.add_argument(
        "--directory-member",
        help="School characteristics CSV in ZIP",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "national_crdc_results"
        ),
    )

    args = parser.parse_args()

    if args.list_members:
        with zipfile.ZipFile(
            args.file
        ) as archive:
            for f in archive.infolist():
                if f.filename.lower().endswith(
                    ".csv"
                ):
                    print(
                        f.filename,
                        f.file_size,
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
            result, indent=2
        )
    )


if __name__ == "__main__":
    main()
