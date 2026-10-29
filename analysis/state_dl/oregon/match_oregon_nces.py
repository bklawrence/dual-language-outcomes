
#!/usr/bin/env python3
"""Match Oregon 2026-27 DLI schools to 2024-25 NCES EDGE identifiers.

Run from repository root:
    python3 analysis/state_dl/oregon/match_oregon_nces.py

The Oregon source CSV is never modified.
School identities are reconciled separately from program observations.
"""

import argparse
import csv
import hashlib
import json
import re
import tempfile
import unicodedata

from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import requests


SCHOOL_URL = (
    "https://data-nces.opendata.arcgis.com/api/download/v1/items/"
    "10e02c7ba56b4ef4a6a050f212f75134/csv?layers=0"
)

DISTRICT_URL = (
    "https://data-nces.opendata.arcgis.com/api/download/v1/items/"
    "c19e2bf4a9104f7d82633e59f47618ec/csv?layers=0"
)

NCES_YEAR = "2024-25"

MCDANIEL_ALIASES = {
    "Leodis V. McDaniel High School",
    "McDaniel High School",
    "Madison High School",
}

CANONICAL_MCDANIEL = "Leodis V. McDaniel High School"


def tidy(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(
        c for c in s
        if not unicodedata.combining(c)
    )
    s = s.casefold().replace("&", " and ")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def school_key(s):
    s = tidy(s)
    s = re.sub(r"\b(school|sch)\b", "", s)
    return " ".join(s.split())


def district_key(s):
    s = tidy(s)
    s = re.sub(
        r"\b(sd|schools|school|district|public|dist)\b",
        "",
        s,
    )
    return " ".join(s.split())


def similarity(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def canonical_name(district, school):
    if (
        district_key(district)
        == district_key("Portland SD 1J")
        and school in MCDANIEL_ALIASES
    ):
        return CANONICAL_MCDANIEL
    return school


def read_csv(path):
    with open(
        path, newline="", encoding="utf-8-sig"
    ) as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError(f"Empty CSV: {path}")

        return [
            {
                k.strip().upper(): (v or "").strip()
                for k, v in row.items()
            }
            for row in reader
        ]


def download(url, dest):
    with requests.get(
        url,
        timeout=180,
        stream=True,
        headers={"User-Agent": "StateDLResearch/1.0"},
    ) as response:

        response.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):
                if chunk:
                    f.write(chunk)

    if dest.stat().st_size < 1000:
        raise RuntimeError(
            f"Downloaded file unexpectedly small: {url}"
        )

    with open(dest, "rb") as f:
        beginning = f.read(100).lstrip().lower()

        if beginning.startswith(
            (b"<!doctype html", b"<html")
        ):
            raise RuntimeError(
                f"Received HTML rather than CSV: {url}"
            )


def oregon(row):
    state = (
        row.get("STATE", "")
        or row.get("STABR", "")
    )

    if state:
        return state.upper() in ("OR", "OREGON")

    return row.get("OPSTFIPS", "") == "41"


def nces_schools(school_rows, district_rows):
    districts = {}

    for row in district_rows:
        if (
            oregon(row)
            and re.fullmatch(
                r"\d{7}",
                row.get("LEAID", ""),
            )
        ):
            districts[row["LEAID"]] = row.get(
                "NAME", ""
            )

    schools = []

    for row in school_rows:
        if not oregon(row):
            continue

        school_id = row.get("NCESSCH", "")

        if not re.fullmatch(
            r"\d{12}", school_id
        ):
            continue

        lea_id = (
            row.get("LEAID", "")
            or school_id[:7]
        )

        schools.append({
            "nces_school_id": school_id,
            "nces_lea_id": lea_id,
            "nces_school_name": row.get("NAME", ""),
            "nces_district_name":
                districts.get(lea_id, ""),
            "nces_city": row.get("CITY", ""),
            "nces_year": NCES_YEAR,
        })

    if len(schools) < 500:
        raise RuntimeError(
            f"Only {len(schools)} Oregon NCES schools. "
            "Check files and schema."
        )

    if not districts:
        raise RuntimeError(
            "No Oregon NCES district names; "
            "cannot safely match schools."
        )

    return list({
        r["nces_school_id"]: r
        for r in schools
    }.values())


def match_school(group, nces):
    aliases = (
        set(group["source_names"])
        | {group["school_name"]}
    )

    if group["school_name"] == CANONICAL_MCDANIEL:
        aliases |= MCDANIEL_ALIASES

    keys = {
        school_key(a)
        for a in aliases
    }

    district = district_key(
        group["district_name"]
    )

    ranked = []

    for n in nces:
        n_name = school_key(
            n["nces_school_name"]
        )

        name_score = max(
            similarity(k, n_name)
            for k in keys
        )

        d_score = similarity(
            district,
            district_key(
                n["nces_district_name"]
            ),
        )

        if (
            name_score < .57
            and not (
                d_score >= .90
                and name_score >= .42
            )
        ):
            continue

        score = (
            .78 * name_score
            + .22 * d_score
        )

        ranked.append((
            score, name_score, d_score, n
        ))

    ranked.sort(
        key=lambda x: (
            -x[0],
            -x[1],
            x[3]["nces_school_id"],
        )
    )

    top = ranked[:3]

    # Automatic assignment requires a unique
    # exact normalized school-name match and
    # an exact normalized district match.
    exact_same_district = [
        r for r in ranked
        if (
            r[1] == 1.0
            and r[2] >= .99
        )
    ]

    status = "review_no_candidate"
    assigned_id = ""

    if len(exact_same_district) == 1:
        status = "matched_exact_name_and_district"
        assigned_id = (
            exact_same_district[0][3]["nces_school_id"]
        )

    elif len(exact_same_district) > 1:
        status = "review_ambiguous_exact"

    elif top:
        status = "review_suggested_candidate"

    return status, assigned_id, top


def write_csv(path, fields, rows):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def build(program_rows, school_rows, district_rows, out):
    required = {
        "STATE",
        "SCHOOL_YEAR",
        "DISTRICT_NAME",
        "SCHOOL_NAME",
        "PARTNER_LANGUAGE",
        "VERIFICATION_STATUS",
    }

    if (
        not program_rows
        or not required.issubset(program_rows[0])
    ):
        missing = (
            required - set(program_rows[0])
            if program_rows
            else required
        )
        raise ValueError(
            f"Oregon input missing fields: {missing}"
        )

    nces = nces_schools(
        school_rows, district_rows
    )

    groups = {}

    for row in program_rows:
        if (
            row["STATE"] != "OR"
            or row["VERIFICATION_STATUS"].startswith(
                "excluded_"
            )
        ):
            continue

        district = row["DISTRICT_NAME"]
        name = canonical_name(
            district, row["SCHOOL_NAME"]
        )

        key = (
            district_key(district),
            school_key(name),
        )

        if key not in groups:
            groups[key] = {
                "district_name": district,
                "school_name": name,
                "source_names": set(),
                "languages": set(),
                "structures": set(),
                "source_observations": 0,
            }

        g = groups[key]

        g["source_names"].add(
            row["SCHOOL_NAME"]
        )
        g["languages"].add(
            row["PARTNER_LANGUAGE"]
        )
        g["structures"].add(
            row.get(
                "PROGRAM_STRUCTURE", "unknown"
            )
        )
        g["source_observations"] += 1

    crosswalk = []
    candidates = []
    group_ids = {}

    for key, g in sorted(groups.items()):
        gid = (
            "OR-"
            + hashlib.sha1(
                "|".join(key).encode()
            ).hexdigest()[:12]
        )

        group_ids[key] = gid

        status, assigned_id, top = match_school(
            g, nces
        )

        best = top[0][3] if top else {}

        crosswalk.append({
            "oregon_school_key": gid,
            "district_name":
                g["district_name"],
            "canonical_school_name":
                g["school_name"],
            "source_school_names":
                "; ".join(sorted(g["source_names"])),
            "partner_languages":
                "; ".join(sorted(g["languages"])),
            "program_structures":
                "; ".join(sorted(g["structures"])),
            "source_observations":
                g["source_observations"],
            "match_status": status,
            "nces_school_id": assigned_id,
            "suggested_nces_school_id":
                best.get("nces_school_id", ""),
            "suggested_nces_name":
                best.get("nces_school_name", ""),
            "suggested_nces_district":
                best.get("nces_district_name", ""),
            "nces_reference_year": NCES_YEAR,
        })

        for rank, (
            score, nscore, dscore, n
        ) in enumerate(top, 1):

            candidates.append({
                "oregon_school_key": gid,
                "district_name":
                    g["district_name"],
                "school_name": g["school_name"],
                "rank": rank,
                "combined_score": f"{score:.4f}",
                "name_score": f"{nscore:.4f}",
                "district_score": f"{dscore:.4f}",
                **n,
            })

    # Prevent the same NCES ID from being assigned
    # to two different Oregon school identities.
    claimed = defaultdict(list)

    for row in crosswalk:
        if row["nces_school_id"]:
            claimed[
                row["nces_school_id"]
            ].append(row)

    for entries in claimed.values():
        if len(entries) > 1:
            for row in entries:
                row["match_status"] = (
                    "review_nces_identity_collision"
                )
                row["nces_school_id"] = ""

    by_key = {
        r["oregon_school_key"]: r
        for r in crosswalk
    }

    enhanced = []
    program_groups = defaultdict(list)

    for row in program_rows:
        out_row = {
            k.lower(): v
            for k, v in row.items()
        }

        excluded = row[
            "VERIFICATION_STATUS"
        ].startswith("excluded_")

        if excluded:
            out_row.update({
                "oregon_school_key": "",
                "school_canonical_name": "",
                "nces_match_status":
                    "excluded_not_dli",
                "nces_candidate_school_id": "",
            })

        else:
            name = canonical_name(
                row["DISTRICT_NAME"],
                row["SCHOOL_NAME"],
            )

            gid = group_ids[(
                district_key(row["DISTRICT_NAME"]),
                school_key(name),
            )]

            match = by_key[gid]

            out_row.update({
                "oregon_school_key": gid,
                "school_canonical_name": name,
                "nces_match_status":
                    match["match_status"],
                "nces_candidate_school_id":
                    match["nces_school_id"],
            })

            program_groups[(
                gid,
                row["PARTNER_LANGUAGE"].casefold(),
            )].append(row)

        enhanced.append(out_row)

    crosswalk_fields = [
        "oregon_school_key",
        "district_name",
        "canonical_school_name",
        "source_school_names",
        "partner_languages",
        "program_structures",
        "source_observations",
        "match_status",
        "nces_school_id",
        "suggested_nces_school_id",
        "suggested_nces_name",
        "suggested_nces_district",
        "nces_reference_year",
    ]

    candidate_fields = [
        "oregon_school_key",
        "district_name",
        "school_name",
        "rank",
        "combined_score",
        "name_score",
        "district_score",
        "nces_school_id",
        "nces_lea_id",
        "nces_school_name",
        "nces_district_name",
        "nces_city",
        "nces_year",
    ]

    write_csv(
        out / "oregon_nces_school_crosswalk.csv",
        crosswalk_fields,
        crosswalk,
    )

    write_csv(
        out / "oregon_nces_match_candidates.csv",
        candidate_fields,
        candidates,
    )

    write_csv(
        out / "oregon_program_observations_with_nces.csv",
        [k.lower() for k in program_rows[0]]
        + [
            "oregon_school_key",
            "school_canonical_name",
            "nces_match_status",
            "nces_candidate_school_id",
        ],
        enhanced,
    )

    summary = {
        "oregon_program_source_observations":
            len(program_rows),
        "dli_candidate_source_observations":
            sum(
                not r["VERIFICATION_STATUS"].startswith(
                    "excluded_"
                )
                for r in program_rows
            ),
        "dli_unique_school_identities":
            len(groups),
        "dli_unique_school_language_keys":
            len(program_groups),
        "source_duplicate_observations_within_school_language":
            sum(
                len(v) - 1
                for v in program_groups.values()
            ),
        "nces_reference_year": NCES_YEAR,
        "nces_oregon_schools_in_reference":
            len(nces),
        "match_status_counts": dict(
            Counter(
                r["match_status"]
                for r in crosswalk
            )
        ),
        "caution": (
            "2024-25 school identity is not proof "
            "of 2023-24 or 2026-27 operation. "
            "DLI eligibility and strand enrollment "
            "require separate validation. "
            "Source observations were not deleted."
        ),
        "nces_sources": {
            "schools": SCHOOL_URL,
            "districts": DISTRICT_URL,
        },
    }

    (
        out / "oregon_nces_match_summary.json"
    ).write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--programs",
        default=(
            "data/registry/"
            "state_dl_programs_oregon.csv"
        ),
    )

    parser.add_argument(
        "--nces-schools",
        type=Path,
    )

    parser.add_argument(
        "--nces-districts",
        type=Path,
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=Path(
            "data/registry/oregon_nces"
        ),
    )

    args = parser.parse_args()

    if bool(args.nces_schools) != bool(
        args.nces_districts
    ):
        parser.error(
            "Specify both NCES files or neither"
        )

    with tempfile.TemporaryDirectory() as tmp:
        school_path = (
            args.nces_schools
            or Path(tmp) / "schools.csv"
        )

        district_path = (
            args.nces_districts
            or Path(tmp) / "districts.csv"
        )

        if not args.nces_schools:
            download(SCHOOL_URL, school_path)
            download(DISTRICT_URL, district_path)

        build(
            read_csv(args.programs),
            read_csv(school_path),
            read_csv(district_path),
            args.out,
        )


if __name__ == "__main__":
    main()
