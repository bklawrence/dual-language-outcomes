
#!/usr/bin/env python3
"""Repair WA grade-3--5 enrollment metrics using saved, original OSPI rows.

Run AFTER collectors/washington_enrollment.py; no re-download is necessary.
Updates the three existing derived enrollment/join CSVs and enrollment report,
backing up pre-repair originals in output/washington/pre_grade3_5_repair.
Source rows and original academic outcomes are never modified.
"""
import argparse
import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

GRADES = ("3rd Grade", "4th Grade", "5th Grade")
COUNTS = {
    "enrollment": "all_students",
    "low_income": "low_income",
    "english_language_learners": "english_language_learners",
    "hispanic_latino": "hispanic_latino_of_any_race",
}
DERIVED = (
    "wa_enrollment_school_years.csv",
    "wa_enrollment_dl_join.csv",
    "wa_academic_enrollment_coverage.csv",
)


def load(path):
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rd = csv.DictReader(fh)
        if not rd.fieldnames:
            raise ValueError(f"No headers: {path}")
        return list(rd), rd.fieldnames


def write(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def numeric(text):
    text = (text or "").strip().replace(",", "")
    return int(text) if re.fullmatch(r"\d+", text) else None


def repair_row(row, by_grade):
    # No partial denominators: all three grade cohorts must be available.
    missing = [g for g in GRADES if g not in by_grade]
    row["grade3_5_rows_present"] = str(3 - len(missing))
    counts = {k: [] for k in COUNTS}

    if not missing:
        for grade in GRADES:
            for kind, col in COUNTS.items():
                counts[kind].append(numeric(by_grade[grade][col]))

    complete = not missing and all(
        all(n is not None for n in vals) for vals in counts.values()
    )

    if complete:
        totals = {k: sum(vals) for k, vals in counts.items()}
        complete = totals["enrollment"] > 0 and all(
            totals[k] <= totals["enrollment"]
            for k in COUNTS
            if k != "enrollment"
        )

    row["grade3_5_complete"] = "yes" if complete else "no"
    row["grade3_5_enrollment_n"] = (
        str(totals["enrollment"]) if complete else ""
    )

    for kind in ("low_income", "english_language_learners", "hispanic_latino"):
        prefix = f"grade3_5_{kind}"
        row[prefix + "_n"] = str(totals[kind]) if complete else ""
        row[prefix + "_pct"] = (
            str(round(100 * totals[kind] / totals["enrollment"], 4))
            if complete
            else ""
        )
        row[prefix + "_status"] = (
            "usable" if complete else "missing_or_suppressed"
        )

    flags = [
        f.strip()
        for f in row.get("review_flags", "").split("|")
        if f.strip()
    ]
    flags = [
        f for f in flags
        if f != "grade3_5_incomplete_or_not_offered"
    ]

    if not complete:
        flags.append("grade3_5_incomplete_or_not_offered")

    row["review_flags"] = " | ".join(dict.fromkeys(flags))
    return complete


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--base",
        type=Path,
        default=Path("output/washington"),
    )
    args = p.parse_args()
    base = args.base

    raw, _ = load(base / "wa_enrollment_source_rows.csv")
    records, fields = load(base / "wa_enrollment_school_years.csv")

    expected = set(COUNTS.values()) | {
        "schoolorganizationid",
        "schoolyear",
        "organizationlevel",
        "gradelevel",
    }

    if raw and not expected.issubset(raw[0]):
        raise ValueError(
            "OSPI source columns changed; refuse to infer field names"
        )

    idx = defaultdict(dict)

    for r in raw:
        if r["organizationlevel"].strip().lower() != "school":
            continue

        key = (
            r["schoolorganizationid"].strip(),
            r["schoolyear"].strip(),
        )
        grade = r["gradelevel"].strip()

        if grade in idx[key]:
            raise ValueError(
                f"Duplicate OSPI grade row for {key} {grade}"
            )

        idx[key][grade] = r

    seen = set()
    changes = {}
    distribution = Counter()

    for r in records:
        key = (
            r["state_school_id"].strip(),
            r["school_year"].strip(),
        )

        if key in seen:
            raise ValueError(
                f"Duplicate aggregate enrollment key {key}"
            )

        seen.add(key)

        before_whole = {
            k: v
            for k, v in r.items()
            if k.startswith("whole_school_")
        }

        ok = repair_row(r, idx.get(key, {}))

        after_whole = {
            k: v
            for k, v in r.items()
            if k.startswith("whole_school_")
        }

        if before_whole != after_whole:
            raise AssertionError(
                "Whole-school values unexpectedly changed"
            )

        distribution[
            (
                r["grade3_5_rows_present"],
                "complete" if ok else "incomplete",
            )
        ] += 1

        changes[key] = {
            k: v
            for k, v in r.items()
            if k.startswith("grade3_5_") or k == "review_flags"
        }

    backups = base / "pre_grade3_5_repair"
    backups.mkdir(parents=True, exist_ok=True)

    for filename in DERIVED:
        path = base / filename

        if path.exists() and not (backups / filename).exists():
            shutil.copy2(path, backups / filename)

        if filename == DERIVED[0]:
            rows, header = records, fields
        else:
            if not path.exists():
                continue

            rows, header = load(path)

            for row in rows:
                key = (
                    row["state_school_id"].strip(),
                    row["school_year"].strip(),
                )

                if key not in changes:
                    raise ValueError(
                        f"Join contains nonexistent enrollment key {key}"
                    )

                row.update(changes[key])

        write(path, rows, header)

    report_path = base / "wa_enrollment_report.json"

    if report_path.exists():
        if not (backups / report_path.name).exists():
            shutil.copy2(report_path, backups / report_path.name)

        report = json.loads(
            report_path.read_text(encoding="utf-8")
        )
    else:
        report = {}

    successful = sum(
        r["grade3_5_complete"] == "yes"
        for r in records
    )

    report["school_years_with_complete_grade3_5_counts"] = successful
    report["grade3_5_repair"] = {
        "source_grade_labels": list(GRADES),
        "complete_school_years": successful,
        "school_years_total": len(records),
        "rows_present_and_completion": [
            {
                "grades_present": int(n),
                "status": status,
                "school_years": count,
            }
            for (n, status), count in sorted(distribution.items())
        ],
        "source_rows_unchanged": True,
        "note": (
            "These are schoolwide grade-group counts, "
            "not DL-participant enrollment."
        ),
    }

    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            report["grade3_5_repair"],
            indent=2,
        )
    )

    if not successful:
        raise RuntimeError(
            "Repair found zero complete grade-3--5 records"
        )


if __name__ == "__main__":
    main()
