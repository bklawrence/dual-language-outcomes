
#!/usr/bin/env python3
"""Import downloaded public Texas TEA TAPR CSV/ZIP exports conservatively.

This imports publicly supplied files; it does not claim to have downloaded TEA
files and does not infer campus x grade x program outcomes from column names.

Run from repository root:
    python collectors/texas_tapr_public_import.py \
        --csv data/raw/texas/tapr_2024_campus.csv \
        --outdir results/texas/tapr_public

Multiple --csv inputs and TEA-supplied ZIP files are supported. No pip packages
are required. Every candidate value remains UNVERIFIED as to grade/subject/EB
scope until corroborated against the official TEA codebook.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
DATA = DEFAULT_ROOT / "data" / "registry" / "texas"

PROGRAM_CODES = {
    "DQ": "Two-way dual-language immersion",
    "DT": "One-way dual-language immersion",
    "DJ": "Transitional bilingual early exit",
    "DK": "Transitional bilingual late exit",
}

SUPPRESSIONS = {"-", "*", "**", "***", "N/A", "NA", "MASKED", "SUPPRESSED"}

CAMPUS_COLUMNS = (
    "CAMPUS",
    "CAMPUSID",
    "CAMPUSNUMBER",
    "CAMPUSCODE",
    "CAMPUSNUM",
    "CAMPUSIDENTIFIER",
)


def campus_id(value: object) -> str:
    """Return the nine-digit public TEA campus ID, or empty if invalid."""
    s = str(value if value is not None else "").strip().lstrip("'")
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(9) if re.fullmatch(r"\d{1,9}", s) else ""


def clean_heading(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def find_campus_column(columns: list[str]) -> str | None:
    for col in columns:
        if clean_heading(col) in CAMPUS_COLUMNS:
            return col
    return None


def candidate_program_code(column: str) -> str:
    """Detect candidate TEA TAPR student-group code; confirm via codebook."""
    key = clean_heading(column)
    if len(key) >= 4 and key.startswith("C") and key[1:3] in PROGRAM_CODES:
        return key[1:3]
    return ""


def iter_files(paths: list[Path]):
    """Yield (source name, CSV reader), including CSVs inside ZIP files."""
    for path in paths:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if not name.lower().endswith(".csv"):
                        continue
                    if name.startswith("__MACOSX/"):
                        continue
                    with archive.open(name) as binary:
                        with io.TextIOWrapper(
                            binary,
                            encoding="utf-8-sig",
                            errors="replace",
                            newline="",
                        ) as handle:
                            yield f"{path.name}::{name}", csv.DictReader(handle)
        else:
            with path.open(
                encoding="utf-8-sig", errors="replace", newline=""
            ) as handle:
                yield path.name, csv.DictReader(handle)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def dump_csv(path: Path, records: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        out = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        out.writeheader()
        out.writerows(records)


def import_public_tapr(
    inputs: list[Path],
    campuses_path: Path,
    cohorts_path: Path,
    output: Path,
) -> dict:
    campuses = read_rows(campuses_path)
    cohorts = read_rows(cohorts_path)

    selected = {
        campus_id(c.get("campus_id")): c
        for c in campuses
    }
    selected.pop("", None)

    source_log = []
    column_inventory = []
    candidate_cells = []
    matched = set()

    for label, reader in iter_files(inputs):
        columns = reader.fieldnames or []
        campus_col = find_campus_column(columns)

        code_columns = {
            col: candidate_program_code(col)
            for col in columns
        }
        code_columns = {
            col: code
            for col, code in code_columns.items()
            if code
        }

        for col in columns:
            code = candidate_program_code(col)
            column_inventory.append({
                "source_file": label,
                "column_name": col,
                "candidate_program_code": code,
                "candidate_program_description": (
                    PROGRAM_CODES[code] if code else ""
                ),
                "grade_verified": "NO",
                "subject_verified": "NO",
                "student_coverage_verified": "NO",
                "codebook_check_required": "YES",
            })

        scanned = 0
        matched_rows = 0
        matched_this = set()

        if campus_col:
            for row in reader:
                scanned += 1
                cid = campus_id(row.get(campus_col))
                if cid not in selected:
                    continue

                matched_rows += 1
                matched.add(cid)
                matched_this.add(cid)

                for col, code in code_columns.items():
                    raw = (row.get(col) or "").strip()
                    if not raw:
                        status = "BLANK"
                    elif raw.upper() in SUPPRESSIONS:
                        status = "SUPPRESSED"
                    else:
                        status = "REPORTED"

                    candidate_cells.append({
                        "source_file": label,
                        "campus_id": cid,
                        "district": selected[cid].get("district", ""),
                        "campus": selected[cid].get("campus", ""),
                        "source_column": col,
                        "candidate_program_code": code,
                        "raw_value": raw,
                        "value_status": status,
                        "tested_grade": "UNVERIFIED",
                        "subject": "UNVERIFIED",
                        "english_learner_scope": "UNVERIFIED",
                        "strict_grade_program_join": "NO",
                    })

        if campus_col and code_columns:
            source_status = "CANDIDATES_NEED_CODEBOOK"
        elif campus_col:
            source_status = "NO_PROGRAM_COLUMNS"
        else:
            source_status = "NO_RELIABLE_CAMPUS_ID_COLUMN"

        source_log.append({
            "source_file": label,
            "campus_id_column": campus_col or "",
            "number_of_columns": len(columns),
            "scanned_rows": scanned,
            "matched_pilot_rows": matched_rows,
            "matched_distinct_pilot_campuses": len(matched_this),
            "candidate_program_columns": len(code_columns),
            "status": source_status,
        })

    audit = []
    for record in cohorts:
        out = dict(record)
        cid = campus_id(record.get("campus_id"))

        out["tapr_public_source_checked"] = "YES" if inputs else "NO"
        out["tapr_public_campus_found"] = (
            "YES" if cid in matched else "NO"
        )
        out["tapr_strict_grade_program_join"] = "UNVERIFIED"
        out["tapr_review_note"] = (
            "Program-column candidates require TEA codebook validation; "
            "no cohort outcomes imputed."
        )
        audit.append(out)

    output.mkdir(parents=True, exist_ok=True)

    dump_csv(
        output / "column_inventory.csv",
        column_inventory,
        [
            "source_file", "column_name", "candidate_program_code",
            "candidate_program_description", "grade_verified",
            "subject_verified", "student_coverage_verified",
            "codebook_check_required",
        ],
    )

    dump_csv(
        output / "candidate_program_cells.csv",
        candidate_cells,
        [
            "source_file", "campus_id", "district", "campus",
            "source_column", "candidate_program_code", "raw_value",
            "value_status", "tested_grade", "subject",
            "english_learner_scope", "strict_grade_program_join",
        ],
    )

    dump_csv(
        output / "import_log.csv",
        source_log,
        [
            "source_file", "campus_id_column", "number_of_columns",
            "scanned_rows", "matched_pilot_rows",
            "matched_distinct_pilot_campuses",
            "candidate_program_columns", "status",
        ],
    )

    audit_fields = list(cohorts[0]) if cohorts else ["campus_id"]
    audit_fields += [
        "tapr_public_source_checked",
        "tapr_public_campus_found",
        "tapr_strict_grade_program_join",
        "tapr_review_note",
    ]
    dump_csv(
        output / "cohort_register_with_tapr_flags.csv",
        audit,
        audit_fields,
    )

    summary = {
        "sources_checked": len(source_log),
        "pilot_campuses": len(selected),
        "matched_distinct_pilot_campuses": len(matched),
        "candidate_program_cells_including_masked": len(candidate_cells),
        "confirmed_grade_specific_program_outcome_joins": 0,
        "cohort_register_rows_preserved": len(cohorts),
        "source_files": [
            {
                "name": p.name,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in inputs
        ],
        "cautions": [
            "Header-based DQ/DT/DJ/DK discovery is not a "
            "validated cross-tabulation",
            "Suppressed values are retained as strings, "
            "not converted to zeros",
            "English-dominant participant inclusion is not "
            "established by program codes",
        ],
    }

    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv", action="append", type=Path, required=True,
        help="Public TEA campus CSV or ZIP, repeatable",
    )
    parser.add_argument(
        "--campuses", type=Path,
        default=DATA / "tapr_pilot_campuses_pass46.csv",
    )
    parser.add_argument(
        "--cohorts", type=Path,
        default=DATA / "tapr_pilot_join_pass45.csv",
    )
    parser.add_argument(
        "--outdir", type=Path,
        default=DEFAULT_ROOT / "results" / "texas" / "tapr_public",
    )
    args = parser.parse_args(argv)

    for p in [*args.csv, args.campuses, args.cohorts]:
        if not p.is_file():
            parser.error(f"Input file not found: {p}")

    result = import_public_tapr(
        args.csv, args.campuses, args.cohorts, args.outdir
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
