
#!/usr/bin/env python3
"""Collect the complete Texas 2024-25 campus identity roster from TEA AskTED.

This is a school-census / DLI-candidate screening stage, NOT a verified DLI
program inventory. Campus names alone cannot establish DLI program presence,
one-way/two-way model, instructional allocation, or strand/whole-school design.

Source: TEA AskTED 2024-25 campus export hosted on the TEA open-data ArcGIS
FeatureServer. Uses object-ID pagination to avoid ArcGIS 2,000-row limits.

Usage: python3 collectors/texas.py
       python3 collectors/texas.py --out output/texas
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


def query(params: dict) -> dict:
    url = LAYER + "/query?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "dual-language-outcomes-research/1.0"}
            )
            with urllib.request.urlopen(req, timeout=75) as response:
                payload = json.load(response)
            if not isinstance(payload, dict) or "error" in payload:
                raise RuntimeError(f"ArcGIS query error: {str(payload)[:700]}")
            return payload
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == 3:
                raise RuntimeError("ArcGIS request failed after retries") from exc
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


def get_metadata() -> dict:
    url = LAYER + "?f=pjson"
    req = urllib.request.Request(
        url, headers={"User-Agent": "dual-language-outcomes-research/1.0"}
    )
    with urllib.request.urlopen(req, timeout=75) as response:
        obj = json.load(response)
    if "error" in obj:
        raise RuntimeError(f"Cannot fetch layer metadata: {obj['error']}")
    available = {f["name"] for f in obj.get("fields", [])}
    missing = set(FIELDS) - available
    if missing:
        raise ValueError(f"ArcGIS fields changed; missing: {sorted(missing)}")
    return obj


def val(record: dict, name: str) -> str:
    value = record.get(name)
    return "" if value is None else str(value).strip()


def identifier(raw: str, width: int) -> str:
    raw = raw.strip()
    if not raw or raw.lower() in {"nan", "null", "none"}:
        return ""
    # Never coerce arbitrary data into an identifier.
    if re.fullmatch(rf"\d{{{width}}}", raw):
        return raw
    if re.fullmatch(rf"\d{{{width-1}}}", raw):
        # Some GIS exports drop a single leading zero on numeric IDs.
        return raw.zfill(width)
    return ""


def campus_id(district: str, school: str) -> str:
    district_digits = identifier(district, 6)
    if re.fullmatch(r"\d{9}", school):
        return school
    if re.fullmatch(r"\d{1,3}", school) and district_digits:
        return district_digits + school.zfill(3)
    if re.fullmatch(r"\d{8}", school):
        return school.zfill(9)
    return ""


def screening(name: str) -> tuple[str, str, str]:
    n = re.sub(r"\s+", " ", name.lower().replace("-", " "))
    strong = [
        (r"\bdual language\b", "dual language in school name"),
        (r"\bdual immersion\b", "dual immersion in school name"),
        (r"\btwo way immersion\b", "two-way immersion in school name"),
        (r"\bbilingual\b", "bilingual in school name"),
        (r"\bimmersion\b", "immersion in school name"),
    ]
    for pattern, label in strong:
        if re.search(pattern, n):
            return ("strong_name_signal", label, "high")
    broad = [
        (r"\blanguage (academy|school|magnet)\b", "language school/academy name"),
        (r"\bmultilingual\b", "multilingual in school name"),
    ]
    for pattern, label in broad:
        if re.search(pattern, n):
            return ("broad_name_signal", label, "medium")
    return ("", "", "")


def write_csv(path: Path, data: list[dict], headers: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="raise")
        writer.writeheader()
        writer.writerows(data)


def collect(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    meta = get_metadata()
    ids_result = query({"where": "1=1", "returnIdsOnly": "true", "f": "json"})
    ids = ids_result.get("objectIds")
    if not isinstance(ids, list):
        raise RuntimeError("ArcGIS did not return an objectIds array")
    ids = sorted(int(x) for x in ids)
    if len(ids) != len(set(ids)) or len(ids) < 6000:
        raise ValueError(f"Unexpected Texas ArcGIS object IDs: {len(ids)}")

    raw = []
    # Object IDs, rather than offset pages, avoid skipped rows with page limits.
    for start in range(0, len(ids), 150):
        batch = ids[start : start + 150]
        result = query({
            "objectIds": ",".join(map(str, batch)),
            "outFields": ",".join(FIELDS),
            "returnGeometry": "false",
            "f": "json",
        })
        features = result.get("features")
        if not isinstance(features, list) or len(features) != len(batch):
            raise ValueError(
                f"ArcGIS returned {len(features) if isinstance(features,list) else 'invalid'} "
                f"features for {len(batch)} IDs, batch {start}"
            )
        for feature in features:
            attrs = feature.get("attributes", {})
            if not isinstance(attrs, dict):
                raise ValueError("Missing attributes in ArcGIS feature")
            raw.append(attrs)

    fetched_ids = [int(r["ObjectID"]) for r in raw]
    if sorted(fetched_ids) != ids:
        raise ValueError("Missing, duplicate, or unexpected ArcGIS object IDs")

    schools, missing_identifiers, candidates = [], [], []
    for r in raw:
        raw_district = val(r, "USER_District_Number")
        raw_school = val(r, "USER_School_Number")
        district = identifier(raw_district, 6)
        campus = campus_id(raw_district, raw_school)
        name = val(r, "USER_School_Name")
        nces_raw = val(r, "USER_NCES_School_ID")
        nces = identifier(nces_raw, 12)
        nces_lea = identifier(val(r, "USER_NCES_District_ID"), 7)
        status = (
            "reported_id_unverified_against_nces" if nces
            else ("source_id_missing" if not nces_raw else "source_id_invalid")
        )
        row = {
            "state": "TX", "school_year": YEAR,
            "texas_campus_id": campus, "texas_district_id": district,
            "texas_school_number": raw_school,
            "school_name": name,
            "district_name": val(r, "USER_District_Name"),
            "nces_school_id_reported": nces,
            "nces_district_id_reported": nces_lea,
            "nces_id_status": status,
            "grade_range": val(r, "USER_Grade_Range"),
            "school_enrollment_oct_2024": val(r, "USER_School_Enrollment_as_of_Oc"),
            "instruction_type_source": val(r, "USER_Instruction_Type"),
            "city": val(r, "USER_School_City"),
            "school_state": val(r, "USER_School_State"),
            "street_address": val(r, "USER_School_Street_Address"),
            "postal_code": val(r, "USER_School_Zip"),
            "school_webpage": val(r, "USER_School_Web_Page_Address"),
            "source_object_id": val(r, "ObjectID"),
            "source_url": LAYER,
            "program_verification_status": "not_checked",
            # Intentionally blank: school name and directory are NOT program proof.
            "dual_language_reported": "",
            "instructional_language": "", "one_way_two_way": "",
            "allocation_model": "", "whole_school_or_strand": "",
            "first_program_year": "", "program_source_url": "",
        }
        schools.append(row)
        if not campus or not district or not name:
            missing_identifiers.append(row)
        signal, reason, priority = screening(name)
        if signal:
            candidates.append({
                **row, "name_signal": signal,
                "screening_reason": reason, "review_priority": priority,
            })

    campus_ids = [x["texas_campus_id"] for x in schools if x["texas_campus_id"]]
    duplicated = [v for v, n in Counter(campus_ids).items() if n > 1]
    if duplicated:
        raise ValueError(
            f"Duplicate Texas campus IDs; do not collapse source schools: {duplicated[:20]}"
        )
    if len(schools) < 6000:
        raise ValueError("Texas school census unexpectedly small")
    if len(missing_identifiers) > max(100, len(schools) // 20):
        raise ValueError("Too many missing Texas campus identifiers or school names")

    schools.sort(key=lambda r: (r["texas_campus_id"], r["school_name"]))
    candidates.sort(key=lambda r: (
        0 if r["review_priority"] == "high" else 1,
        r["district_name"], r["school_name"],
    ))
    write_csv(out / "tx_2024_25_all_campuses.csv", schools, CAMPUS_FIELDS)
    write_csv(out / "tx_2024_25_dl_name_candidates.csv", candidates, CANDIDATE_FIELDS)
    write_csv(out / "tx_2024_25_identity_review.csv", missing_identifiers, CAMPUS_FIELDS)
    write_csv(
        out / "tx_2024_25_source_attributes.csv", raw, FIELDS
    )

    report = {
        "source": LAYER,
        "source_description": "TEA AskTED 2024-25 school campus export",
        "source_snapshot_year": YEAR,
        "collected_utc": datetime.now(timezone.utc).isoformat(),
        "arcgis_metadata_last_edit_ms": (meta.get("editingInfo") or {}).get("lastEditDate"),
        "arcgis_object_ids": len(ids),
        "school_census_rows": len(schools),
        "unique_nonempty_texas_campus_ids": len(set(campus_ids)),
        "rows_missing_identity_fields": len(missing_identifiers),
        "nces_ids_reported_12_digit": sum(bool(r["nces_school_id_reported"]) for r in schools),
        "dl_name_candidates": len(candidates),
        "candidate_signal_counts": dict(Counter(r["name_signal"] for r in candidates)),
        "programs_verified": 0,
        "programs_unverified_not_assumed_absent": len(schools),
        "source_is_a_school_directory_not_a_dli_roster": True,
        "warnings": [
            "Name-based candidate signals have false positives and false negatives.",
            "No Texas DLI participation, language, ratio, one/two-way or strand status has been inferred.",
            "NCES identifiers are source-reported and need independent 2024-25 NCES cross-check.",
            "This is a 2024-25 snapshot, not evidence that a program operated in any other year.",
            "All campuses are retained to allow subsequent non-DLI / EL comparisons.",
        ],
        "upstream_fields": FIELDS,
    }
    (out / "tx_2024_25_collection_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (out / "tx_2024_25_source_schema.json").write_text(
        json.dumps({"fields": meta.get("fields", []), "source": LAYER}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("output/texas"))
    args = parser.parse_args()
    collect(args.out)


if __name__ == "__main__":
    main()
