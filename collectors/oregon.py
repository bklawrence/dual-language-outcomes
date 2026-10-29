
#!/usr/bin/env python3
"""
Extract Oregon's 2026-27 dual-language directory.

Fixes:
- Separates actual PDF table rows
- Prevents neighboring school records from merging
- Preserves multiline names and notes
- Handles schools listing multiple languages
- Quarantines ambiguous records instead of guessing

Outputs:
  data/registry/state_dl_programs_oregon.csv
  data/registry/oregon_2026_27_extraction_audit.csv
  data/registry/oregon_2026_27_summary.json

NCES IDs and historical models are not inferred.
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
    "https://www.oregon.gov/ode/"
    "schools-and-districts/MME/Documents/"
    "Dual%20Language%20Directory%202026-2027.pdf"
)

YEAR = "2026-27"

HEADERS = [
    "district_raw",
    "school_raw",
    "language_raw",
    "allocation_raw",
    "model_raw",
    "structure_raw",
    "year_established_raw",
    "feeder_raw",
    "notes_raw",
]

CUTS = [
    .064, .175, .272, .344, .412,
    .511, .593, .657, .775, .921,
]

OUTPUT_FIELDS = [
    "state",
    "school_year",
    "district_name",
    "school_name",
    "partner_language",
    "instructional_allocation",
    "allocation_detail",
    "population_model",
    "program_structure",
    "year_established",
    "feeder_pathway",
    "program_notes",
    "source_district_raw",
    "source_school_raw",
    "source_language_raw",
    "source_population_model_raw",
    "source_structure_raw",
    "verification_status",
    "source_page",
    "source_url",
    "source_sha256",
    "nces_school_id",
    "nces_match_status",
]

AUDIT_FIELDS = [
    "page",
    "row_top",
    "row_bottom",
    "extraction_issue",
    *HEADERS,
]

KNOWN_LANGUAGES = (
    "Mandarin Chinese",
    "Spanish",
    "Russian",
    "French",
    "Japanese",
    "Chinese",
    "Korean",
    "Vietnamese",
    "Arabic",
    "German",
    "Portuguese",
    "Hawaiian",
    "Indigenous",
    "English",
)


# ==========================================
# TEXT NORMALIZATION
# ==========================================

def clean(value):
    return re.sub(
        r"\s+", " ", str(value or "")
    ).strip()


def norm_na(value):
    text = clean(value)
    return (
        ""
        if text.lower() in {
            "", "n/a", "na", "none", "-"
        }
        else text
    )


def classify_model(raw):
    val = (
        norm_na(raw)
        .lower()
        .replace("‐", "-")
        .replace("–", "-")
    )

    if (
        "two-way" in val
        or "two way" in val
        or "(twi)" in val
    ):
        return "two_way"

    if (
        "one-way" in val
        or "one way" in val
        or "(owi)" in val
    ):
        return "one_way"

    return "unknown"


def classify_structure(raw):
    val = (
        norm_na(raw)
        .lower()
        .replace("-", " ")
    )

    if (
        "whole school" in val
        or "schoolwide" in val
    ):
        return "whole_school"

    if (
        "strand" in val
        or "cohort within" in val
    ):
        return "strand"

    return "unknown"


def classify_allocation(raw):
    matches = re.findall(
        r"(?<!\d)(\d{1,3})\s*/\s*"
        r"(\d{1,3})(?!\d)",
        norm_na(raw),
    )

    ratios = {
        f"{int(a)}-{int(b)}"
        for a, b in matches
        if int(a) + int(b) == 100
    }

    if len(ratios) == 1:
        return next(iter(ratios))

    if len(ratios) > 1:
        return "varies_by_grade"

    return (
        "other"
        if norm_na(raw)
        else "unknown"
    )


def language_values(raw):
    """
    Separate recognizable language names.

    'Mandarin Chinese' is one language.
    'Spanish Russian' represents two languages.

    Unrecognized text is quarantined.
    """

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
                    name
                    for name in KNOWN_LANGUAGES
                    if (
                        remaining == name
                        or remaining.startswith(
                            name + " "
                        )
                    )
                ),
                None,
            )

            if not found:
                break

            parsed.append(found)

            remaining = remaining[
                len(found):
            ].strip()

        if parsed and not remaining:
            result.extend(parsed)
        else:
            issues.append(
                "unrecognized_language_text"
            )

    if issues:
        return [], ";".join(
            sorted(set(issues))
        )

    languages = list(
        dict.fromkeys(result)
    )

    issue = (
        "multi_language_cell"
        if len(languages) > 1
        else ""
    )

    return languages, issue


# ==========================================
# LOCATE PDF TABLE
# ==========================================

def header_bottom(page):
    words = page.extract_words()

    bottoms = [
        word["bottom"]
        for word in words
        if (
            word["text"].lower() == "district"
            and word["top"] < page.height * .20
            and word["x0"] < page.width * .25
        )
    ]

    if not bottoms:
        raise RuntimeError(
            "Oregon table header not found."
        )

    return max(bottoms) + 1.0


def footer_top(page):
    words = page.extract_words()

    footers = [
        word["top"]
        for word in words
        if (
            word["top"] > .77 * page.height
            and "patiño" in word["text"].lower()
        )
    ]

    if footers:
        return min(footers) - 2

    return .94 * page.height


# ==========================================
# DETECT COMPLETE TABLE ROWS
# ==========================================

def is_blue_fill(obj):
    """
    Identify Oregon's alternating
    pale-blue row backgrounds.
    """

    if obj.get("fill") is False:
        return False

    color = obj.get(
        "non_stroking_color"
    )

    if (
        not isinstance(color, (tuple, list))
        or len(color) < 3
    ):
        return False

    red, green, blue = color[:3]

    return (
        isinstance(red, (int, float))
        and .45 <= red < .96
        and green >= red
        and blue > red + .035
    )


def shaded_bands(page, top, bottom):
    """
    Find complete shaded rows.

    Crucially, do not use every rectangle
    boundary independently as a row cut.
    """

    matches = []

    for obj in (
        list(page.rects)
        + list(page.curves)
    ):
        x0 = obj.get("x0", -1)
        x1 = obj.get("x1", -1)

        y0 = obj.get("top", -1)
        y1 = obj.get("bottom", -1)

        if not (
            top - 6 <= y0 < y1 <= bottom + 3
        ):
            continue

        if not (
            .052 * page.width <= x0
            <= .085 * page.width
            and x1 >= .16 * page.width
        ):
            continue

        if not (
            5 <= y1 - y0
            <= .35 * page.height
        ):
            continue

        if is_blue_fill(obj):
            matches.append((
                max(top, y0),
                min(bottom, y1),
            ))

    matches.sort()

    bands = []

    for start, stop in matches:
        if (
            bands
            and start <= bands[-1][1] + 1.5
        ):
            bands[-1] = (
                min(start, bands[-1][0]),
                max(stop, bands[-1][1]),
            )
        else:
            bands.append((
                start, stop
            ))

    return bands


def candidate_spans(page, first, last):
    """
    Each shaded band is one row.

    Each white gap between shaded bands
    is another row.

    This prevents the accidental creation
    of overlapping composite school rows.
    """

    bands = shaded_bands(
        page, first, last
    )

    if not bands:
        raise RuntimeError(
            "No blue table rows found. "
            "Inspect PDF layout."
        )

    candidates = []
    position = first

    for start, stop in bands:
        if start - position > 3:
            candidates.append((
                position,
                start,
                "white",
            ))

        if stop - start > 3:
            candidates.append((
                start,
                stop,
                "blue",
            ))

        position = max(
            position, stop
        )

    if last - position > 3:
        candidates.append((
            position,
            last,
            "white",
        ))

    return candidates, len(bands)


# ==========================================
# EXTRACT CHARACTERS WITHIN EACH ROW
# ==========================================

def cell_text(chars, x0, x1, y0, y1):
    """
    Assign characters according to their
    center coordinates.

    This avoids borrowing text from a
    neighboring row when the PDF's
    character boxes overlap row boundaries.
    """

    selected = [
        char
        for char in chars
        if (
            x0 <= (
                char["x0"] + char["x1"]
            ) / 2 < x1
            and y0 <= (
                char["top"] + char["bottom"]
            ) / 2 < y1
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
    rows = []
    diagnostics = []

    with pdfplumber.open(pdf_path) as doc:

        for page_no, page in enumerate(
            doc.pages, 1
        ):
            first = header_bottom(page)
            last = footer_top(page)

            spans, band_count = (
                candidate_spans(
                    page, first, last
                )
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
                char
                for char in page.chars
                if (
                    first <= (
                        char["top"]
                        + char["bottom"]
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
                    for a, b in zip(
                        CUTS, CUTS[1:]
                    )
                ]

                if (
                    not clean(cells[0])
                    and not clean(cells[1])
                ):
                    continue

                row = {
                    "page": page_no,
                    "row_top": round(y0, 2),
                    "row_bottom": round(y1, 2),
                    **dict(zip(
                        HEADERS, cells
                    )),
                }

                issues = []

                district_lines = [
                    x
                    for x in cells[0].splitlines()
                    if clean(x)
                ]

                if len(district_lines) > 1:
                    issues.append(
                        "multiple_district_lines"
                    )

                if (
                    not norm_na(cells[0])
                    or not norm_na(cells[1])
                ):
                    issues.append(
                        "missing_school_or_district"
                    )

                if not norm_na(cells[2]):
                    issues.append(
                        "missing_language"
                    )

                if clean(cells[0]).lower().startswith(
                    "school district"
                ):
                    issues.append(
                        "header_contamination"
                    )

                row["extraction_issue"] = (
                    ";".join(issues)
                )

                rows.append(row)

    return rows, diagnostics


# ==========================================
# CONSTRUCT SCHOOL PROGRAM RECORDS
# ==========================================

def build_records(rows, digest):
    records = []
    ignored = Counter()
    seen = set()

    for row in rows:

        # Never publish a row that still
        # contains an extraction ambiguity.

        if row["extraction_issue"]:
            ignored[
                "quarantined_geometry"
            ] += 1
            continue

        languages, lang_issue = (
            language_values(
                row["language_raw"]
            )
        )

        if not languages:
            ignored[
                lang_issue
                or "unrecognized_language"
            ] += 1

            row["extraction_issue"] = (
                lang_issue
                or "unrecognized_language"
            )
            continue

        district = clean(
            row["district_raw"]
        )

        school = clean(
            row["school_raw"]
        )

        # Do not publish school names that
        # visibly begin with stray fragments
        # or end with an isolated letter.

        suspect_school = (
            re.match(
                r"^(?:School\b|Charter\b|\(EIHS\))",
                school,
                re.I,
            )
            or re.search(
                r"\b[A-Z]$",
                school,
            )
        )

        if suspect_school:
            row["extraction_issue"] = (
                "school_name_fragment"
            )

            ignored[
                "school_name_fragment"
            ] += 1
            continue

        raw_year = norm_na(
            row["year_established_raw"]
        )

        year = (
            raw_year
            if re.fullmatch(
                r"(?:19|20)\d{2}",
                raw_year,
            )
            else ""
        )

        for language in languages:

            status = (
                "listed_in_state_directory"
            )

            if lang_issue:
                status = (
                    "listed_multi_language_cell_"
                    "needs_review"
                )

            original_text = (
                row["model_raw"]
                + " "
                + row["notes_raw"]
            )

            if re.search(
                r"native language program"
                r"|not a dual language",
                original_text,
                re.I,
            ):
                status = (
                    "needs_review_possible_non_DL"
                )

            record = {
                "state": "OR",
                "school_year": YEAR,

                "district_name": district,
                "school_name": school,
                "partner_language": language,

                "instructional_allocation":
                    classify_allocation(
                        row["allocation_raw"]
                    ),

                "allocation_detail":
                    clean(
                        row["allocation_raw"]
                    ),

                "population_model":
                    classify_model(
                        row["model_raw"]
                    ),

                "program_structure":
                    classify_structure(
                        row["structure_raw"]
                    ),

                "year_established": year,

                "feeder_pathway":
                    norm_na(
                        row["feeder_raw"]
                    ),

                "program_notes":
                    norm_na(
                        row["notes_raw"]
                    ),

                "source_district_raw":
                    district,

                "source_school_raw":
                    school,

                "source_language_raw":
                    clean(
                        row["language_raw"]
                    ),

                "source_population_model_raw":
                    norm_na(
                        row["model_raw"]
                    ),

                "source_structure_raw":
                    norm_na(
                        row["structure_raw"]
                    ),

                "verification_status":
                    status,

                "source_page":
                    row["page"],

                "source_url":
                    SOURCE_URL,

                "source_sha256":
                    digest,

                "nces_school_id": "",

                "nces_match_status":
                    "not_yet_matched",
            }

            key = (
                district.casefold(),
                school.casefold(),
                language.casefold(),
                row["page"],
                record["allocation_detail"],
                record[
                    "source_population_model_raw"
                ],
            )

            if key in seen:
                ignored[
                    "duplicate_source_observation"
                ] += 1
                continue

            seen.add(key)
            records.append(record)

    return records, dict(ignored)


# ==========================================
# FILE OUTPUT
# ==========================================

def write_csv(path, fields, records):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(records)


# ==========================================
# MAIN
# ==========================================

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "--pdf",
        type=Path,
        help="Read a local PDF instead",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/registry"),
    )

    args = parser.parse_args()

    output = args.output
    output.mkdir(
        parents=True,
        exist_ok=True,
    )

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

        if not response.content.startswith(
            b"%PDF"
        ):
            raise RuntimeError(
                "Oregon source did not return a PDF."
            )

        pdf_path.write_bytes(
            response.content
        )

    try:
        digest = hashlib.sha256(
            pdf_path.read_bytes()
        ).hexdigest()

        rows, diagnostics = source_rows(
            pdf_path
        )

        records, excluded = build_records(
            rows, digest
        )

        write_csv(
            output
            / "oregon_2026_27_extraction_audit.csv",
            AUDIT_FIELDS,
            rows,
        )

        write_csv(
            output
            / "state_dl_programs_oregon.csv",
            OUTPUT_FIELDS,
            records,
        )

        summary = {
            "state": "OR",
            "source_school_year": YEAR,
            "source_url": SOURCE_URL,

            "extracted_utc":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "source_sha256": digest,

            "raw_directory_rows":
                len(rows),

            "program_observations":
                len(records),

            "quarantined_source_rows":
                sum(
                    bool(r["extraction_issue"])
                    for r in rows
                ),

            "exclusion_reasons":
                excluded,

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

            "page_diagnostics":
                diagnostics,

            "caution": (
                "2026-27 only. Quarantined rows "
                "need source inspection. Do not "
                "infer NCES IDs or historical "
                "instructional models."
            ),
        }

        (
            output
            / "oregon_2026_27_summary.json"
        ).write_text(
            json.dumps(
                summary,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        print(
            json.dumps(
                summary,
                indent=2,
            )
        )

        # Fail visibly if extraction is
        # implausible or too ambiguous.

        if (
            not 70 <= len(rows) <= 350
            or len(records) < 70
        ):
            raise RuntimeError(
                "Implausible directory row count. "
                "Inspect extraction audit."
            )

        if (
            summary["quarantined_source_rows"]
            > max(15, len(rows) // 10)
        ):
            raise RuntimeError(
                "Too many quarantined rows. "
                "Inspect audit before publishing."
            )

        for expected in (
            "Arco Iris",
            "Barnes Elementary",
            "Hazeldale Elementary",
        ):
            if not any(
                expected.casefold()
                in r["school_name"].casefold()
                for r in records
            ):
                raise RuntimeError(
                    "Expected school not extracted: "
                    + expected
                )

    finally:
        if (
            not args.pdf
            and pdf_path.exists()
        ):
            pdf_path.unlink()


if __name__ == "__main__":
    main()
