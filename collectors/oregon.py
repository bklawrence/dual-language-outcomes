
#!/usr/bin/env python3
"""Extract Oregon's 2026-27 dual-language directory by PDF table rows.

Run from the repository root:
    python3 collectors/oregon.py

Writes the same three data/registry files as the original collector.
Ambiguous rows remain in the extraction audit, not in the school-level output.
NCES identifiers and historical cohort models are not inferred.
"""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import requests
from pdfplumber.utils import extract_text

SOURCE_URL = (
    "https://www.oregon.gov/ode/schools-and-districts/MME/Documents/"
    "Dual%20Language%20Directory%202026-2027.pdf"
)
YEAR = "2026-27"
HEADERS = [
    "district_raw", "school_raw", "language_raw", "allocation_raw",
    "model_raw", "structure_raw", "year_established_raw", "feeder_raw",
    "notes_raw",
]
# PDF has nine columns, from left to right.
CUTS = [.064, .175, .272, .344, .412, .511, .593, .657, .775, .921]
OUTPUT_FIELDS = [
    "state", "school_year", "district_name", "school_name",
    "partner_language", "instructional_allocation", "allocation_detail",
    "population_model", "program_structure", "year_established",
    "feeder_pathway", "program_notes", "source_district_raw",
    "source_school_raw", "source_language_raw",
    "source_population_model_raw", "source_structure_raw",
    "verification_status", "source_page", "source_url", "source_sha256",
    "nces_school_id", "nces_match_status",
]
AUDIT_FIELDS = [
    "page", "row_top", "row_bottom", "extraction_issue",
    "normalization_note", *HEADERS,
]
KNOWN_LANGUAGES = (
    "Mandarin Chinese", "Spanish", "Russian", "French", "Japanese",
    "Chinese", "Korean", "Vietnamese", "Arabic", "German",
    "Portuguese", "Hawaiian", "Indigenous", "English",
)

# Explicit corrections of names clipped in the PDF.
# The original names remain in source_school_raw.
SCHOOL_NAME_CORRECTIONS = {
    ("Central SD 13J", "Independence Elementary S"):
        "Independence Elementary School",
    ("Hood River County SD", "Hood River Valley High Sch"):
        "Hood River Valley High School",
    ("Pilot Rock SD 2", "Pilot Rock Elementary Scho"):
        "Pilot Rock Elementary School",
    ("Portland SD 1J", "Roseway Heights Middle Sc hool"):
        "Roseway Heights Middle School",
}

# Correct only this known language-cell artifact.
LANGUAGE_CELL_CORRECTIONS = {
    ("Gresham-Barlow SD 10J", "North Gresham Elementary", "S Spanish"):
        "Spanish",
}

KNOWN_MULTILINE_DISTRICTS = {"Oregon Department of Education"}
KNOWN_SOURCE_SHA256 = (
    "464e9020dbdd866b1f330e92a257188593cdf901d15900e3b5e4a8d31caf4ada"
)

HERITAGE_MODEL = "heritage language program"
NATIVE_MODEL = "native language revitalization"


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def norm_na(value):
    text = clean(value)
    return "" if text.lower() in {"", "n/a", "na", "none", "-"} else text


def classify_model(raw):
    val = norm_na(raw).lower().replace("‐", "-").replace("–", "-")
    if "two-way" in val or "two way" in val or "(twi)" in val:
        return "two_way"
    if "one-way" in val or "one way" in val or "(owi)" in val:
        return "one_way"
    return "unknown"


def classify_structure(raw):
    val = norm_na(raw).lower().replace("-", " ")
    if "whole school" in val or "schoolwide" in val:
        return "whole_school"
    if "strand" in val or "cohort within" in val:
        return "strand"
    return "unknown"


def classify_allocation(raw):
    matches = re.findall(
        r"(?<!\d)(\d{1,3})\s*/\s*(\d{1,3})(?!\d)",
        norm_na(raw),
    )
    ratios = {
        f"{int(a)}-{int(b)}" for a, b in matches
        if int(a) + int(b) == 100
    }
    if len(ratios) == 1:
        return next(iter(ratios))
    if len(ratios) > 1:
        return "varies_by_grade"
    return "other" if norm_na(raw) else "unknown"


def language_values(raw):
    """Return languages and any parsing issue."""
    value = norm_na(raw)
    if not value:
        return [], "missing_language"

    lines = [
        clean(x)
        for x in re.split(r"[;\n]+", raw)
        if clean(x)
    ]
    result = []
    issues = []

    for line in lines:
        if line in KNOWN_LANGUAGES:
            result.append(line)
            continue

        remaining = line
        parsed = []

        while remaining:
            found = next(
                (
                    name for name in KNOWN_LANGUAGES
                    if remaining == name
                    or remaining.startswith(name + " ")
                ),
                None,
            )
            if not found:
                break

            parsed.append(found)
            remaining = remaining[len(found):].strip()

        if parsed and not remaining:
            result.extend(parsed)
        else:
            issues.append("unrecognized_language_text")

    if issues:
        return [], ";".join(sorted(set(issues)))

    languages = list(dict.fromkeys(result))
    issue = "multi_language_cell" if len(languages) > 1 else ""
    return languages, issue


# ==========================================
# PDF TABLE GEOMETRY
# ==========================================

def header_bottom(page):
    words = page.extract_words()
    bottoms = [
        w["bottom"]
        for w in words
        if (
            w["text"].lower() == "district"
            and w["top"] < page.height * .20
            and w["x0"] < page.width * .25
        )
    ]
    if not bottoms:
        raise RuntimeError("Oregon table header not found")
    return max(bottoms) + 1.0


def footer_top(page):
    words = page.extract_words()
    footers = [
        w["top"]
        for w in words
        if (
            w["top"] > .77 * page.height
            and "patiño" in w["text"].lower()
        )
    ]
    return min(footers) - 2 if footers else .94 * page.height


def is_blue_fill(obj):
    if obj.get("fill") is False:
        return False

    col = obj.get("non_stroking_color")
    if not isinstance(col, (tuple, list)) or len(col) < 3:
        return False

    red, green, blue = col[:3]

    return (
        isinstance(red, (int, float))
        and .45 <= red < .96
        and green >= red
        and blue > red + .035
    )


def shaded_bands(page, top, bottom):
    """Find complete shaded rows, not every rectangle edge."""
    matches = []

    for obj in list(page.rects) + list(page.curves):
        x0, x1 = obj.get("x0", -1), obj.get("x1", -1)
        y0, y1 = obj.get("top", -1), obj.get("bottom", -1)

        if not (top - 6 <= y0 < y1 <= bottom + 3):
            continue

        if not (
            .052 * page.width <= x0 <= .085 * page.width
            and x1 >= .16 * page.width
        ):
            continue

        if not (5 <= y1 - y0 <= .35 * page.height):
            continue

        if is_blue_fill(obj):
            matches.append((
                max(top, y0),
                min(bottom, y1),
            ))

    matches.sort()
    bands = []

    for a, b in matches:
        if bands and a <= bands[-1][1] + 1.5:
            bands[-1] = (
                min(a, bands[-1][0]),
                max(b, bands[-1][1]),
            )
        else:
            bands.append((a, b))

    return bands


def candidate_spans(page, first, last):
    """Each blue band and intervening white band is a row."""
    bands = shaded_bands(page, first, last)

    if not bands:
        raise RuntimeError(
            "No blue table rows found; inspect PDF layout"
        )

    candidates = []
    pos = first

    for start, stop in bands:
        if start - pos > 3:
            candidates.append((pos, start, "white"))

        if stop - start > 3:
            candidates.append((start, stop, "blue"))

        pos = max(pos, stop)

    if last - pos > 3:
        candidates.append((pos, last, "white"))

    return candidates, len(bands)


def cell_text(chars, x0, x1, y0, y1):
    """Assign characters by center, avoiding neighboring rows."""
    selected = [
        c for c in chars
        if (
            x0 <= (c["x0"] + c["x1"]) / 2 < x1
            and y0 <= (c["top"] + c["bottom"]) / 2 < y1
        )
    ]

    if not selected:
        return ""

    return (
        extract_text(
            selected,
            x_tolerance=2,
            y_tolerance=3,
        )
        or ""
    ).strip()


def source_rows(pdf_path):
    rows, diagnostics = [], []

    with pdfplumber.open(pdf_path) as doc:
        for page_no, page in enumerate(doc.pages, 1):
            first, last = header_bottom(page), footer_top(page)
            spans, band_count = candidate_spans(
                page, first, last
            )

            diagnostics.append({
                "page": page_no,
                "candidate_spans": len(spans),
                "blue_bands": band_count,
                "page_width": page.width,
                "page_height": page.height,
                "rectangles": len(page.rects),
            })

            chars = [
                c for c in page.chars
                if (
                    first <= (
                        c["top"] + c["bottom"]
                    ) / 2 < last
                )
            ]

            for y0, y1, _ in spans:
                cells = [
                    cell_text(
                        chars,
                        a * page.width + .7,
                        b * page.width - .7,
                        y0 + .15,
                        y1 - .15,
                    )
                    for a, b in zip(CUTS, CUTS[1:])
                ]

                if not clean(cells[0]) and not clean(cells[1]):
                    continue

                row = {
                    "page": page_no,
                    "row_top": round(y0, 2),
                    "row_bottom": round(y1, 2),
                    **dict(zip(HEADERS, cells)),
                }

                issues = []
                district_lines = [
                    x for x in cells[0].splitlines()
                    if clean(x)
                ]

                # Permit the known wrapped state-agency name.
                if (
                    len(district_lines) > 1
                    and clean(cells[0])
                    not in KNOWN_MULTILINE_DISTRICTS
                ):
                    issues.append("multiple_district_lines")

                if (
                    not norm_na(cells[0])
                    or not norm_na(cells[1])
                ):
                    issues.append("missing_school_or_district")

                if not norm_na(cells[2]):
                    issues.append("missing_language")

                if clean(cells[0]).lower().startswith(
                    "school district"
                ):
                    issues.append("header_contamination")

                row["extraction_issue"] = ";".join(issues)
                row["normalization_note"] = ""
                rows.append(row)

    return rows, diagnostics


# ==========================================
# NORMALIZE PROGRAM OBSERVATIONS
# ==========================================

def build_records(rows, digest):
    records = []
    ignored = Counter()
    seen = set()

    for row in rows:
        row.setdefault("normalization_note", "")

        if row["extraction_issue"]:
            ignored["quarantined_geometry"] += 1
            continue

        district = clean(row["district_raw"])
        original_school = clean(row["school_raw"])

        school = SCHOOL_NAME_CORRECTIONS.get(
            (district, original_school),
            original_school,
        )

        notes = []
        if school != original_school:
            notes.append("verified_school_name_correction")

        source_language = clean(row["language_raw"])

        language_text = LANGUAGE_CELL_CORRECTIONS.get(
            (district, original_school, source_language),
            row["language_raw"],
        )

        if clean(language_text) != source_language:
            notes.append("verified_language_cell_correction")

        if not district or not school:
            row["extraction_issue"] = (
                "missing_school_or_district"
            )
            ignored["missing_school_or_district"] += 1
            continue

        # Quarantine stray fragments from broken rows.
        if (
            re.match(
                r"^(?:School\b|Charter\b|\(EIHS\))",
                school,
                re.I,
            )
            or re.search(r"\b[A-Z]$", school)
        ):
            row["extraction_issue"] = "school_name_fragment"
            ignored["school_name_fragment"] += 1
            continue

        source_model = norm_na(row["model_raw"])
        normalized_model = source_model.casefold()

        is_heritage = (
            HERITAGE_MODEL in normalized_model
        )
        is_native = (
            NATIVE_MODEL in normalized_model
        )

        if is_native:
            # One source observation, NOT three
            # invented dual-language programs.
            languages = [""]
            status = (
                "excluded_native_language_"
                "revitalization_not_dli"
            )
            notes.append(
                "native_language_names_in_source_language_raw"
            )
        else:
            languages, language_issue = language_values(
                language_text
            )

            if not languages:
                row["extraction_issue"] = (
                    language_issue or "missing_language"
                )
                ignored[row["extraction_issue"]] += 1
                continue

            if is_heritage:
                status = (
                    "excluded_heritage_language_not_dli"
                )
            elif re.search(
                r"not a dual language",
                source_model + " " + row["notes_raw"],
                re.I,
            ):
                status = "needs_review_possible_non_dli"
            elif language_issue:
                status = (
                    "listed_multi_language_cell_needs_review"
                )
            else:
                status = "listed_in_state_directory"

        row["normalization_note"] = ";".join(notes)

        raw_year = norm_na(
            row["year_established_raw"]
        )
        year = (
            raw_year
            if re.fullmatch(r"(?:19|20)\d{2}", raw_year)
            else ""
        )

        for language in languages:
            record = {
                "state": "OR",
                "school_year": YEAR,
                "district_name": district,
                "school_name": school,
                "partner_language": language,
                "instructional_allocation":
                    classify_allocation(row["allocation_raw"]),
                "allocation_detail":
                    clean(row["allocation_raw"]),
                "population_model":
                    classify_model(row["model_raw"]),
                "program_structure":
                    classify_structure(row["structure_raw"]),
                "year_established": year,
                "feeder_pathway":
                    norm_na(row["feeder_raw"]),
                "program_notes":
                    norm_na(row["notes_raw"]),
                "source_district_raw":
                    clean(row["district_raw"]),
                "source_school_raw": original_school,
                "source_language_raw": source_language,
                "source_population_model_raw": source_model,
                "source_structure_raw":
                    norm_na(row["structure_raw"]),
                "verification_status": status,
                "source_page": row["page"],
                "source_url": SOURCE_URL,
                "source_sha256": digest,
                "nces_school_id": "",
                "nces_match_status": "not_yet_matched",
            }

            # Retain separate language tracks.
            # Do not duplicate identical source observations.
            key = (
                district.casefold(),
                school.casefold(),
                language.casefold(),
                row["page"],
                record["allocation_detail"],
                record["source_population_model_raw"],
            )

            if key in seen:
                ignored["duplicate_source_observation"] += 1
                continue

            seen.add(key)
            records.append(record)

    return records, dict(ignored)


# ==========================================
# OUTPUTS AND VALIDATION
# ==========================================

def write_csv(path, fields, records):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w", newline="", encoding="utf-8"
    ) as out:
        writer = csv.DictWriter(
            out,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        help="Read a local copy of the source PDF",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/registry"),
    )
    args = parser.parse_args()

    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    pdf_path = (
        args.pdf
        or output / "_oregon_source_temp.pdf"
    )

    if not args.pdf:
        response = requests.get(
            SOURCE_URL,
            timeout=120,
            headers={
                "User-Agent":
                    "Mozilla/5.0 "
                    "(compatible; StateDLResearch/1.0)"
            },
        )
        response.raise_for_status()

        if not response.content.startswith(b"%PDF"):
            raise RuntimeError(
                "Oregon source did not return a PDF"
            )

        pdf_path.write_bytes(response.content)

    try:
        digest = hashlib.sha256(
            pdf_path.read_bytes()
        ).hexdigest()

        rows, diagnostics = source_rows(pdf_path)
        records, excluded = build_records(rows, digest)

        write_csv(
            output / "oregon_2026_27_extraction_audit.csv",
            AUDIT_FIELDS,
            rows,
        )
        write_csv(
            output / "state_dl_programs_oregon.csv",
            OUTPUT_FIELDS,
            records,
        )

        summary = {
            "state": "OR",
            "source_school_year": YEAR,
            "source_url": SOURCE_URL,
            "extracted_utc":
                datetime.now(timezone.utc).isoformat(),
            "source_sha256": digest,
            "raw_directory_rows": len(rows),
            "program_observations": len(records),
            "quarantined_source_rows": sum(
                bool(r["extraction_issue"]) for r in rows
            ),
            "exclusion_reasons": excluded,
            "school_name_corrections": sum(
                "verified_school_name_correction"
                in r.get("normalization_note", "")
                for r in rows
            ),
            "language_cell_corrections": sum(
                "verified_language_cell_correction"
                in r.get("normalization_note", "")
                for r in rows
            ),
            "verification_status_counts": dict(
                Counter(
                    r["verification_status"]
                    for r in records
                )
            ),
            "allocation_counts": dict(
                Counter(
                    r["instructional_allocation"]
                    for r in records
                )
            ),
            "structure_counts": dict(
                Counter(
                    r["program_structure"]
                    for r in records
                )
            ),
            "population_model_counts": dict(
                Counter(
                    r["population_model"]
                    for r in records
                )
            ),
            "page_diagnostics": diagnostics,
            "caution": (
                "2026-27 only. Quarantined rows need "
                "source inspection; do not infer NCES "
                "IDs or historical instructional models."
            ),
        }

        (
            output / "oregon_2026_27_summary.json"
        ).write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )

        print(json.dumps(summary, indent=2))

        if (
            not 70 <= len(rows) <= 350
            or len(records) < 70
        ):
            raise RuntimeError(
                "Implausible row count. Inspect extraction audit."
            )

        if summary["quarantined_source_rows"] > max(
            15, len(rows) // 10
        ):
            raise RuntimeError(
                "Too many quarantined rows. Inspect audit."
            )

        for expected in (
            "Arco Iris",
            "Barnes Elementary",
            "Hazeldale Elementary",
            "Independence Elementary School",
            "North Gresham Elementary",
            "Four Rivers Community Charter School",
            "Warm Springs K-8 Academy",
        ):
            if not any(
                expected.casefold()
                in r["school_name"].casefold()
                for r in records
            ):
                raise RuntimeError(
                    f"Expected school not extracted: {expected}"
                )

        if digest == KNOWN_SOURCE_SHA256:
            counts = Counter(
                r["verification_status"]
                for r in records
            )
            if (
                counts[
                    "excluded_heritage_language_not_dli"
                ] != 11
                or counts[
                    "excluded_native_language_revitalization_not_dli"
                ] != 1
            ):
                raise RuntimeError(
                    "Non-DLI classifications differ from "
                    "the audited PDF; inspect records."
                )

    finally:
        if not args.pdf and pdf_path.exists():
            pdf_path.unlink()


if __name__ == "__main__":
    main()
