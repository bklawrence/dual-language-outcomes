
#!/usr/bin/env python3
"""Audit public Texas TAPR CSV/ZIP exports against the 66-campus pilot.

Recognizes descriptive TEA headings, including "9 Digit Campus Number"
and "Dual Lang Immersion/Two-Way". Preserves raw values and never treats
an all-grades program result as a grade-specific cohort outcome.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
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

CAMPUS_COLUMNS = {
    "9DIGITCAMPUSNUMBER",
    "CAMPUS",
    "CAMPUSID",
    "CAMPUSNUMBER",
    "CAMPUSCODE",
    "CAMPUSNUM",
    "CAMPUSIDENTIFIER",
}

SUPPRESSED = {
    "-", "*", "**", "***", "N/A", "NA",
    "MASKED", "SUPPRESSED"
}

PROGRAM_RE = re.compile(
    r"^STAAR Performance, (.*?), "
    r"SY (\d{4}-\d{2}), (.*?), ([#%].*)$",
    re.I,
)

GRADE_RE = re.compile(
    r"^Campus 2024 Domain 1A: (.*?), Grade ([345]), "
    r"(All Students|EB/EL), STAAR "
    r"(Reading/ELA|Reading/EB/ELA|Mathematics) "
    r"(Numerator|Denominator)$",
    re.I,
)


def clean(text):
    return re.sub(
        r"[^A-Z0-9]", "", (text or "").upper()
    )


def norm_campus(value):
    text = str(
        value if value is not None else ""
    ).strip().lstrip("'")

    if text.endswith(".0"):
        text = text[:-2]

    if re.fullmatch(r"\d{1,9}", text):
        return text.zfill(9)

    return ""


def campus_field(headers):
    for heading in headers:
        if clean(heading) in CAMPUS_COLUMNS:
            return heading

    return None


def describe(header):
    """Return kind, code, group, subject, metric, grade, year."""

    found = PROGRAM_RE.match(header)

    if found and found.group(3) in PROGRAM_GROUPS:
        subject, year, group, metric = found.groups()
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

    found = GRADE_RE.match(header)

    if found:
        standard, grade, group, subject, count = (
            found.groups()
        )

        subject = (
            "reading_ela"
            if subject.lower().startswith("reading")
            else "mathematics"
        )

        label = (
            "all_students"
            if group == "All Students"
            else "EB_EL"
        )

        return (
            "school_grade",
            "",
            label,
            subject,
            f"{standard} {count}",
            grade,
            "2023-24",
        )

    return ("other", "", "", "", "", "", "")


def value_status(raw):
    if not raw:
        return "BLANK"

    if raw.upper() in SUPPRESSED:
        return "SUPPRESSED"

    return "REPORTED_UNVERIFIED"


def source_tables(paths):
    for path in paths:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if not name.lower().endswith(".csv"):
                        continue

                    if name.startswith("__MACOSX/"):
                        continue

                    with archive.open(name) as stream:
                        with io.TextIOWrapper(
                            stream,
                            encoding="utf-8-sig",
                            errors="replace",
                            newline="",
                        ) as handle:
                            yield (
                                f"{path.name}::{name}",
                                csv.DictReader(handle),
                            )

        else:
            with path.open(
                encoding="utf-8-sig",
                errors="replace",
                newline="",
            ) as handle:
                yield path.name, csv.DictReader(handle)


def read_csv(path):
    with path.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(
            csv.DictReader(
                line for line in handle
                if line.strip()
            )
        )


def save_csv(path, rows, fields):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)


def run(inputs, campuses_path, cohorts_path, outdir):
    campuses = read_csv(campuses_path)
    cohorts = read_csv(cohorts_path)

    selected = {
        norm_campus(row.get("campus_id")): row
        for row in campuses
    }

    selected.pop("", None)

    inventory = []
    program_cells = []
    grade_cells = []
    logs = []

    found_campuses = set()
    seen_program_groups = Counter()

    for source, reader in source_tables(inputs):
        headers = reader.fieldnames or []

        id_field = campus_field(headers)

        descriptors = {
            header: describe(header)
            for header in headers
        }

        program_headers = [
            h for h in headers
            if descriptors[h][0] == "program"
        ]

        grade_headers = [
            h for h in headers
            if descriptors[h][0] == "school_grade"
        ]

        for header in headers:
            (
                kind,
                code,
                group,
                subject,
                metric,
                grade,
                year,
            ) = descriptors[header]

            inventory.append({
                "source_file": source,
                "column_name": header,
                "column_kind": kind,
                "candidate_program_code": code,
                "group_label": group,
                "subject_in_header": subject,
                "metric_in_header": metric,
                "tested_grade_in_header": grade,
                "school_year_in_header": year,
                "student_coverage_verified": "NO",
                "codebook_check_required": "YES",
            })

            if kind == "program":
                seen_program_groups[group] += 1

        scanned = 0
        matched_rows = 0
        matches = set()

        if id_field:
            for row in reader:
                scanned += 1

                cid = norm_campus(
                    row.get(id_field)
                )

                if cid not in selected:
                    continue

                matched_rows += 1
                matches.add(cid)
                found_campuses.add(cid)

                school = selected[cid]

                for header in program_headers:
                    (
                        _,
                        code,
                        group,
                        subject,
                        metric,
                        grade,
                        year,
                    ) = descriptors[header]

                    raw = str(
                        row.get(header) or ""
                    ).strip()

                    program_cells.append({
                        "source_file": source,
                        "campus_id": cid,
                        "district": school.get(
                            "district", ""
                        ),
                        "campus": school.get(
                            "campus", ""
                        ),
                        "school_year": year,
                        "program_code": code,
                        "program_group": group,
                        "subject": subject,
                        "metric": metric,
                        "tested_grade": grade,
                        "raw_value": raw,
                        "value_status": value_status(raw),
                        "source_column": header,
                        "strict_grade_program_join": "NO",
                        "english_dominant_included":
                            "UNVERIFIED",
                    })

                for header in grade_headers:
                    (
                        _,
                        _,
                        group,
                        subject,
                        metric,
                        grade,
                        year,
                    ) = descriptors[header]

                    raw = str(
                        row.get(header) or ""
                    ).strip()

                    grade_cells.append({
                        "source_file": source,
                        "campus_id": cid,
                        "district": school.get(
                            "district", ""
                        ),
                        "campus": school.get(
                            "campus", ""
                        ),
                        "school_year": year,
                        "student_group": group,
                        "tested_grade": grade,
                        "subject": subject,
                        "metric": metric,
                        "raw_value": raw,
                        "value_status": value_status(raw),
                        "source_column": header,
                        "is_dual_language_participant_outcome":
                            "NO",
                    })

        logs.append({
            "source_file": source,
            "campus_id_column": id_field or "",
            "number_of_columns": len(headers),
            "scanned_rows": scanned,
            "matched_pilot_rows": matched_rows,
            "matched_distinct_pilot_campuses":
                len(matches),
            "program_group_columns":
                len(program_headers),
            "school_grade_columns":
                len(grade_headers),
            "status": (
                "MATCHED"
                if matches
                else (
                    "NO_RELIABLE_CAMPUS_ID_COLUMN"
                    if not id_field
                    else "NO_PILOT_MATCHES"
                )
            ),
        })

    audit = []

    for cohort in cohorts:
        record = dict(cohort)

        cid = norm_campus(
            record.get("campus_id")
        )

        record.update({
            "tapr_public_source_checked":
                "YES" if inputs else "NO",
            "tapr_public_campus_found":
                "YES" if cid in found_campuses else "NO",
            "tapr_strict_grade_program_join": "NO",
            "tapr_review_note": (
                "Schoolwide grade measures and all-grades "
                "bilingual program measures are separate; "
                "no cohort outcome imputed."
            ),
        })

        audit.append(record)

    save_csv(
        outdir / "column_inventory.csv",
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
        outdir / "candidate_program_cells.csv",
        program_cells,
        [
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
        ],
    )

    save_csv(
        outdir / "school_grade_cells.csv",
        grade_cells,
        [
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
        ],
    )

    save_csv(
        outdir / "import_log.csv",
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

    fields = (
        list(cohorts[0])
        if cohorts else ["campus_id"]
    )

    fields = [
        x for x in fields
        if not x.startswith("tapr_")
    ]

    save_csv(
        outdir / "cohort_register_with_tapr_flags.csv",
        audit,
        fields + [
            "tapr_public_source_checked",
            "tapr_public_campus_found",
            "tapr_strict_grade_program_join",
            "tapr_review_note",
        ],
    )

    summary = {
        "sources_checked": len(logs),
        "pilot_campuses": len(selected),
        "matched_distinct_pilot_campuses":
            len(found_campuses),
        "program_group_columns_in_source_headers":
            dict(seen_program_groups),
        "candidate_program_cells_including_masked":
            len(program_cells),
        "reported_program_cells_unverified": sum(
            c["value_status"] == "REPORTED_UNVERIFIED"
            for c in program_cells
        ),
        "school_grade_cells_including_masked":
            len(grade_cells),
        "confirmed_grade_specific_program_outcome_joins":
            0,
        "cohort_register_rows_preserved":
            len(cohorts),
        "source_files": [
            {
                "name": path.name,
                "sha256": hashlib.sha256(
                    path.read_bytes()
                ).hexdigest(),
            }
            for path in inputs
        ],
        "cautions": [
            "Bilingual-program results are across tested "
            "grades, not cohort-level.",
            "The grade 3/4/5 results are schoolwide or "
            "EB/EL, not program-specific.",
            "Reported values and program participation "
            "semantics require TEA codebook validation.",
            "Suppressed values remain strings and are "
            "never converted to zeros.",
        ],
    }

    outdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        outdir / "summary.json"
    ).write_text(
        json.dumps(
            summary,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    return summary


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--csv",
        action="append",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--campuses",
        type=Path,
        default=REGISTRY /
            "tapr_pilot_campuses_pass46.csv",
    )

    parser.add_argument(
        "--cohorts",
        type=Path,
        default=REGISTRY /
            "tapr_pilot_join_pass45.csv",
    )

    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT /
            "results/texas/tapr_public",
    )

    args = parser.parse_args()

    for path in [
        *args.csv,
        args.campuses,
        args.cohorts,
    ]:
        if not path.is_file():
            parser.error(
                f"File not found: {path}"
            )

    print(
        json.dumps(
            run(
                args.csv,
                args.campuses,
                args.cohorts,
                args.outdir,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
