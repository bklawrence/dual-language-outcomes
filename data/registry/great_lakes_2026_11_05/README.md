# Wisconsin, Michigan, Illinois and Indiana structural inventory

Reviewed November 5, 2026: **306 programme records at 294 provisional school/campus units**. Illinois expands an existing seed; its original identities, rows and claims remain intact. See [findings and coverage](../../../docs/status/GREAT_LAKES_2026_11_05.md).

| State | School/campus CSV | Programme/language-strand CSV | Reviewed input |
|---|---|---|---|
| WI | [wi_schools.csv](wi_schools.csv) | [wi_programmes.csv](wi_programmes.csv) | [wi_programmes.json](wi_programmes.json) |
| MI | [mi_schools.csv](mi_schools.csv) | [mi_programmes.csv](mi_programmes.csv) | [mi_programmes.json](mi_programmes.json) |
| IL | [il_schools.csv](il_schools.csv) | [il_programmes.csv](il_programmes.csv) | [il_programmes.json](il_programmes.json) |
| IN | [in_schools.csv](in_schools.csv) | [in_programmes.csv](in_programmes.csv) | [in_programmes.json](in_programmes.json) |

JSON files are reviewed build inputs. CSVs are generated offline and checked in for browsing. School CSVs have one row per research unit; programme CSVs retain distinct language or explicitly distinct population strands. These are provisional research units, not verified unique NCES school counts. Academy of the Americas and Global Prep have flagged campus identity questions.

**2025–26 is the operation reference year.** Actual source dates remain separate. Filter `confirmed_qualifying_2025_26` in school CSVs, or operation and eligibility fields in programme CSVs, before reference-year analysis. Candidates, historical closures and future starts are intentionally retained. Original Illinois seed screening fields are historical claims; current reviewed operation is in status history and the new CSV fields.

Elementary coverage includes any K–5 grade, including K–8, grades 3–5 and 5–6. Secondary-only continuations remain recorded and excluded from that denominator. Wisconsin K3/K4 mean preschool; K5 means five-year-old kindergarten. Bull and Chicago’s Thomas preschool are screening records, not K–12 programme rows.

[sources.csv](sources.csv) indexes 177 complete public HTTP snapshots, retrieval timestamps and SHA-256 hashes. Raw bytes and metadata are under `data/raw/great_lakes_2026_11_05/`. [retrieval_log.csv](retrieval_log.csv) retains unsuccessful and unselected retrievals. Search pages and HTTP status alone are not programme evidence. Text extractions support review; the U-46 roster has a labelled visual transcription of PDF page 10. Its older feeder diagram is not treated as the new host list.

`reviews.json` records bounded continuity checks. `identity_decisions.json` documents Illinois identity reuse, and `legacy_illinois_rows.json` freezes original canonical rows for preservation checks. `*_screening.json` retains unresolved district/school discovery and language-class or preschool exclusions. Supporting-source references are included in portable build inputs.

Published instructional policies are not observed pupil exposure. Pupil-background percentages, literacy-only ratios, qualitative full immersion and English specials do not supply an unreported total-day share. Two Lawrence Township ELC allocations retain explicit same-programme inference flags and named donor programme IDs. Indigenous academic medium, public funding and elective-language provision are assessed separately.

New proficiency collection is deferred. Earlier research, 78 dated reports and all 12 assessment/context/EL/SEDA outputs are preserved.
