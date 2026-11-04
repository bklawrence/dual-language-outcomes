# National data dictionary

Schema version: **1.2.0**. Generated from `src/dl_outcomes/schemas/catalog.json`.

Empty CSV cells are null. IDs and school years remain strings. All listed headers are required, including in zero-row tables.

## states

The 50 US states; codes and FIPS remain strings.

Path: `data/curated/registry/states.csv`. Primary key: `state_code`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `state_code` | string | pattern: ^[A-Z]{2}$ |
| `state_name` | string |  |
| `state_fips` | string | pattern: ^\d{2}$ |

## datasets

Source dataset identity, distinct from a particular release.

Path: `data/curated/sources/datasets.csv`. Primary key: `dataset_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `dataset_id` | string |  |
| `state_code` | string / null | states.state_code |
| `layer` | string | inventory, dl_participants, state_assessments, demographics, el_proficiency, el_exit_policy, el_exit_outcomes, seda |
| `dataset_name` | string |  |
| `publisher` | string / null |  |
| `source_url` | string |  |
| `native_dataset_id` | string / null |  |
| `notes` | string / null |  |

## sources

Immutable source vintage; sha256 describes snapshot_path when saved, or remote bytes for metadata-only records.

Path: `data/curated/sources/source_releases.csv`. Primary key: `source_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `source_id` | string |  |
| `dataset_id` | string | datasets.dataset_id |
| `source_url` | string |  |
| `version_label` | string |  |
| `publication_date` | string / null |  |
| `retrieved_at` | string / null |  |
| `data_as_of_raw` | string / null |  |
| `snapshot_path` | string / null |  |
| `sha256` | string / null | pattern: ^[0-9a-f]{64}$ |
| `snapshot_kind` | string | saved_public_source, legacy_snapshot, metadata_only |
| `notes` | string / null |  |
| `evidence_period_raw` | string / null |  |

## districts

Research district identity; native IDs live in the dated crosswalk.

Path: `data/curated/registry/districts.csv`. Primary key: `district_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `district_id` | string |  |
| `state_code` | string | states.state_code |
| `district_name` | string |  |
| `identity_status` | string | state_identifier, provisional_name_group, legacy_provisional |

## schools

Research school identity, independent of current district or program.

Path: `data/curated/registry/schools.csv`. Primary key: `school_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `school_id` | string |  |
| `state_code` | string | states.state_code |
| `school_name` | string |  |
| `identity_status` | string | state_identifier, provisional, legacy_provisional |
| `screening_status` | string |  |

## identifiers

Native identifier aliases; time validity is unknown unless explicitly documented.

Path: `data/curated/registry/identifier_crosswalk.csv`. Primary key: `identifier_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `identifier_id` | string |  |
| `entity_type` | string | school, district, program |
| `entity_id` | string |  |
| `namespace` | string |  |
| `native_id` | string |  |
| `valid_from_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `valid_to_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `match_status` | string |  |
| `source_id` | string | sources.source_id |

Additional unique keys:

- `namespace, native_id, valid_from_year, valid_to_year, source_id`

## school_district_history

Dated affiliation observations, not inferred continuous district membership.

Path: `data/curated/registry/school_district_history.csv`. Primary key: `membership_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `membership_id` | string |  |
| `school_id` | string | schools.school_id |
| `district_id` | string | districts.district_id |
| `school_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `validity_status` | string | source_year, snapshot_only, legacy_undated |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |

## programs

Research program records. Provisional evidence groups are not verified distinct program counts.

Path: `data/curated/registry/programs.csv`. Primary key: `program_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `program_id` | string |  |
| `state_code` | string | states.state_code |
| `program_name` | string |  |
| `identity_status` | string | verified_program, provisional_evidence_group, legacy_provisional |
| `screening_status` | string |  |
| `notes` | string / null |  |

## program_sites

Program-to-school association with separately documented time validity.

Path: `data/curated/registry/program_sites.csv`. Primary key: `site_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `site_id` | string |  |
| `program_id` | string | programs.program_id |
| `school_id` | string | schools.school_id |
| `valid_from_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `valid_to_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `link_status` | string | documented, provisional, legacy_provisional |
| `source_id` | string | sources.source_id |

## program_status_history

Dated research assessments of program operation and eligibility, kept separate from the dates of language, design and allocation evidence. Retains closures, future plans and continuity reviews.

Path: `data/curated/program_history/program_status_history.csv`. Primary key: `status_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `status_id` | string |  |
| `site_id` | string | program_sites.site_id |
| `school_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `operating_status` | string |  |
| `eligibility_status` | string |  |
| `instructional_scope` | string / null |  |
| `public_funding_status` | string / null |  |
| `confirmation_method` | string |  |
| `evidence_period_raw` | string / null |  |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |
| `notes` | string / null |  |

Additional unique keys:

- `site_id, school_year, source_id`

## program_languages

Language-specific claims; an unreported partner language is never filled with English.

Path: `data/curated/program_history/program_languages.csv`. Primary key: `language_record_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `language_record_id` | string |  |
| `site_id` | string | program_sites.site_id |
| `language_code` | string / null |  |
| `language_name` | string |  |
| `language_role` | string | instruction_language, additional_language, elective, reported_instruction_language |
| `valid_from_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `valid_to_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `evidence_period_raw` | string / null |  |
| `verification_status` | string | documented, district_policy_only, provisional, unverified, continuity_review, published_plan_not_observed, metadata_only, not_reported |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |
| `notes` | string / null |  |

## program_configurations

Program design and model history at the actual documented grade/year/cohort scope.

Path: `data/curated/program_history/program_configurations.csv`. Primary key: `configuration_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `configuration_id` | string |  |
| `site_id` | string | program_sites.site_id |
| `school_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `entry_cohort_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `grade_scope` | string |  |
| `population_model` | string | one_way, two_way, unknown |
| `delivery_structure` | string | strand, whole_school, mixed, unknown |
| `program_kind` | string |  |
| `reported_model_label` | string / null |  |
| `evidence_period_raw` | string / null |  |
| `verification_status` | string | documented, district_policy_only, provisional, unverified, continuity_review, published_plan_not_observed, metadata_only, not_reported |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |
| `notes` | string / null |  |

## allocation_schedules

Preserve a policy even when language-specific numeric shares cannot safely be attributed.

Path: `data/curated/program_history/allocation_schedules.csv`. Primary key: `schedule_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `schedule_id` | string |  |
| `school_id` | string | schools.school_id |
| `site_id` | string / null | program_sites.site_id |
| `school_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `entry_cohort_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `grade_scope` | string |  |
| `reported_model_label` | string / null |  |
| `percentage_basis` | string |  |
| `schedule_status` | string | reported_policy_requires_review, documented_plan, observed_schedule |
| `evidence_review_status` | string / null |  |
| `grade_support_status` | string / null | NOT_REVIEWED, DISTRICT_GRADE_BAND_MODEL, CAMPUS_GRADE_BAND_MODEL, EXPLICIT_GRADE, DISTRICT_ENTRY_GRADE_MODEL, MODEL_LABEL_MINUTES_DIFFER, EARLIER_GRADE_PROXY_NOT_TARGET_QUANTIFIED, SOURCE_DOES_NOT_SUPPORT_PROGRAM_GRADE_PERIOD, UNRECOVERED, PUBLISHED_MODEL_ONLY, CONFLICTING_SOURCE_CLAIMS, SOURCE_GRADE_SCOPE_NOT_REPORTED, COMPOSITE_TRACK_SCOPE_UNRESOLVED |
| `evidence_period_raw` | string / null |  |
| `tested_cohort_exposure` | string | not_established, verified |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |
| `notes` | string / null |  |

## instructional_allocations

One row per named language in a documented schedule; no fixed Spanish/English columns.

Path: `data/curated/program_history/instructional_allocations.csv`. Primary key: `allocation_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `allocation_id` | string |  |
| `schedule_id` | string | allocation_schedules.schedule_id |
| `language_name` | string |  |
| `language_code` | string / null |  |
| `instruction_share_pct` | number | minimum 0; maximum 100 |
| `evidence_type` | string | documented_plan, observed_schedule |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |

Additional unique keys:

- `schedule_id, language_name`

## evidence_claims

Attribute-specific evidence; a confirmed school does not confirm its language allocation.

Path: `data/curated/sources/evidence_claims.csv`. Primary key: `claim_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `claim_id` | string |  |
| `entity_type` | string | school, district, program, site, schedule |
| `entity_id` | string |  |
| `attribute` | string |  |
| `reported_value` | string / null |  |
| `valid_from_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `valid_to_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `grade_scope` | string |  |
| `entry_cohort_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `verification_status` | string | documented, district_policy_only, provisional, unverified, continuity_review, published_plan_not_observed, metadata_only, not_reported |
| `confirmation_method` | string |  |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |
| `import_source_id` | string / null | sources.source_id |
| `notes` | string / null |  |
| `evidence_period_raw` | string / null |  |

## reporting_units

The actual source aggregation unit, not an inferred instructional track.

Path: `data/curated/registry/reporting_units.csv`. Primary key: `reporting_unit_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `reporting_unit_id` | string |  |
| `state_code` | string | states.state_code |
| `entity_type` | string | school, district, state |
| `entity_id` | string |  |
| `program_reporting_group` | string / null |  |
| `source_unit_label` | string |  |
| `reporting_scope` | string | entity_wide, program_reporting_group |

## populations

Preserve source subgroup definitions and the DL/EL distinction.

Path: `data/curated/assessments/population_definitions.csv`. Primary key: `population_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `population_id` | string |  |
| `state_code` | string | states.state_code |
| `population_label` | string |  |
| `population_scope` | string | all_students, current_el, former_el, dl_all_participants, dl_current_el_only, dl_non_el, mixed_bilingual_services, not_reported, non_el |
| `native_group_type` | string / null |  |
| `native_group_label` | string |  |
| `definition` | string |  |
| `source_id` | string | sources.source_id |

## assessments

Instrument and scoring definitions; source-release vintage is recorded separately.

Path: `data/curated/assessments/assessment_definitions.csv`. Primary key: `assessment_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `assessment_id` | string |  |
| `state_code` | string / null | states.state_code |
| `assessment_name` | string |  |
| `assessment_family` | string |  |
| `construct` | string | academic_achievement, english_language_proficiency, partner_language_proficiency, derived_standardized_achievement, not_reported |
| `assessment_version` | string |  |
| `scale_description` | string |  |
| `valid_from_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `valid_to_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `source_id` | string | sources.source_id |

## metrics

Metric units and population/denominator meaning; proficiency percentages are not interchangeable across states.

Path: `data/curated/assessments/metric_definitions.csv`. Primary key: `metric_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `metric_id` | string |  |
| `metric_name` | string |  |
| `metric_family` | string | academic_proficiency, assessment_count, demographic_count, demographic_rate, english_proficiency, el_exit_rate, el_exit_count, seda_achievement, seda_growth, partner_proficiency |
| `value_unit` | string | percent, count, scale_score, standard_deviation, grade_equivalent, other |
| `denominator_definition` | string |  |
| `comparability_group` | string |  |
| `notes` | string / null |  |

## dl_participant_outcomes

One observation per published unit/period/grade/population/instrument/administration/language/metric/source vintage.

Path: `data/curated/dl_participant_outcomes/observations.csv`. Primary key: `observation_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `observation_id` | string |  |
| `reporting_unit_id` | string | reporting_units.reporting_unit_id |
| `school_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `period_start` | string / null |  |
| `period_end` | string / null |  |
| `grade_scope` | string |  |
| `entry_cohort_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `cohort_status` | string | repeated_cross_section, identified_cohort, not_reported |
| `population_id` | string | populations.population_id |
| `assessment_id` | string / null | assessments.assessment_id |
| `administration` | string |  |
| `subject` | string |  |
| `domain` | string |  |
| `assessed_language` | string |  |
| `metric_id` | string | metrics.metric_id |
| `value_raw` | string / null |  |
| `value_numeric` | number / null |  |
| `value_status` | string | observed, derived, bounded, suppressed, not_reported, not_applicable |
| `value_lower_bound` | number / null |  |
| `value_upper_bound` | number / null |  |
| `source_value_unit` | string |  |
| `numerator` | number / null | minimum 0 |
| `denominator` | number / null | minimum 0 |
| `denominator_status` | string | reported, derived_matching_population, not_reported, suppressed, not_applicable |
| `tested_n` | number / null | minimum 0 |
| `expected_n` | number / null | minimum 0 |
| `standard_error` | number / null | minimum 0 |
| `source_population_raw` | string |  |
| `source_grade_raw` | string |  |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |
| `derivation_method` | string / null |  |
| `notes` | string / null |  |
| `cohort_label` | string / null |  |
| `period_basis` | string | school_year, calendar_year, calendar_date, not_reported |

Additional unique keys:

- `reporting_unit_id, school_year, period_start, period_end, grade_scope, entry_cohort_year, population_id, assessment_id, administration, subject, domain, assessed_language, metric_id, source_id, cohort_status, cohort_label, period_basis`

## state_assessments

One observation per published unit/period/grade/population/instrument/administration/language/metric/source vintage.

Path: `data/curated/state_assessments/observations.csv`. Primary key: `observation_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `observation_id` | string |  |
| `reporting_unit_id` | string | reporting_units.reporting_unit_id |
| `school_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `period_start` | string / null |  |
| `period_end` | string / null |  |
| `grade_scope` | string |  |
| `entry_cohort_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `cohort_status` | string | repeated_cross_section, identified_cohort, not_reported |
| `population_id` | string | populations.population_id |
| `assessment_id` | string / null | assessments.assessment_id |
| `administration` | string |  |
| `subject` | string |  |
| `domain` | string |  |
| `assessed_language` | string |  |
| `metric_id` | string | metrics.metric_id |
| `value_raw` | string / null |  |
| `value_numeric` | number / null |  |
| `value_status` | string | observed, derived, bounded, suppressed, not_reported, not_applicable |
| `value_lower_bound` | number / null |  |
| `value_upper_bound` | number / null |  |
| `source_value_unit` | string |  |
| `numerator` | number / null | minimum 0 |
| `denominator` | number / null | minimum 0 |
| `denominator_status` | string | reported, derived_matching_population, not_reported, suppressed, not_applicable |
| `tested_n` | number / null | minimum 0 |
| `expected_n` | number / null | minimum 0 |
| `standard_error` | number / null | minimum 0 |
| `source_population_raw` | string |  |
| `source_grade_raw` | string |  |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |
| `derivation_method` | string / null |  |
| `notes` | string / null |  |
| `cohort_label` | string / null |  |
| `period_basis` | string | school_year, calendar_year, calendar_date, not_reported |

Additional unique keys:

- `reporting_unit_id, school_year, period_start, period_end, grade_scope, entry_cohort_year, population_id, assessment_id, administration, subject, domain, assessed_language, metric_id, source_id, cohort_status, cohort_label, period_basis`

## demographics

One observation per published unit/period/grade/population/instrument/administration/language/metric/source vintage.

Path: `data/curated/demographics/observations.csv`. Primary key: `observation_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `observation_id` | string |  |
| `reporting_unit_id` | string | reporting_units.reporting_unit_id |
| `school_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `period_start` | string / null |  |
| `period_end` | string / null |  |
| `grade_scope` | string |  |
| `entry_cohort_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `cohort_status` | string | repeated_cross_section, identified_cohort, not_reported |
| `population_id` | string | populations.population_id |
| `assessment_id` | string / null | assessments.assessment_id |
| `administration` | string |  |
| `subject` | string |  |
| `domain` | string |  |
| `assessed_language` | string |  |
| `metric_id` | string | metrics.metric_id |
| `value_raw` | string / null |  |
| `value_numeric` | number / null |  |
| `value_status` | string | observed, derived, bounded, suppressed, not_reported, not_applicable |
| `value_lower_bound` | number / null |  |
| `value_upper_bound` | number / null |  |
| `source_value_unit` | string |  |
| `numerator` | number / null | minimum 0 |
| `denominator` | number / null | minimum 0 |
| `denominator_status` | string | reported, derived_matching_population, not_reported, suppressed, not_applicable |
| `tested_n` | number / null | minimum 0 |
| `expected_n` | number / null | minimum 0 |
| `standard_error` | number / null | minimum 0 |
| `source_population_raw` | string |  |
| `source_grade_raw` | string |  |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |
| `derivation_method` | string / null |  |
| `notes` | string / null |  |
| `cohort_label` | string / null |  |
| `period_basis` | string | school_year, calendar_year, calendar_date, not_reported |

Additional unique keys:

- `reporting_unit_id, school_year, period_start, period_end, grade_scope, entry_cohort_year, population_id, assessment_id, administration, subject, domain, assessed_language, metric_id, source_id, cohort_status, cohort_label, period_basis`

## el_proficiency

One observation per published unit/period/grade/population/instrument/administration/language/metric/source vintage.

Path: `data/curated/el_proficiency/observations.csv`. Primary key: `observation_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `observation_id` | string |  |
| `reporting_unit_id` | string | reporting_units.reporting_unit_id |
| `school_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `period_start` | string / null |  |
| `period_end` | string / null |  |
| `grade_scope` | string |  |
| `entry_cohort_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `cohort_status` | string | repeated_cross_section, identified_cohort, not_reported |
| `population_id` | string | populations.population_id |
| `assessment_id` | string / null | assessments.assessment_id |
| `administration` | string |  |
| `subject` | string |  |
| `domain` | string |  |
| `assessed_language` | string |  |
| `metric_id` | string | metrics.metric_id |
| `value_raw` | string / null |  |
| `value_numeric` | number / null |  |
| `value_status` | string | observed, derived, bounded, suppressed, not_reported, not_applicable |
| `value_lower_bound` | number / null |  |
| `value_upper_bound` | number / null |  |
| `source_value_unit` | string |  |
| `numerator` | number / null | minimum 0 |
| `denominator` | number / null | minimum 0 |
| `denominator_status` | string | reported, derived_matching_population, not_reported, suppressed, not_applicable |
| `tested_n` | number / null | minimum 0 |
| `expected_n` | number / null | minimum 0 |
| `standard_error` | number / null | minimum 0 |
| `source_population_raw` | string |  |
| `source_grade_raw` | string |  |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |
| `derivation_method` | string / null |  |
| `notes` | string / null |  |
| `cohort_label` | string / null |  |
| `period_basis` | string | school_year, calendar_year, calendar_date, not_reported |

Additional unique keys:

- `reporting_unit_id, school_year, period_start, period_end, grade_scope, entry_cohort_year, population_id, assessment_id, administration, subject, domain, assessed_language, metric_id, source_id, cohort_status, cohort_label, period_basis`

## el_exit_outcomes

One observation per published unit/period/grade/population/instrument/administration/language/metric/source vintage.

Path: `data/curated/el_exit_outcomes/observations.csv`. Primary key: `observation_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `observation_id` | string |  |
| `reporting_unit_id` | string | reporting_units.reporting_unit_id |
| `school_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `period_start` | string / null |  |
| `period_end` | string / null |  |
| `grade_scope` | string |  |
| `entry_cohort_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `cohort_status` | string | repeated_cross_section, identified_cohort, not_reported |
| `population_id` | string | populations.population_id |
| `assessment_id` | string / null | assessments.assessment_id |
| `administration` | string |  |
| `subject` | string |  |
| `domain` | string |  |
| `assessed_language` | string |  |
| `metric_id` | string | metrics.metric_id |
| `value_raw` | string / null |  |
| `value_numeric` | number / null |  |
| `value_status` | string | observed, derived, bounded, suppressed, not_reported, not_applicable |
| `value_lower_bound` | number / null |  |
| `value_upper_bound` | number / null |  |
| `source_value_unit` | string |  |
| `numerator` | number / null | minimum 0 |
| `denominator` | number / null | minimum 0 |
| `denominator_status` | string | reported, derived_matching_population, not_reported, suppressed, not_applicable |
| `tested_n` | number / null | minimum 0 |
| `expected_n` | number / null | minimum 0 |
| `standard_error` | number / null | minimum 0 |
| `source_population_raw` | string |  |
| `source_grade_raw` | string |  |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |
| `derivation_method` | string / null |  |
| `notes` | string / null |  |
| `cohort_label` | string / null |  |
| `period_basis` | string | school_year, calendar_year, calendar_date, not_reported |

Additional unique keys:

- `reporting_unit_id, school_year, period_start, period_end, grade_scope, entry_cohort_year, population_id, assessment_id, administration, subject, domain, assessed_language, metric_id, source_id, cohort_status, cohort_label, period_basis`

## seda

One observation per published unit/period/grade/population/instrument/administration/language/metric/source vintage.

Path: `data/curated/seda/observations.csv`. Primary key: `observation_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `observation_id` | string |  |
| `reporting_unit_id` | string | reporting_units.reporting_unit_id |
| `school_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `period_start` | string / null |  |
| `period_end` | string / null |  |
| `grade_scope` | string |  |
| `entry_cohort_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `cohort_status` | string | repeated_cross_section, identified_cohort, not_reported |
| `population_id` | string | populations.population_id |
| `assessment_id` | string / null | assessments.assessment_id |
| `administration` | string |  |
| `subject` | string |  |
| `domain` | string |  |
| `assessed_language` | string |  |
| `metric_id` | string | metrics.metric_id |
| `value_raw` | string / null |  |
| `value_numeric` | number / null |  |
| `value_status` | string | observed, derived, bounded, suppressed, not_reported, not_applicable |
| `value_lower_bound` | number / null |  |
| `value_upper_bound` | number / null |  |
| `source_value_unit` | string |  |
| `numerator` | number / null | minimum 0 |
| `denominator` | number / null | minimum 0 |
| `denominator_status` | string | reported, derived_matching_population, not_reported, suppressed, not_applicable |
| `tested_n` | number / null | minimum 0 |
| `expected_n` | number / null | minimum 0 |
| `standard_error` | number / null | minimum 0 |
| `source_population_raw` | string |  |
| `source_grade_raw` | string |  |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |
| `derivation_method` | string / null |  |
| `notes` | string / null |  |
| `cohort_label` | string / null |  |
| `period_basis` | string | school_year, calendar_year, calendar_date, not_reported |

Additional unique keys:

- `reporting_unit_id, school_year, period_start, period_end, grade_scope, entry_cohort_year, population_id, assessment_id, administration, subject, domain, assessed_language, metric_id, source_id, cohort_status, cohort_label, period_basis`

## observation_program_links

Separate associations never duplicate or allocate an observation to a language track.

Path: `data/curated/links/observation_program_links.csv`. Primary key: `link_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `link_id` | string |  |
| `observation_table` | string | dl_participant_outcomes, state_assessments, demographics, el_proficiency, el_exit_outcomes, seda |
| `observation_id` | string |  |
| `site_id` | string | program_sites.site_id |
| `attribution_status` | string | direct_program, combined_reporting_group, schoolwide_context, unresolved |
| `evidence_source_id` | string | sources.source_id |
| `notes` | string / null |  |
| `attribution_basis` | string | explicit_program_identifier, explicit_single_track_population, context_only, combined_source_group, unresolved |

## el_exit_policies

Dated exit rules, including domain and non-test requirements; not actual exit outcomes.

Path: `data/curated/el_exit/exit_policies.csv`. Primary key: `policy_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `policy_id` | string |  |
| `state_code` | string | states.state_code |
| `assessment_id` | string | assessments.assessment_id |
| `valid_from_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `valid_to_year` | string / null | pattern: ^\d{4}-\d{2}$ |
| `grade_scope` | string |  |
| `overall_cut_score` | number / null |  |
| `domain_cut_scores_json` | string |  |
| `additional_requirements_json` | string |  |
| `policy_status` | string | documented, provisional |
| `source_id` | string | sources.source_id |
| `source_locator` | string |  |
| `notes` | string / null |  |

## coverage

State/year/layer collection status; absence in the pilot never means no public data exist.

Path: `data/curated/coverage/state_year_layer_coverage.csv`. Primary key: `coverage_id`.

| Column | Type | Allowed values / reference |
|---|---|---|
| `coverage_id` | string |  |
| `state_code` | string | states.state_code |
| `school_year` | string | pattern: ^\d{4}-\d{2}$ |
| `layer` | string | inventory, dl_participants, state_assessments, demographics, el_proficiency, el_exit_policy, el_exit_outcomes, seda |
| `collection_status` | string | not_collected, source_identified, pilot_partial, collected, searched_not_found, not_publicly_reported |
| `smallest_available_unit` | string |  |
| `grade_scope` | string |  |
| `population_scope` | string |  |
| `source_id` | string / null | sources.source_id |
| `last_reviewed_date` | string / null |  |
| `notes` | string / null |  |
| `availability_basis` | string | collected_source_scope, source_availability_review, not_established |

Additional unique keys:

- `state_code, school_year, layer`
