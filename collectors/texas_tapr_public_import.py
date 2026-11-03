
#!/usr/bin/env python3
"""Import 2023-24 TEA TAPR statewide; retain the 66-campus pilot audit.

Statewide extracts are matched on TEA's nine-digit campus number.
Grade-specific school outcomes are NOT joined to all-grades
program outcomes as cohort scores.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "data/registry/texas"

PROGRAM_GROUPS = {
    "Dual Lang Immersion/Two-Way": (
        "DQ", "two_way_dual_language"
    ),
    "Dual Lang Immersion/One-Way": (
        "DT", "one_way_dual_language"
    ),
    "Trans Bil/Early Exit": (
        "DJ", "transitional_bilingual_early_exit"
    ),
    "Trans Bil/Late Exit": (
        "DK", "transitional_bilingual_late_exit"
    ),
}

PROGRAM_RE = re.compile(
    r"^STAAR Performance, (.*?), "
    r"SY (\d{4}-\d{2}), (.*?), ([#%].*)$",
    re.I
)

GRADE_RE = re.compile(
    r"^Campus 2024 Domain 1A: (.*?), Grade ([345]), "
    r"(All Students|EB/EL), STAAR "
    r"(Reading/ELA|Reading/EB/ELA|Mathematics) "
    r"(Numerator|Denominator)$",
    re.I
)

ID_FIELDS = {
    "9DIGITCAMPUSNUMBER",
    "CAMPUSID",
    "CAMPUSNUMBER",
    "CAMPUSCODE",
    "TEXASCAMPUSID",
}

MASKS = {
    "-1", "-", "*", "**", "***",
    "N/A", "NA", "MASKED", "SUPPRESSED", "."
}

PROGRAM_FIELDS = [
    "source_file",
    "campus_id",
    "district",
    "campus",
    "school_year",
    "program_code",
    "program_group",
    "subject",
    "metric",
    "tested_grade",
    "raw_value",
    "value_status",
    "source_column",
    "strict_grade_program_join",
    "english_dominant_included",
]

GRADE_FIELDS = [
    "source_file",
    "campus_id",
    "district",
    "campus",
    "school_year",
    "student_group",
    "tested_grade",
    "subject",
    "metric",
    "raw_value",
    "value_status",
    "source_column",
    "is_dual_language_participant_outcome",
]


def normalize_id(value):
    s = str(value or "").strip().lstrip("'")

    if s.endswith(".0"):
        s = s[:-2]

    if re.fullmatch(r"\d{1,9}", s):
        return s.zfill(9)

    return ""


def canonical(value):
    return re.sub(
        r"[^A-Z0-9]",
        "",
        str(value or "").upper()
    )


def status(value):
    s = str(value or "").strip()

    if not s:
        return "BLANK"

    if (
        s.upper() in MASKS
        or re.fullmatch(r"-\d+(?:\.\d+)?", s)
    ):
        return "MASKED_OR_NEGATIVE_CODE"

    try:
        float(s.replace(",", ""))
        return "NUMERIC_UNVERIFIED"
    except ValueError:
        return "OTHER_UNVERIFIED"


def reported(value):
    if status(value) == "NUMERIC_UNVERIFIED":
        return value

    return ""


def describe(column):
    m = PROGRAM_RE.fullmatch(column)

    if m and m.group(3) in PROGRAM_GROUPS:
        subject, year, group, metric = m.groups()
        code, label = PROGRAM_GROUPS[group]

        return (
            "program",
            code,
            label,
            subject,
            metric,
            "ALL_TESTED_GRADES",
            year,
        )

    m = GRADE_RE.fullmatch(column)

    if m:
        level, grade, group, subject, count = (
            m.groups()
        )

        return (
            "school_grade",
            "",
            (
                "all_students"
                if group == "All Students"
                else "EB_EL"
            ),
            (
                "reading_ela"
                if subject.lower().startswith("reading")
                else "mathematics"
            ),
            f"{level} {count}",
            grade,
            "2023-24",
        )

    return ("other", "", "", "", "", "", "")


def read_rows(path):
    with path.open(
        encoding="utf-8-sig",
        newline=""
    ) as f:
        return list(
            csv.DictReader(
                line for line in f
                if line.strip()
            )
        )


@contextmanager
def read_source(path):
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            names = [
                n for n in z.namelist()
                if n.lower().endswith(".csv")
                and not n.startswith("__MACOSX/")
            ]

            if len(names) != 1:
                raise ValueError(
                    f"{path}: expected one CSV member; "
                    f"found {len(names)}"
                )

            with z.open(names[0]) as raw:
                with io.TextIOWrapper(
                    raw,
                    encoding="utf-8-sig",
                    errors="replace",
                    newline="",
                ) as f:
                    yield (
                        f"{path.name}::{names[0]}",
                        csv.DictReader(f),
                    )

    else:
        with path.open(
            encoding="utf-8-sig",
            newline=""
        ) as f:
            yield path.name, csv.DictReader(f)


def save_csv(path, rows, columns):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=columns,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(rows)


def registry_file(explicit):
    if explicit:
        return explicit

    for path in (
        REGISTRY / "texas_master_pass44.csv",
        REGISTRY /
        "texas_dual_language_master_with_structure_pass44.csv",
        REGISTRY / "texas_master.csv",
    ):
        if path.is_file():
            return path

    return None


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--csv",
        action="append",
        type=Path,
        required=True
    )

    parser.add_argument(
        "--campuses",
        type=Path,
        default=REGISTRY /
        "tapr_pilot_campuses_pass46.csv"
    )

    parser.add_argument(
        "--cohorts",
        type=Path,
        default=REGISTRY /
        "tapr_pilot_join_pass45.csv"
    )

    parser.add_argument(
        "--research-master",
        type=Path,
        default=None
    )

    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT / "results/texas/tapr_public"
    )

    args = parser.parse_args()

    for p in [
        *args.csv,
        args.campuses,
        args.cohorts,
    ]:
        if not p.is_file():
            parser.error(
                f"Missing file: {p}"
            )

    if (
        args.research_master
        and not args.research_master.is_file()
    ):
        parser.error(
            f"Missing research master: "
            f"{args.research_master}"
        )

    out = args.outdir

    out.mkdir(
        parents=True,
        exist_ok=True
    )

    pilot = {
        normalize_id(r.get("campus_id")): r
        for r in read_rows(args.campuses)
    }

    pilot.pop("", None)

    cohorts = read_rows(args.cohorts)

    # One record per TEA campus, regardless of
    # program designation.

    campus_data = {}

    program_availability = defaultdict(
        lambda: Counter()
    )

    meets = defaultdict(dict)

    inventory = []
    logs = []
    pilot_program = []
    pilot_grades = []

    scanned_ids = set()
    group_columns = Counter()
    statewide_stats = Counter()

    # Write large statewide tables as compressed
    # CSVs rather than storing them in memory.

    with (
        gzip.open(
            out / "statewide_program_cells.csv.gz",
            "wt",
            encoding="utf-8",
            newline=""
        ) as pf,
        gzip.open(
            out / "statewide_school_grade_cells.csv.gz",
            "wt",
            encoding="utf-8",
            newline=""
        ) as gf
    ):
        pw = csv.DictWriter(
            pf,
            fieldnames=PROGRAM_FIELDS
        )

        gw = csv.DictWriter(
            gf,
            fieldnames=GRADE_FIELDS
        )

        pw.writeheader()
        gw.writeheader()

        for src in args.csv:
            with read_source(src) as (source, reader):
                headers = reader.fieldnames or []

                id_field = next(
                    (
                        h for h in headers
                        if canonical(h) in ID_FIELDS
                    ),
                    None
                )

                d = {
                    h: describe(h)
                    for h in headers
                }

                pfields = [
                    h for h in headers
                    if d[h][0] == "program"
                ]

                gfields = [
                    h for h in headers
                    if d[h][0] == "school_grade"
                ]

                for h in headers:
                    (
                        typ,
                        code,
                        group,
                        subject,
                        metric,
                        grade,
                        year,
                    ) = d[h]

                    inventory.append({
                        "source_file": source,
                        "column_name": h,
                        "column_kind": typ,
                        "candidate_program_code": code,
                        "group_label": group,
                        "subject_in_header": subject,
                        "metric_in_header": metric,
                        "tested_grade_in_header": grade,
                        "school_year_in_header": year,
                        "student_coverage_verified": "NO",
                        "codebook_check_required": "YES",
                    })

                    if typ == "program":
                        group_columns[group] += 1

                if not id_field:
                    raise RuntimeError(
                        f"{source}: cannot identify "
                        "TEA campus number"
                    )

                rows_in_source = 0
                matched_pilot = 0
                distinct = set()

                for row in reader:
                    rows_in_source += 1

                    cid = normalize_id(
                        row.get(id_field)
                    )

                    if not cid:
                        statewide_stats[
                            "invalid_id_rows"
                        ] += 1
                        continue

                    scanned_ids.add(cid)

                    if cid not in campus_data:
                        campus_data[cid] = {
                            "campus_id": cid,
                            "district_id": str(
                                row.get(
                                    "6 Digit County District Number"
                                ) or ""
                            ).strip(),
                            "district": str(
                                row.get(
                                    "District Name"
                                ) or ""
                            ).strip(),
                            "campus": str(
                                row.get(
                                    "Campus Name"
                                ) or ""
                            ).strip(),
                            "source_categories_seen": 0,
                        }

                    campus_data[cid][
                        "source_categories_seen"
                    ] += 1

                    school = campus_data[cid]

                    if cid in pilot:
                        matched_pilot += 1
                        distinct.add(cid)

                    for col in pfields:
                        (
                            _,
                            code,
                            group,
                            subject,
                            metric,
                            grade,
                            year,
                        ) = d[col]

                        raw = str(
                            row.get(col) or ""
                        ).strip()

                        st = status(raw)

                        if st != "BLANK":
                            program_availability[
                                (cid, code)
                            ][st] += 1

                            statewide_stats[
                                f"program_{st}"
                            ] += 1

                            record = {
                                "source_file": source,
                                "campus_id": cid,
                                "district": school[
                                    "district"
                                ],
                                "campus": school[
                                    "campus"
                                ],
                                "school_year": year,
                                "program_code": code,
                                "program_group": group,
                                "subject": subject,
                                "metric": metric,
                                "tested_grade": grade,
                                "raw_value": raw,
                                "value_status": st,
                                "source_column": col,
                                "strict_grade_program_join":
                                    "NO",
                                "english_dominant_included":
                                    "UNVERIFIED",
                            }

                            pw.writerow(record)

                            if (
                                metric in (
                                    "# of Tests",
                                    "# At Meets GL Standard or Above",
                                    "% At Meets GL Standard or Above",
                                )
                                and subject in (
                                    "Reading/Language Arts",
                                    "Mathematics",
                                )
                            ):
                                meets[
                                    (cid, code, subject)
                                ][metric] = raw

                        if cid in pilot:
                            pilot_program.append({
                                "source_file": source,
                                "campus_id": cid,
                                "district": pilot[cid].get(
                                    "district",
                                    school["district"]
                                ),
                                "campus": pilot[cid].get(
                                    "campus",
                                    school["campus"]
                                ),
                                "school_year": year,
                                "program_code": code,
                                "program_group": group,
                                "subject": subject,
                                "metric": metric,
                                "tested_grade": grade,
                                "raw_value": raw,
                                "value_status": st,
                                "source_column": col,
                                "strict_grade_program_join":
                                    "NO",
                                "english_dominant_included":
                                    "UNVERIFIED",
                            })

                    for col in gfields:
                        (
                            _,
                            code,
                            group,
                            subject,
                            metric,
                            grade,
                            year,
                        ) = d[col]

                        raw = str(
                            row.get(col) or ""
                        ).strip()

                        st = status(raw)

                        if st != "BLANK":
                            statewide_stats[
                                f"school_grade_{st}"
                            ] += 1

                            gw.writerow({
                                "source_file": source,
                                "campus_id": cid,
                                "district": school[
                                    "district"
                                ],
                                "campus": school[
                                    "campus"
                                ],
                                "school_year": year,
                                "student_group": group,
                                "tested_grade": grade,
                                "subject": subject,
                                "metric": metric,
                                "raw_value": raw,
                                "value_status": st,
                                "source_column": col,
                                "is_dual_language_participant_outcome":
                                    "NO",
                            })

                        if cid in pilot:
                            pilot_grades.append({
                                "source_file": source,
                                "campus_id": cid,
                                "district": pilot[cid].get(
                                    "district",
                                    school["district"]
                                ),
                                "campus": pilot[cid].get(
                                    "campus",
                                    school["campus"]
                                ),
                                "school_year": year,
                                "student_group": group,
                                "tested_grade": grade,
                                "subject": subject,
                                "metric": metric,
                                "raw_value": raw,
                                "value_status": st,
                                "source_column": col,
                                "is_dual_language_participant_outcome":
                                    "NO",
                            })

                logs.append({
                    "source_file": source,
                    "campus_id_column": id_field,
                    "number_of_columns": len(headers),
                    "scanned_rows": rows_in_source,
                    "matched_pilot_rows": matched_pilot,
                    "matched_distinct_pilot_campuses":
                        len(distinct),
                    "program_group_columns":
                        len(pfields),
                    "school_grade_columns":
                        len(gfields),
                    "status": (
                        "MATCHED"
                        if distinct
                        else "NO_PILOT_MATCHES"
                    ),
                })

    # Optional link to the historical Texas master.
    # This is an ID match, not a cohort-exposure match.

    research = registry_file(
        args.research_master
    )

    registry_ids = set()
    research_rows = []

    if research:
        for r in read_rows(research):
            cid = normalize_id(
                r.get("campus_id")
                or r.get("texas_campus_id")
            )

            if not cid:
                continue

            registry_ids.add(cid)

            research_rows.append({
                "record_id": r.get(
                    "record_id", ""
                ),
                "campus_id": cid,
                "research_district": r.get(
                    "district", ""
                ),
                "research_campus": r.get(
                    "campus", ""
                ),
                "research_student_group": r.get(
                    "assessment_student_group", ""
                ),
                "kindergarten_model_policy": r.get(
                    "analysis_K_ratio", ""
                ),
                "kindergarten_model_status": r.get(
                    "analysis_K_ratio_status", ""
                ),
                "policy_source_url": r.get(
                    "analysis_K_ratio_source_url", ""
                ),
                "structure_class": r.get(
                    "implementation_class", ""
                ),
                "matched_tapr_2023_24": (
                    "YES"
                    if cid in scanned_ids
                    else "NO"
                ),
                "tapr_district": campus_data.get(
                    cid, {}
                ).get("district", ""),
                "tapr_campus": campus_data.get(
                    cid, {}
                ).get("campus", ""),
                "cohort_specific_outcome_join":
                    "NO",
            })

        save_csv(
            out / "statewide_research_registry_join.csv",
            research_rows,
            [
                "record_id",
                "campus_id",
                "research_district",
                "research_campus",
                "research_student_group",
                "kindergarten_model_policy",
                "kindergarten_model_status",
                "policy_source_url",
                "structure_class",
                "matched_tapr_2023_24",
                "tapr_district",
                "tapr_campus",
                "cohort_specific_outcome_join",
            ],
        )

    # Build an index of all Texas campuses.

    campus_index = []

    for cid, c in sorted(
        campus_data.items()
    ):
        count_by = {
            code: program_availability.get(
                (cid, code),
                Counter()
            )
            for code in (
                "DQ", "DT", "DJ", "DK"
            )
        }

        numeric = {
            code: count_by[code][
                "NUMERIC_UNVERIFIED"
            ]
            for code in count_by
        }

        campus_index.append({
            **c,
            "in_66_campus_pilot": (
                "YES"
                if cid in pilot
                else "NO"
            ),
            "in_research_master": (
                "NOT_CHECKED"
                if research is None
                else (
                    "YES"
                    if cid in registry_ids
                    else "NO"
                )
            ),
            "two_way_numeric_cells":
                numeric["DQ"],
            "one_way_numeric_cells":
                numeric["DT"],
            "trans_early_numeric_cells":
                numeric["DJ"],
            "trans_late_numeric_cells":
                numeric["DK"],
            "any_DL_numeric": (
                "YES"
                if numeric["DQ"] or numeric["DT"]
                else "NO"
            ),
            "any_transitional_numeric": (
                "YES"
                if numeric["DJ"] or numeric["DK"]
                else "NO"
            ),
        })

    save_csv(
        out / "statewide_campus_index.csv",
        campus_index,
        [
            "campus_id",
            "district_id",
            "district",
            "campus",
            "source_categories_seen",
            "in_66_campus_pilot",
            "in_research_master",
            "two_way_numeric_cells",
            "one_way_numeric_cells",
            "trans_early_numeric_cells",
            "trans_late_numeric_cells",
            "any_DL_numeric",
            "any_transitional_numeric",
        ],
    )

    # Build a compact school/program/subject
    # outcomes table for statewide comparison.

    readable_meets = []

    for (
        cid,
        code,
        subject
    ), metrics in sorted(
        meets.items()
    ):
        record = {
            "campus_id": cid,
            "district": campus_data[cid][
                "district"
            ],
            "campus": campus_data[cid][
                "campus"
            ],
            "program_code": code,
            "subject": subject,
            "tests_raw": metrics.get(
                "# of Tests", ""
            ),
            "meets_n_raw": metrics.get(
                "# At Meets GL Standard or Above",
                ""
            ),
            "meets_pct_raw": metrics.get(
                "% At Meets GL Standard or Above",
                ""
            ),
        }

        record["tests_numeric"] = reported(
            record["tests_raw"]
        )

        record["meets_n_numeric"] = reported(
            record["meets_n_raw"]
        )

        record["meets_pct_numeric"] = reported(
            record["meets_pct_raw"]
        )

        record[
            "comparison_eligible_for_review"
        ] = (
            "YES"
            if all(
                record[x]
                for x in (
                    "tests_numeric",
                    "meets_n_numeric",
                    "meets_pct_numeric",
                )
            )
            else "NO"
        )

        record["tested_grade"] = (
            "ALL_TESTED_GRADES"
        )

        readable_meets.append(
            record
        )

    save_csv(
        out / "statewide_program_meets.csv",
        readable_meets,
        [
            "campus_id",
            "district",
            "campus",
            "program_code",
            "subject",
            "tests_raw",
            "meets_n_raw",
            "meets_pct_raw",
            "tests_numeric",
            "meets_n_numeric",
            "meets_pct_numeric",
            "comparison_eligible_for_review",
            "tested_grade",
        ],
    )

    # Preserve pilot files and cohort history.

    save_csv(
        out / "candidate_program_cells.csv",
        pilot_program,
        PROGRAM_FIELDS
    )

    save_csv(
        out / "school_grade_cells.csv",
        pilot_grades,
        GRADE_FIELDS
    )

    save_csv(
        out / "column_inventory.csv",
        inventory,
        [
            "source_file",
            "column_name",
            "column_kind",
            "candidate_program_code",
            "group_label",
            "subject_in_header",
            "metric_in_header",
            "tested_grade_in_header",
            "school_year_in_header",
            "student_coverage_verified",
            "codebook_check_required",
        ],
    )

    save_csv(
        out / "import_log.csv",
        logs,
        [
            "source_file",
            "campus_id_column",
            "number_of_columns",
            "scanned_rows",
            "matched_pilot_rows",
            "matched_distinct_pilot_campuses",
            "program_group_columns",
            "school_grade_columns",
            "status",
        ],
    )

    audit = []

    for r in cohorts:
        cid = normalize_id(
            r.get("campus_id")
        )

        audit.append({
            **r,
            "tapr_public_source_checked":
                "YES",
            "tapr_public_campus_found": (
                "YES"
                if cid in campus_data
                else "NO"
            ),
            "tapr_strict_grade_program_join":
                "NO",
            "tapr_review_note": (
                "Grade-specific school and "
                "all-grades program results "
                "remain separate; no cohort "
                "outcome imputed."
            ),
        })

    cohort_fields = (
        list(cohorts[0])
        if cohorts
        else ["campus_id"]
    )

    save_csv(
        out / "cohort_register_with_tapr_flags.csv",
        audit,
        cohort_fields + [
            "tapr_public_source_checked",
            "tapr_public_campus_found",
            "tapr_strict_grade_program_join",
            "tapr_review_note",
        ],
    )

    # Count statewide data availability
    # separately for each program type.

    group_summary = {}

    for code in (
        "DQ", "DT", "DJ", "DK"
    ):
        group_summary[code] = {
            "campuses_with_any_numeric_program_cell":
                sum(
                    program_availability[
                        (cid, code)
                    ]["NUMERIC_UNVERIFIED"] > 0
                    for cid in campus_data
                ),
            "campuses_with_readable_reading_meets_percentage":
                sum(
                    status(
                        meets.get(
                            (
                                cid,
                                code,
                                "Reading/Language Arts"
                            ),
                            {}
                        ).get(
                            "% At Meets GL Standard or Above",
                            ""
                        )
                    ) == "NUMERIC_UNVERIFIED"
                    for cid in campus_data
                ),
            "campuses_with_readable_math_meets_percentage":
                sum(
                    status(
                        meets.get(
                            (
                                cid,
                                code,
                                "Mathematics"
                            ),
                            {}
                        ).get(
                            "% At Meets GL Standard or Above",
                            ""
                        )
                    ) == "NUMERIC_UNVERIFIED"
                    for cid in campus_data
                ),
        }

    summary = {
        "school_year": "2023-24",
        "sources_checked": len(logs),
        "statewide_distinct_campuses":
            len(campus_data),
        "pilot_campuses": len(pilot),
        "matched_distinct_pilot_campuses":
            sum(
                cid in campus_data
                for cid in pilot
            ),
        "research_master_path": (
            str(research)
            if research
            else None
        ),
        "research_master_match_status": (
            "MATCHED"
            if research
            else "NOT_IN_REPOSITORY"
        ),
        "research_master_distinct_campuses": (
            len(registry_ids)
            if research
            else None
        ),
        "research_master_campuses_matched": (
            len(
                registry_ids & scanned_ids
            )
            if research
            else None
        ),
        "research_master_rows": (
            len(research_rows)
            if research
            else None
        ),
        "statewide_program_reporting_by_group":
            group_summary,
        "statewide_nonblank_cell_counts":
            dict(statewide_stats),
        "candidate_program_cells_including_masked_pilot":
            len(pilot_program),
        "school_grade_cells_including_masked_pilot":
            len(pilot_grades),
        "cohort_register_rows_preserved":
            len(cohorts),
        "confirmed_grade_specific_program_outcome_joins":
            0,
        "source_files": [
            {
                "name": p.name,
                "sha256": hashlib.sha256(
                    p.read_bytes()
                ).hexdigest(),
            }
            for p in args.csv
        ],
        "cautions": [
            (
                "TAPR program groups are all-tested-"
                "grades aggregates, not kindergarten "
                "cohorts."
            ),
            (
                "No numeric or percentage score is "
                "imputed for blank or negative TEA codes."
            ),
            (
                "An unreported program cell does not "
                "prove the program is absent."
            ),
            (
                "K instructional ratio is a separate, "
                "dated historical policy variable."
            ),
            (
                "Any research-master match is an ID "
                "link, not confirmed student exposure."
            ),
        ],
    }

    (
        out / "summary.json"
    ).write_text(
        json.dumps(
            summary,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    (
        out / "statewide_summary.json"
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
