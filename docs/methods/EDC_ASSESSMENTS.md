# Native state assessment collection: EDC v3.1

The first national assessment collection follows the user's November 6, 2026 instruction: collect ELA and mathematics from spring 2022 onward, including grade and assessment-population subgroup counts, before attempting any cross-state norming. The pinned Education Data Center (EDC) v3.1 release ends in **spring 2025**. The years collected are **2021–22, 2022–23, 2023–24 and 2024–25**; the API's year is the spring of testing. Spring 2021 is excluded.

Data sourced from the Education Data Center (www.eddatacenter.org), a partner project of the National Center for Civic Innovation, Inc.

Source: [EDC data](https://www.eddatacenter.org/data), [API documentation](https://www.eddatacenter.org/api), [v3.1 technical documentation](https://www.eddatacenter.org/data_documentation/EDC_technical_documentation_v3.1.pdf), [codebook](https://www.eddatacenter.org/data_codebooks/EDC_codebook_v3.1.xlsx), and [terms](https://www.eddatacenter.org/terms-of-service). Saved reference documents and capture receipts accompany the collection.

## Cohort and observation unit

The target cohort is every programme-associated **school research identity in the frozen national structural baseline v1**, including elementary, combined and secondary campuses and source-vintage supplements. It is not limited to elementary schools or to schools with known language allocation. Separate historical screening-only registry leads are not promoted into this cohort or described as confirmed DL schools.

These school identities select historical school outcomes. Their inclusion **does not establish that a DL programme operated in a particular testing year**, that a tested student participated, or that the current kindergarten model applied to that student. Each result is schoolwide context and a repeated cross-section. No observations are added to the DL-participant, ELP, EL-exit or SEDA layers.

EDC covers **grades 3–8**, not high-school assessments. Aggregate `G38` rows are retained as `all_tested_grades`; they are not assigned to an individual grade. A high-school-only campus, a private/BIE school outside EDC's scope, an early-grade campus, an unresolved identity and an absent school result can each explain a gap. An unmatched record is not evidence of closure, nonpublication or lack of a DL programme.

Native reporting grain is state × source school × school year × assessment name/type × subject × grade label × student group/subgroup × source version. Each native result is saved once. School research aliases and multiple programme/language strands use a separate association table. Joining those associations must not turn one source score into multiple independent observations. Distinct source rows at the same measurement grain remain visible in `source_grain_conflicts.csv`.

## Collected fields

| Requested information | Retained EDC information |
|---|---|
| ELA and math proficiency | `ProficientOrAbove_count`, `ProficientOrAbove_percent`, `ProficiencyCriteria`, assessment name/type, grade and year |
| Achievement distributions | Counts and proportions in `Lev1` through `Lev5`, plus available scale-score mean/SD |
| Students represented in each grade | `StudentGroup_TotalTested` and `StudentSubGroup_TotalTested`; all-student rows distinguish the total from a particular subgroup |
| ELL | All published `EL Status` categories, including `English Learner`, exited and combined categories as distinct rows |
| Economic disadvantage | Published `Economic Status` categories, including EDC's `Economically Disadvantaged` label |
| Race/ethnicity | All published `RaceEth` categories |
| Disability | All published `Disability Status` categories |
| Gender | All published `Gender` categories |
| Reporting and comparability context | Participation rate, native IDs/names, version, assessment-name and subject cut-score change flags |

Additional reading, English and writing results are retained under **separate source subject labels** where EDC supplies them; they do not become duplicate ELA observations. Spanish-language-arts and other subject categories are not folded into ELA. The assessed language of an EDC result is `not_reported`: the export has no row-level assessment-language variable, and programme language does not supply it.

Subgroups can overlap. Never sum EL, economic disadvantage, disability, gender and race counts to obtain a grade total. EDC also cautions that race/ethnicity categories may not be mutually exclusive. An omitted subgroup is not an observed zero; EDC drops some zero-count subgroup rows. Combined current/former EL categories must not be treated as current ELL counts or as rates of exiting EL status.

**These are assessment-population counts, not a national grade-enrollment census.** EDC's codebook defines them as valid scores, with documented substitutions. Some fields and proficiency counts are EDC-derived; a numeric value means reported by EDC, not independently verified as a direct SEA count. Its export has no row-level count-origin flag. `count_basis`, `count_proxy_source_spring_year` and `count_provenance_note` retain the documented qualifications:

| State/period | EDC v3.1 documentation, Table 21 |
|---|---|
| Utah, 2022–2025 | School/district counts use CCD enrollment proxies. |
| Kansas and North Dakota, 2022–2024 | Spring 2022 EDFacts counts are reused. |
| Kansas and North Dakota, 2025 | Counts use 2024–25 CCD enrollment. |
| Arkansas subgroups, 2022–2024 | Some counts use spring 2022 EDFacts; row-specific provenance is not identified. |
| Illinois, 2022 | EDFacts substitutions are documented; row-specific source years are not identified in the export. |

Other counts retain EDC's general qualification that their exact row-level origin is unavailable. Source years for proxies are not relabeled as newly observed headcounts. Missing enrollment and ELL enrollment totals remain separate future context needs. EDC's economic-disadvantage category combines state classifications such as low income, FRL eligibility and other SEA definitions; it is **not a single nationwide FRL definition**. The native EDC labels are retained; detailed state eligibility definitions are not newly established by this collection.

## Values and comparability

Native CSV cells remain unchanged in `native/`. The analysis-ready CSVs retain each numeric field's raw text, numeric value, status and bounds. `0` is zero, `*` is suppressed, `--`/empty is not reported, and ranges/open bounds have no invented point estimate. Unrecognized tokens and out-of-domain fractions are retained for review in `value_anomalies.csv`.

EDC proportions are multiplied by 100 to express percentages, including interval endpoints. This is a unit conversion, **not cross-state norming**. State proficiency criteria, assessment types and change flags remain attached. No national proficiency average, common achievement scale, SEDA estimate, or reconstruction of suppressed cells is created.

## Identity checks and provenance

NCES/state identifiers remain strings. Some public GCS CSV exports omit an initial zero; the normalized NCES field pads only valid 11/12-digit school IDs, while the source cell remains unchanged.

Existing grade-context NCES candidates are not applied blindly. For each source year, the collector corroborates the school identifier and source school name, checks the reported district identifier, and retains the decision in `school_matches.csv`. Additional public CCD directory evidence can corroborate a unique school/district identity. Conservative abbreviation/accent normalization, identifier suffix removal and reviewed district-name correspondences are documented in code and configuration. Abbreviations, old names and district discrepancies that require review have school/year-specific decisions in `config/edc_identity_reviews.csv`; unresolved candidates never become result links. These associations do not merge research identities or certify programme histories.

The original state/year CSV responses are cached locally in ignored `.cache/edc_v3_1/`. Every accepted download is checked against its GCS server MD5 and has a SHA-256 receipt. Git stores selected native rows as compressed CSV, not 16+ GB of unrelated source records. The receipt records the original URL, resolved URL, retrieval, full-file hash, selected-extract hash and original CSV data-record positions. **An extract is reserialized CSV with verbatim field values, not a claim to archive the entire original response.** `saved_source_extract` distinguishes it from original source bytes in the source catalogue.

The collection manifest pins cohort/identity evidence, review configurations, source receipts, data files and transformation code. Frozen structural baselines and prior assessment pilots retain their original bytes. New assessment results are a partitioned layer rather than an expansion of the legacy pilot CSVs.

## Reproduce and query

```bash
# Public network collection; resume cache and verify full-file integrity.
dl-outcomes edc collect

# A new, empty destination is required. Existing collections are not overwritten.
dl-outcomes edc build --destination /tmp/edc-new-vintage

# Offline checks of saved receipts, complete cohort/year audit and all normalized cells.
dl-outcomes edc check --reproduce

# Register the completed collection in the national source and coverage catalogue.
dl-outcomes build
dl-outcomes validate

# Optional analytics environment: adds three separate EDC tables and Parquet files.
dl-outcomes export-analytics --destination /tmp/dl-edc-analytics
```

`--reuse /path/to/prior-collection` can reuse selected native extracts during a new build only when the source hash, extract hash, school-unit set and subject/subgroup selection agree. Changed selections are read from the original cached CSVs. Reuse does not bypass identity adjudication.

The analytical tables are `edc_school_grade_results`, `edc_school_matches` and `edc_school_year_coverage`. Their CSV-derived values remain strings so IDs, bounds and exact decimals survive; cast explicit `_numeric` columns when needed. For example:

```sql
SELECT nces_school_id, school_name, school_year, grade_scope, subject,
       TRY_CAST(ProficientOrAbove_percent_numeric AS DOUBLE) AS proficient_percent,
       ProficientOrAbove_percent_status,
       StudentSubGroup_TotalTested_raw, count_basis
FROM edc_school_grade_results
WHERE student_group = 'All Students'
  AND subject IN ('ELA', 'math')
  AND grade_scope IN ('3', '4', '5', '6', '7', '8');
```

Use `EXISTS` against the identity bridge to select a research school without multiplying source records through aliases. Select a source version explicitly when combining this collection with prior WA/TX pilot observations for the same year; those releases are not additional students.
