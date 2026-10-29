
#!/usr/bin/env python3
"""Audit Oregon's coordinate-based extraction.

Multiline cells are not automatically composite rows.
Non-DLI programs remain documented but are excluded
from provisional dual-language candidate observations.
"""

import argparse
import json
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True)
    parser.add_argument("--programs", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    audit = pd.read_csv(
        args.audit, dtype=str
    ).fillna("")

    programs = pd.read_csv(
        args.programs, dtype=str
    ).fillna("")

    required = {
        "extraction_issue",
        "school_raw",
        "district_raw",
    }

    if not required.issubset(audit.columns):
        raise ValueError(
            f"Missing audit columns: {required - set(audit.columns)}"
        )

    audit["audit_id"] = range(1, len(audit) + 1)

    unresolved = (
        audit["extraction_issue"].str.strip().ne("")
    )

    non_dli = audit["model_raw"].str.contains(
        r"Heritage Language Program|Native Language\s+Revitalization",
        regex=True,
        case=False,
        na=False,
    )

    audit["repair_status"] = "parsed_directory_row"

    audit.loc[
        non_dli, "repair_status"
    ] = "source_non_dli_program"

    audit.loc[
        unresolved, "repair_status"
    ] = "requires_source_review"

    audit.to_csv(
        out / "source_rows_with_status.csv",
        index=False,
    )

    audit.loc[unresolved].to_csv(
        out / "rows_requiring_geometry.csv",
        index=False,
    )

    # Exclude explicitly non-DLI programs.
    # Retain other candidates as provisional,
    # not verified NCES school records.

    excluded = (
        programs["verification_status"]
        .str.startswith("excluded_")
    )

    candidates = programs.loc[~excluded].copy()

    candidates["repair_status"] = (
        "provisional_not_nces_matched"
    )

    needs_review = (
        candidates["verification_status"]
        .str.contains(
            "needs_review",
            case=False,
            regex=False,
            na=False,
        )
    )

    candidates.loc[
        needs_review, "repair_status"
    ] = "program_review_needed"

    candidates.to_csv(
        out / "provisional_noncomposite_observations.csv",
        index=False,
    )

    report = {
        "original_directory_rows": int(len(audit)),
        "original_observations": int(len(programs)),
        "unresolved_source_rows": int(
            unresolved.sum()
        ),
        "non_dli_source_rows": int(
            non_dli.sum()
        ),
        "non_dli_observations_excluded_from_candidates":
            int(excluded.sum()),
        "provisional_dli_candidate_observations":
            int(len(candidates)),
        "candidate_observations_requiring_review":
            int(needs_review.sum()),
        "verified_nces_matches": 0,
        "note": (
            "Multiline cells are allowed. "
            "Source listing is not outcome "
            "eligibility or NCES verification."
        ),
    }

    (out / "repair_report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
