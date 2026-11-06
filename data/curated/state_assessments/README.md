# State assessment data

The national EDC school/grade collection is in [data/assessments/edc_v3_1_2022_2025](../../assessments/edc_v3_1_2022_2025/README.md). It contains the spring 2022–2025 ELA/math results and assessment-population subgroups for the national baseline school cohort. Large files are partitioned, gzip-compressed CSVs.

`observations.csv` in this folder preserves the original Washington pilot. It is not the complete national EDC table. The national source and coverage catalogues register the EDC collection separately, and analytical export includes `edc_school_grade_results`, `edc_school_matches` and `edc_school_year_coverage`.

See [school/year coverage](../../assessments/edc_v3_1_2022_2025/school_year_coverage.csv) and [methods](../../../docs/methods/EDC_ASSESSMENTS.md). Results are schoolwide context; counts include documented source substitutions and do not establish total grade enrollment or DL participation. State scales remain unchanged.
