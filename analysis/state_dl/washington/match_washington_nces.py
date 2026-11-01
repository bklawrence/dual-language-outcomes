
#!/usr/bin/env python3
"""Conservative 2024-25 NCES match for Washington dual-language schools.

All languages are included. Only unique exact school+district matches are
accepted automatically; plausible aliases go to review, never silent approval.
NCES reference CSV is downloaded on GitHub Actions if not already cached.
"""
import argparse
import csv
import difflib
import hashlib
import json
import re
import time
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

SCHOOLS_URL = (
    "https://data-nces.opendata.arcgis.com/api/download/v1/items/"
    "10e02c7ba56b4ef4a6a050f212f75134/csv?layers=0"
)
DISTRICTS_URL = (
    "https://data-nces.opendata.arcgis.com/api/download/v1/items/"
    "c19e2bf4a9104f7d82633e59f47618ec/csv?layers=0"
)


def download(url, path):
    if path.exists() and path.stat().st_size > 1000:
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "dual-language-research/1.0"},
            )

            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()

            if len(data) < 1000 or b"," not in data[:2500]:
                raise ValueError(
                    "Downloaded file does not appear to be an NCES CSV"
                )

            path.write_bytes(data)
            return

        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 2)


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)

        if not reader.fieldnames:
            raise ValueError(f"No CSV columns: {path}")

        return list(reader), reader.fieldnames


def write(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fields,
            extrasaction="ignore",
        )
        w.writeheader()
        w.writerows(rows)


def col(row, names):
    lowered = {k.lower(): k for k in row}

    for n in names:
        if n.lower() in lowered:
            return (row[lowered[n.lower()]] or "").strip()

    return ""


def norm(value, district=False):
    value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode()
    )

    value = value.lower().replace("&", " and ")
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)

    fixes = {
        "sch": "school",
        "elem": "elementary",
        "el": "elementary",
        "ms": "middle",
        "hs": "high",
    }

    words = [fixes.get(w, w) for w in value.split()]

    if district:
        while words and words[-1] in {
            "district",
            "schools",
            "school",
            "public",
            "sd",
        }:
            words.pop()

        words = [
            w for w in words
            if w not in {"no", "number"}
        ]

        # Strip bare district numbers only at the end.
        while words and words[-1].isdigit():
            words.pop()

    else:
        while words and words[-1] == "school":
            words.pop()

    return " ".join(words)


def similarity(a, b):
    if not a or not b:
        return 0.0

    return difflib.SequenceMatcher(None, a, b).ratio()


def sha256(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for data in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(data)

    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()

    p.add_argument(
        "--base",
        type=Path,
        default=Path("output/washington"),
    )

    p.add_argument(
        "--nces-schools",
        type=Path,
    )

    p.add_argument(
        "--nces-districts",
        type=Path,
    )

    args = p.parse_args()
    base = args.base

    refs = base / "nces_reference"

    school_path = args.nces_schools or (
        refs / "nces_schools_2024_25.csv"
    )

    district_path = args.nces_districts or (
        refs / "nces_districts_2024_25.csv"
    )

    if not args.nces_schools:
        download(SCHOOLS_URL, school_path)

    if not args.nces_districts:
        download(DISTRICTS_URL, district_path)

    roster, _ = read(
        base / "wa_all_dl_schools.csv"
    )

    observations, obs_header = read(
        base / "wa_all_dl_school_years.csv"
    )

    schools, _ = read(school_path)
    districts, _ = read(district_path)

    if len(roster) < 100 or len(observations) < 300:
        raise ValueError(
            "Unexpectedly small Washington DL registry; refusing to match"
        )

    lea_names = {}

    for r in districts:
        state = col(
            r,
            ["STATE", "ST", "LSTATE"],
        )

        if state and state.upper() != "WA":
            continue

        id_ = col(
            r,
            [
                "LEAID",
                "NCES_LEA_ID",
                "NCESDIST",
                "LEA_ID",
            ],
        )

        name = col(
            r,
            ["NAME", "LEA_NAME", "district_name"],
        )

        if id_ and name:
            lea_names[id_] = name

    ref = []

    for r in schools:
        state = col(
            r,
            ["STATE", "ST", "LSTATE"],
        )

        id_ = col(
            r,
            [
                "NCESSCH",
                "NCES_SCHOOL_ID",
                "NCESID",
                "NCES_ID",
            ],
        )

        lea = col(
            r,
            [
                "LEAID",
                "NCES_LEA_ID",
                "NCESDIST",
                "LEA_ID",
            ],
        ) or id_[:7]

        if (
            state.upper() != "WA"
            or not re.fullmatch(r"\d{12}", id_)
        ):
            continue

        name = col(
            r,
            ["NAME", "SCH_NAME", "school_name"],
        )

        dname = lea_names.get(lea, "")

        if not name:
            continue

        ref.append({
            "nces_school_id": id_,
            "nces_lea_id": lea,
            "nces_school_name": name,
            "nces_district_name": dname,
            "nm": norm(name),
            "dm": norm(dname, district=True),
        })

    if len(ref) < 1000 or len(lea_names) < 100:
        raise ValueError(
            f"NCES reference looks incomplete: "
            f"WA schools={len(ref)}, LEAs={len(lea_names)}"
        )

    by_name_dist = defaultdict(list)

    for x in ref:
        by_name_dist[
            (x["nm"], x["dm"])
        ].append(x)

    roster_ids = [
        r["state_school_id"]
        for r in roster
    ]

    if len(set(roster_ids)) != len(roster_ids):
        raise ValueError(
            "Washington school identities are not unique"
        )

    crosswalk = []
    candidates = []
    review = []

    for r in sorted(
        roster,
        key=lambda x: (
            x["district_latest"],
            x["school_name_latest"],
        ),
    ):
        name = r["school_name_latest"]
        district = r["district_latest"]

        nm = norm(name)
        dm = norm(district, district=True)

        exact = by_name_dist.get(
            (nm, dm),
            [],
        )

        # Candidate ranking prioritizes school name,
        # then district similarity.
        scored = []

        for x in ref:
            ns = similarity(nm, x["nm"])
            ds = similarity(dm, x["dm"])

            if ns < 0.57 and ds < 0.80:
                continue

            score = round(
                0.72 * ns + 0.28 * ds,
                5,
            )

            scored.append((score, ns, ds, x))

        scored.sort(
            key=lambda z: (
                -z[0],
                -z[1],
                z[3]["nces_school_id"],
            )
        )

        unique = []
        seen_ids = set()

        for tup in scored:
            candidate_id = tup[3]["nces_school_id"]

            if candidate_id not in seen_ids:
                unique.append(tup)
                seen_ids.add(candidate_id)

            if len(unique) >= 5:
                break

        for rank, (score, ns, ds, x) in enumerate(
            unique,
            1,
        ):
            candidates.append({
                "state_school_id": r["state_school_id"],
                "school_name": name,
                "district_name": district,
                "rank": rank,
                "candidate_nces_school_id":
                    x["nces_school_id"],
                "candidate_nces_name":
                    x["nces_school_name"],
                "candidate_nces_district":
                    x["nces_district_name"],
                "name_similarity": f"{ns:.4f}",
                "district_similarity": f"{ds:.4f}",
                "combined_score": f"{score:.4f}",
            })

        match = exact[0] if len(exact) == 1 else None

        if match:
            status = "matched_exact_name_and_district"
        elif len(exact) > 1:
            status = "review_multiple_exact_candidates"
        elif unique:
            status = "review_candidate_only"
        else:
            status = "unmatched_no_candidate"

        first = unique[0][3] if unique else {}

        row = {
            "state": "WA",
            "school_id": r["school_id"],
            "state_school_id": r["state_school_id"],
            "school_name": name,
            "district_name": district,
            "languages_reported": r["languages_reported"],
            "nces_reference_year": "2024-25",
            "match_status": status,
            "nces_school_id":
                match["nces_school_id"] if match else "",
            "nces_lea_id":
                match["nces_lea_id"] if match else "",
            "suggested_nces_school_id":
                first.get("nces_school_id", ""),
            "suggested_nces_school_name":
                first.get("nces_school_name", ""),
            "suggested_nces_district":
                first.get("nces_district_name", ""),
            "verification_method": (
                "exact_normalized_school_and_district"
                if match
                else "requires_manual_review"
            ),
        }

        crosswalk.append(row)

        if not match:
            review.append(row)

    # Detect multiple WA state IDs assigned
    # to the same NCES campus.
    assigned = defaultdict(list)

    for r in crosswalk:
        if r["nces_school_id"]:
            assigned[
                r["nces_school_id"]
            ].append(r)

    for rows in assigned.values():
        if len(rows) > 1:
            for r in rows:
                r["match_status"] = "review_nces_id_collision"
                r["nces_school_id"] = ""
                r["nces_lea_id"] = ""
                r["verification_method"] = (
                    "requires_manual_review"
                )
                review.append(r)

    xref = {
        r["state_school_id"]: r
        for r in crosswalk
    }

    joined = []
    seen = set()

    for obs in observations:
        key = (
            obs["state_school_id"],
            obs["school_year"],
            obs["instructional_language"],
        )

        if key in seen:
            raise ValueError(
                f"Duplicate WA school-language-year key {key}"
            )

        seen.add(key)

        if obs["state_school_id"] not in xref:
            raise ValueError(
                "Unmatched WA registry identity "
                f"{obs['state_school_id']}"
            )

        match = xref[obs["state_school_id"]]

        joined.append({
            **obs,
            "nces_school_id": match["nces_school_id"],
            "nces_match_status": match["match_status"],
            "nces_reference_year": "2024-25",
        })

    if len(joined) != len(observations):
        raise AssertionError(
            "Lost Washington program observations"
        )

    out = base / "nces"
    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    write(
        out / "wa_nces_school_crosswalk.csv",
        crosswalk,
        list(crosswalk[0]),
    )

    write(
        out / "wa_nces_match_candidates.csv",
        candidates,
        (
            list(candidates[0])
            if candidates
            else ["state_school_id"]
        ),
    )

    write(
        out / "wa_nces_review_queue.csv",
        review,
        list(crosswalk[0]),
    )

    write(
        out / "wa_all_program_observations_with_nces.csv",
        joined,
        list(joined[0]),
    )

    summary = {
        "nces_reference_year": "2024-25",
        "washington_all_language_schools":
            len(roster),
        "washington_program_language_years":
            len(observations),
        "nces_wa_schools_in_reference":
            len(ref),
        "nces_wa_districts_in_reference":
            len(lea_names),
        "school_match_status_counts": dict(
            Counter(
                r["match_status"]
                for r in crosswalk
            )
        ),
        "automatic_matches": sum(
            bool(r["nces_school_id"])
            for r in crosswalk
        ),
        "review_required": len(review),
        "nces_school_source_sha256":
            sha256(school_path),
        "nces_district_source_sha256":
            sha256(district_path),
        "rules": (
            "Only unique exact normalized school + "
            "district matches accepted; "
            "no fuzzy auto-matches."
        ),
        "caution": (
            "No 2025-26 NCES identity inferred from "
            "a later school name; "
            "review new schools and aliases."
        ),
    }

    (
        out / "wa_nces_match_summary.json"
    ).write_text(
        json.dumps(summary, indent=2) + "\n"
    )

    print(
        json.dumps(summary, indent=2)
    )


if __name__ == "__main__":
    main()
