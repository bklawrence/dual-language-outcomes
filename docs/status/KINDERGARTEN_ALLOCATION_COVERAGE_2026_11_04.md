# Kindergarten allocation coverage: revised denominator

November 4, 2026. This review supersedes the earlier all-campus allocation/model-label percentages for kindergarten coverage. Secondary DL continuations remain in the inventory. Their K-allocation status is **not applicable**, rather than missing or undefined.

The denominator includes identified programmes serving kindergarten, deduplicated to schools. A K–8/K–12 campus with a documented K programme counts once. A programme beginning in first grade, an upper-elementary continuation or a secondary-only programme is excluded. Unknown programme grades are listed separately; they are not counted as missing K allocations. A ratio label or the word “Elementary” in a school name cannot establish K eligibility. Texas's explicitly flagged campus proxies are described below.

## Current review files

- [State counts and explicitly scoped percentages](../../data/reports/kindergarten_allocation_coverage_2026_11_04_by_state.csv)
- [School denominator audit](../../data/reports/kindergarten_allocation_coverage_2026_11_04_by_school.csv)
- [Programme audit, grade evidence IDs, periods and allocation status](../../data/reports/kindergarten_allocation_coverage_2026_11_04_by_program.csv)
- [Texas school view](../../data/reports/texas_kindergarten_allocation_coverage_2026_11_04.csv) and [Washington school view](../../data/reports/washington_kindergarten_allocation_coverage_2026_11_04.csv)

The national structural views also expose K eligibility/status. Excluded, candidate, historical and future programmes are preserved, with an explicit reference-working-set flag. For the eleven reviewed states, the working set is confirmed qualifying programmes in 2025–26. Texas retains its provisional 2023–24 TAPR candidate inventory, Washington uses 2025–26 state-reported DL rows, Oregon uses its 2026–27 directory, and Illinois remains a preliminary seed. These are different research scopes, not contemporaneous statewide censuses.

The CSV `denominator_status` distinguishes a classified working set, a partial denominator and a denominator not established. Percentages are named `*_pct_among_identified_k_schools`; unknowns are reported alongside them. A blank percentage means no denominator has been established, not 0% coverage. A 100% value for a small identified subset does not describe the remaining unknown schools. The identified K denominator plus secondary exclusions, other non-K exclusions and unknowns always equals the working-set school count. Having allocation evidence at one K track does not establish coverage for every track at that school.

## Washington correction and saved CSVs

The [2025–26 CSV](../../data/registry/washington/wa_dl_programs_2025_26.csv) contains **195 DL source records at 175 schools**. The [longitudinal CSV](../../data/registry/washington/wa_programs.csv) preserves all **1,002 native structural rows across 2023–24 through 2025–26**, including separately flagged heritage/tribal categories. Every native field remains available, with national IDs for DL candidates and snapshot/hash/query/row provenance. See the [CSV guide](../../data/registry/washington/README.md).

The earlier **175/175 = 100%** described annual model-label completeness. This source has no programme grades, K timetable or explicit second instructional language. It therefore cannot establish a K denominator or K language-allocation coverage. All 175 current school units need grade-scope review; the percentage is blank. Secondary schools remain as candidates, with no grades assigned from their names.

## Texas denominator and qualifications

The existing programme files lack dependable campus grades. A newly archived [2024–25 AskTED-derived directory layer](../../data/raw/tx/grade_context_2024_25_captured_2026_11_04/) supplies grade-range **context**, matched by the exact nine-digit Texas campus ID. Five original JSON responses retain the directory's 9,739 rows, query, year, retrieval timestamp and SHA-256. Only the 1,586 matched existing inventory campuses receive grade-context claims; the other directory schools are not added as DL candidates.

Among the 1,610 Texas working-set campuses, the directory identifies **188 secondary-only campuses** and **135 other campuses without K**. It identifies 1,263 K-serving campuses; 24 inventory campuses are unmatched. One unmatched campus has explicit campus/programme K-scope evidence, giving an identified denominator of **1,264**, with **23** still unknown. Of these 1,264, **1,259** rely on a K-serving-campus proxy rather than verified programme grades. These proxies are flagged and require programme-grade review. Directory ranges such as `PK 01-08` are disjoint bands and do not imply K.

Within that provisional denominator, **767/1,264 (60.7%)** have a retained, cited K model not explicitly rejected by the saved reviews. **51** have grade-supported K-model evidence; Texas has no accepted named-language numerical plans in the national tables. The 60.7% is a policy/model-label research-completeness figure across mixed source periods, not the percentage with verified K timetables or a 2025–26 operating census. The directory year remains 2024–25 and is not backdated to the 2023–24 TAPR group.

## Evidence and reproducibility

The reports distinguish cited K models, grade-supported K models and accepted plans with named-language shares. Rejected period/programme links, pre-K proxies, conflicting shares and unresolved composite-track models do not supply K-coverage numerators. Unreviewed K labels remain separate from grade-supported evidence. Older and undated sources retain their periods; future dated schedules are not backdated into the reference year. No model is treated as tested-cohort exposure.

`dl-outcomes build` regenerates the review CSVs and WA exports offline. They are hashed in the build/report manifest and included in portable releases. Grade decisions point to configuration, schedule or evidence-claim IDs in the national tables, which lead to source locators and snapshots. The [earlier baseline CSV](../../data/reports/allocation_coverage_by_state_2026_11_04.csv), Texas Pass 48–51 files and original source/model observations remain preserved. School/programme identity sets and assessment/proficiency pilot outputs are unchanged.
