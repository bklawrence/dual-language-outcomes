# National longitudinal data model

Schema version: **1.0.0**. Scope: all 50 US states and all instructional languages. This is a public aggregate-data research model, with source-specific observations and explicit uncertainty. The initial migration includes Illinois seed inputs and Texas/Washington pilots; it does not claim completed collection for 50 states.

## Entities, candidates and time

`schools` and `districts` identify research entities. State/NCES/other native identifiers belong in `identifier_crosswalk`, with namespace, source, review status and known year validity. Identifiers are strings. Names are labels and dated evidence, not automatic join keys.

`programs` is separate from schools. **`provisional_evidence_group` is not a verified distinct program.** Texas starts from provisional TAPR-category/language evidence keys; Washington starts from school/reported-language evidence groups. These records make the existing work linkable without manufacturing official program IDs or continuity. A future reviewed identity decision can consolidate aliases while preserving original source identifiers.

`program_sites` permits a program to have multiple school sites and documented validity periods. A move, rename or closure must retain the underlying evidence. Blank start/end dates mean unknown; they do not establish uninterrupted operation. Program design, instructional languages and allocations are time-dependent tables, rather than permanent attributes of a school.

`config/identity_mappings.csv` provides reviewed aliases. Pending rows never apply. Accepted rows require evidence and may be limited to school years. Two accepted identities applying to the same alias/year fail resolution. An undated observation does not silently use a year-limited mapping. Washington source-row program aliases include the source vintage because row numbers are not durable program IDs.

`program_configurations` records one-way/two-way status, strand/whole-school structure, reported model, grade and cohort scope where supported. Texas TAPR one-way/two-way categories remain provisional reporting-category associations, not independent proof of campus instructional hosting. Washington annual model labels are not entering-cohort schedules.

`allocation_schedules` preserves raw policy/model evidence even when a numeric schedule cannot safely be attributed to a language track. `instructional_allocations` contains one row per **named** language in a documented schedule. Complete schedules must total 100%. An advertised model label does not create named-language percentages or verified tested-cohort exposure. The Illinois seed's 2025–26 90/10 plan is migrated as two language rows and remains a plan. Texas's 970 policy records retain their labels and unresolved historical/cohort context.

## Three assessment layers

| Conceptual layer | Curated tables | Scope |
|---|---|---|
| 1. DL participants | `dl_participant_outcomes` | A source explicitly identifies a DL participant population. Current-EL-only and all-participant populations remain distinct. |
| 2. State assessments and context | `state_assessments`, `demographics`, `el_proficiency`, `el_exit_outcomes`; definitions and `el_exit_policies` | Native school/grade/subgroup, district or state reports. DL membership is not inferred. |
| 3. Stanford SEDA | `seda` | The actual release's geography, grades, periods, measures, population and uncertainty. SEDA derives from state assessment data and is not an independent testing system. |

Every published observation is stored once at this grain:

```text
reporting unit × year/period × grade scope × population definition
× cohort (if identified) × assessment/version × administration
× subject/domain × assessed language × metric × source vintage
```

The assessed language is independent of the program's instructional languages. Academic achievement, English-language proficiency and partner-language proficiency are separate constructs. A proficiency percentage, scale score, standardized SEDA estimate and growth estimate are different measures with different units and definitions.

Unknown grade, language, instrument version or denominator remains explicit. All-grade results do not become grade-specific results. A district result does not become a school result. The eight imported Texas subject results are current-EL one-way-DL groups across all tested grades, including one district group. They are neither grade 3/4/5 scores nor results for all DL participants.

## Attribution links

`reporting_units` describes the actual source entity and any program reporting category. `observation_program_links` records an association without copying the observation value. Its statuses are `schoolwide_context`, `combined_reporting_group`, `unresolved` and `direct_program`.

The pilot has **no direct instructional-track outcome attribution**. Washington schoolwide results can be linked as context to two language candidates without becoming two independent scores. Texas reporting-group matches remain unresolved/combined. The Round Rock district aggregate has no campus/track links.

Direct attribution requires an explicit basis and dated `outcome_population` evidence for that site. Schoolwide/non-DL populations cannot be promoted to program outcomes. Multiple direct links for the same source observation fail validation. Analysis code must preserve these statuses rather than treating a school/program join as participant membership.

## English learners, poverty and comparability

`population_definitions` preserves current EL, former EL, non-EL, all-student and DL-specific populations, along with native labels and group types. Subgroups may overlap and must not be summed as mutually exclusive categories without source support.

`el_exit_policies` stores the applicable assessment/version, grade scope, effective years, overall and domain thresholds, additional requirements and source. WIDA ACCESS is one possible instrument; TELPAS, ELPAC and others use their own definitions. Actual reclassification/exit counts and rates belong in `el_exit_outcomes`, with the published numerator and denominator definition. Meeting a test threshold is not automatically official exit. Changes in EL enrollment cannot establish an exit count.

FRL eligibility, direct certification, CEP participation and state-defined economic disadvantage must use separate metrics. Washington's native `low_income` count is retained as OSPI low income; this migration does not certify that every year's definition equals FRL eligibility. Derived enrollment shares use subgroup and all-student counts from the identical school/year/grade row. They are not assessment-tested denominators or DL-participant demographics.

Metrics retain denominator definitions and comparability groups. The pipeline does not pool state proficiency percentages as equivalent scores or treat English-language-proficiency scales as interchangeable across instruments or scoring revisions. Cross-state/time harmonization must document its choices separately.

## Longitudinal records and revisions

School year/reporting period, entering cohort, publication/version and retrieval are separate. Source vintages remain separate observations; the same school/year can legitimately have multiple revised releases. Analyses must select vintages explicitly and avoid counting revisions as additional student samples.

`period_basis` distinguishes school-year ranges, calendar-year ranges and actual calendar dates. A pooled school-year estimate can retain `period_start=2009-10` and `period_end=2018-19`; it does not require invented day/month boundaries. Citation `evidence_period_raw` describes a claim's applicability and is separate from an explicitly reported source `data_as_of_raw`.

Repeated school/grade cross-sections are labeled `repeated_cross_section`. They do not demonstrate that the same students remained enrolled or followed the current instructional model. An identified cohort requires an actual cohort label or entry year. Policy evidence alone does not verify tested-cohort exposure.

The observation `value_raw`, normalized value, source unit, status and bounds retain masks and reporting conventions. `0` is observed zero; suppressed/missing/bounded values have no numeric point estimate. Washington source fractions are explicitly converted to percentages. Reported tested and expected counts remain separate from an unverified proficiency denominator. Rates derived from enrollment counts are marked derived and carry their formula/counts.

## Evidence and releases

`source_releases` identifies the exact source vintage. Saved public sources and legacy snapshots have a relative path and SHA-256. Citation-only records are explicitly `metadata_only`; a remote hash does not mean the original document is archived. Legacy import dates/publication dates are not invented.

`evidence_claims` attaches verification to a particular attribute, entity, source and time scope. Confirming program existence does not confirm allocation, language pairing or whole-school delivery. A continuity-based confirmation can be stored with method `continuity_review` and its supporting search/review evidence; it is distinguishable from a dated campus report. Competing claims and unknown validity remain visible.

`data/curated/manifest.json` records input, config, code and output hashes plus schema version. A frozen local release bundles the pipeline and exact inputs/outputs. Earlier Texas/five-state checkpoints remain unchanged in their original locations; normalized national seed originals are archived byte for byte.

## Coverage and current limits

Coverage is state × year × layer. The initial configurable tracking window is 2014–15 through 2025–26, expanded automatically when imported research includes other years. It is a tracking window, not a declaration that earlier data do not exist.

`not_collected`, `source_identified`, `pilot_partial`, `collected`, `searched_not_found` and `not_publicly_reported` have distinct meanings. A zero-row output table does not establish nonpublication. Existing California/Idaho/Montana/Nevada/Wyoming/Oregon research files are recognized as identified sources without claiming they have been fully migrated.

`availability_basis=collected_source_scope` means the listed smallest unit is demonstrated by the collected source, not a completed search for every finer public reporting option. A future availability review can explicitly record `source_availability_review`. Retrieval-based review dates are retained only where known; undated legacy observations do not acquire invented review dates.

ELP observations, actual EL exits, exit policies and SEDA remain uncollected in this initial pilot. NCES/SEDA identity crosswalks are supported by the model but no new matches are inferred. The next collection work should identify each state's participant-report availability and historical coverage before expanding those layers.
