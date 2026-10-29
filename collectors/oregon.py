
#!/usr/bin/env python3
"""
Extract the 2026-27 Oregon dual-language directory.

Output:
  data/registry/state_dl_programs_oregon.csv
  data/registry/oregon_2026_27_extraction_audit.csv
  data/registry/oregon_2026_27_summary.json

The directory provides school, language,
allocation, population model, program structure,
year established, pathways, and notes.

NCES IDs are deliberately left unmatched.
Historical instructional models are not inferred.
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

# Nine column boundaries in the Oregon PDF,
# expressed as fractions of page width.
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


def clean(value):
    return re.sub(
        r"\s+", " ", str(value or "")
    ).strip()


def norm_na(value):
    s = clean(value)
    if s.lower() in ("", "n/a", "na", "none", "-"):
        return ""
    return s


def classify_model(raw):
    value = (
        norm_na(raw)
        .lower()
        .replace("‐", "-")
        .replace("–", "-")
    )

    if (
        "two-way" in value
        or "two way" in value
        or "(twi)" in value
    ):
        return "two_way"

    if (
        "one-way" in value
        or "one way" in value
        or "(owi)" in value
    ):
        return "one_way"

    return "unknown"


def classify_structure(raw):
    value = (
        norm_na(raw)
        .lower()
        .replace("-", " ")
    )

    if (
        "whole school" in value
        or "schoolwide" in value
    ):
        return "whole_school"

    if (
        "strand" in value
        or "cohort within" in value
    ):
        return "strand"

    return "unknown"


def classify_allocation(raw):
    value = norm_na(raw)

    matches = re.findall(
        r"(?<!\d)(\d{1,3})\s*/\s*"
        r"(\d{1,3})(?!\d)",
        value,
    )

    ratios = sorted({
        f"{int(a)}-{int(b)}"
        for a, b in matches
        if int(a) + int(b) == 100
    })

    if len(ratios) == 1:
        return ratios[0]

    if len(ratios) > 1:
        return "varies_by_grade"

    if value:
        return "other"

    return "unknown"


def language_values(raw):
    value = norm_na(raw)

    if not value:
        return ["unknown"]

    # Preserve the original language cell in
    # the output. A multi-language cell will
    # also receive a review flag.

    items = [
        clean(item)
        for item in re.split(r";|\n", raw)
        if clean(item)
    ]

    return items or [value]


# ========================================
# PDF TABLE EXTRACTION
# ========================================

def header_bottom(page):
    words = page.extract_words()

    candidates = [
        word["bottom"]
        for word in words
        if (
            word["text"].lower() == "district"
            and word["top"] < .20 * page.height
            and word["x0"] < .25 * page.width
        )
    ]

    if not candidates:
        raise RuntimeError(
            "Could not locate the "
            "School District table header."
        )

    return max(candidates) + 2


def footer_top(page):
    words = page.extract_words()

    footers = [
        word["top"]
        for word in words
        if (
            word["top"] > .82 * page.height
            and "patiño" in word["text"].lower()
        )
    ]

    if footers:
        return min(footers) - 3

    return page.height * .92


def row_spans(page, first_y, final_y):
    """
    Locate shaded rows in the PDF.

    The alternating blue and white rows
    provide row boundaries even when
    individual cells contain several lines.
    """

    bands = []

    for item in (
        list(page.rects) + list(page.curves)
    ):

        x0 = item.get("x0", -1)
        x1 = item.get("x1", -1)

        top = item.get("top", -1)
        bottom = item.get("bottom", -1)

        height = bottom - top

        if not (
            first_y < top < bottom < final_y
        ):
            continue

        if not (
            .045 * page.width <= x0
            <= .09 * page.width
            and x1 >= .16 * page.width
            and 5 <= height <= 95
        ):
            continue

        if (
            item.get("non_stroking_color")
            is None
        ):
            continue

        bands.append((top, bottom))

    unique = {}

    for top, bottom in bands:
        unique[
            (round(top, 1), round(bottom, 1))
        ] = (top, bottom)

    bands = sorted(unique.values())

    if len(bands) < 2:
        raise RuntimeError(
            "Too few shaded table rows found. "
            "The PDF layout may have changed."
        )

    edges = [first_y, final_y]

    for top, bottom in bands:
        edges.extend([top, bottom])

    edges.sort()

    merged = []

    for edge in edges:
        if (
            not merged
            or edge - merged[-1] > 1.2
        ):
            merged.append(edge)

    return [
        (a, b)
        for a, b in zip(
            merged, merged[1:]
        )
        if b - a > 3
    ]


def extract_rows(pdf_path):
    rows = []
    diagnostics = []

    with pdfplumber.open(pdf_path) as doc:

        for pageno, page in enumerate(
            doc.pages, 1
        ):

            top = header_bottom(page)
            bottom = footer_top(page)

            spans = row_spans(
                page, top, bottom
            )

            diagnostics.append({
                "page": pageno,
                "candidate_spans": len(spans),
                "page_width": page.width,
                "page_height": page.height,
                "rectangles": len(page.rects),
            })

            for y0, y1 in spans:

                values = []

                for a, b in zip(
                    CUTS, CUTS[1:]
                ):

                    cropped = page.crop((
                        page.width * a + .7,
                        y0 + .4,
                        page.width * b - .7,
                        y1 - .4,
                    ))

                    text = (
                        cropped.extract_text(
                            x_tolerance=2,
                            y_tolerance=3,
                        )
                        or ""
                    ).strip()

                    values.append(text)

                if (
                    not clean(values[0])
                    and not clean(values[1])
                ):
                    continue

                if (
                    "School District" in values[0]
                    or "Dual Language Directory"
                    in values[0]
                ):
                    continue

                rows.append({
                    "page": pageno,
                    **dict(
                        zip(HEADERS, values)
                    ),
                })

    return rows, diagnostics


# ========================================
# STANDARDIZE THE PROGRAM RECORDS
# ========================================

def build_records(rows, digest):
    records = []

    for row in rows:

        district = clean(
            row["district_raw"]
        )

        school = clean(
            row["school_raw"]
        )

        if not district or not school:
            continue

        if not norm_na(
            row["language_raw"]
        ):
            continue

        original_text = (
            row["model_raw"]
            + " "
            + row["notes_raw"]
        )

        if re.search(
            r"Native Language Program"
            r"|not a dual language",
            original_text,
            re.I,
        ):
            status = (
                "needs_review_possible_non_DL"
            )
        else:
            status = (
                "listed_in_state_directory"
            )

        raw_year = norm_na(
            row["year_established_raw"]
        )

        if re.fullmatch(
            r"(19|20)\d{2}",
            raw_year,
        ):
            start = raw_year
        else:
            start = ""

        languages = language_values(
            row["language_raw"]
        )

        if (
            len(languages) > 1
            and status
            == "listed_in_state_directory"
        ):
            status = (
                "listed_multi_language_cell_"
                "needs_review"
            )

        for language in languages:

            records.append({
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

                "year_established": start,

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
            })

    return records


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


# ========================================
# MAIN
# ========================================

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "--pdf",
        type=Path,
        help="Use a local PDF instead",
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

    pdf_file = (
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
                "Source did not return a PDF."
            )

        pdf_file.write_bytes(
            response.content
        )

    try:

        digest = hashlib.sha256(
            pdf_file.read_bytes()
        ).hexdigest()

        rows, diagnostics = extract_rows(
            pdf_file
        )

        records = build_records(
            rows, digest
        )

        write_csv(
            output
            / "oregon_2026_27_extraction_audit.csv",
            ["page", *HEADERS],
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
                "2026-27 observations only; "
                "do not backfill earlier years "
                "or infer NCES identifiers."
            ),
        }

        (
            output
            / "oregon_2026_27_summary.json"
        ).write_text(
            json.dumps(
                summary,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            json.dumps(
                summary,
                indent=2,
            )
        )

        # Fail visibly if we have not
        # extracted a plausible directory.

        if not 70 <= len(rows) <= 350:
            raise RuntimeError(
                "Unexpected directory row count: "
                f"{len(rows)}. Inspect audit."
            )

        if len(records) < 70:
            raise RuntimeError(
                "Too few program observations. "
                "Inspect extraction audit."
            )

        for expected in (
            "Aloha-Huber Park",
            "Barnes Elementary",
            "Hazeldale Elementary",
        ):

            if not any(
                expected.lower()
                in r["school_name"].lower()
                for r in records
            ):
                raise RuntimeError(
                    "Known school not parsed: "
                    f"{expected}"
                )

    finally:

        if (
            not args.pdf
            and pdf_file.exists()
        ):
            pdf_file.unlink()


if __name__ == "__main__":
    main()
