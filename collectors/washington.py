
#!/usr/bin/env python3
"""Collect Washington's public dual-language report-card data.

Preserves original rows and creates a provisional school
inventory. Does not infer language pairs or DL models.
"""

import argparse
import csv
import json
import re
import sys
import time

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DATASET_ID = "d4w4-82bk"
SOURCE_URL = f"https://data.wa.gov/d/{DATASET_ID}"
API_URL = f"https://data.wa.gov/resource/{DATASET_ID}.json"

PAGE_SIZE = 5000
MAX_ROWS = 200000


def canonical(value):
    return re.sub(
        r"[^a-z0-9]", "",
        str(value).lower()
    )


def column(fields, *aliases):
    lookup = {canonical(k): k for k in fields}
    for alias in aliases:
        if canonical(alias) in lookup:
            return lookup[canonical(alias)]
    return None


def get_json(url):
    for attempt in range(5):
        try:
            req = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent":
                        "DL-Outcomes-Research/0.1",
                },
            )
            with urlopen(req, timeout=75) as response:
                return json.load(response)

        except HTTPError as exc:
            if (
                exc.code not in
                (429, 500, 502, 503, 504)
                or attempt == 4
            ):
                raise

        except (URLError, TimeoutError, ConnectionError):
            if attempt == 4:
                raise

        time.sleep(2 ** attempt)

    raise RuntimeError("Exceeded retries")


def fetch_rows():
    rows = []

    for offset in range(
        0, MAX_ROWS + 1, PAGE_SIZE
    ):
        params = urlencode({
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$order": ":id",
        })

        page = get_json(
            API_URL + "?" + params
        )

        if not isinstance(page, list):
            raise ValueError(
                "Expected JSON array; API schema changed"
            )

        if not all(
            isinstance(x, dict) for x in page
        ):
            raise ValueError(
                "Unexpected source row"
            )

        if offset == MAX_ROWS and page:
            raise RuntimeError(
                "Safety limit reached; incomplete download"
            )

        rows.extend(page)

        print(
            f"Fetched {len(rows)} rows",
            flush=True,
        )

        if len(page) < PAGE_SIZE:
            break

    if not rows:
        raise RuntimeError(
            "Source returned zero rows"
        )

    return rows


def write_csv(path, records, fields):
    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(records)


def make_outputs(rows, output):
    fields = sorted(
        set().union(*(r.keys() for r in rows))
    )

    mapping = {
        "organization_level": column(
            fields,
            "organizationlevel",
            "organization_level",
            "organizationtype",
            "organizationlevelname",
            "datalevel",
        ),
        "school_name": column(
            fields,
            "schoolname",
            "school_name",
            "schoolorganizationname",
            "schoolfullname",
            "school",
        ),
        "school_id": column(
            fields,
            "schoolorganizationid",
            "school_organization_id",
            "schoolcode",
            "school_code",
            "schoolid",
            "schoolorganizationcode",
        ),
        "district_name": column(
            fields,
            "districtname",
            "district_name",
            "leaname",
            "lea_name",
            "districtorganizationname",
        ),
        "school_year": column(
            fields,
            "schoolyear",
            "school_year",
            "reportingyear",
            "schoolyearcode",
        ),
    }

    # Preserve original published records.
    write_csv(
        output / "wa_dual_language_source_rows.csv",
        rows,
        fields,
    )

    # Field audit, including example values.
    columns = []

    for field in fields:
        example = next(
            (
                str(r[field])
                for r in rows
                if r.get(field) not in (None, "")
            ),
            "",
        )

        columns.append({
            "source_field": field,
            "normalized_field": canonical(field),
            "example_nonempty_value": example,
        })

    write_csv(
        output / "source_columns.csv",
        columns,
        [
            "source_field",
            "normalized_field",
            "example_nonempty_value",
        ],
    )

    candidates = {}
    level_counts = Counter()
    rejected = Counter()

    for r in rows:
        def field_value(name):
            key = mapping[name]
            return str(
                r.get(key, "") if key else ""
            ).strip()

        level = field_value(
            "organization_level"
        ).lower()

        school = field_value("school_name")
        school_id = field_value("school_id")
        district = field_value("district_name")
        year = field_value("school_year")

        level_counts[
            level or "(not supplied)"
        ] += 1

        if mapping["organization_level"]:
            is_school = level in (
                "school",
                "school level",
                "school-level",
                "school building",
            )
        else:
            is_school = bool(
                school and school_id
            )

        if not is_school:
            rejected[
                "non_school_level_or_unknown"
            ] += 1
            continue

        if not school and not school_id:
            rejected[
                "missing_school_identity"
            ] += 1
            continue

        key = (
            year,
            school_id or canonical(school),
            canonical(district),
        )

        if key not in candidates:
            candidates[key] = {
                "state": "WA",
                "source_dataset_id": DATASET_ID,
                "school_year": year,
                "school_name": school,
                "district_name": district,
                "state_school_id": school_id,
                "source_row_count": 0,
                "language_pair": "",
                "starting_model": "",
                "verification_status":
                    "candidate_needs_review",
                "source_url": SOURCE_URL,
            }

        candidates[key][
            "source_row_count"
        ] += 1

    school_rows = sorted(
        candidates.values(),
        key=lambda r: (
            r["school_year"],
            r["district_name"],
            r["school_name"],
            r["state_school_id"],
        ),
    )

    write_csv(
        output / "wa_school_candidates.csv",
        school_rows,
        [
            "state",
            "source_dataset_id",
            "school_year",
            "school_name",
            "district_name",
            "state_school_id",
            "source_row_count",
            "language_pair",
            "starting_model",
            "verification_status",
            "source_url",
        ],
    )

    report = {
        "generated_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "source_url": SOURCE_URL,
        "source_dataset_id": DATASET_ID,
        "download_status": "success",
        "source_rows": len(rows),
        "source_fields": len(fields),
        "school_year_candidate_records":
            len(school_rows),
        "distinct_source_school_ids": len({
            r["state_school_id"]
            for r in school_rows
            if r["state_school_id"]
        }),
        "field_mapping": mapping,
        "organization_levels":
            dict(level_counts),
        "excluded_rows": dict(rejected),
        "caution": [
            "Candidate schools are not verified "
            "Spanish-English DL programs.",
            "No instructional allocations inferred.",
            "These are not DL-participant "
            "assessment outcomes.",
            "Existing registry files unchanged.",
        ],
    }

    (
        output / "collection_report.json"
    ).write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    if not school_rows:
        raise RuntimeError(
            "No school rows identified. "
            "Inspect source_columns.csv and report."
        )

    return report


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/washington"),
    )

    parser.add_argument(
        "--input-json",
        type=Path,
        help="Optional local JSON test fixture",
    )

    args = parser.parse_args()

    args.output.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        if args.input_json:
            rows = json.loads(
                args.input_json.read_text(
                    encoding="utf-8"
                )
            )
        else:
            rows = fetch_rows()

        if not isinstance(rows, list) or not rows:
            raise ValueError(
                "Expected nonempty list of rows"
            )

        report = make_outputs(
            rows,
            args.output,
        )

        for key in (
            "source_rows",
            "school_year_candidate_records",
            "distinct_source_school_ids",
        ):
            print(key, report[key])

    except Exception as exc:
        print(
            f"COLLECTOR FAILED: {exc}",
            file=sys.stderr,
        )
        (
            args.output / "run_error.txt"
        ).write_text(
            str(exc) + "\n",
            encoding="utf-8",
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
