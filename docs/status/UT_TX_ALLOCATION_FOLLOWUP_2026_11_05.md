# Utah and Texas allocation follow-up

November 5, 2026. **Utah now has a recorded 50/50 model for all 127 identified elementary hosts.** A bounded Texas district-site pass added model information for **69 of the 598 campuses that previously had no allocation observation**. All decisions retain their sources, grade scope and evidence periods. New proficiency collection remains deferred.

## Utah: statewide elementary model and official roster

The user authorized assigning Utah elementary DLI programmes a common **50/50** model. [Davis School District's official description](https://www.davis.k12.ut.us/o/dsd/page/elementary-dual-language-immersion) corroborates the basis: “All state-sponsored schools with Dual Language Immersion programs are required to implement the fifty-fifty model.” This records the statewide model reported by an official district; it does not claim that a state statute or original regulation was independently located.

The assignment is explicitly marked `USER_AUTHORIZED_STATEWIDE_ELEMENTARY_MODEL`, with the instruction preserved in the migration configuration. It adds a campus-level policy schedule and retains all earlier evidence. It supplies neither an observed timetable nor an exact kindergarten/cohort allocation. Secondary-only hosts and the ten host records whose grades remain unresolved do not inherit the elementary assignment.

The [official 2026–27 USBE roster supplied by the user](https://schools.utah.gov/curr/dualimmersion/resources/DLI-Schools_2026-27.pdf) was downloaded again. Its SHA-256 matches the previously saved original exactly: `d0c835edcb0de3b7d2fdf2920d52e0c6f7477a266a787141ce3c05c144b6ae52`. **All 280 school rows and 348 language cells already map to retained research records**, so no new programme identities were invented. Multiple language strands remain separate. The reconciliation retains its 2026–27 roster year and includes secondary rows; it does not confirm operation in 2025–26. The broader inventory also retains older observations and provisional school-name variants, including the unresolved Cache Spring Creek alias question.

- [Elementary policy assignments](../../data/reports/ut_tx_allocation_followup_2026_11_05_utah_models.csv)
- [School/language roster reconciliation](../../data/reports/ut_tx_allocation_followup_2026_11_05_utah_roster_reconciliation.csv)

## Texas: results and remaining work

The fixed target cohort contains **598 campuses in 162 districts**. It is a subset of the 623 elementary schools missing usable numerical models in the previous audit: the other 25 had only an earlier-grade Aldine proxy and were outside this pass. The starting cohort and its baseline build are frozen with a checksum.

District roots, programme pages, public documents and sitemaps were checked, with **892 retrieval receipts** covering all 162 districts. This was a district-site pass, not an exhaustive historical search of every campus and board archive. Successful retrieval is not itself evidence of a model or of programme operation. Raw snapshots are saved for the cited decisions and review cases; other attempted pages retain retrieval receipts rather than full archives.

| Result among the original 598 campuses | Campuses |
|---|---:|
| Numerical model information added | 69 |
| Still without a numerical model | 529 |
| Of those unfilled campuses: included in user-review cases | 119 |
| Of those unfilled campuses: no quantified model established in checked sources | 323 |
| Of those unfilled campuses: retrieval or programme discovery incomplete | 80 |
| Of those unfilled campuses: a model was found but campus scope remains unresolved | 7 |

There are **29 accepted decisions across 27 districts** and **14 review cases**. One filled campus, Midlothian's J A Vitovsky, also has a review question: its 70/30 label is explicit, but the language order is not. The 119 figure counts only unfilled campuses in review; the complete review packet includes that additional campus.

Examples of accepted evidence include Spring Branch's explicit 50/50 policy for both one-way and two-way programmes (14 campuses); Alvin's dated 2026–27 one-way 50/50 plan (seven named receiving target campuses); Frisco's 80/20-to-50/50 progression; and Clear Creek's campus-specific brochures for McWhirter, Landolt and Stewart. A current model for one receiving campus was not assigned to its feeder schools or to every other language strand.

Important review cases include:

- **Austin (46 targets):** Spanish descriptions give subject-language assignments without total minutes; Mandarin uses either 80/20 or 50/50 without a campus-to-model mapping. Summitt's explicit Vietnamese 50/50 programme is outside this target cohort.
- **Ector County (19 targets):** a current linked early-exit transitional bilingual plan suggests a possible programme change to investigate. Cameron's separate DLI 50/50 description does not supply the missing model for those 19 campuses. Historical DLI categories are retained pending campus-specific change evidence.
- **Grand Prairie, Denton, Red Oak and Goose Creek:** useful literacy or subject-language plans do not establish a total-day ratio.
- **Irving and Tomball:** explicit two-way 50/50 policies do not establish the historical one-way models for the target campuses.
- **Longview:** its literal 90/10 *English/Spanish* grade-5 endpoint and transitional language require review before a familiar Spanish-dominant entry label can be assigned.
- **Judson:** its 50/50 label is accompanied by a student-composition explanation and a different current campus list; instructional-time and campus scope need clarification.

Student-language composition, generic legal minimums and pre-K-only percentages were not converted into whole-day elementary allocations. Programmes whose names or delivery may have changed retain the original reporting categories. No operating-status, instructional-language pair or tested-cohort exposure was inferred from a new model citation.

- [69 campus additions, with sources, grades and dates](../../data/reports/ut_tx_allocation_followup_2026_11_05_texas_added_models.csv)
- [All 598 target-campus outcomes](../../data/reports/ut_tx_allocation_followup_2026_11_05_texas_598_status.csv)
- [Questions, excerpts and options for user review](../../data/reports/ut_tx_allocation_followup_2026_11_05_texas_review.md), also available as a [CSV](../../data/reports/ut_tx_allocation_followup_2026_11_05_texas_review.csv)
- [District research receipts and limitations](../../data/registry/ut_tx_allocation_2026_11_05/texas_research_log.json)

## Updated elementary coverage

Elementary still means a school serving any K–5 grade, including 1–6, 3–6 and K–8; schools starting in grade 6 or later are excluded. These are model-availability figures within the retained inventories, not statewide census or observed exposure estimates.

| View | Utah before → after | Texas before → after |
|---|---|---|
| Reference working inventories | 25/33 (75.8%) → 33/33 (100%) | 797/1,420 (56.1%) → 853/1,420 (60.1%) |
| All recorded hosts with elementary grades | 31/127 (24.4%) → 127/127 (100%) | 797/1,420 (56.1%) → 866/1,420 (61.0%) |

Thirteen of the Texas additions are explicitly later than the 2023–24 TAPR reference set, so only the broader view counts those later plans. Undated sources retain unknown applicability; their presence in a reference working-set view is not confirmation of delivery in that reference year. South San Antonio's chart is retained with its conflicting page-year labels rather than choosing an operating year.

[Current state percentages](../../data/reports/elementary_allocation_coverage_2026_11_05_by_state.csv) and [school-level evidence](../../data/reports/elementary_allocation_coverage_2026_11_05_by_school.csv) expose both views. The November 4 dated audit files remain preserved as the earlier checkpoint.

## Reproduction and validation

The build uses saved source bytes and reviewed decisions offline. Some official district sites place programme text in JSON page payloads. The original HTTP response and derived text are retained separately; `python scripts/extract_embedded_page_text.py <snapshot>` reproduces that text without evaluating JavaScript. Browser-rendered archives are explicitly labelled as rendered DOM, rather than original HTTP response bodies. South San Antonio's image-based model records a researcher chart transcription separately from verbatim excerpts.

The additive migration keeps the 28-table schema, existing programme identities, earlier source observations and the 12 assessment/definition/link outputs unchanged. All **134 unit tests pass**, including elementary scope, roster equality, fixed target boundaries, review exclusions, dates, source checksums, derived text and absence of invented named-language shares. National validation and all seven structural/historical source audits pass. DuckDB and Parquet row counts match the manifest for all 28 tables; documentation links also resolve.
