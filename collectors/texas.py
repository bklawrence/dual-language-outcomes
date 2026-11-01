
#!/usr/bin/env python3
"""Collect the complete Texas 2024-25 AskTED campus directory.

This is a complete school roster plus a NAME-BASED DLI SCREENING QUEUE,
not a verified DLI program list. Preserve all campuses for future comparisons.

Texas AskTED uses leading apostrophes to preserve leading zeros in identifiers.
Those apostrophes are formatting, not part of the school or NCES number.

Run: python3 collectors/texas.py --out output/texas
Requires Python 3.10+ standard library only.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LAYER = (
    "https://services2.arcgis.com/5MVN2jsqIrNZD4tP/ArcGIS/rest/services/"
    "Schools_2024_to_2025/FeatureServer/0"
)
YEAR = "2024-25"

FIELDS = [
    "ObjectID",
    "USER_District_Number",
    "USER_District_Name",
    "USER_School_Number",
    "USER_School_Name",
    "USER_NCES_District_ID",
    "USER_NCES_School_ID",
    "USER_Grade_Range",
    "USER_School_Enrollment_as_of_Oc",
    "USER_Instruction_Type",
    "USER_School_City",
    "USER_School_State",
    "USER_School_Street_Address",
    "USER_School_Zip",
    "USER_School_Web_Page_Address",
]

CAMPUS_FIELDS = [
    "state", "school_year", "texas_campus_id", "texas_district_id",
    "texas_school_number", "school_name", "district_name",
    "nces_school_id_reported", "nces_district_id_reported",
    "nces_id_status", "grade_range", "school_enrollment_oct_2024",
    "instruction_type_source", "city", "school_state", "street_address",
    "postal_code", "school_webpage", "source_object_id", "source_url",
    "program_verification_status", "dual_language_reported",
    "instructional_language", "one_way_two_way", "allocation_model",
    "whole_school_or_strand", "first_program_year", "program_source_url",
]

CANDIDATE_FIELDS = CAMPUS_FIELDS + [
    "name_signal", "screening_reason", "review_priority",
]


def get_json(url: str) -> dict:
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "dual-language-outcomes-research/1.1"
                },
            )
            with urllib.request.urlopen(request, timeout=90) as response:
                data = json.load(response)

            if not isinstance(data, dict) or "error" in data:
                raise RuntimeError(
                    f"Unexpected ArcGIS response: {str(data)[:600]}"
                )

            return data

        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == 3:
                raise RuntimeError(
                    f"ArcGIS request failed: {url[:180]}"
                ) from exc

            time.sleep(2 * (attempt + 1))

    raise AssertionError("Unreachable")


def query(params: dict) -> dict:
    url = LAYER + "/query?" + urllib.parse.urlencode(params)
    return get_json(url)


def get_metadata() -> dict:
    metadata = get_json(LAYER + "?f=pjson")
    available = {
        f["name"]
        for f in metadata.get("fields", [])
    }

    missing = set(FIELDS) - available

    if missing:
        raise ValueError(
            f"ArcGIS source changed; missing fields: {sorted(missing)}"
        )

    return metadata


def value(row: dict, field: str) -> str:
    data = row.get(field)
    return "" if data is None else str(data).strip()


def digits(raw: str) -> str:
    """Remove AskTED spreadsheet apostrophes and known separators.

    Examples:
        "'001902" -> "001902"
        "'001902001" -> "001902001"

    Never invent identifiers or extract digits from arbitrary strings.
    """
    text = (raw or "").strip()

    if text.startswith(("'", "\u2019")):
        text = text[1:].strip()

    if re.fullmatch(r"\d{3}-\d{3}(?:-\d{3})?", text):
        text = text.replace("-", "")

    return text if text.isascii() and text.isdigit() else ""


def identifier(
    raw: str,
    width: int,
    *,
    allow_short: bool = False,
) -> str:
    d = digits(raw)

    if len(d) == width:
        return d

    # Some numeric exports omit a single leading zero.
    if allow_short and len(d) == width - 1:
        return d.zfill(width)

    return ""


def campus_id(raw_district: str, raw_school: str) -> str:
    district = identifier(
        raw_district,
        6,
        allow_short=True,
    )

    school = digits(raw_school)

    if not district or not school:
        return ""

    if len(school) == 9:
        return school if school.startswith(district) else ""

    if len(school) == 8:
        nine = school.zfill(9)
        return nine if nine.startswith(district) else ""

    if 1 <= len(school) <= 3:
        return district + school.zfill(3)

    return ""


def screening(name: str) -> tuple[str, str, str]:
    text = re.sub(
        r"\s+",
        " ",
        name.lower().replace("-", " "),
    )

    for regex, reason in [
        (r"\bdual language\b", "dual language in campus name"),
        (r"\bdual immersion\b", "dual immersion in campus name"),
        (r"\btwo way immersion\b", "two-way immersion in campus name"),
        (r"\bbilingual\b", "bilingual in campus name"),
        (r"\bimmersion\b", "immersion in campus name"),
    ]:
        if re.search(regex, text):
            return "strong_name_signal", reason, "high"

    for regex, reason in [
        (
            r"\blanguage (academy|school|magnet)\b",
            "language academy/school name",
        ),
        (r"\bmultilingual\b", "multilingual in campus name"),
    ]:
        if re.search(regex, text):
            return "broad_name_signal", reason, "medium"

    return "", "", ""


def write_csv(
    path: Path,
    rows: list[dict],
    fields: list[str],
) -> None:
    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=fields,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def collect(out: Path) -> dict:
    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    metadata = get_metadata()

    id_payload = query({
        "where": "1=1",
        "returnIdsOnly": "true",
        "f": "json",
    })

    object_ids = id_payload.get("objectIds")

    if not isinstance(object_ids, list):
        raise RuntimeError(
            "ArcGIS did not supply an objectIds array"
        )

    object_ids = sorted(
        int(obj)
        for obj in object_ids
    )

    if (
        len(object_ids) < 6000
        or len(set(object_ids)) != len(object_ids)
    ):
        raise ValueError(
            f"Unexpected or duplicate ArcGIS object IDs: "
            f"{len(object_ids)}"
        )

    raw = []

    for start in range(0, len(object_ids), 150):
        batch = object_ids[start:start + 150]

        response = query({
            "objectIds": ",".join(map(str, batch)),
            "outFields": ",".join(FIELDS),
            "returnGeometry": "false",
            "f": "json",
        })

        features = response.get("features")

        if (
            not isinstance(features, list)
            or len(features) != len(batch)
        ):
            raise ValueError(
                "ArcGIS returned an unexpected number of features "
                f"at offset {start}"
            )

        raw.extend(
            f.get("attributes", {})
            for f in features
        )

    received_ids = sorted(
        int(x["ObjectID"])
        for x in raw
    )

    if received_ids != object_ids:
        raise ValueError(
            "Fetched ArcGIS object IDs do not match requested IDs"
        )

    schools = []
    candidates = []
    identity_review = []
    identity_examples = []
    nces_statuses = Counter()

    for source in raw:
        district_raw = value(
            source,
            "USER_District_Number",
        )

        school_raw = value(
            source,
            "USER_School_Number",
        )

        district = identifier(
            district_raw,
            6,
            allow_short=True,
        )

        campus = campus_id(
            district_raw,
            school_raw,
        )

        name = value(
            source,
            "USER_School_Name",
        )

        raw_nces = value(
            source,
            "USER_NCES_School_ID",
        )

        nces = identifier(
            raw_nces,
            12,
        )

        nces_lea = identifier(
            value(source, "USER_NCES_District_ID"),
            7,
        )

        nces_status = (
            "reported_id_unverified_against_nces"
            if nces
            else "source_id_invalid"
            if raw_nces
            else "source_id_missing"
        )

        nces_statuses[nces_status] += 1

        row = {
            "state": "TX",
            "school_year": YEAR,
            "texas_campus_id": campus,
            "texas_district_id": district,
            "texas_school_number": school_raw,
            "school_name": name,
            "district_name": value(
                source, "USER_District_Name"
            ),
            "nces_school_id_reported": nces,
            "nces_district_id_reported": nces_lea,
            "nces_id_status": nces_status,
            "grade_range": value(
                source, "USER_Grade_Range"
            ),
            "school_enrollment_oct_2024": value(
                source, "USER_School_Enrollment_as_of_Oc"
            ),
            "instruction_type_source": value(
                source, "USER_Instruction_Type"
            ),
            "city": value(
                source, "USER_School_City"
            ),
            "school_state": value(
                source, "USER_School_State"
            ),
            "street_address": value(
                source, "USER_School_Street_Address"
            ),
            "postal_code": value(
                source, "USER_School_Zip"
            ),
            "school_webpage": value(
                source, "USER_School_Web_Page_Address"
            ),
            "source_object_id": value(
                source, "ObjectID"
            ),
            "source_url": LAYER,
            "program_verification_status": "not_checked",
            "dual_language_reported": "",
            "instructional_language": "",
            "one_way_two_way": "",
            "allocation_model": "",
            "whole_school_or_strand": "",
            "first_program_year": "",
            "program_source_url": "",
        }

        schools.append(row)

        if not campus or not district or not name:
            identity_review.append(row)

            if len(identity_examples) < 8:
                identity_examples.append({
                    "object_id": value(
                        source, "ObjectID"
                    ),
                    "raw_district": district_raw,
                    "raw_school": school_raw,
                    "name": name,
                })

        signal, reason, priority = screening(name)

        if signal:
            candidates.append({
                **row,
                "name_signal": signal,
                "screening_reason": reason,
                "review_priority": priority,
            })

    campus_ids = [
        r["texas_campus_id"]
        for r in schools
        if r["texas_campus_id"]
    ]

    duplicates = [
        key
        for key, count in Counter(campus_ids).items()
        if count > 1
    ]

    schools.sort(
        key=lambda r: (
            r["texas_campus_id"],
            r["school_name"],
        )
    )

    candidates.sort(
        key=lambda r: (
            r["review_priority"] != "high",
            r["district_name"],
            r["school_name"],
        )
    )

    # Save all results before validation fails, if a source
    # formatting problem remains. GitHub can upload the
    # diagnostic files even on a failed run.

    write_csv(
        out / "tx_2024_25_all_campuses.csv",
        schools,
        CAMPUS_FIELDS,
    )

    write_csv(
        out / "tx_2024_25_dl_name_candidates.csv",
        candidates,
        CANDIDATE_FIELDS,
    )

    write_csv(
        out / "tx_2024_25_identity_review.csv",
        identity_review,
        CAMPUS_FIELDS,
    )

    write_csv(
        out / "tx_2024_25_source_attributes.csv",
        raw,
        FIELDS,
    )

    report = {
        "source": LAYER,
        "source_description": (
            "TEA AskTED 2024-25 campus directory"
        ),
        "source_snapshot_year": YEAR,
        "collected_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "arcgis_object_ids": len(object_ids),
        "school_census_rows": len(schools),
        "unique_nonempty_texas_campus_ids": len(
            set(campus_ids)
        ),
        "duplicate_texas_campus_ids": duplicates[:25],
        "rows_missing_identity_fields": len(
            identity_review
        ),
        "missing_identity_examples": identity_examples,
        "nces_id_status_counts": dict(nces_statuses),
        "nces_ids_reported_12_digit": sum(
            bool(r["nces_school_id_reported"])
            for r in schools
        ),
        "dl_name_candidates": len(candidates),
        "candidate_signal_counts": dict(
            Counter(
                r["name_signal"]
                for r in candidates
            )
        ),
        "programs_verified": 0,
        "programs_unverified_not_assumed_absent": len(
            schools
        ),
        "source_is_a_school_directory_not_a_dli_roster": True,
        "warnings": [
            (
                "Leading apostrophes in AskTED identifiers "
                "removed as Excel formatting."
            ),
            (
                "Name signals have false positives "
                "and false negatives."
            ),
            (
                "No DLI program presence, language, "
                "instructional ratio, or strand status inferred."
            ),
            (
                "NCES IDs are source-reported and still "
                "require independent verification."
            ),
            (
                "All campuses retained for subsequent "
                "comparison groups."
            ),
        ],
        "upstream_fields": FIELDS,
    }

    report_path = (
        out / "tx_2024_25_collection_report.json"
    )

    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    schema_path = (
        out / "tx_2024_25_source_schema.json"
    )

    schema_path.write_text(
        json.dumps({
            "source": LAYER,
            "fields": metadata.get("fields", []),
        }, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))

    if duplicates:
        raise ValueError(
            f"Duplicate Texas campus IDs: {duplicates[:12]}"
        )

    if len(identity_review) > max(
        100,
        len(schools) // 20,
    ):
        raise ValueError(
            f"Too many incomplete identities: "
            f"{len(identity_review)} / {len(schools)}. "
            "See tx_2024_25_identity_review.csv "
            "and tx_2024_25_source_attributes.csv"
        )

    return report


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--out",
        type=Path,
        default=Path("output/texas"),
    )

    args = parser.parse_args()
    collect(args.out)


if __name__ == "__main__":
    main()
