# Oklahoma, Arkansas, Louisiana, Alabama and Mississippi

First structural pass reviewed November 5, 2026: **101 programme records across 86 provisional school/campus reporting units**, supported by **79 saved public sources**. Source publication dates, historical records and later starts remain separate from the **2025–26 operation reference**. See [findings and coverage](../../../docs/status/SOUTH_CENTRAL_2026_11_05.md).

| State | School CSV | Programme/strand CSV | Screening CSV | Reviewed programme input |
|---|---|---|---|---|
| OK | [ok_schools.csv](ok_schools.csv) | [ok_programmes.csv](ok_programmes.csv) | [ok_screening.csv](ok_screening.csv) | [ok_programmes.json](ok_programmes.json) |
| AR | [ar_schools.csv](ar_schools.csv) | [ar_programmes.csv](ar_programmes.csv) | [ar_screening.csv](ar_screening.csv) | [ar_programmes.json](ar_programmes.json) |
| LA | [la_schools.csv](la_schools.csv) | [la_programmes.csv](la_programmes.csv) | [la_screening.csv](la_screening.csv) | [la_programmes.json](la_programmes.json) |
| AL | [al_schools.csv](al_schools.csv) | [al_programmes.csv](al_programmes.csv) | [al_screening.csv](al_screening.csv) | [al_programmes.json](al_programmes.json) |
| MS | [ms_schools.csv](ms_schools.csv) | [ms_programmes.csv](ms_programmes.csv) | [ms_screening.csv](ms_screening.csv) | [ms_programmes.json](ms_programmes.json) |

Mississippi's school/programme CSVs intentionally contain headers only. Its directory and tribal-language checks are preserved in screening. No verified programme in this bounded pass does not establish statewide absence. Arkansas's two named programmes start in 2026–27 and remain outside the reference-year confirmed denominator.

School CSVs contain one row per provisional research unit. Programme CSVs separate explicitly different instructional languages and population strands. Filter `confirmed_qualifying_2025_26` in school CSVs or operation/eligibility fields in programme CSVs for reference-year analysis. Historical closures, funding candidates, unresolved school mappings and later starts remain available. The national programme view combines source periods for review and is not a contemporaneous configuration table.

Elementary coverage includes schools serving any K–5 grade, including K–8, 3–5 and 5–8. Secondary continuations remain recorded outside that denominator. [grade_context_decisions.json](grade_context_decisions.json) records 68 reviewed school-grade matches to saved **2024–25 CCD directory fields**. These are grade-context matches, not new durable school/programme identifier crosswalks or DL confirmations. Audubon and ISL campus reporting units retain explicit identity limits.

[sources.csv](sources.csv) and [sources.json](sources.json) index saved public HTTP responses, source URLs, retrieval times and SHA-256 hashes. Seventy-five preserve the original response bytes; four ISL HTML snapshots have an embedded map-service token redacted after GitHub push protection rejected the originals. Their metadata and [redaction receipts](source_redactions.json) retain both original-response and saved-redacted checksums. Visible and embedded programme text was checked unchanged. Saved bytes and metadata are under `data/raw/south_central_2026_11_05/`. [retrieval_log.csv](retrieval_log.csv) also records failed and unselected acquisitions. Some Lafayette Parish pages returned 503; search snippets remain discovery evidence, with no programme certification inferred from them.

Reviewed source selections are in [extractions](extractions/index.json): all 35 actual CODOFIL map objects, 24 state-certified site labels, 13 Calcasieu language/school rows and 11 Jefferson two-way Spanish hosts. CODOFIL's page headline says 36; its API returns 35 rows with `hasMore=false`. State certification is a separate selective roster. Native names, fields and campus aliases are retained, with no invented extra school. Glen View's linked JPEG has a labelled visual transcription.

Model labels and named-language shares are separate. Where a source publishes 60% French, a qualified 60/40 label retains the arithmetic remainder without creating unreported English-share rows. FLAIM's 60–70% range stays a range. Audubon's state 70% profile and lower-elementary 70–90% description keep their grade qualifications. LeBlanc's brochure filename contains 2025, but its explicit recruitment year and 60/40 diagram apply to 2026–27. None is measured pupil exposure.

The [review cases](../../reports/south_central_2026_11_05_review_cases.csv), [missing-field backlog](../../reports/south_central_2026_11_05_backlog.csv) and [change events](../../reports/south_central_2026_11_05_change_events.csv) retain school mapping, phaseout, range, funding and implementation questions. Previous identities, 114 dated reports, earlier registry inputs/exports and all 12 existing assessment/context/EL/SEDA outputs are preserved. New proficiency collection remains deferred.
