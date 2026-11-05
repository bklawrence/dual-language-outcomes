# Elementary-school allocation-model audit

November 4, 2026. In the reference working inventories, **1,292 of 2,055 elementary school units (62.9%)** have numerical language-allocation-model data. All 15 represented states are included. These are within-inventory completeness figures, not estimates of the percentage of every DL school in a state.

Elementary means a school serving at least one grade **K–5**: K–8, K–12, 1–6, 3–6 and 5–8 therefore qualify. A school starting in sixth grade or later is excluded, even if its local designation includes “elementary.” Preschool-only sites are excluded. Schools are deduplicated across language tracks and accepted grade-context aliases; canonical registry and programme identities remain unchanged.

## Reference working inventories

| State | Elementary schools | With numerical allocation | Coverage | Grade classification unresolved |
|---|---:|---:|---:|---:|
| Arizona | 5 | 5 | 100.0% | 0 |
| California | 210 | 199 | 94.8% | 0 |
| Colorado | 8 | 6 | 75.0% | 0 |
| Idaho | 15 | 7 | 46.7% | 0 |
| Illinois | 12 | 1 | 8.3% | 0 |
| Kansas | 6 | 5 | 83.3% | 0 |
| Montana | 5 | 2 | 40.0% | 0 |
| Nebraska | 2 | 1 | 50.0% | 0 |
| New Mexico | 92 | 8 | 8.7% | 0 |
| Nevada | 5 | 2 | 40.0% | 0 |
| Oregon | 109 | 106 | 97.2% | 0 |
| Texas | 1,420 | 797 | 56.1% | 0 |
| Utah | 33 | 25 | 75.8% | 0 |
| Washington | 126 | 126 | 100.0% | 0 |
| Wyoming | 7 | 2 | 28.6% | 0 |

This view follows the existing operation/eligibility selections. CA/ID/MT/NV/WY and the six western/plains states use confirmed qualifying 2025–26 programmes, including accepted continuity reviews. Washington uses 2025–26 state-reported DL rows. Oregon uses its 2026–27 directory. Texas uses the provisional 2023–24 TAPR-campus working inventory, which does not independently confirm every campus hosted a DL programme. Illinois is a 12-school provisional seed. Small reviewed subsets, especially Arizona and Nebraska, must not be interpreted as complete statewide inventories. Programme operation dates and model-evidence dates remain separate.

## All recorded programme hosts

The broader view retains historical, unconfirmed, future and eligibility-review records. It is useful for auditing the entire research backlog, but it is not an operating DL-school census. Across this broader view, **1,344 of 2,232 identified elementary school units (60.2%)** have numerical models; **45 additional host school units have unresolved grades** and are outside that denominator. Percentages with unresolved grades are conditional on the classified subset.

| State | Identified elementary schools | With numerical allocation | Coverage | Other hosts with unresolved grades |
|---|---:|---:|---:|---:|
| Arizona | 29 | 28 | 96.6% | 2 |
| California | 213 | 206 | 96.7% | 0 |
| Colorado | 29 | 19 | 65.5% | 27 |
| Idaho | 15 | 8 | 53.3% | 0 |
| Illinois | 12 | 1 | 8.3% | 0 |
| Kansas | 8 | 6 | 75.0% | 1 |
| Montana | 8 | 2 | 25.0% | 1 |
| Nebraska | 10 | 1 | 10.0% | 2 |
| New Mexico | 114 | 8 | 7.0% | 0 |
| Nevada | 5 | 2 | 40.0% | 1 |
| Oregon | 109 | 106 | 97.2% | 0 |
| Texas | 1,420 | 797 | 56.1% | 0 |
| Utah | 127 | 31 | 24.4% | 10 |
| Washington | 126 | 126 | 100.0% | 0 |
| Wyoming | 7 | 3 | 42.9% | 1 |

## What counts as allocation data

A school counts once when at least one retained programme or campus-level source reports a numerical instructional allocation: 90/10, 80/20, 70/30, 50/50, another combination totaling 100, or full target-language immersion. Accepted normalized plans stated as equal half-days or equal instructional minutes also count. One-way/two-way labels alone, student-language composition, qualitative subject-language descriptions without time shares, and generic “Other” labels do not count.

The numerator measures availability of model information. It does not require a K timetable, a named English partner or coverage of every language strand. A published annual 50/50 label can count without a grade-by-grade schedule. Older and undated policies retain their periods; this is not a verified 2025–26 timetable comparison or tested-cohort exposure measure. Explicitly later dated schedules are excluded from the reference numerator; the broader view retains later evidence.

Unsupported programme/grade/period attributions, unrecovered citations and pre-K-only proxies rejected by the existing reviews do not supply model evidence. Conflicting numerical claims, model/minute disagreements and campus-level composite models remain information available, with their review flags retained. Counting them does not select a preferred ratio or assign a campus model to every track. The state CSV includes a count of schools with these flags.

## Grade evidence and examples

The audit archives only school IDs, names, district labels and grade-directory fields from the Urban Institute Education Data Portal’s NCES CCD directory. Archived variable definitions establish that API year 2024 means school year **2024–25**, and that grade code -1 means pre-K. Missing/ungraded codes never become grades. The older 2023–24 Texas directory fills grade gaps on records whose 2024–25 grades are absent, retaining its own year. These are school-grade context records, not new DL confirmations or durable NCES identity crosswalks.

Existing NCES/state school identifiers are preferred, followed by unique exact normalized school+district names. Twenty-five explicit grade-context alias decisions retain their rationale in the audit configuration. When directory grades are unavailable, documented programme grades can establish a school-grade proxy; that basis is flagged. School names alone do not assign a grade band.

- Washington: 126 elementary-serving schools and 49 secondary-only schools in the 2025–26 working set. All 126 elementary schools have a published numerical model label: **100% model availability**, with no inference of K schedules.
- Columbia Vista Intermediate: its official district opening article states **grades 4–6**, so it counts as elementary under this definition despite having no K intake.
- Pretty Eagle Catholic Academy: the official operator profile states **K–8**. It is included in the denominator; no allocation ratio is invented.
- Denver Language School: the school’s directory span is **K–8**. A separately retained French middle-grade programme does not make the whole school secondary-only.
- Lowell Elementary and San Tan Elementary: documented equal core-instruction minutes or half-days provide quantified 50/50 plans even when the label is prose. Percentage basis and source limitations remain in the original schedule records.

## Saved audit and reproducibility

- [Reference-state table](../../data/reports/elementary_allocation_coverage_2026_11_04_reference_by_state.csv)
- [All-recorded-host state table](../../data/reports/elementary_allocation_coverage_2026_11_04_all_records_by_state.csv)
- [Both scopes in one CSV](../../data/reports/elementary_allocation_coverage_2026_11_04_by_state.csv)
- [School-level audit with model labels, grade/source periods and evidence IDs](../../data/reports/elementary_allocation_coverage_2026_11_04_by_school.csv)
- [Grade match/exception configuration](../../config/research_migrations/elementary_allocation_audit_2026_11_04.json)

`dl-outcomes build` regenerates these views offline from preserved snapshots and source-linked national records. All files are included in report/input hashes and portable release bundles. Existing programme/school identities, historical source exports and the 12 assessment/definition/link outputs remain unchanged; no new proficiency, demographic or SEDA observations are imported. The [earlier kindergarten audit](KINDERGARTEN_ALLOCATION_COVERAGE_2026_11_04.md) answers a separate, narrower question.
