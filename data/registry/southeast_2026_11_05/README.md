# Florida / Georgia / South Carolina / North Carolina / Tennessee

Reviewed structural inputs, November 5, 2026, with a 2025–26 operation reference and separate source vintages. [Findings and interpretation](../../../docs/status/SOUTHEAST_2026_11_05.md).

| State | Programme CSV | School/campus CSV | Screening CSV |
|---|---|---|---|
| Florida | [fl_programmes.csv](fl_programmes.csv) | [fl_schools.csv](fl_schools.csv) | [fl_screening.csv](fl_screening.csv) |
| Georgia | [ga_programmes.csv](ga_programmes.csv) | [ga_schools.csv](ga_schools.csv) | [ga_screening.csv](ga_screening.csv) |
| South Carolina | [sc_programmes.csv](sc_programmes.csv) | [sc_schools.csv](sc_schools.csv) | [sc_screening.csv](sc_screening.csv) |
| North Carolina | [nc_programmes.csv](nc_programmes.csv) | [nc_schools.csv](nc_schools.csv) | [nc_screening.csv](nc_screening.csv) |
| Tennessee | [tn_programmes.csv](tn_programmes.csv) | [tn_schools.csv](tn_schools.csv) | [tn_screening.csv](tn_screening.csv) |

Programme rows are language strands or source-specific programme evidence groups, not separate schools. School rows combine these at provisional reporting units. Future starts, private/public-funding candidates, historical hosts and secondary continuations remain visible; filter the reference-status/eligibility fields explicitly.

The reviewed JSON inputs, not the CSV review exports, drive the offline build. Every observation, allocation and event cites a key in [sources.csv](sources.csv) / [sources.json](sources.json). The source index links saved HTTP responses and metadata with URLs, retrieval timestamps and checksums. The folder/review date is the session research date; acquisition metadata retains the exact UTC retrieval timestamps. Readable text is under [extractions](extractions); [retrieval_log.csv](retrieval_log.csv) includes unsuccessful acquisitions and search leads, which are not primary programme proof.

[roster_reconciliation.json](extractions/roster_reconciliation.json) links original/reviewed source rows to programme and school keys or a screening disposition. Individual `*_rows.csv` / JSON files preserve the NC state directory (316 original rows and fields), GA state appendix (87 schools / 93 language-school cells), both Broward rosters, Palm Beach’s actual named list, Miami-Dade’s three programme-format lists, and Harnett’s 14 historical hosts. Original PDF/HTML captures remain authoritative for manually selected table fields; a `raw` object in a reviewed PDF selection is the selected row transcription, not a replacement for the complete original response.

[grade_context_decisions.json](grade_context_decisions.json) documents 473 exact normalized school and reviewed reporting-group matches to 2024–25 CCD. [Unmatched grade cases](unmatched_grade_context.json) retain the remaining source proxies; these are not rejected programme records or durable identifier mappings.

[reviews.json](reviews.json) documents bounded continuity decisions. [Review cases](../../reports/southeast_2026_11_05_review_cases.csv) distinguish unresolved programme language, rollout dates, model inference, policy vintages and funding. [Backlog](../../reports/southeast_2026_11_05_backlog.csv) also includes missing allocation, one-/two-way and strand/whole-school fields.

One public Montessori website snapshot embedded a map-service credential in page configuration. Its saved `_redacted.html` variant changes only that configuration value. [source_redactions.json](source_redactions.json) and its response metadata retain original-acquisition and saved-response hashes and verify visible/embedded programme text was unchanged. The unredacted response is not redistributed in Git.

Coverage is model information across cited periods, not current statewide completeness, exact K exposure, complete strand coverage or assumed student-level exposure. Proficiency, demographics, EL-exit and SEDA collection remains deferred.
