# Nine-district structural gap pilot

Research date: November 6, 2026. Reference: 2025–26. This pass covers Austin, Garland and Alief in Texas; Union County, Buncombe and Charlotte-Mecklenburg in North Carolina; and Albuquerque, Las Cruces and Gadsden in New Mexico.

The fixed comparison contains **348 existing programme-site evidence groups across 290 school research identities**, including **222 elementary-containing school identities**. It includes unresolved candidates and secondary continuations. These are research units, not verified counts of distinct programmes or district censuses. No school/programme identities were added, removed or merged.

The [district comparison](../../reports/structural_gaps_pilot_2026_11_06_by_district.csv), [school comparison](../../reports/structural_gaps_pilot_2026_11_06_school_comparison.csv), [field comparison](../../reports/structural_gaps_pilot_2026_11_06_field_comparison.csv) and [completeness table](../../reports/structural_gaps_pilot_2026_11_06_completeness.csv) distinguish genuinely new availability from verification or additional detail. All selections in this comparison use 2025–26. Texas's **baseline target-year selections** are compared; its 2023–24 source-vintage working denominator is not relabelled as a 2025–26 roster.

| Measure in the fixed pilot sample | Before | After |
|---|---:|---:|
| Elementary school identities with a numerical primary-grade model | 37 / 222 (16.7%) | 59 / 222 (26.6%) |
| Programme-site language classifications resolved | 94 / 348 | 157 / 348 |
| Programme-site one-way/two-way classifications resolved | 72 / 348 | 98 / 348 |
| Programme-site whole-school/strand classifications resolved | 72 / 348 | 73 / 348 |
| Programme-site grade scopes resolved | 83 / 348 | 108 / 348 |

There are **257 appended observations covering 93 school identities**. This is not 257 newly filled gaps. In particular, Alief's 18 one-way campuses already had published model labels in the 2025–26 selections. The new work supports programme languages, type, grade scope and named-language policy shares without claiming new model availability there. A model at some primary grade does not establish an entry-kindergarten ratio or every language strand's model.

The 22 newly covered elementary school identities are in Union County (15), Garland (2), Charlotte-Mecklenburg (1), Albuquerque (2) and Las Cruces (2). Whole-school/strand documentation yielded only one newly resolved programme classification. The next pass for that variable should seek admissions rules, programme-specific enrollment guides, implementation plans and board attachments that state who participates.

## Evidence and decisions

- [observations.json](observations.json): reviewed values, original research identities, quotations, source chains, actual source periods, reference applicability and inference methods. [CSV export](../../reports/structural_gaps_pilot_2026_11_06_observations.csv).
- [sources.json](sources.json): 69 archived receipts, comprising 68 new captures and one reused state-report archive. [Source CSV](../../reports/structural_gaps_pilot_2026_11_06_sources.csv) distinguishes sources supporting observations from documents screened without assigning a classification.
- [extractions](extractions/): reviewed text and structured page nodes. Alief's campus roster lives in button nodes in a Nuxt payload; those names are preserved rather than lost when only HTML paragraphs are extracted. Doña Ana's original diagram is retained with a separately labelled manual transcription.
- [district_reviews.json](district_reviews.json): all nine bounded reviews, including Gadsden's unresolved result.
- [review_cases.json](review_cases.json) and [review-case CSV](../../reports/structural_gaps_pilot_2026_11_06_review_cases.csv): nine retained source, date or programme-scope questions.
- [source_attempts.json](source_attempts.json): 119 public HTTP attempts, including discovery searches and unusable responses. Search results are discovery leads, not policy evidence. Effort is reported as source counts; researcher-hours were not timed and are not estimated.
- [baseline_programme_records.json](baseline_programme_records.json) and [preservation.json](preservation.json): the fixed comparison identities and preservation receipts.

Original response bytes are retained under [data/raw/structural_gaps_pilot_2026_11_06](../../raw/structural_gaps_pilot_2026_11_06/). The New Mexico state PDF's official endpoint returned HTTP 202 without usable content; this pass reuses the repository's complete ERIC archive of the same 2024–25 annual report. No assessment results are extracted from it.

## Interpretation rules

The source observation year remains null when the source is undated. A separate earliest-reviewed-reference bound prevents an undated policy reviewed for 2025–26 from silently filling Texas's 2023–24 denominator. That bound is **not a policy start date**. Field selections, source scope and operation confirmations remain distinct. Continuity reviews use the user's existing rule; a later roster omission is not a closure finding.

Union County's explicitly all-Spanish core phases are normalized to **100/0 for core instruction**, with inference methods and excluded non-core time stated. Later 50/50 phases remain separate. The Mandarin programme's kindergarten ratio remains unquantified; its grades 4–5 have a published approximate half-day model. Shiloh Valley Elementary, which serves grades 3–5, receives no kindergarten schedule.

Alief's published 50/50 target is a programme policy, not observed pupil-specific minutes. Campus grade bands are clipped to the saved campus-grade context; elementary campuses do not acquire an intermediate-school grade. Las Cruces's Central and Doña Ana retain the 50/50 programme label, **native-language K–1 literacy exceptions**, and separate grades 2–5 policies. Non-core time with no language assignment is not allocated to either language.

Garland's September 5, 2025 district story confirms English/Vietnamese instruction at Hickman and Lister. The kindergarten 50/50 model is directly supported at Hickman and explicitly inferred for the matching Lister programme under the user's rule. It is not assigned to Spanish programmes. Vial's campus and magnet pages say 50/50; its conflicting EB summary remains a review case.

Albuquerque's published DLI definition explicitly names English plus a partner language. It is linked to the dated state report's school-specific Spanish DL flags for the same district programmes. Independent charter models and unresolved map/report mismatches are excluded from that linkage. English is not supplied by default, and generic Chinese is not automatically renamed Mandarin.

Coronado's sole-option programme supports whole-school classification and its K 80/20 to grade-5 50/50 progression. Reilly's earlier school-wide programme and its move to a Wooten strand in 2026–27 are distinct observations. Campus-only structural context is retained separately from language-specific programme assignments.

## Reproduction and preservation

`dl-outcomes build` appends the reviewed facts through `dl_outcomes.gap_pilot`; it performs no network collection. `dl-outcomes validate` and the structural report check validate the saved data. Run `python -m unittest discover -s tests -v` for the full suite, including reference bounds, scope, attribution, preservation and offline reproduction.

The frozen [national baseline v1](../../baselines/national_structural_v1/README.md), every original canonical structural row, all prior registered reports, and all twelve assessment/context outputs remain preserved. Changed derived reports receive a new path under `data/reports/structural_gaps_pilot_2026_11_06/revised/`; the current global report records the old-to-new path mapping. This pilot does not create a new national census, alter the v1 percentages or collect proficiency/EL-exit/SEDA observations.
