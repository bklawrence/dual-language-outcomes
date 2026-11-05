# Texas model review after the matching-programme rule

November 5, 2026, review round 1. The user's rule permits assigning an existing model to other schools in the same district whose programme type and language match. These assignments are recorded as research classifications with their inference basis, not as independently observed timetables.

This review adds model information for **22 more campuses**. Combined with the first pass's 69, **91 of the original 598 missing-model campuses** now have a model classification; **507 remain unclassified**. There are 29 programme assignments across 25 campuses, including three campuses that already had a model on another strand or source record.

## Decisions

| Case | Result |
|---|---|
| Denton | The explicit user instruction assigns **50/50 to all four recorded elementary two-way strands**, including Borman. Like one-way Spanish/English candidates inherit the existing Rivera 50/50 label under the general matching rule. Seven formerly unfilled campuses now have model information. |
| Red Oak | **One-way confirmed** at Wooden and Schupmann. Overall allocation and kindergarten allocation remain **unknown**. Its literacy percentages do not establish either value. |
| Irving | T Haley's Spanish/English two-way programme inherits **50/50**; four matching historical one-way candidates inherit the existing **80/20** label. The one-way label is not borrowed from a two-way programme. |
| Elgin Intermediate | The matching one-way and two-way primary-grade continuation components inherit **50/50** separately. This assigns neither a secondary timetable nor a kindergarten allocation. |
| Mount Pleasant / Wallace | The **two-way** continuation strand inherits the named elementary Spanish/English **50/50** model. The separate one-way strand remains unclassified. |
| Judson | The explicit **50/50 programme label** is assigned to the three matching two-way Spanish/English candidates. The student-composition explanation is not treated as measured instructional time. |
| Longview | The literal reported endpoint is **90% English / 10% Spanish by grade 5**. It is retained with the source's transitional wording and a programme-definition flag. It is not classified as a 90% Spanish entry model; K and earlier-grade allocations remain unknown. |
| Austin | Held: Spanish programmes have differing model labels; Mandarin is explicitly described as either 80/20 or 50/50. Type and language do not identify one model. No model is transferred between Spanish, Mandarin and Vietnamese strands. |
| Tomball, Ector, SCUC / Wilder | Held where target and donor programme types differ. Possible programme changes and mismatched source periods remain visible. |
| Grand Prairie, Goose Creek | Held: the checked documents give literacy or subject-language plans without a numerical overall model to inherit. |
| Midlothian | The existing **70/30** label remains; language ordering and K allocation remain unresolved. |

The complete [case outcomes](../../data/reports/texas_allocation_review_2026_11_05_case_outcomes.csv), [programme assignments](../../data/reports/texas_allocation_review_2026_11_05_assignments.csv), [current outcomes for all 598 campuses](../../data/reports/texas_allocation_review_2026_11_05_598_after_review.csv) and [readable review report](../../data/reports/texas_allocation_review_2026_11_05_outcomes.md) retain the basis for every decision.

## Inference and source quality

The rule is applied within a district, separately by one-way/two-way type and instructional-language family. Known language differences block a match. Where the campus language is missing but the district programme family supports Spanish/English, that language match is explicitly marked as inferred; it does not overwrite the programme-language observations. Conflicting plausible models within the same family remain unresolved.

Two sets of classifications inherit **existing, unreviewed legacy labels**: Denton's one-way Rivera 50/50 label and Irving's one-way 80/20 labels. Their original citations currently return 404. The saved legacy claims remain the donor evidence; their `NOT_REVIEWED` flags and citation failures are retained. These are user-authorized inferences from existing classifications, not newly confirmed primary-source facts. They can be excluded by filtering `classification_basis`, `legacy_donor_review_status` and the model-evidence flags.

The four Denton two-way assignments preserve the user's explicit instruction as their authority, with the district's public English/Spanish programme description as context. Longview's five records preserve a literal district-source endpoint. The other 20 programme assignments are marked `USER_AUTHORIZED_SAME_PROGRAMME_INFERENCE`. All 29 use `PUBLISHED_MODEL_ONLY`, have no assigned operating year and do not establish tested-cohort exposure. No named-language time-share observations were created.

## Coverage and preserved history

Across all retained source periods, Texas elementary model availability becomes **888/1,420 (62.5%)**, up from 866/1,420 (61.0%) after the first pass. The older reference working-set view becomes **875/1,420 (61.6%)**. These figures include inferred classifications; the new state and school views identify inference separately. They remain inventory coverage figures, not statewide census estimates, contemporaneous timetables or evidence that a historical programme still operates.

The current [state coverage](../../data/reports/elementary_allocation_coverage_2026_11_05_reviewed_by_state.csv), [school evidence](../../data/reports/elementary_allocation_coverage_2026_11_05_reviewed_by_school.csv) and [national programme view](../../data/reports/structural_inventory_2026_11_05_reviewed_program_view.csv) use a separate reviewed edition. The first-pass November 5 reports, 598-campus cohort and original review questions are preserved with checksums. Later resolution claims supersede the earlier pending decision requests without deleting the evidence history.

Programme identities, historical population categories, earlier source observations and the assessment pilots are preserved. The phase remains structural collection across all 50 states; no additional proficiency, EL-exit or SEDA collection is included.

Validation passes: all **144 unit tests**, national schema/provenance checks, all seven historical and structural source audits, and matching DuckDB/Parquet row counts for all 28 tables. Earlier checkpoint hashes and local documentation links also pass.
