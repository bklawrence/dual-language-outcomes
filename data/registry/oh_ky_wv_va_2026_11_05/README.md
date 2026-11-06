# Ohio, Kentucky, West Virginia and Virginia structural review

Reviewed November 5, 2026, against a **2025–26 operating reference**. This is a partial public-source inventory, not a statewide census. The 110 programme records represent 108 provisional school units, including candidates, historical hosts and later starts. West Virginia has screening records and header-only school/programme CSVs; no qualifying academic DL programme was verified in this pass. That is not evidence of statewide absence.

| State | School CSV | Programme CSV | Screening CSV |
|---|---|---|---|
| Ohio | [oh_schools.csv](oh_schools.csv) | [oh_programmes.csv](oh_programmes.csv) | [oh_screening.csv](oh_screening.csv) |
| Kentucky | [ky_schools.csv](ky_schools.csv) | [ky_programmes.csv](ky_programmes.csv) | [ky_screening.csv](ky_screening.csv) |
| West Virginia | [wv_schools.csv](wv_schools.csv) | [wv_programmes.csv](wv_programmes.csv) | [wv_screening.csv](wv_screening.csv) |
| Virginia | [va_schools.csv](va_schools.csv) | [va_programmes.csv](va_programmes.csv) | [va_screening.csv](va_screening.csv) |

One school row represents a provisional school unit. Programme rows distinguish language strands: GALA has Spanish and Mandarin Chinese, while Columbus World Language Middle has French and Spanish continuations. Source names and programme IDs are not official durable identifiers or validated NCES programme crosswalks.

The JSON files are the reviewed build inputs. Programme observations preserve actual source periods, grades, languages, population type, delivery structure and allocation separately from the 2025–26 research assessment. Undated or older descriptions can support continuity after bounded change review; that does not date the model to 2025. Explicitly later policies remain in the all-recorded view and do not fill a reference-year allocation gap. Plans, expansions, course cuts and host changes remain separate events.

Use [sources.csv](sources.csv) or [sources.json](sources.json) to locate the **105 saved public documents** in [the raw source directory](../../raw/oh_ky_wv_va_2026_11_05/). Each snapshot has URL, retrieval timestamp, content type and SHA-256 metadata. [retrieval_log.csv](retrieval_log.csv) also records unsuccessful acquisitions and search leads; a successful HTTP response does not automatically make a page primary programme evidence. Sources blocked by HTTP 403 were not treated as programme proof.

[Source-row reconciliations](extractions/roster_reconciliation.json) preserve twelve roster selections, including actual third-party directory cards, Fairfax's 17 current elementary rows and 16 named 2025–26 admissions hosts, Fayette's five current hosts and ten 2018 hosts/plans, the VADLEN network's fifteen division leads, and Virginia Beach's existing/future pathways. Directory inclusion alone does not verify academic immersion. A flyer meeting venue, transport feeder or duplicate directory name is not an extra DL school.

The two original Arlington chart PNGs are archived. Their critical grade/language percentages and 2025–26 rollout were visually verified; derived text and extraction methods are saved. Fayette's image-only brochure has derived OCR, with its school list visually checked. The linked Harrisonburg brochure is an original image PDF with a selected manual transcription, explicitly identified as incomplete; its PDF creation timestamp is not a claimed publication date. Alexandria's current district-linked handbook is saved as its complete public text export, distinct from the 2022 PTA-hosted official handbook.

[Grade-context decisions](grade_context_decisions.json) record 107 unique normalized school/district or explicitly reviewed name-alias matches to 2024–25 CCD school grades. This is denominator context only. Mountain View Upper was not open in that snapshot and remains [unmatched](unmatched_grade_context.json). Any K–5 grade qualifies for the elementary denominator, including Bailey's Upper (3–5) and Daniel Morgan Intermediate (5–6). Secondary continuation records receive no elementary allocation.

See the [findings](../../../docs/status/OH_KY_WV_VA_2026_11_05.md), [state counts](../../reports/oh_ky_wv_va_2026_11_05_by_state.csv), [missing-field backlog](../../reports/oh_ky_wv_va_2026_11_05_backlog.csv), [review cases](../../reports/oh_ky_wv_va_2026_11_05_review_cases.csv), and [dated changes](../../reports/oh_ky_wv_va_2026_11_05_change_events.csv). Proficiency, demographics, EL-exit and SEDA collection remains deferred; prior analytical outputs are preserved.
