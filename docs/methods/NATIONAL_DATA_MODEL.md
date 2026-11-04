# National longitudinal data model

Schema version: **1.3.0**. Scope: all 50 US states and all instructional languages. This is a public aggregate-data research model, with source-specific observations and explicit uncertainty. Partial structural working sets now cover 15 states, including the Utah, Colorado, New Mexico, Arizona, Nebraska and Kansas first pass. Additional proficiency collection follows completion of the 50-state structural program work.

State-level evidence claims retain discovery/screening rows whose school or language-track identity has not been reviewed. They reference an existing state identity and do not create a programme, school or district/LEA match. A source reporting-group heading such as New Mexico's “State Charter Schools” is retained as context, not manufactured into one district. School/program IDs in the six-state batch are provisional research keys; no NCES matches were inferred.

## Entities, candidates and time

`schools` and `districts` identify research entities. State/NCES/other native identifiers belong in `identifier_crosswalk`, with namespace, source, review status and known year validity. Identifiers are strings. Names are labels and dated evidence, not automatic join keys.

`programs` is separate from schools. **`provisional_evidence_group` is not a verified distinct program.** Texas starts from provisional TAPR-category/language evidence keys; Washington starts from school/reported-language evidence groups. These records make the existing work linkable without manufacturing official program IDs or continuity. A future reviewed identity decision can consolidate aliases while preserving original source identifiers.

`program_sites` permits a program to have multiple school sites and documented validity periods. A move, rename or closure must retain the underlying evidence. Blank start/end dates mean unknown; they do not establish uninterrupted operation. Program design, instructional languages and allocations are time-dependent tables, rather than permanent attributes of a school.

`config/identity_mappings.csv` provides reviewed aliases. Pending rows never apply. Accepted rows require evidence and may be limited to school years. Two accepted identities applying to the same alias/year fail resolution. An undated observation does not silently use a year-limited mapping. Washington source-row program aliases include the source vintage because row numbers are not durable program IDs.

`program_configurations` records one-way/two-way status, strand/whole-school structure, reported model, grade and cohort scope where supported. Texas TAPR one-way/two-way categories remain provisional reporting-category associations, not independent proof of campus instructional hosting. Washington annual model labels are not entering-cohort schedules.

`program_status_history` separates reference-year operation and eligibility assessments from the actual dates of language/design evidence. It preserves confirmed, uncertain, discontinued and future statuses, public-funding/content scope and confirmation method. A program can be operating while its public-program eligibility remains unresolved. Continuity confirmation requires its saved review; it does not refresh older allocations or structure descriptions. Oregon’s directory listing status is distinct from independently confirmed campus implementation.

`allocation_schedules` preserves raw policy/model evidence even when a numeric schedule cannot safely be attributed to a language track. `instructional_allocations` contains one row per **named** language in a documented schedule. Complete schedules must total 100%. An advertised model label does not create named-language percentages or verified tested-cohort exposure. The Illinois seed's 2025–26 90/10 plan is migrated as two language rows and remains a plan. Texas's 970 original policy records and 23 separate current Spring observations remain explicit. Five-state model-only share selections survive as evidence claims; only selected explicit K schedules become named-language plan rows. Conflicting points/ranges and later-only schedules remain visible without selecting an unsupported reference-year point. Oregon ratios remain directory policies with unspecified language ordering; English and K applicability are not inferred.

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

`not_collected`, `source_identified`, `pilot_partial`, `collected`, `searched_not_found` and `not_publicly_reported` have distinct meanings. A zero-row output table does not establish nonpublication. The six newly integrated states have `integrated_partial` collection profiles. An archived target-year vintage without a supported annual observation may remain `source_identified`; migration does not upgrade it into confirmed operation.

`availability_basis=collected_source_scope` means the listed smallest unit is demonstrated by the collected source, not a completed search for every finer public reporting option. A future availability review can explicitly record `source_availability_review`. Retrieval-based review dates are retained only where known; undated legacy observations do not acquire invented review dates.

ELP observations, actual EL exits, exit policies and SEDA remain uncollected. Existing Texas/Washington assessment pilots are preserved byte for byte. `config/project.json` sets the active phase to `structural_inventory` and defers new proficiency collection until the state structural inventories are finished. The next collection work adds remaining-state schools, languages, allocation schedules, one-way/two-way organization and strand/whole-school evidence. Assessment availability and collection follow that structural phase.

## Integrated structural evidence and review views

`evidence_claims.evidence_period_raw` retains fiscal-year, multi-year and change-period descriptions. Only an explicitly consecutive single academic year populates typed validity years: `FY2026`, `2020-25` and undated descriptions do not become invented annual observations. The reviewed five-state 2025–26 inventory retains earlier 2026–27 research as a superseded vintage, not a second annual census. All 3,480 attribute claims preserve original values (empty values become null), source classification, excerpts, conflicts and applicability. The Bergan/Bergen spelling correction retains both research school aliases under the same reviewed program lineage. Oregon uses the already reviewed NCES crosswalk; its 2024–25 identity reference does not date 2026–27 instruction to 2024–25.

The generated structural review view unions attributes across their source periods for inspection. It is not a single contemporaneous configuration. State summaries distinguish all registry schools (including screening leads), program-host school units and provisional program evidence groups. California’s 1,310 historical school leads do not create additional language-track programs; Oregon’s 12 source-classified heritage/revitalization rows remain separate screening evidence. Status-history coverage is evidence availability, not a count of confirmed operating or eligible programs. Earlier frozen releases keep their own contracts and source bytes.
