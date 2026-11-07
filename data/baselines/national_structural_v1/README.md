# National structural baseline v1

Frozen 2026-11-06 for a **2025-26 target reference**. This is a partial research inventory covering all 50 state research passes, not a national school census or a participant dataset. It contains 5,131 programme-site evidence groups and 4,617 existing school research identities. These are provisional research units, not verified counts of distinct programmes.

Start with [programmes.csv](programmes.csv), [schools.csv](schools.csv) and [state_summary.csv](state_summary.csv). [working_programmes_2025_26.csv](working_programmes_2025_26.csv) contains the working reference cohort; the `in_confirmed_qualifying_cohort` flag distinguishes explicit operation/eligibility reviews from source-year listings. Candidates, future phases and historical records remain in the full inventory.

Texas's source working reference is 2023–24 and Oregon's is 2026–27. Their [2,072 source-vintage rows](source_vintage_programmes.csv) are separate from the 2025–26 selections. They must not be stacked and described as a single-year census. Unknown reference-year operation is not programme absence.

Each row in [programme_fields.csv](programme_fields.csv) is **programme site × selection year × variable**. Source dates, evidence IDs, conflicts, inference and provisional classifications are explicit. [field_evidence.csv](field_evidence.csv) records selected and excluded evidence, including later-only observations. An undated or older policy compatible with programme continuity is not a newly observed annual configuration. Retrieval dates never determine policy validity. The versioned [rules](rules.json) and original source records document the choices.

[allocations.csv](allocations.csv) preserves grade/service scopes, percentage bases, source passages and all historical schedules. A programme is not reduced to a single entry ratio. Named-language percentages remain in [the original allocation-language table](evidence/instructional_allocations.csv). Campus-only policies are not silently assigned to each language strand. Secondary-only elementary entry models are not applicable; campuses serving any K–5 grade count as elementary-containing. Source model availability and a resolved, language-specific policy are separate measures.

Model notation is standardized in separate normalized columns. With two explicitly named languages including English, the normalized ratio is partner-language/English; otherwise a numeric source ratio retains an explicitly unresolved language order. The raw label and language shares remain unchanged. Core/classroom scope, annual model-only labels and unspecified instructional denominators are distinct basis classes.

School-grade context keeps its own source year. If only a later campus directory is available, it is explicitly marked as a grade-context proxy, not a reference-year configuration. Later **allocation policies** remain excluded from earlier selections. [Coverage reconciliation](coverage_reconciliation.csv) and [school-level changes](coverage_changes.csv) compare this baseline with the saved prior audit; 57 school-unit changes are listed individually. The original evidence and earlier reports are unchanged. [Source-vintage school rows](source_vintage_schools.csv) retain the corresponding grade/identifier/membership context. Campus-level delivery reports remain school context and are not assigned to every language strand.

The [state](completeness_by_state.csv), [language](completeness_by_language.csv), [school-level](completeness_by_school_level.csv) and [district](gaps_by_district.csv) audits distinguish documented, inferred, provisional, conflicting, later-only, missing and not-applicable values. Their structural-variable denominator is programme sites. [Allocation coverage](allocation_coverage_by_state.csv) instead counts schools, grouping only by the existing grade-context audit units; that grouping does not authorize outcome joins. Language groups overlap for multilingual programmes and must not be summed as independent samples.

Unknown elementary applicability is tallied separately and does not inflate the applicable denominator. Availability of selected evidence differs from a resolved classification: provisional labels, conflicts and reported models needing review are shown separately. An inferred classification retains its inference status even when usable under the research rules.

[Research priorities](research_priorities.csv) rank unresolved record counts in the source working inventories; [review_queue.csv](review_queue.csv) lists the underlying records. Percentages describe the reviewed inventory, not completeness of statewide school lists. Zero denominators are marked explicitly, including screening-only states. No probability of research success or arbitrary confidence score is invented.

Existing canonical identities are preserved. [Native identifier records](evidence/identifiers.csv) retain source/review/year scope. Grade-context NCES candidates are **not automatic outcome crosswalks**. [Possible aliases/co-locations](identity_review_queue.csv) need review before any additional merging; no name-based merges were performed. [Screening school candidates](screening_school_candidates.csv) remain separate from programme hosts.

The [table contracts](table_contracts.json) document CSV keys and columns. The [evidence folder](evidence/) freezes all structural source records and histories, including the source catalogue and claims. Original web/PDF archives remain at the paths and hashes in that catalogue; they are not duplicated here. The [manifest](manifest.json) pins the original table paths, hashes, rules, code and provenance. The [pipeline](pipeline/dl_outcomes/) preserves the implementation. Twelve assessment/context output receipts remain unchanged; no proficiency, demographic, EL-exit or SEDA data were collected.

From the repository root, verify with:

```bash
dl-outcomes baseline check national_structural_v1 --reproduce
```

The command reads the frozen evidence, not updated live tables. For future historical reproduction after the main implementation changes, use the frozen package with `PYTHONPATH=data/baselines/national_structural_v1/pipeline python -m dl_outcomes.cli baseline check national_structural_v1 --reproduce`. Install this baseline's [pinned core requirements](requirements-lock.txt) first. Creating a baseline with an existing ID fails; later research belongs in a new baseline version.
