
#!/usr/bin/env python3
"""Reproduce Washington dual-language regressions.

Run from the repository root:

    python3 analysis/washington_regressions.py

Required inputs in output/washington/:
    wa_all_dl_school_years.csv
    wa_academic_outcomes.csv
    wa_enrollment_school_years.csv

Results are written to output/washington/analysis/.

Outcomes are schoolwide, not verified outcomes
for dual-language program participants.
"""

import argparse
import hashlib
import json
import os

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels
import statsmodels.formula.api as smf


SCRIPT_VERSION = "1.0.0"

YEARS = (
    "2023-24",
    "2024-25",
    "2025-26",
)

MODELS = (
    "50-50",
    "80-20",
    "90-10",
)

CONTROL_SETS = {
    "primary": ("low", "hisp"),
    "plus_current_ell": ("low", "hisp", "ell"),
}

INPUT_FILES = (
    "wa_all_dl_school_years.csv",
    "wa_academic_outcomes.csv",
    "wa_enrollment_school_years.csv",
)


def sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for part in iter(
            lambda: handle.read(1024 * 1024),
            b""
        ):
            digest.update(part)

    return digest.hexdigest()


def load_school_data(input_dir):
    for name in INPUT_FILES:
        path = input_dir / name

        if not path.is_file():
            raise FileNotFoundError(
                f"Required source missing: {path}"
            )

    school = pd.read_csv(
        input_dir / INPUT_FILES[0],
        dtype={"state_school_id": str},
    )

    academic = pd.read_csv(
        input_dir / INPUT_FILES[1],
        usecols=[
            "state_school_id",
            "school_year",
            "grade",
            "subject",
            "student_group",
            "testadministration",
            "pct_consistent_grade_or_above",
        ],
        dtype={"state_school_id": str},
        low_memory=False,
    )

    enrollment = pd.read_csv(
        input_dir / INPUT_FILES[2],
        dtype={"state_school_id": str},
    )

    # -----------------------------------
    # SELECT QUALIFYING PROGRAMS
    # -----------------------------------

    school = school.loc[
        school["school_year"].isin(YEARS)
        & school["instructional_language"].eq(
            "Spanish"
        )
        & school["program_designs"].eq(
            "Two-Way Dual Language Program"
        )
        & school["reported_models"].isin(MODELS),
        [
            "state_school_id",
            "school_year",
            "school_name",
            "district_name",
            "reported_models",
        ],
    ].rename(
        columns={
            "reported_models": "model",
            "district_name": "district",
        }
    )

    keys = [
        "state_school_id",
        "school_year",
    ]

    if school.duplicated(keys).any():
        raise ValueError(
            "Duplicate qualifying program school-years"
        )

    # -----------------------------------
    # CONSTRUCT ACADEMIC OUTCOMES
    # -----------------------------------

    academic["grade"] = pd.to_numeric(
        academic["grade"],
        errors="coerce",
    )

    measure = "pct_consistent_grade_or_above"

    academic[measure] = pd.to_numeric(
        academic[measure],
        errors="coerce",
    )

    academic = academic.loc[
        academic["testadministration"].eq("SBAC")
        & academic["student_group"].eq(
            "All Students"
        )
        & academic["subject"].isin(
            ("ELA", "Math")
        )
        & academic["grade"].isin((3, 4, 5)),
    ].copy()

    # The source stores proficiency as 0..1.
    # Missing and suppressed values stay missing.

    academic.loc[
        ~academic[measure].between(0, 1),
        measure,
    ] = np.nan

    academic = academic.dropna(
        subset=[measure]
    )

    grade_keys = keys + [
        "subject",
        "grade",
    ]

    if academic.duplicated(grade_keys).any():
        raise ValueError(
            "Duplicate academic school/year/"
            "subject/grade records"
        )

    academic["score"] = (
        academic[measure] * 100
    )

    means = (
        academic
        .groupby(keys + ["subject"])["score"]
        .agg(rate="mean", grades="size")
        .reset_index()
    )

    rates = means.pivot(
        index=keys,
        columns="subject",
        values="rate",
    ).rename(
        columns={
            "ELA": "ela",
            "Math": "math",
        }
    )

    grade_counts = means.pivot(
        index=keys,
        columns="subject",
        values="grades",
    ).rename(
        columns={
            "ELA": "n_ela_grades",
            "Math": "n_math_grades",
        }
    )

    outcomes = rates.join(
        grade_counts
    ).reset_index()

    outcomes.columns.name = None

    # -----------------------------------
    # CONSTRUCT SCHOOLWIDE DEMOGRAPHICS
    # -----------------------------------

    shares = {
        "whole_school_low_income_pct": "low",
        "whole_school_hispanic_latino_pct": "hisp",
        "whole_school_english_language_learners_pct":
            "ell",
    }

    keep = keys + [
        "all_grades_row_count",
        "whole_school_enrollment_n",
    ]

    for source in shares:
        keep.extend([
            source,
            source.removesuffix("_pct") + "_status",
        ])

    enrollment = enrollment[keep].copy()

    if enrollment.duplicated(keys).any():
        raise ValueError(
            "Duplicate enrollment school-years"
        )

    for source in shares:
        status = (
            source.removesuffix("_pct")
            + "_status"
        )

        enrollment.loc[
            enrollment[status] != "usable",
            source,
        ] = np.nan

        enrollment[source] = pd.to_numeric(
            enrollment[source],
            errors="coerce",
        )

        enrollment.loc[
            ~enrollment[source].between(0, 100),
            source,
        ] = np.nan

    # Require exactly one All Grades row.

    enrollment.loc[
        pd.to_numeric(
            enrollment["all_grades_row_count"],
            errors="coerce",
        ) != 1,
        list(shares),
    ] = np.nan

    enrollment = enrollment.rename(
        columns=shares
    ).rename(
        columns={
            "whole_school_enrollment_n":
                "enrollment"
        }
    )

    enrollment["enrollment"] = pd.to_numeric(
        enrollment["enrollment"],
        errors="coerce",
    )

    # -----------------------------------
    # MERGE ALL THREE DATASETS
    # -----------------------------------

    data = (
        school
        .merge(
            outcomes,
            on=keys,
            how="left",
            validate="one_to_one",
        )
        .merge(
            enrollment,
            on=keys,
            how="left",
            validate="one_to_one",
        )
    )

    for col in (
        "ela", "math",
        "low", "hisp", "ell"
    ):
        data[col] = pd.to_numeric(
            data[col],
            errors="coerce",
        )

    data["primary_eligible"] = (
        data[
            ["ela", "math", "low", "hisp"]
        ]
        .notna()
        .all(axis=1)
    )

    data["sensitivity_eligible"] = (
        data[
            ["ela", "math", "low", "hisp", "ell"]
        ]
        .notna()
        .all(axis=1)
    )

    def exclusion_reason(row):
        missing = []

        for col in (
            "ela", "math", "low", "hisp"
        ):
            if pd.isna(row[col]):
                missing.append(
                    f"missing_{col}"
                )

        return ";".join(missing)

    data["exclusion_reasons"] = data.apply(
        exclusion_reason,
        axis=1,
    )

    return data.sort_values([
        "school_year",
        "model",
        "state_school_id",
    ])


def run_analysis(data, output_dir):
    coefficients = []
    adjusted_means = []
    comparisons = []
    sample_counts = []
    text_summaries = []

    report = {}

    for year in YEARS:
        year_data = data.loc[
            data["school_year"] == year
        ]

        report[year] = {}

        for specification, controls in (
            CONTROL_SETS.items()
        ):

            sample = year_data.dropna(
                subset=[
                    "ela",
                    "math",
                    *controls,
                ]
            ).copy()

            model_counts = (
                sample["model"]
                .value_counts()
                .to_dict()
            )

            if any(
                model_counts.get(m, 0) < 3
                for m in MODELS
            ):
                raise ValueError(
                    f"Insufficient observations: "
                    f"{year}, {specification}: "
                    f"{model_counts}"
                )

            for model in MODELS:
                sample_counts.append({
                    "school_year": year,
                    "specification": specification,
                    "model": model,
                    "registry_schools": int(
                        (
                            year_data["model"] == model
                        ).sum()
                    ),
                    "analyzed_schools": int(
                        model_counts.get(model, 0)
                    ),
                })

            districts = (
                sample
                .groupby("district")["model"]
                .nunique()
            )

            report[year][specification] = {
                "schools": int(len(sample)),
                "districts": int(
                    sample["district"].nunique()
                ),
                "districts_with_multiple_models":
                    int((districts > 1).sum()),
                "by_model": {
                    model: int(
                        model_counts.get(model, 0)
                    )
                    for model in MODELS
                },
            }

            common_profile = {
                variable: float(
                    sample[variable].mean()
                )
                for variable in controls
            }

            for outcome in ("ela", "math"):

                formula = (
                    f'{outcome} ~ '
                    'C(model, Treatment('
                    'reference="50-50"))'
                )

                for variable in controls:
                    formula += f" + {variable}"

                # -----------------------
                # HC3 ROBUST OLS
                # -----------------------

                fit = smf.ols(
                    formula,
                    data=sample,
                ).fit(
                    cov_type="HC3"
                )

                # -----------------------
                # DISTRICT CLUSTERING
                # -----------------------

                cluster_fit = smf.ols(
                    formula,
                    data=sample,
                ).fit(
                    cov_type="cluster",
                    cov_kwds={
                        "groups": sample["district"]
                    },
                )

                ci = fit.conf_int(
                    alpha=0.05
                )

                text_summaries.append(
                    "=" * 80
                    + f"\n{year} | "
                    + f"{specification} | "
                    + f"{outcome.upper()}\n"
                    + f"Formula: {formula}\n\n"
                    + fit.summary().as_text()
                    + "\n\nDISTRICT-CLUSTERED "
                    + "SENSITIVITY\n"
                    + cluster_fit.summary().as_text()
                    + "\n"
                )

                # -----------------------
                # SAVE EVERY COEFFICIENT
                # -----------------------

                for term in fit.params.index:
                    coefficients.append({
                        "school_year": year,
                        "specification":
                            specification,
                        "outcome": outcome,
                        "term": term,
                        "coefficient_pp":
                            float(fit.params[term]),
                        "hc3_se":
                            float(fit.bse[term]),
                        "hc3_p_value":
                            float(fit.pvalues[term]),
                        "ci95_low":
                            float(ci.loc[term, 0]),
                        "ci95_high":
                            float(ci.loc[term, 1]),
                        "district_clustered_se":
                            float(
                                cluster_fit.bse[term]
                            ),
                        "district_clustered_p_value":
                            float(
                                cluster_fit.pvalues[term]
                            ),
                        "n_schools":
                            int(fit.nobs),
                        "n_districts":
                            int(
                                sample["district"]
                                .nunique()
                            ),
                        "r_squared":
                            float(fit.rsquared),
                        "adjusted_r_squared":
                            float(fit.rsquared_adj),
                    })

                # -----------------------
                # RAW AND ADJUSTED MEANS
                # -----------------------

                for model in MODELS:
                    profile = pd.DataFrame([{
                        "model": model,
                        **common_profile,
                    }])

                    raw = sample.loc[
                        sample["model"] == model,
                        outcome,
                    ].mean()

                    predicted = float(
                        fit.predict(profile).iloc[0]
                    )

                    adjusted_means.append({
                        "school_year": year,
                        "specification":
                            specification,
                        "outcome": outcome,
                        "model": model,
                        "schools": int(
                            model_counts[model]
                        ),
                        "raw_mean_pct": float(raw),
                        "adjusted_mean_pct":
                            predicted,
                        "common_low_pct":
                            common_profile.get(
                                "low", np.nan
                            ),
                        "common_hisp_pct":
                            common_profile.get(
                                "hisp", np.nan
                            ),
                        "common_ell_pct":
                            common_profile.get(
                                "ell", np.nan
                            ),
                    })

                # -----------------------
                # 80-20 VERSUS 90-10
                # -----------------------

                term_80 = next(
                    term
                    for term in fit.params.index
                    if "[T.80-20]" in term
                )

                term_90 = next(
                    term
                    for term in fit.params.index
                    if "[T.90-10]" in term
                )

                contrast = np.zeros(
                    len(fit.params)
                )

                terms = list(
                    fit.params.index
                )

                contrast[
                    terms.index(term_80)
                ] = 1

                contrast[
                    terms.index(term_90)
                ] = -1

                test = fit.t_test(
                    contrast
                )

                comparisons.append({
                    "school_year": year,
                    "specification":
                        specification,
                    "outcome": outcome,
                    "comparison":
                        "80-20 minus 90-10",
                    "difference_pp": float(
                        np.asarray(
                            test.effect
                        ).item()
                    ),
                    "p_value_hc3": float(
                        np.asarray(
                            test.pvalue
                        ).item()
                    ),
                    "ci95_low": float(
                        test.conf_int()[0, 0]
                    ),
                    "ci95_high": float(
                        test.conf_int()[0, 1]
                    ),
                })

                report[year][specification][
                    outcome
                ] = {
                    "r_squared":
                        float(fit.rsquared)
                }

    # -----------------------------------
    # WRITE RESULTS
    # -----------------------------------

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    data.to_csv(
        output_dir /
        "wa_regression_school_sample.csv",
        index=False,
    )

    pd.DataFrame(
        sample_counts
    ).to_csv(
        output_dir /
        "wa_regression_sample_counts.csv",
        index=False,
    )

    pd.DataFrame(
        coefficients
    ).to_csv(
        output_dir /
        "wa_regression_coefficients.csv",
        index=False,
    )

    pd.DataFrame(
        adjusted_means
    ).to_csv(
        output_dir /
        "wa_regression_means.csv",
        index=False,
    )

    pd.DataFrame(
        comparisons
    ).to_csv(
        output_dir /
        "wa_regression_80_vs_90.csv",
        index=False,
    )

    (
        output_dir /
        "wa_regression_full_output.txt"
    ).write_text(
        "\n".join(text_summaries),
        encoding="utf-8",
    )

    return report


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("output/washington"),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "output/washington/analysis"
        ),
    )

    args = parser.parse_args()

    data = load_school_data(
        args.input_dir
    )

    report = run_analysis(
        data,
        args.output_dir,
    )

    # -----------------------------------
    # REPRODUCIBILITY METADATA
    # -----------------------------------

    report["provenance"] = {
        "generated_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "analysis_script":
            "analysis/washington_regressions.py",

        "analysis_version":
            SCRIPT_VERSION,

        "github_sha":
            os.environ.get(
                "GITHUB_SHA",
                "not_run_in_github_actions",
            ),

        "inputs_sha256": {
            name: sha256(
                args.input_dir / name
            )
            for name in INPUT_FILES
        },

        "versions": {
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "statsmodels":
                statsmodels.__version__,
        },

        "method":
            "School-equal, schoolwide "
            "grades 3-5 SBAC proficiency; "
            "OLS with HC3 standard errors",

        "warning":
            "These are schoolwide associations, "
            "not verified DL-participant "
            "effects. District and reported "
            "instructional model are confounded.",
    }

    path = (
        args.output_dir /
        "wa_regression_report.json"
    )

    path.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                year: report[year]
                for year in YEARS
            },
            indent=2,
        )
    )

    print(
        f"Analysis saved to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
