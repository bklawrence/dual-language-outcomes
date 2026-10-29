
#!/usr/bin/env python3
"""Reconcile Oregon 2026-27 schools to 2024-25 NCES IDs.

Run after match_oregon_nces.py.
Preserves original extraction and matching outputs.
"""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

# Reviewed Oregon school aliases and NCES identifiers.
# These decisions apply specifically to the 2024-25 reference.

APPROVED = {
    "Arco Iris Spanish Immersion Charter": "410192001791",
    "Bear Creek Elementary": "410198000258",
    "Caldera High School": "410198001902",
    "High Desert Middle": "410198000263",
    "R.E. Jewell Elementary": "410198000266",
    "Trost Elementary K-6": "410264000165",
    "Buena Vista Spanish Immersion Elementary School": "410474001345",
    "Charlemagne Elementary": "410474001344",
    "Hé Lin Chinese Immersion Elementary": "410474001858",
    "Yujin Gakuen Japanese Immersion Elementary School": "410474001348",
    "Evergreen Middle School": "410002301322",
    "Poynter Middle School": "410002301251",
    "Wy'east Middle School": "410651000388",
    "Lot Whitcomb Elementary": "410883000080",
    "Rex Putnam High School": "410883000095",
    "Wilbur Rowe Middle School": "410883000092",
    "Oregon City High School": "410933000126",
    "Four Rivers Community Charter School- Community School": "410000901592",
    "Four Rivers Community Charter School - Junior Prep": "410000901592",
    "Four Rivers Community Charter School - Senior Prep": "410000901592",
    "Pilor Rock Jr/Sr High School": "410966001086",
    "César Chávez School": "411004000884",
    "Dr. Martin Luther King Jr. Elementary School": "411004000911",
    "Harrison Park Middle School": "411004000885",
    "Lent K-5 School": "411004000915",
    "Rigler School": "411004000931",
    "Rose City Park Elementary School": "411004001868",
    "Roseway Heights Middle School": "411004000932",
    "Chavez Elementary School": "411082001826",
    "Fowler Middle School": "411224001196",
}

# Correct IDs absent from the top three fuzzy suggestions.
EXTERNAL = {
    "Hé Lin Chinese Immersion Elementary": (
        "Eugene SD 4J",
        "4104740",
        "https://www.4j.lane.edu/24697_2?articleID=27392 ; "
        "https://plainschools.com/schools/chinese-language-immersion-school-or",
    ),
    "Rose City Park Elementary School": (
        "Portland SD 1J",
        "4110040",
        "https://plainschools.com/schools/rose-city-park-or",
    ),
}

NEW_SCHOOL = (
    "Umatilla SD 6R",
    "Columbia Vista Intermediate",
)

NEW_SCHOOL_EVIDENCE = (
    "https://www.umatilla.k12.or.us/article/2361487"
)

FOUR_RIVERS = {
    name for name, ident in APPROVED.items()
    if ident == "410000901592"
}


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)

        if (
            not rd.fieldnames
            or len(rd.fieldnames) != len(set(rd.fieldnames))
        ):
            raise ValueError(
                f"Duplicate or missing headers in {path}"
            )

        return list(rd), list(rd.fieldnames)


def write(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore",
        )
        w.writeheader()
        w.writerows(rows)


def require(test, reason):
    if not test:
        raise RuntimeError(reason)


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--crosswalk",
        default=(
            "data/registry/oregon_nces/"
            "oregon_nces_school_crosswalk.csv"
        ),
    )

    ap.add_argument(
        "--candidates",
        default=(
            "data/registry/oregon_nces/"
            "oregon_nces_match_candidates.csv"
        ),
    )

    ap.add_argument(
        "--programs",
        default="data/registry/state_dl_programs_oregon.csv",
    )

    ap.add_argument(
        "--out",
        default="data/registry/oregon_nces/reconciled",
    )

    args = ap.parse_args()

    crosswalk, cw_columns = read(args.crosswalk)
    candidates, _ = read(args.candidates)
    programs, program_columns = read(args.programs)

    require(
        len(crosswalk) == 196 and len(programs) == 223,
        "Oregon snapshot has changed; review aliases "
        "before applying fixes.",
    )

    require(
        all(
            r["nces_reference_year"] == "2024-25"
            for r in crosswalk
        ),
        "Reconciliation is only for the 2024-25 NCES reference.",
    )

    remaining = [
        r for r in crosswalk
        if r["match_status"] == "review_suggested_candidate"
    ]

    require(
        len(remaining) == 31,
        "Expected exactly 31 first-pass review cases.",
    )

    require(
        {
            r["canonical_school_name"]
            for r in remaining
        } == set(APPROVED) | {NEW_SCHOOL[1]},
        "Review names changed; do not silently reuse approvals.",
    )

    by_candidate = defaultdict(list)

    for c in candidates:
        by_candidate[c["oregon_school_key"]].append(c)

    reconciled = []
    audit = []

    for original in crosswalk:
        r = dict(original)
        name = r["canonical_school_name"]

        r["original_match_status"] = r["match_status"]
        r["original_nces_school_id"] = r["nces_school_id"]
        r["reconciliation_evidence"] = (
            "2024-25 NCES directory: exact school and district"
        )

        if r["match_status"] == "review_suggested_candidate":

            if (r["district_name"], name) == NEW_SCHOOL:
                r["nces_school_id"] = ""
                r["match_status"] = (
                    "unmatched_new_school_after_reference_year"
                )
                r["reconciliation_evidence"] = (
                    NEW_SCHOOL_EVIDENCE
                )
                rank = ""

            else:
                ident = APPROVED[name]

                require(
                    bool(re.fullmatch(r"\d{12}", ident)),
                    f"Invalid ID for {name}",
                )

                hits = [
                    c for c in by_candidate[r["oregon_school_key"]]
                    if c["nces_school_id"] == ident
                ]

                if name in EXTERNAL:
                    district, lea, evidence = EXTERNAL[name]

                    require(
                        r["district_name"] == district
                        and ident.startswith(lea),
                        f"External identity guard failed: {name}",
                    )

                    require(
                        not hits,
                        f"External correction now appears "
                        f"among candidates: {name}",
                    )

                    rank = "outside_top_three"

                else:
                    require(
                        len(hits) == 1,
                        f"Approved NCES ID absent/ambiguous: {name}",
                    )

                    hit = hits[0]
                    district = hit["nces_district_name"]

                    expected = (
                        r["district_name"] == district
                        or (
                            r["district_name"] == "Bend-LaPine SD 1"
                            and district
                            == "Bend-LaPine Administrative SD 1"
                        )
                    )

                    require(
                        expected
                        and hit["nces_lea_id"] == ident[:7],
                        f"Candidate district/LEA mismatch: {name}",
                    )

                    evidence = (
                        "2024-25 NCES candidate record; "
                        "reviewed school/district alias"
                    )

                    rank = hit["rank"]

                r["nces_school_id"] = ident

                r["match_status"] = (
                    "reconciled_shared_grade_band"
                    if name in FOUR_RIVERS
                    else "reconciled_school_alias"
                )

                r["reconciliation_evidence"] = evidence

            audit.append({
                "oregon_school_key": r["oregon_school_key"],
                "district_name": r["district_name"],
                "school_name": name,
                "previous_suggested_nces_id":
                    r["suggested_nces_school_id"],
                "approved_nces_id": r["nces_school_id"],
                "candidate_rank": rank,
                "decision": r["match_status"],
                "evidence": r["reconciliation_evidence"],
            })

        else:
            require(
                r["match_status"] == "matched_exact_name_and_district"
                and bool(
                    re.fullmatch(r"\d{12}", r["nces_school_id"])
                ),
                f"Unexpected original match status: {name}",
            )

        reconciled.append(r)

    # Detect NCES identity collisions.
    # Only the documented Four Rivers grouping is allowed.

    owners = defaultdict(list)

    for r in reconciled:
        if r["nces_school_id"]:
            owners[r["nces_school_id"]].append(
                r["canonical_school_name"]
            )

    conflicts = {
        ident: set(names)
        for ident, names in owners.items()
        if len(names) > 1
    }

    require(
        conflicts == {"410000901592": FOUR_RIVERS},
        f"Unexpected reuse of NCES school ID: {conflicts}",
    )

    # Rebuild the enhanced observations using the ORIGINAL
    # program CSV, avoiding duplicate nces_match_status headers.

    names = defaultdict(set)

    for r in reconciled:
        aliases = {
            r["canonical_school_name"],
            *r["source_school_names"].split("; "),
        }

        for alias in aliases:
            names[
                (r["district_name"], alias)
            ].add(r["oregon_school_key"])

    by_key = {
        r["oregon_school_key"]: r
        for r in reconciled
    }

    out_rows = []
    grouped = defaultdict(list)

    output_columns = [
        c for c in program_columns
        if c not in {"nces_school_id", "nces_match_status"}
    ] + [
        "source_nces_school_id",
        "source_nces_match_status",
        "oregon_school_key",
        "canonical_school_name",
        "nces_school_id",
        "nces_match_status",
        "nces_reference_year",
        "program_identity_key",
        "source_observations_for_program",
        "multiple_source_observations",
    ]

    for p in programs:
        row = {
            k: v for k, v in p.items()
            if k not in {"nces_school_id", "nces_match_status"}
        }

        row["source_nces_school_id"] = p.get(
            "nces_school_id", ""
        )
        row["source_nces_match_status"] = p.get(
            "nces_match_status", ""
        )

        if p["verification_status"].startswith("excluded_"):
            row.update(
                oregon_school_key="",
                canonical_school_name="",
                nces_school_id="",
                nces_match_status="excluded_not_dli",
                nces_reference_year="2024-25",
                program_identity_key="",
                source_observations_for_program="",
                multiple_source_observations="",
            )

        else:
            matches = names[
                (p["district_name"], p["school_name"])
            ]

            require(
                len(matches) == 1,
                "School alias ambiguous or missing: "
                + p["school_name"],
            )

            school_key = next(iter(matches))
            record = by_key[school_key]

            program_key = (
                "OR-P-"
                + hashlib.sha1(
                    (
                        school_key
                        + "|"
                        + p["partner_language"].casefold()
                    ).encode()
                ).hexdigest()[:12]
            )

            row.update(
                oregon_school_key=school_key,
                canonical_school_name=record[
                    "canonical_school_name"
                ],
                nces_school_id=record["nces_school_id"],
                nces_match_status=record["match_status"],
                nces_reference_year="2024-25",
                program_identity_key=program_key,
            )

            grouped[program_key].append(row)

        out_rows.append(row)

    # Keep McDaniel's separate source observations,
    # but identify repeated school-language combinations.

    for items in grouped.values():
        for row in items:
            row["source_observations_for_program"] = str(
                len(items)
            )
            row["multiple_source_observations"] = str(
                len(items) > 1
            ).lower()

    matched = sum(
        bool(r["nces_school_id"])
        for r in reconciled
    )

    require(
        (
            matched,
            len(owners),
            len(grouped),
            len(audit),
        ) == (195, 193, 209, 31),
        "Final count check failed; do not publish silently.",
    )

    require(
        sum(
            r.get("multiple_source_observations") == "true"
            for r in out_rows
        ) == 4,
        "McDaniel duplicate-source audit changed unexpectedly.",
    )

    require(
        len(output_columns) == len(set(output_columns)),
        "Duplicate output headers.",
    )

    target = Path(args.out)
    target.mkdir(parents=True, exist_ok=True)

    write(
        target / "oregon_nces_school_crosswalk_reconciled.csv",
        cw_columns + [
            "original_match_status",
            "original_nces_school_id",
            "reconciliation_evidence",
        ],
        reconciled,
    )

    write(
        target / "oregon_program_observations_with_nces_reconciled.csv",
        output_columns,
        out_rows,
    )

    write(
        target / "oregon_nces_reconciliation_audit.csv",
        list(audit[0]),
        audit,
    )

    summary = {
        "nces_reference_year": "2024-25",
        "source_observations_retained": len(programs),
        "dli_source_observations": len([
            p for p in programs
            if not p["verification_status"].startswith("excluded_")
        ]),
        "directory_school_identities": len(reconciled),
        "matched_directory_identities": matched,
        "distinct_nces_school_ids": len(owners),
        "unmatched_new_school_identities": 1,
        "school_language_keys": len(grouped),
        "reconciliation_decisions": len(audit),
        "match_status_counts": dict(
            Counter(r["match_status"] for r in reconciled)
        ),
        "caution": (
            "Identity match does not verify historical DLI "
            "cohorts or schoolwide outcome comparability."
        ),
    }

    (
        target / "oregon_nces_reconciliation_summary.json"
    ).write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
