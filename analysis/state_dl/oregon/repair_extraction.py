
#!/usr/bin/env python3
"""Conservative repair of Oregon 2026-27 DLI extraction.

Inputs:
  oregon_2026_27_extraction_audit.csv
  state_dl_programs_oregon.csv

Outputs:
  source_rows_with_status.csv
  rows_requiring_geometry.csv
  provisional_noncomposite_observations.csv
  repair_report.json

Composite PDF rows are quarantined, not automatically split.
"""

import argparse
import json
import pathlib
import re

import pandas as pd


def normalized(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def line_count(value):
    return len([
        line for line in str(value).splitlines()
        if line.strip()
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True)
    parser.add_argument("--programs", required=True)
    parser.add_argument(
        "--out",
        default="data/state_dl/oregon_repaired"
    )
    args = parser.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    audit = pd.read_csv(
        args.audit, dtype=str
    ).fillna("")

    programs = pd.read_csv(
        args.programs, dtype=str
    ).fillna("")

    # A PDF-extracted row is potentially composite if
    # it contains multiple districts or language entries.
    # Do not split school names on newline boundaries:
    # legitimate school names can occupy several lines.

    composite = audit.apply(
        lambda row: (
            line_count(row["district_raw"]) > 1
            or line_count(row["language_raw"]) > 1
        ),
        axis=1
    )

    audit["audit_id"] = range(1, len(audit) + 1)

    audit["repair_status"] = composite.map({
        True: "requires_pdf_geometry",
        False: "candidate_single_record"
    })

    audit.to_csv(
        out / "source_rows_with_status.csv",
        index=False
    )

    audit[composite].to_csv(
        out / "rows_requiring_geometry.csv",
        index=False
    )

    # Retain existing non-review observations.
    # These remain provisional, not source-verified.

    candidates = programs[
        ~programs["verification_status"].str.contains(
            "needs_review",
            case=False,
            na=False
        )
    ].copy()

    candidates["repair_status"] = (
        "provisional_single_record_unverified"
    )

    candidates["school_name"] = (
        candidates["school_name"].map(normalized)
    )

    # Detect suspicious fragments caused by
    # extraction across column or row boundaries.

    bad_school = candidates["school_name"].str.match(
        r"^(School\b|Charter\b|\(EIHS\))",
        case=False
    )

    bad_language = candidates["partner_language"].str.contains(
        r"^(o |S )|Spanish Russian",
        case=False,
        regex=True
    )

    suspect = bad_school | bad_language

    candidates.loc[
        suspect, "repair_status"
    ] = "requires_manual_school_or_language_check"

    candidates.to_csv(
        out / "provisional_noncomposite_observations.csv",
        index=False
    )

    report = {
        "original_directory_rows": len(audit),
        "original_observations": len(programs),
        "audit_composite_rows": int(composite.sum()),
        "audit_candidate_single_rows": int((~composite).sum()),
        "provisional_observations": len(candidates),
        "provisional_flagged_for_check": int(suspect.sum()),
        "verified_school_records": 0,
        "note": (
            "Composite rows require PDF-coordinate "
            "reconstruction before NCES matching."
        )
    }

    (out / "repair_report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8"
    )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
