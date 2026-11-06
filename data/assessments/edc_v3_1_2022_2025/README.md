# EDC school/grade assessments, spring 2022–2025

**1,538,145 source result rows**, selected for the national DL baseline's school cohort. Results are available for **3,891 of 4,617 school research identities (84.3%)**, corresponding to **3,889 distinct EDC school reporting units**. **3,890 research identities have grade-specific rows** in at least one year. Reported or bounded all-student grade-specific proficiency percentages are available for **3,872 identities in ELA and 3,872 in math**, counted separately by subject. These are availability counts, not counts of confirmed annual DL participation.

The collection uses **EDC SADR version 3.1**. API years 2022–2025 mean **school years 2021–22 through 2024–25**. The source release ends at spring 2025. Spring 2021 is excluded. EDC supplies grades **3–8** and some grade aggregates, not high-school assessment results.

Data sourced from the Education Data Center (www.eddatacenter.org), a partner project of the National Center for Civic Innovation, Inc.

## Open the data

| File or folder | Contents |
|---|---|
| [school_grade_results/](school_grade_results/) | Analysis-ready CSVs, partitioned by state and spring year, compressed with gzip. Raw values, numeric values, statuses, bounds and source labels remain explicit. |
| [native/](native/) | Selected original EDC field values, plus a stable result key and original CSV data-record position. CSV rows are reserialized; these are not the full original files. |
| [partitions.csv](partitions.csv) | State/year row counts and paths to every native and analysis-ready partition. Includes zero-row partitions. |
| [school_year_coverage.csv](school_year_coverage.csv) | Every research school × each of the four years, including matched/unmatched status, grade-result availability, subgroup row availability and ELA/math proficiency availability. |
| [state_coverage.csv](state_coverage.csv) | All 50 states × four years. States without target-cohort schools are explicit. |
| [school_matches.csv](school_matches.csv) | Dated research-school ↔ EDC-unit associations and supporting identity checks. |
| [school_match_gaps.csv](school_match_gaps.csv) | One row per research identity missing at least one year; saved grade context is distinguished from verified annual reporting scope. |
| [identity_review_queue.csv](identity_review_queue.csv) | All unmatched school-years, including four cases that need further identity adjudication. A failed match is not proof of nonpublication or closure. |
| [targets.csv](targets.csv) | Frozen-baseline cohort and the identifiers/directory evidence used for matching. |
| [field_coverage.csv](field_coverage.csv) | State/year/grade/subgroup availability, with reported, bounded, suppressed and missing values counted separately. |
| [school_grade_subgroup_coverage.csv.gz](school_grade_subgroup_coverage.csv.gz) | Source-unit/grade/subject subgroup-availability audit. Counts describe source rows across available assessment types, not student totals. |
| [shared_source_unit_aliases.csv](shared_source_unit_aliases.csv) | Research aliases sharing a source unit. Results are stored once; the research identities are not merged. |
| [source_grain_conflicts.csv](source_grain_conflicts.csv), [value_anomalies.csv](value_anomalies.csv) | Source-quality review queues; both contain zero flagged cases in this collection. |
| [sources/](sources/), [reference/](reference/) | Retrieval/hash receipts, original full-file URLs, selected-extract hashes, codebook, technical documentation and terms. |
| [table_contracts.json](table_contracts.json), [summary.json](summary.json), [manifest.json](manifest.json) | Column/grain definitions, collection totals, exact input/output/code hashes. |

For example, [TX_2025.csv.gz](school_grade_results/TX_2025.csv.gz) contains Texas spring 2025 results, and [UT_2025.csv.gz](school_grade_results/UT_2025.csv.gz) contains Utah spring 2025 results. Download and decompress the CSVs before opening them in a spreadsheet. Compression keeps large national extracts manageable in Git. Optional Parquet/DuckDB export is available through the project CLI.

## Interpret the rows

The data retain ELA/math proficiency counts and percentages, achievement-level counts/proportions, available scale-score statistics, participation rates and test/cut-score change flags. Published EL-status, economic-status, race/ethnicity, disability and gender subgroups remain separate. Supplementary reading/English/writing results retain their own subject labels.

**Counts describe the assessment population or an EDC-documented proxy. They are not a complete grade-enrollment census.** Utah uses enrollment proxies; Kansas/North Dakota and some Arkansas subgroup counts use documented federal substitutions, including older counts. Read `count_basis`, `count_proxy_source_spring_year` and `count_provenance_note`. EDC's economic-disadvantage label retains state-defined eligibility and must not be treated as one nationwide FRL definition. Current and former EL categories remain distinct; these are academic results, not English-language-proficiency test results or EL-exit rates.

`*_raw` preserves the EDC cell. `*_numeric` is populated only for a numeric point. A range or open bound has bound fields and no point estimate. `*` is suppressed, `--`/empty is not reported, and `0` is zero. Percentages in numeric/bound columns are expressed on a 0–100 scale; original EDC proportions remain in raw columns. This unit conversion does **not** norm the results across states. Native proficiency criteria and assessment types remain attached.

`G38` is `all_tested_grades`, not grade 38 or a result replicated across individual grades. The cohort includes elementary, combined and secondary campuses. Of the **726 identities without any matched year**, saved grade context suggests 249 grade-9-plus campuses and 46 campuses ending before grade 3; 431 require further identity/source-coverage review. Those context classifications do not certify historical grade spans. Schools outside EDC scope, private/BIE campuses, new schools and alternate public labels can explain gaps. Source absence is not asserted from an unmatched name.

All results are **schoolwide context, not identified DL-participant outcomes**. A school match does not establish that the programme operated in that year, that tested students participated, or that the current allocation model applied to their kindergarten cohort. Multiple language strands must not duplicate an outcome. Earlier WA/TX assessment pilots remain separate vintages and are not additional student samples.

See [methods and reproduction commands](../../../docs/methods/EDC_ASSESSMENTS.md) for the exact collection, identity, population, proxy and comparability rules. Offline verification:

```bash
dl-outcomes edc check --reproduce
dl-outcomes validate
```
