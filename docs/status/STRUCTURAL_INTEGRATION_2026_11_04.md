# Existing structural research integration

Integration date: **November 4, 2026**. The six remaining researched states are integrated into the shared model: California, Idaho, Montana, Nevada, Oregon and Wyoming. Together with Texas, Washington and the Illinois seed, the shared program tables now contain evidence for **nine states**. The remaining **41 states** still need structural program collection. None of these working sets establishes statewide completeness.

**Collection order: finish the state structural inventories first; add proficiency data afterward.** Existing assessment pilots remain unchanged. This pass adds no academic, language-proficiency, EL exit or SEDA observations.

## Integrated working sets

| State | School units linked to program evidence | Provisional program evidence groups | Reference and limit |
|---|---:|---:|---|
| [California](../states/CA.md) | 264 | 292 | Reviewed 2025–26 inventory, including candidates and a future proposal; 230 qualifying confirmed records at 215 schools |
| [Idaho](../states/ID.md) | 18 | 18 | Reviewed 2025–26 inventory; all 18 qualifying records confirmed under their stated evidence/continuity method |
| Illinois | 12 | 12 | Existing provisional seed; four additional screened-out schools remain in the registry |
| [Montana](../states/MT.md) | 9 | 9 | Reviewed 2025–26 inventory; five qualifying confirmed records, two closed programs, two operating programs with unresolved public-funding eligibility |
| [Nevada](../states/NV.md) | 6 | 6 | Reviewed 2025–26 inventory; five qualifying confirmed records and one content-scope candidate |
| [Oregon](../states/OR.md) | 194 | 209 | 2026–27 directory; reviewed aliases and shared school identities; listing/track scope remains distinct from confirmed implementation |
| Texas | 1,610 | 1,863 | Existing Pass 51 provisional reporting-group/language evidence; mixed policy periods |
| Washington | 177 | 191 | Existing multilingual evidence groups across 2023–24 through 2025–26; not a single-year campus count |
| [Wyoming](../states/WY.md) | 13 | 13 | Reviewed 2025–26 inventory; 11 qualifying confirmed records and two unresolved candidates |

Program evidence groups are **not verified counts of distinct programs**. The [machine-readable state summary](../../data/reports/structural_integration_2026_11_04_by_state.csv) separately reports all registry schools, school units linked to programs, provisional program groups, status records and qualifying confirmed counts where established. Blank confirmed counts for the earlier pilots/directory mean that this status measure has not been established under the five-state confirmation rule.

California's **1,310 historical CDE school leads** are now represented as school-level screening evidence for 2024–25. Already documented CDS matches are reused; no new fuzzy matches are inferred. There are 133 overlaps with the curated native-ID matches, leaving 1,441 California registry units in total, of which 264 have curated program links. These registry units must not be counted as 1,441 confirmed DL schools. The lead records do not manufacture language tracks, allocation schedules or current operation.

Oregon retains **223 source observations**: 211 DLI-directory observations resolve to 209 provisional program keys across 194 school units. The remaining 12 source-classified heritage/revitalization listings remain separate screening records, giving 206 Oregon registry school units overall. McDaniel's four observations retain two language keys and one school identity. Three Four Rivers grade-band evidence keys share one reviewed NCES school identity; that match does not prove three distinct programs or one continuous participant cohort. The newly opened Columbia Vista identity remains unmatched to the older NCES reference.

## What is preserved and normalized

- All **338** reviewed five-state program records retain their research IDs, with **3,480** attribute claims, the saved continuity reviews and change findings. Earlier research snapshots and source bytes remain intact. Empty legacy values become null in nullable shared fields, never zero.
- The new `program_status_history` table separates reference-year operation, public-program eligibility, instructional scope, funding status and confirmation method. A continuing school with unresolved funding eligibility is distinguishable from a confirmed qualifying public DL program.
- Source-specific one-way/two-way, strand/whole-school, grade and language claims populate the shared histories. A review's 2025–26 reference year does not date an older or undated design to 2025–26.
- **51 selected explicit K plans** add 102 named-language share rows. They are documented plans, not verified student exposure. Published model-only selections remain reviewable source labels and preserved share claims rather than accepted named-language percentages.
- SFUSD's older Spanish 80/20 evidence remains alongside the dated 2025–26 K 50/50 policy. Yu Ming's competing point schedules/range remain unresolved. West Portal's later 2026–27 schedule is not assigned to 2025–26. Hardin Primary does not inherit Crow Agency's K ratio. Nk̓ʷusm curriculum-category percentages are not language-time shares.
- Oregon's source language labels do not create an English partner. Unspecified grade scope does not become K. Composite source cells retain campus-level allocation evidence without assigning it separately to every expanded language candidate; track-level population/whole-school claims remain unresolved.
- The Bergan/Bergen name correction retains both prior and corrected research school aliases under the same reviewed lineage. Oregon uses the already approved NCES matches and leaves suggestions/unmatched identities unassigned; its 2024–25 identity reference is separate from its 2026–27 directory year.

The source-applicability field `evidence_claims.evidence_period_raw` preserves nonannual descriptions such as `FY2026` and `2020-25`. Only an explicitly consecutive single academic year becomes a typed validity year. The earlier 2026–27 five-state research is retained as a superseded research vintage, not converted into a second independently confirmed annual census.

## Review and reproduce

The [program review view](../../data/reports/structural_integration_2026_11_04_program_view.csv) contains one row per program/site evidence group. Its model, language and delivery columns are unions across source periods, **not a single contemporaneous configuration**. Use the normalized source/history rows when selecting a specific year. Preserved model-only share claims carry review flags; they must not be treated as verified instructional minutes.

The [integration audit](../../config/research_migrations/structural_integration_2026_11_04.json) hashes 29 retained legacy inputs and 12 unchanged assessment/definition/link tables. It also protects the prior Illinois/Texas/Washington school and program identity sets. The [generated report manifest](../../data/reports/structural_integration_2026_11_04.json) records the current build ID, state coverage and review-view hashes. Schema **1.2.0** has 28 tables. Earlier frozen releases retain their original contracts.

```bash
dl-outcomes build
dl-outcomes validate
python scripts/validate_structural_integration.py
python -m unittest discover -s tests -v
```

The build uses only saved research. It regenerates and hashes the structural review views; frozen bundles include them. Standalone report regeneration is available through `scripts/build_structural_integration_report.py`. No external research or new proficiency collection is required to reproduce the integration.

The next collection work should cover additional states' schools, districts, instructional languages, language allocations, grade coverage, one-way/two-way organization and strand/whole-school choices. Proficiency collection follows completion of the structural phase.

Local verification passed: **76 tests**, national/structural validation, the preserved Texas and five-state validators, deterministic offline rebuild and immutable-release checks, and row-count/field checks across all **28 Parquet and DuckDB tables**. The legacy inputs, prior identity sets, assessment values and earlier frozen release manifest remain unchanged.
