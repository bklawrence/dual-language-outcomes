# EDC school/grade assessment collection — November 6, 2026

The first national assessment collection adds native state ELA/math results from **spring 2022 through spring 2025**, using **Education Data Center SADR v3.1**. It contains **1,538,145 source rows** for the frozen national structural baseline's school cohort. No cross-state norming, SEDA estimation or DL-participant attribution is applied.

Data sourced from the Education Data Center (www.eddatacenter.org), a partner project of the National Center for Civic Innovation, Inc.

## Coverage

All **4,617 school research identities** are audited for each of four years, including elementary, combined and secondary sites. The source covers grades 3–8; high-school assessments require another source. School-year labels are 2021–22 through 2024–25.

| School year | School identities matched | With grade-specific rows | With ELA grade proficiency | With math grade proficiency | Source result rows |
|---|---:|---:|---:|---:|---:|
| 2021–22 | 3,824 | 3,823 | 3,808 | 3,805 | 370,504 |
| 2022–23 | 3,846 | 3,845 | 3,829 | 3,827 | 378,324 |
| 2023–24 | 3,866 | 3,864 | 3,849 | 3,843 | 390,200 |
| 2024–25 | 3,841 | 3,839 | 3,823 | 3,820 | 399,117 |

Proficiency availability means at least one reported or bounded all-student percentage at an actual grade, counted separately by subject. It does not mean all grades/subgroups are available or that a numeric point is observed in every row.

Across any year, **3,891 research identities** match **3,889 distinct source school units**; 3,890 research identities have grade-specific rows. **3,779** have matched identities in all four years. The bridge preserves aliases without multiplying results. Multiple language strands do not create additional test observations.

The **726 never-matched research identities** include 249 whose saved grade context suggests grade 9-plus only, 46 whose saved context ends before grade 3, and 431 requiring further identity/source-coverage review. Saved grade context is not a historical annual grade observation. An unsuccessful match does not establish school closure, lack of a programme or nonpublication.

Four school-year candidates remain held for identity review: Central Middle School, Delaware, in 2021–22 and 2022–23; and Spartan Learning Academy/Bernalillo Middle, New Mexico, in those same years. Their candidate results are not assigned to the research school without resolving the identity questions. Other unmatched labels remain in the broader gap audit for later work.

## Retained information and interpretation

The extracts include all published requested groups: all students, EL status, economic status, race/ethnicity, disability status and gender. Each retains source subgroup labels, valid-score/substitute counts, proficiency counts/percentages, achievement-level distributions, available scale-score statistics, participation rates and assessment/cut-score change flags. Supplementary reading/English/writing outcomes remain separate subjects.

Counts are **EDC assessment-population counts or documented proxies**, not complete grade or ELL enrollment totals. Utah uses CCD enrollment proxies; Kansas/North Dakota and some Arkansas subgroup counts use documented federal substitutions, including older counts. Exact source years are left unknown where not established by the documentation/export. Economic disadvantage retains EDC's state-defined category and is not recoded as universal FRL eligibility. Current/former/combined EL categories remain distinct and do not establish EL-exit rates.

Suppression, ranges, missing values and observed zeros remain distinct. Percentages are converted from source fractions to a 0–100 unit; no common achievement scale is constructed. Source criteria, assessment types and change flags remain attached. Schoolwide results do not identify DL participants or establish historical programme exposure.

## Reproducibility and repository integration

The collection uses **192 integrity-verified state/year source downloads** for the 48 states represented by programme-associated school identities. All 50 states remain in the coverage report; Mississippi/West Virginia have no baseline programme-school targets, and North Dakota's target has no matched EDC results. This is not a statement of statewide programme or assessment absence.

The original CSVs total **16,528,139,792 bytes** and remain in ignored local cache. Git stores the selected source rows, normalized CSV partitions, full-file/extract checksums, retrieval receipts, original data-record positions, identity evidence, source documentation and a file/code manifest. Every successful download was checked against the GCS server MD5. The selected records have zero duplicate measurement-grain conflicts and zero unrecognized/out-of-domain value flags in the saved review queues.

The national build registers the external source releases and actual grade availability without rewriting the earlier TX/WA pilot observation tables. Schema 1.5.0 adds `saved_source_extract` provenance. Optional analytical export adds `edc_school_grade_results`, `edc_school_matches` and `edc_school_year_coverage` as separate DuckDB/Parquet tables. The source bridge and outcomes remain separate to preserve reporting units and uncertainty. Earlier structural reports receive no rewrites; the current metadata report uses a new path. Frozen national baseline v1 remains intact.

Verification commands for this collection are `dl-outcomes edc check --reproduce`, `dl-outcomes build`, `dl-outcomes validate`, the full unittest suite, and the analytical export/count checks in CI.

Local verification passed: **332 tests**, the national build/validation, reproduction of all **1,538,145 rows across 192 partitions**, and row-count checks for all **31 DuckDB/Parquet tables**. The test suite also verified frozen-baseline reproduction and preservation of the prior assessment/context outputs.

Start with the [dataset file guide](../../data/assessments/edc_v3_1_2022_2025/README.md), [school/year coverage](../../data/assessments/edc_v3_1_2022_2025/school_year_coverage.csv), [gap audit](../../data/assessments/edc_v3_1_2022_2025/school_match_gaps.csv) and [methods](../methods/EDC_ASSESSMENTS.md).
