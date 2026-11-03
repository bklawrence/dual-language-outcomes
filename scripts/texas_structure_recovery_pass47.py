
#!/usr/bin/env python3
"""Pass 47: dated Texas whole-school/strand evidence audit.

Does not infer student-level or cohort-level exposure.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

URL = {
    "SA": "https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/5576/Saisd/8dcc7b27-f611-4f66-b639-df28ed4f2368/SAISD-Dual-Language-Handbook-.docx.pdf?disposition=inline",
    "FW": "https://resources.finalsite.net/images/v1717011774/fwisdorg/c4m04t2a5sxkxb8kdx2k/Two-Way_Informational_Flyer_2-20-18.pdf",
    "DAL": "https://thehub.dallasisd.org/dallas-isd-news-archives/dallas-isd-news-archives-post-page/~board/dallas-isd-news-archives/post/seven-additional-schools-to-offer-two-way-dual-language-program-this-school-year",
    "AUSTIN": "https://go.boarddocs.com/tx/austinisd/Board.nsf/files/BXV8M91EEF9E/%24file/Attachment%202%20-%20Dual%20Language%20Programs%20by%20Elementary%20Campus%202020-21.pdf",
    "RR": "https://www.boarddocs.com/tx/rrisd/Board.nsf/files/AQBK2U4FCE00/%24file/H2.DL%20Board%20Presentation%208-17-17%20%281%29.pdf",
    "WHARTON": "https://wharton.houstonisd.org/academics-programs/academic-offerings",
    "HELMS": "https://helms.houstonisd.org/about-us/school-history",
    "LOVE": "https://love.houstonisd.org/academics-programs",
    "BROWNING": "https://browning.houstonisd.org/about-us",
    "MARK_WHITE": "https://mwhite.houstonisd.org/academics-programs/dual-language-immersion-programs",
    "SPRING": "https://news.springisd.org/2020/04/pre-k-and-kindergarten-online-registration-for-2020-21-school-year-opens-april-27/",
    "BAMMEL": "https://news.springisd.org/2021/05/dual-language-program-to-anchor-new-school-for-international-studies-at-bammel/",
    "SOUTH_SAN": "https://sanantonioreport.org/south-san-isd-to-add-dual-language-programs-at-5-elementary-schools/",
}

# Documented 2023-24 San Antonio DL grade offerings.
# Grade availability does NOT imply universal participation.

SA_GRADES = dict(item.split(":") for item in """
015907101:PK-5 015907103:PK-5 015907106:PK-5
015907107:K-8 015907110:K-5 015907112:PK-5
015907116:PK-5 015907117:PK-8 015907118:PK-7
015907121:K-5 015907123:PK-3 015907126:PK-5
015907133:PK-4 015907134:PK-5 015907135:PK-5
015907136:PK-5 015907138:PK-8 015907144:K-5
015907146:PK-4 015907147:PK-5 015907148:PK-5
015907149:K-5 015907150:K-5 015907153:PK-5
015907155:K-5 015907158:PK-5 015907160:PK-5
015907161:PK-8 015907163:PK-8 015907164:PK-5
015907165:PK-5 015907168:PK-5 015907172:PK-6
015907174:PK-5 015907175:K-8 015907176:PK-5
015907241:PK-5
""".split())

SA_WALL = {"015907138", "015907163"}

FW_FOUNDING = """
220905149 220905116 220905127
""".split()

FW_ADDED = """
220905117 220905160 220905121 220905107
220905153 220905148 220905166
""".split()

DALLAS_2019 = """
057905385 057905121 057905186 057905220
057905266 057905160 057905274
""".split()

DALLAS_PLANNED = ["057905307"]

AUSTIN_ALL = """
227901104 227901132 227901133 227901158
""".split()

RR_2017 = """
246909122 246909136 246909109 246909115
246909121 246909137 246909118 246909106
246909111 246909127 246909101 246909113
""".split()


def load(path):
    with path.open(
        encoding="utf-8-sig",
        newline=""
    ) as f:
        return list(csv.DictReader(f))


def write(path, rows, columns):
    with path.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=columns,
            extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--master",
        type=Path,
        default=ROOT / "data/registry/texas/texas_master_pass44.csv"
    )

    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT / "results/texas/structure_pass47"
    )

    args = parser.parse_args()

    master = load(args.master)
    byid = defaultdict(list)

    for row in master:
        byid[row["campus_id"]].append(row)

    if len(master) != 1856 or len(byid) != 1610:
        raise SystemExit(
            "Pass 44 count mismatch: expected "
            "1856 records and 1610 campuses"
        )

    events = []

    def add(cid, period, kind, scope, grade, url_key, notes):
        if cid not in byid:
            return

        base = byid[cid][0]

        events.append({
            "campus_id": cid,
            "district": base["district"],
            "campus": base["campus"],
            "evidence_period": period,
            "evidence_kind": kind,
            "scope_at_evidence_date": scope,
            "documented_grade_band": grade,
            "source_url": URL[url_key],
            "interpretation": notes,
            "confirms_2023_24_whole_school": (
                "YES" if kind == "2023_wall_to_wall"
                else "NO"
            ),
            "confirms_2023_24_strand": "NOT_VERIFIED",
        })

    # San Antonio: 2023-24 district handbook.

    for cid, grades in SA_GRADES.items():
        add(
            cid, "2023-24", "2023_grade_roster",
            "DL offered; coverage unknown", grades, "SA",
            "Grade offering does not establish "
            "whole-school or whole-grade enrollment"
        )

    for cid in SA_WALL:
        add(
            cid, "2023-24", "2023_wall_to_wall",
            "100% of classrooms dual language",
            "PK-8", "SA",
            "Handbook identifies Irving and Twain "
            "as wall-to-wall DL"
        )

    # Fort Worth: historical rollout.

    for cid in FW_FOUNDING:
        add(
            cid, "2013-14 to 2018-19",
            "historic_rollout",
            "DL began in PK/K; expanded by grade",
            "PK-5 by 2018-19", "FW",
            "Opt-in English speakers; this does not "
            "prove same-grade non-DL sections"
        )

    for cid in FW_ADDED:
        add(
            cid, "by 2018-19",
            "historic_program_site",
            "Two-way DL program offered",
            "unverified", "FW",
            "Launch year and 2023-24 structure unknown"
        )

    # Dallas: announced program expansions.

    for cid in DALLAS_2019:
        add(
            cid, "2019-20",
            "historic_program_launch",
            "New two-way DL program announced",
            "unverified", "DAL",
            "Program launch does not establish "
            "same-grade strand structure"
        )

    for cid in DALLAS_PLANNED:
        add(
            cid, "planned 2020",
            "future_program_launch",
            "Two-way DL announced for reopening",
            "unverified", "DAL",
            "Do not treat planned opening "
            "as confirmed enrollment"
        )

    # Austin: documented 2020-21 all-DL campuses.
    # Reilly includes more than one partner language.

    for cid in AUSTIN_ALL:
        add(
            cid, "2020-21",
            "historic_whole_school",
            "All students enrolled in some DL program",
            "PK-5", "AUSTIN",
            "Reilly also offered Mandarin-English DL; "
            "2023-24 continuation unverified"
        )

    # Spring ISD: historical kindergarten choice.

    for cid in ["101919108", "101919122"]:
        add(
            cid, "2020-21",
            "historic_opt_in_K",
            "Kindergarten DL offered as a family choice",
            "K", "SPRING",
            "Not confirmation of 2023-24 "
            "same-grade strands"
        )

    add(
        "101919130", "2021-22",
        "historic_grade_limited_start",
        "DL PK-2 alongside other campus grades",
        "PK-2", "BAMMEL",
        "No complete 2023-24 grade-level verification"
    )

    # South San Antonio: initial rollout.

    for cid in [
        "015908109", "015908104",
        "015908107", "015908113"
    ]:
        add(
            cid, "2020-21",
            "historic_program_launch",
            "K/PK dual-language rollout",
            "K", "SOUTH_SAN",
            "Universal coverage not established"
        )

    # Round Rock: 2017 fifth-grade comparison.

    for cid in RR_2017:
        add(
            cid, "2017 grade 5",
            "historic_DL_subset",
            "DL participants distinguished "
            "from all campus students",
            "grade 5", "RR",
            "Does not establish 2023-24 structure"
        )

    # Houston: school-specific program descriptions.

    houston = [
        (
            "101912256", "WHARTON",
            "historically_currently_whole",
            "All students in Spanish-English DL",
            "2000 launch; current"
        ),
        (
            "101912170", "HELMS",
            "historically_currently_whole",
            "Full Spanish immersion",
            "2023 transition; current"
        ),
        (
            "101912198", "LOVE",
            "later_multiple_programs",
            "DL and English-only",
            "current undated"
        ),
        (
            "101912120", "BROWNING",
            "later_multiple_programs",
            "DL and English-only",
            "current undated"
        ),
        (
            "101912483", "MARK_WHITE",
            "later_multiple_programs",
            "Spanish and French DL plus traditional",
            "current undated"
        ),
    ]

    for cid, key, kind, scope, year in houston:
        add(
            cid, year, kind, scope,
            "unverified", key,
            "Source does not establish a complete "
            "2023-24 grade-level enrollment roster"
        )

    # Assemble evidence by campus.

    evidence_by_campus = defaultdict(list)

    for event in events:
        evidence_by_campus[event["campus_id"]].append(event)

    campuses = []

    for cid, rows in sorted(byid.items()):
        base = rows[0]
        evidence = evidence_by_campus.get(cid, [])

        whole = any(
            e["confirms_2023_24_whole_school"] == "YES"
            for e in evidence
        )

        models = sorted({
            r["analysis_K_ratio"]
            for r in rows
            if r["analysis_K_ratio"]
        })

        campuses.append({
            "campus_id": cid,
            "district": base["district"],
            "campus": base["campus"],
            "historical_K_models": (
                ";".join(models) if models else "unresolved"
            ),
            "registry_rows": len(rows),
            "whole_school_DL_2023_24": (
                "YES" if whole else "UNKNOWN"
            ),
            "strand_in_same_grade_2023_24": "UNKNOWN",
            "DL_grade_band_roster_2023_24": (
                "YES" if any(
                    e["evidence_kind"] == "2023_grade_roster"
                    for e in evidence
                ) else "NO"
            ),
            "evidence_count": len(evidence),
            "documented_scopes": "; ".join(sorted({
                e["scope_at_evidence_date"]
                for e in evidence
            })),
            "periods": "; ".join(sorted({
                e["evidence_period"]
                for e in evidence
            })),
            "evidence_urls": "; ".join(dict.fromkeys(
                e["source_url"] for e in evidence
            )),
            "cohort_exposure_confirmed": "NO",
        })

    # Save four research outputs.

    args.outdir.mkdir(
        parents=True,
        exist_ok=True
    )

    write(
        args.outdir / "structure_campus_pass47.csv",
        campuses,
        list(campuses[0])
    )

    write(
        args.outdir / "structure_evidence_pass47.csv",
        events,
        list(events[0])
    )

    districts = []

    for district in [
        "DALLAS ISD",
        "FORT WORTH ISD",
        "SAN ANTONIO ISD",
        "HOUSTON ISD"
    ]:
        matches = [
            row for row in campuses
            if row["district"] == district
        ]

        districts.append({
            "district": district,
            "research_campuses": len(matches),
            "campuses_with_source_specific_evidence": sum(
                r["evidence_count"] > 0
                for r in matches
            ),
            "confirmed_whole_school_2023_24": sum(
                r["whole_school_DL_2023_24"] == "YES"
                for r in matches
            ),
            "with_2023_24_grade_band_roster": sum(
                r["DL_grade_band_roster_2023_24"] == "YES"
                for r in matches
            ),
        })

    write(
        args.outdir / "structure_priority_districts_pass47.csv",
        districts,
        list(districts[0])
    )

    summary = {
        "registry_records": len(master),
        "distinct_campuses": len(byid),
        "campuses_with_any_campus_specific_evidence":
            len(evidence_by_campus),
        "evidence_records": len(events),
        "kinds": dict(Counter(
            e["evidence_kind"] for e in events
        )),
        "confirmed_whole_school_2023_24": sum(
            r["whole_school_DL_2023_24"] == "YES"
            for r in campuses
        ),
        "confirmed_same_grade_strand_2023_24": 0,
        "priority_districts": districts,
        "caution": (
            "Program availability is not whole-school or "
            "strand status. Historical evidence is not "
            "automatically applied to 2023-24 or K-entry."
        ),
    }

    (
        args.outdir / "structure_summary_pass47.json"
    ).write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8"
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
