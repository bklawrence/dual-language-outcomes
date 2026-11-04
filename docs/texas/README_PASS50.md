# Texas instructional-language audit — Pass 50

Audit date: **November 4, 2026**. This pass checks the language classifications in the Pass 49 Texas research export. It retains the **1,610 campuses and 1,856 campus × 2023–24 TAPR reporting groups**. It is a language-evidence audit, not a verified statewide program census or a new outcomes analysis.

## Updated tables

| File | Purpose |
|---|---|
| [Campus language inventory](../../data/registry/texas/texas_campus_language_inventory_pass50.csv) | Readable table with one row per campus; separately shows campus evidence, district policy support, prior labels and unresolved cases |
| [Language tracks](../../data/registry/texas/texas_language_program_tracks_pass50.csv) | Preferred provisional track export, with previous labels, sources, dates and correction reasons |
| [Classification audit](../../data/registry/texas/texas_language_classification_audit_pass50.csv) | Row-level before/after decisions |
| [Language-role and change reviews](../../data/registry/texas/texas_language_role_reviews_pass50.csv) | Additional languages, possible tracks, later offerings and a reported program-model change |
| [Source register](../../data/registry/texas/pass50/source_register.csv) | URLs, retrieval dates, content hashes, short evidence excerpts, source scope and limitations |
| [Allocation evidence](../../data/registry/texas/texas_k_allocation_evidence_pass50.csv) | Original 970 policy observations with language-link audit fields |
| [Summary](../../data/registry/texas/language_audit_summary_pass50.json) | Counts and audit status |
| [Current file pointer](../../data/registry/texas/current_inventory.json) | Preferred Texas files for this research workflow |

Passes 48 and 49 remain unchanged for provenance. The national registry tables, collectors and existing outcome joins have not been rewritten.

## Findings and corrections

**Wimbish World Language Academy has separate French–English and Spanish–English core-content tracks.** Its official description specifies math and science in French or Spanish and a separate Mandarin FLES elective. The preferred export adds the previously omitted French track, resolves the existing unknown row to Spanish, and removes the old allocation note restricting the study to Spanish. Mandarin is not counted as a Wimbish immersion track.

The audit also confirms and preserves the following non-Spanish offerings. Most were already distinguished in Pass 49; they should not be presented as newly discovered corrections. Each language pair is a separate candidate track, not a combined trilingual program.

| Campus | Documented core language pair(s) | Evidence period / limitation |
|---|---|---|
| Wimbish, Arlington | French–English; Spanish–English | Undated official campus description accessed in 2026; 2023–24 operation not established by this source |
| Hickman, Garland | Vietnamese–English | District core-subject description dated September 5, 2025 |
| Vernal Lister, Garland | Vietnamese–English; Spanish–English | **2023–24 campus improvement plan** separately identifies one-way Vietnamese K–4 and Spanish K–5 |
| Mandarin Immersion Magnet School, Houston | Mandarin–English | Official 2024–25 campus roster and campus instructional description |
| Arabic Immersion Magnet School, Houston | Arabic–English | Official 2024–25 campus roster and school history |
| Mark White, Houston | French–English; Spanish–English | Official 2024–25 roster; **later French-model change reported**, described below |
| Reilly, Austin | Mandarin–English; Spanish–English | 2023–24 application choices |
| Summitt, Austin | Vietnamese–English | 2023–24 application, printed as “Summit” |
| Doss, Austin | Mandarin–English | 2023–24 application and campus description; two TAPR categories do not prove two distinct programs |
| Joslin, Austin | Mandarin–English; Spanish–English | 2023–24 choices also include a combined Spanish-and-Mandarin application option; a trilingual content track is not established |
| Wooten, Austin | Mandarin–English; Spanish–English | **2026–27 roster only**; do not backdate these offerings to the 2023–24 reporting groups |

Houston's official **2024–25** roster was matched by campus number, not by a language default or school-name keyword. It confirms Spanish at additional previously unverified campuses while retaining its Arabic, Mandarin and French exceptions. The roster's raw spelling `Spansih` is preserved alongside its normalized value in the portable transcription. Five merged campus-number/name cells were split and checked against the PDF text.

Across the export:

- **26 previously unknown rows** now have a documented language pair; one additional French track is added at Wimbish.
- **63 Spanish–English labels** return to `UNVERIFIED` because their source could not support that row's language pair or grade/program scope. This does **not** establish that those schools teach a different language.
- **57 historical Spanish-only labels** also become pair-unverified: their source links were absent and their English pairing had not been established. Original labels remain in the `previous_*` and raw fields.
- **1,863 provisional track records** now comprise 802 Spanish–English, 7 Mandarin–English, 3 Vietnamese–English, 2 French–English, 1 Arabic–English and **1,048 unverified** records. These are evidence-record counts, not distinct program counts.
- Confirmation scope remains explicit: **84 campus-documented records**, **708 district-policy-supported records**, **23 prior-source records not independently reconfirmed**, and **1,048 unverified records**. District support alone is not campus/year confirmation.

## Electives, third languages and unresolved cases

**Do not replace a core partner language with an additional language merely because it appears on a school website.** Cameron Dual Language Magnet in Ector County explicitly uses Spanish/English for its core 50/50 model and describes French as a third language through songs, music, theatre and arts. Ben Milam in Midland separately describes French foreign-language instruction beginning in fourth grade. Mesita in El Paso explicitly retains English/Spanish core instruction and identifies Mandarin as an added third language. PSJA likewise describes English/Spanish academic instruction and optional Mandarin as a third language. The five reviewed Ysleta international campuses remain pair-unverified; their third-language/LOTE descriptions do not establish a replacement immersion partner.

Two important leads remain unresolved:

- **Weaver, Garland:** an official historical Mandarin-program handout and the 2026 Mandarin directory warrant investigation of an additional Mandarin track. The current district roster separately identifies a Spanish program. The 2024–25 campus plan and current signature-program page do not resolve Mandarin content instruction or its operating dates. Their omission is not proof the program ended. Retain the separately supported Spanish model and flag Mandarin; do not replace Spanish or claim a confirmed 2023–24 Mandarin track.
- **Stafford Elementary:** its official page describes Vietnamese–English and Chinese–English programs starting at **Stafford Primary**, plus separate Spanish/English bilingual instruction. The older Primary references and proposed 2010 launch do not establish which languages belong to Elementary's 2023–24 two-way reporting population. Keep that pairing unverified and preserve all three leads. The secondary directory's Mandarin designation does not, by itself, settle the official page's broader “Chinese” wording.

Gunn's feeder-continuation description is also insufficient to confirm its historical secondary core-content language plan. Colony Meadows' later Mandarin offering and 2027–28 recruitment flyer are recorded as context, without adding a 2023–24 parent record.

## Mark White: retain history, flag the reported model change

The [Houston Chronicle's February 4, 2026 report](https://www.houstonchronicle.com/news/houston-texas/education/hisd/article/hisd-ends-french-dual-language-21284000.php), corroborated by [Hoodline](https://hoodline.com/2026/02/hisd-french-cutback-plan-has-mark-white-parents-on-edge/), describes a proposed 2026–27 shift to English core subjects and French enrichment in grades 1–5, with PK/K retaining near-50/50 French instruction. The article reports presentation slides and describes the change as expected/proposed. **Final implementation was not established in this pass.**

This is a material change indication: the older campus description cannot establish uninterrupted 2026–27 French immersion. It also does not invalidate the official 2024–25 French track or justify relabeling that historical track as Spanish.

## How to interpret and reproduce the data

`language_pair` is the reviewed classification; `raw_*` and `previous_*` preserve earlier evidence and labels. `pair_verification_scope` distinguishes `CAMPUS_DOCUMENTED`, `DISTRICT_POLICY_ONLY`, `PRIOR_EVIDENCE_NOT_INDEPENDENTLY_RECONFIRMED` and `UNVERIFIED`. `language_pair_verified_in_source=YES` means the pair is supported **at that stated scope**, not that a particular campus/year or TAPR participant population is confirmed. Source dates are independent of `assessment_year=2023-24`.

The district rules corroborate **existing explicit Spanish labels only**, within their stated program/grade scope. They do not fill unknown campuses with Spanish. An older useful description is retained as policy evidence; labels are not withdrawn merely because a webpage is undated. Missing evidence, wrong source scope, reported changes and unresolved language roles are recorded separately. The source register and search log document successful, failed and unused retrievals; a failed request or unsuccessful search is not closure evidence. One guessed Weaver PDF URL returned a Lister document and was explicitly rejected.

All **970** original allocation observations remain. **25** previously linked observations are now unlinked because their language assignment lacks sufficient support; **648** retain their original provisional links. Their original allocation values, source URLs, entry years and policy dates are preserved. Neither retained links nor this language audit establish tested-cohort exposure. A language-allocation audit for other purposes would need separate review of grade-specific schedules and rollout dates.

**No TAPR outcome has been assigned or duplicated across languages.** Every track remains provisional, and all language-specific outcome attribution remains `NOT_ESTABLISHED`. A dated campus listing, including Doss or Lister, does not separately identify the one-way/two-way participant populations or allow disaggregation of a combined result. The campus table deduplicates repeated language evidence across reporting categories.

Reviewed build inputs are in [pass50/](../../data/registry/texas/pass50/): campus decisions, district rules, language-role reviews, source register, search log and the official Houston roster transcription. Rebuild and validate from repository root:

```bash
python3 scripts/build_texas_language_audit_pass50.py
python3 scripts/validate_texas_language_audit_pass50.py
python3 scripts/validate_texas_pass48.py
python3 -m unittest discover -s tests -v
```

The build uses only the standard library and saved decisions; it does not fetch changing webpages. The manifest records input/output hashes. Tests check unknown-language defaults, omitted French tracks, third-language substitution, backdating, ambiguous allocation links and unsupported language-specific outcomes. Passing these checks establishes consistency and provenance safeguards, not independent proof for every campus in the research universe.
