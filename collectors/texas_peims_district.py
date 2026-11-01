
#!/usr/bin/env python3
"""Texas district-level dual-language PEIMS evidence register.

Creates a 2019-20 through 2025-26 district-year framework
from the 2024-25 campus directory.

Imports verified, normalized TEA program-count files when
present under input/texas/peims_eb_program_reports/.

Does not infer campus DLI participation, instructional ratios,
or missing enrollment counts.
"""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

YEARS = tuple(
    f"{y}-{str(y + 1)[-2:]}"
    for y in range(2019, 2026)
)

REPORT_URL = (
    "https://rptsvr1.tea.texas.gov/adhocrpt/adlepgm.html"
)

INPUT_HEADERS = [
    "texas_district_id",
    "school_year",
    "program_type",
    "student_group",
    "student_count",
    "source_url",
]

COUNT_HEADERS = INPUT_HEADERS + [
    "count_status",
    "source_file_sha256",
    "source_file_name",
]

FRAME_HEADERS = [
    "texas_district_id",
    "district_name_2024_25",
    "school_year",
    "campuses_in_2024_25_directory",
    "reported_campus_enrollment_2024_25_sum",
    "one_way_eb_n",
    "one_way_eb_status",
    "two_way_eb_n",
    "two_way_eb_status",
    "one_way_all_students_n",
    "one_way_all_students_status",
    "two_way_all_students_n",
    "two_way_all_students_status",
    "district_dli_evidence",
    "peims_records_read",
    "campus_dli_status",
    "allocation_model",
    "whole_school_or_strand",
    "peims_report_page",
]

PROGRAMS = {
    "dual_one_way": "dual_one_way",
    "one_way": "dual_one_way",
    "dual language immersion/one-way": "dual_one_way",
    "dual language one-way": "dual_one_way",
    "be-dual one-way": "dual_one_way",
    "dual_two_way": "dual_two_way",
    "two_way": "dual_two_way",
    "dual language immersion/two-way": "dual_two_way",
    "dual language two-way": "dual_two_way",
    "be-dual two-way": "dual_two_way",
    "transitional_early_exit": "transitional_early_exit",
    "transitional_late_exit": "transitional_late_exit",
    "esl": "esl",
    "total_bilingual": "total_bilingual",
}

GROUPS = {
    "emergent_bilingual": "emergent_bilingual",
    "eb": "emergent_bilingual",
    "english_learner": "emergent_bilingual",
    "english learner": "emergent_bilingual",
    "all_students": "all_students",
    "all": "all_students",
    "total": "all_students",
    "non_emergent_bilingual": "non_emergent_bilingual",
    "non_eb": "non_emergent_bilingual",
}

MASKED = {
    "n/a",
    "na",
    "*",
    "--",
    "-",
    "-999",
    "-9999999",
    "suppressed",
    "masked",
    "<5",
    "<10",
}


def load_csv(path):
    with path.open(
        newline="",
        encoding="utf-8-sig",
    ) as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError(f"No headers in {path}")

        return list(reader), list(reader.fieldnames)


def write_csv(path, rows, headers):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=headers,
            extrasaction="raise",
        )

        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def parse_count(value):
    value = str(
        value or ""
    ).strip().lower().replace(",", "")

    if value in MASKED:
        return "", "suppressed"

    if not value:
        return "", "not_reported"

    if not re.fullmatch(r"\d+", value):
        raise ValueError(
            f"Invalid student count: {value!r}"
        )

    return str(int(value)), "reported_numeric"


def load_districts(campus_path):
    rows, headers = load_csv(campus_path)

    required = {
        "texas_district_id",
        "district_name",
        "texas_campus_id",
        "school_enrollment_oct_2024",
    }

    if not required.issubset(headers):
        raise ValueError(
            f"Missing campus columns: "
            f"{sorted(required - set(headers))}"
        )

    districts = {}
    seen_campuses = set()

    for row in rows:
        did = row["texas_district_id"].strip()
        name = row["district_name"].strip()
        cid = row["texas_campus_id"].strip()

        if (
            not re.fullmatch(r"\d{6}", did)
            or not re.fullmatch(r"\d{9}", cid)
            or not name
        ):
            raise ValueError(
                f"Invalid district/campus: {did}/{cid}"
            )

        if cid in seen_campuses:
            raise ValueError(
                f"Duplicate campus: {cid}"
            )

        seen_campuses.add(cid)

        if did not in districts:
            districts[did] = {
                "name": name,
                "campuses": 0,
                "enrollment": 0,
            }

        if districts[did]["name"] != name:
            raise ValueError(
                f"Conflicting district name: {did}"
            )

        districts[did]["campuses"] += 1

        enrollment = row[
            "school_enrollment_oct_2024"
        ].strip().replace(",", "")

        if enrollment.isdigit():
            districts[did]["enrollment"] += int(
                enrollment
            )

    if len(rows) < 6000 or len(districts) < 900:
        raise ValueError(
            "Unexpectedly small Texas campus census"
        )

    return districts, len(rows)


def load_peims_sources(folder, districts):
    counts = []
    sources = []
    seen = set()

    if not folder.exists():
        return counts, sources

    for path in sorted(folder.glob("*.csv")):
        raw, headers = load_csv(path)

        if not set(INPUT_HEADERS).issubset(headers):
            raise ValueError(
                f"{path}: expected columns "
                f"{INPUT_HEADERS}"
            )

        digest = sha256(path)

        for line, row in enumerate(raw, start=2):
            did = row[
                "texas_district_id"
            ].strip().lstrip("'\u2019")

            year = row["school_year"].strip()

            program = PROGRAMS.get(
                row["program_type"].strip().lower()
            )

            group = GROUPS.get(
                row["student_group"].strip().lower()
            )

            url = row["source_url"].strip()

            if (
                did not in districts
                or year not in YEARS
                or not program
                or not group
                or not url.startswith("https://")
            ):
                raise ValueError(
                    f"Invalid PEIMS row {path}:{line}"
                )

            if (
                "example" in url
                or "actual-tea-export" in url
            ):
                raise ValueError(
                    "Placeholder evidence URL"
                )

            key = (
                did,
                year,
                program,
                group,
            )

            if key in seen:
                raise ValueError(
                    f"Duplicate PEIMS observation: {key}"
                )

            seen.add(key)

            number, status = parse_count(
                row["student_count"]
            )

            counts.append({
                "texas_district_id": did,
                "school_year": year,
                "program_type": program,
                "student_group": group,
                "student_count": number,
                "source_url": url,
                "count_status": status,
                "source_file_sha256": digest,
                "source_file_name": path.name,
            })

        sources.append({
            "file": path.name,
            "sha256": digest,
            "rows": len(raw),
        })

    return counts, sources


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--campuses",
        type=Path,
        default=Path(
            "output/texas/tx_2024_25_all_campuses.csv"
        ),
    )

    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path(
            "output/texas/tx_2024_25_dl_name_candidates.csv"
        ),
    )

    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(
            "input/texas/peims_eb_program_reports"
        ),
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=Path(
            "output/texas/peims_district"
        ),
    )

    args = parser.parse_args()

    args.out.mkdir(
        parents=True,
        exist_ok=True,
    )

    districts, campus_total = load_districts(
        args.campuses
    )

    observations, manifest = load_peims_sources(
        args.source_dir,
        districts,
    )

    index = {
        (
            r["texas_district_id"],
            r["school_year"],
            r["program_type"],
            r["student_group"],
        ): r
        for r in observations
    }

    grouped = defaultdict(list)

    for row in observations:
        grouped[
            (
                row["texas_district_id"],
                row["school_year"],
            )
        ].append(row)

    frame = []
    evidence_counts = Counter()

    for did, district in sorted(districts.items()):
        for year in YEARS:

            def cell(program, group):
                record = index.get(
                    (did, year, program, group)
                )

                if record:
                    return (
                        record["student_count"],
                        record["count_status"],
                    )

                return "", "not_collected"

            one_eb, one_eb_status = cell(
                "dual_one_way",
                "emergent_bilingual",
            )

            two_eb, two_eb_status = cell(
                "dual_two_way",
                "emergent_bilingual",
            )

            one_all, one_all_status = cell(
                "dual_one_way",
                "all_students",
            )

            two_all, two_all_status = cell(
                "dual_two_way",
                "all_students",
            )

            data = grouped.get(
                (did, year),
                [],
            )

            dual_rows = [
                r for r in data
                if r["program_type"] in (
                    "dual_one_way",
                    "dual_two_way",
                )
            ]

            positive = any(
                r["count_status"] == "reported_numeric"
                and int(r["student_count"]) > 0
                for r in dual_rows
            )

            if positive:
                evidence = (
                    "district_dli_participation_confirmed"
                )
            elif dual_rows:
                evidence = (
                    "district_dli_presence_not_established"
                )
            else:
                evidence = (
                    "no_dli_program_report_collected"
                )

            evidence_counts[evidence] += 1

            frame.append({
                "texas_district_id": did,
                "district_name_2024_25":
                    district["name"],
                "school_year": year,
                "campuses_in_2024_25_directory":
                    district["campuses"],
                "reported_campus_enrollment_2024_25_sum":
                    district["enrollment"],
                "one_way_eb_n": one_eb,
                "one_way_eb_status": one_eb_status,
                "two_way_eb_n": two_eb,
                "two_way_eb_status": two_eb_status,
                "one_way_all_students_n": one_all,
                "one_way_all_students_status":
                    one_all_status,
                "two_way_all_students_n": two_all,
                "two_way_all_students_status":
                    two_all_status,
                "district_dli_evidence": evidence,
                "peims_records_read": len(data),
                "campus_dli_status":
                    "unknown_do_not_infer_from_district",
                "allocation_model": "",
                "whole_school_or_strand": "",
                "peims_report_page": REPORT_URL,
            })

    write_csv(
        args.out / "tx_peims_district_years.csv",
        frame,
        FRAME_HEADERS,
    )

    write_csv(
        args.out / "tx_peims_program_counts_long.csv",
        observations,
        COUNT_HEADERS,
    )

    district_rows = [
        {
            "texas_district_id": did,
            "district_name": d["name"],
            "campus_count_2024_25": d["campuses"],
            "school_enrollment_sum_2024_25":
                d["enrollment"],
        }
        for did, d in sorted(districts.items())
    ]

    write_csv(
        args.out / "tx_peims_district_directory_2024_25.csv",
        district_rows,
        [
            "texas_district_id",
            "district_name",
            "campus_count_2024_25",
            "school_enrollment_sum_2024_25",
        ],
    )

    write_csv(
        args.out / "tx_peims_import_template.csv",
        [],
        INPUT_HEADERS,
    )

    priority = defaultdict(list)

    if args.candidates.exists():
        candidates, headers = load_csv(
            args.candidates
        )

        if not {
            "texas_district_id",
            "school_name",
        }.issubset(headers):
            raise ValueError(
                "Candidate file missing identity fields"
            )

        for row in candidates:
            did = row["texas_district_id"]

            if did not in districts:
                raise ValueError(
                    f"Unknown candidate district: {did}"
                )

            priority[did].append(
                row["school_name"]
            )

    priority_rows = [
        {
            "texas_district_id": did,
            "district_name": districts[did]["name"],
            "flagged_campus_names": " | ".join(names),
            "flagged_campus_count": len(names),
            "dli_program_verified":
                "no_name_signal_only",
        }
        for did, names in sorted(priority.items())
    ]

    write_csv(
        args.out / "tx_peims_name_signal_districts.csv",
        priority_rows,
        [
            "texas_district_id",
            "district_name",
            "flagged_campus_names",
            "flagged_campus_count",
            "dli_program_verified",
        ],
    )

    report = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "campus_roster_source": str(args.campuses),
        "campus_roster_sha256": sha256(args.campuses),
        "campuses_in_2024_25_roster": campus_total,
        "distinct_2024_25_districts": len(districts),
        "years": list(YEARS),
        "district_year_rows": len(frame),
        "districts_with_dli_name_signals":
            len(priority),
        "campuses_with_dli_name_signals":
            sum(map(len, priority.values())),
        "TEA_program_source_page": REPORT_URL,
        "peims_source_files": manifest,
        "program_count_observations":
            len(observations),
        "district_year_statuses":
            dict(evidence_counts),
        "requires_verified_TEA_program_exports":
            not bool(manifest),
        "cautions": [
            (
                "Historical district operation is not "
                "established by the 2024-25 directory."
            ),
            (
                "No PEIMS count is inferred from "
                "a campus name or directory listing."
            ),
            (
                "Missing, uncollected and suppressed "
                "values are never treated as zero."
            ),
            (
                "District participation does not verify "
                "which individual campuses offer DLI."
            ),
            (
                "Instructional language, ratios and "
                "whole-school versus strand remain unknown."
            ),
        ],
    }

    report_path = (
        args.out / "tx_peims_district_report.json"
    )

    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
