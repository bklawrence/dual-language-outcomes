# Six-state mid-Atlantic and Connecticut structural inventory

Reviewed November 5, 2026, against a **2025–26 operating reference**. The partial public-source inventory contains **433 programme records across 404 provisional school units**, including separately flagged plans, candidates and historical hosts. It is not a statewide census. There are **99 archived public documents** with URL, retrieval timestamp, content type and checksum metadata.

| State | School CSV | Programme CSV | Screening CSV |
|---|---|---|---|
| Pennsylvania | [pa_schools.csv](pa_schools.csv) | [pa_programmes.csv](pa_programmes.csv) | [pa_screening.csv](pa_screening.csv) |
| Maryland | [md_schools.csv](md_schools.csv) | [md_programmes.csv](md_programmes.csv) | [md_screening.csv](md_screening.csv) |
| Delaware | [de_schools.csv](de_schools.csv) | [de_programmes.csv](de_programmes.csv) | [de_screening.csv](de_screening.csv) |
| New Jersey | [nj_schools.csv](nj_schools.csv) | [nj_programmes.csv](nj_programmes.csv) | [nj_screening.csv](nj_screening.csv) |
| New York | [ny_schools.csv](ny_schools.csv) | [ny_programmes.csv](ny_programmes.csv) | [ny_screening.csv](ny_screening.csv) |
| Connecticut | [ct_schools.csv](ct_schools.csv) | [ct_programmes.csv](ct_programmes.csv) | [ct_screening.csv](ct_screening.csv) |

One school row is a provisional school unit; programme rows distinguish language strands. NYC general/special education rows are service observations within a school-language strand. These identities are not durable official programme IDs. Official NYC DBNs are retained in the national identifier table; CCD matches supply dated grade context only.

Coverage means a numerical language-allocation model is available for an elementary-containing school in the reviewed reference working set. Any K–5 grade qualifies, including grades 3–6 and 5–6. Grade 6+ only schools remain in the dataset and are excluded from this denominator. Undated and older explicit policies can support continuity after bounded review; they are not newly dated 2025–26 observations. Explicitly later policies remain separate. A model at one primary grade does not establish the full kindergarten progression, every strand, a complete bell schedule or individual/cohort exposure.

The JSON files are reviewed build inputs. [sources.csv](sources.csv) and [sources.json](sources.json) locate the 99 exact public snapshots in [the raw archive](../../raw/mid_atlantic_ct_2026_11_05/). [retrieval_log.csv](retrieval_log.csv) also records searches and failed acquisitions, which are not programme proof. No blocked page was bypassed or treated as verified content.

[Source-row reconciliations](extractions/roster_reconciliation.json) preserve twelve captured roster selections, including all 579 NYC source cells, all 57 Delaware map host rows and actual third-party directory cards. NYC/NJ third-party directory captures are first-page lead selections only; unverified cards are screening records. Original field values, ordinals, duplicates and programme links are preserved in companion JSON/CSV files.

[Grade-context decisions](grade_context_decisions.json) retain 390 reviewed unique normalized names or explicit aliases in the six 2024–25 CCD directories. [Dated school grade updates](school_grade_updates.json) override older Windham context for two hosts. Twelve hosts remain [unmatched](unmatched_grade_context.json), without fabricated identifiers. The Bridgeport handbook includes derived OCR; critical instructional percentages were visually verified on PDF page 7 (printed page 4).

See the [findings](../../../docs/status/MID_ATLANTIC_CT_2026_11_05.md), [review cases](../../reports/mid_atlantic_ct_2026_11_05_review_cases.csv), [backlog](../../reports/mid_atlantic_ct_2026_11_05_backlog.csv) and [dated changes](../../reports/mid_atlantic_ct_2026_11_05_change_events.csv). Proficiency and the other assessment layers remain deferred.

The [November 6 Herricks correction](extractions/herricks_2026_11_06_correction.json) preserves three district-linked public PDFs identified through user follow-up. The FAQ explicitly documents the one-way 50/50 elementary model at Denton Avenue and mentions September 2023 intake. A separate 2026–27 kindergarten flyer corroborates half-day instruction without backdating it. Formal secondary continuation stays separate. The parent presentation includes comparative Utah and future-assessment material; no outcome observations or secondary percentage are imported. New York reference elementary model coverage is now 8/200 (4.0%).
