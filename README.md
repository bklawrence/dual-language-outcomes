# Dual-language outcomes

A longitudinal research dataset for dual-language programs across all **50 US states**, including all instructional languages. The national model separates school/program histories from three assessment layers: DL-participant reports, state assessments and context, and Stanford SEDA estimates.

**Current phase: finish the structural program inventories for all 50 states before collecting additional proficiency data.** Partial structural evidence, including separately flagged candidates and historical hosts, is integrated for **22 states**: Alaska, Arizona, California, Colorado, Hawaiʻi, Idaho, Illinois, Iowa, Kansas, Minnesota, Missouri, Montana, Nebraska, Nevada, New Mexico, North Dakota, Oregon, South Dakota, Texas, Utah, Washington and Wyoming. The latest first pass adds North Dakota, South Dakota, Minnesota, Iowa, Missouri, Alaska and Hawaiʻi. The other **28 states** have no integrated program working set yet. Represented states still have discovery and verification gaps; North Dakota's school candidate does not yet establish a qualifying public-school denominator. Existing assessment pilots are preserved; new proficiency, EL exit and SEDA collection is deferred until structural data is collected for all states.

## Start here

- [Seven-state findings and coverage](docs/status/NORTHERN_CENTRAL_AK_HI_2026_11_05.md), [school/programme CSVs](data/registry/northern_central_ak_hi_2026_11_05/README.md) and [review cases](data/reports/northern_central_ak_hi_2026_11_05_review_cases.csv)
- [Architecture and interpretation](docs/methods/NATIONAL_DATA_MODEL.md)
- [Table contracts and data dictionary](schemas/README.md)
- [Current Texas review results](docs/status/TEXAS_ALLOCATION_REVIEW_2026_11_05.md): Denton 50/50, Red Oak one-way with allocation unknown, and the matching-programme inference rule; [programme assignments](data/reports/texas_allocation_review_2026_11_05_assignments.csv), [all 598 current outcomes](data/reports/texas_allocation_review_2026_11_05_598_after_review.csv) and [case dispositions](data/reports/texas_allocation_review_2026_11_05_outcomes.md)
- [Preserved Utah/Texas first-pass checkpoint](docs/status/UT_TX_ALLOCATION_FOLLOWUP_2026_11_05.md): Utah's elementary 50/50 policy, the original 69 Texas additions and original review questions
- [Six-state research status](docs/status/WESTERN_PLAINS_2026_11_04.md), [batch coverage](data/reports/western_plains_2026_11_04_by_state.csv), [programme review view](data/reports/western_plains_2026_11_04_program_view.csv) and [remaining gaps](data/reports/western_plains_2026_11_04_backlog.csv)
- [Current national state summary](data/reports/structural_inventory_2026_11_05_northern_central_ak_hi_by_state.csv), [national programme view](data/reports/structural_inventory_2026_11_05_northern_central_ak_hi_program_view.csv) and [preserved earlier nine-state milestone](docs/status/STRUCTURAL_INTEGRATION_2026_11_04.md)
- [State/year/layer coverage](data/curated/coverage/state_year_layer_coverage.csv)
- [Elementary allocation-model methods and November 4 baseline](docs/status/ELEMENTARY_ALLOCATION_AUDIT_2026_11_04.md), [current reference-state percentages](data/reports/elementary_allocation_coverage_2026_11_05_northern_central_ak_hi_reference_by_state.csv), [all recorded hosts](data/reports/elementary_allocation_coverage_2026_11_05_northern_central_ak_hi_all_records_by_state.csv) and [school-level evidence](data/reports/elementary_allocation_coverage_2026_11_05_northern_central_ak_hi_by_school.csv), including inference flags
- [Kindergarten denominator rules and November 4 baseline](docs/status/KINDERGARTEN_ALLOCATION_COVERAGE_2026_11_04.md), [current counts](data/reports/kindergarten_allocation_coverage_2026_11_05_northern_central_ak_hi_by_state.csv) and [school exclusions/unknowns](data/reports/kindergarten_allocation_coverage_2026_11_05_northern_central_ak_hi_by_school.csv)
- [Washington saved CSVs](data/registry/washington/README.md), including the [2025–26 DL records](data/registry/washington/wa_dl_programs_2025_26.csv)
- [Earlier allocation/model-label baseline](docs/status/ALLOCATION_COVERAGE_2026_11_04.md) and [Texas Pass 51 milestone](docs/status/TEXAS_CLEANUP_PASS51_2026_11_04.md)
- [Build provenance and table counts](data/curated/manifest.json)
- [Texas pilot](docs/states/TX.md) and [Washington pilot](docs/states/WA.md)
- [Adding a source or state](docs/methods/ADDING_SOURCES.md)

## Install, build and validate

Python 3.10+ is supported. These commands use an isolated virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt -e .
.venv/bin/dl-outcomes validate
.venv/bin/dl-outcomes build
.venv/bin/python -m unittest discover -s tests -v
```

`build` is offline and deterministic for the saved input/config/code bytes. It creates all 28 contract tables, the structural review views and headers for uncollected layers, then validates them. `validate` checks source/report hashes, reporting grain, populations, identities, dates and attribution. It does not independently verify every reported research claim.

The unchanged assessment pilots contain eight Texas subject results from four published one-way-DL/current-EL reporting groups, plus Washington school-level academic and enrollment observations for two multilingual elementary schools across 2023–24, 2024–25 and 2025–26. Washington program metadata covers a broader set of schools and preserves related heritage/tribal records for review. Program evidence groups are not verified distinct program counts.

## Repository layout

```text
config/                    State profiles, study coverage window, reviewed ID aliases
schemas/                   Contract guide and generated data dictionary
src/dl_outcomes/            Build, state adapters, collection, validation and releases
  schemas/catalog.json     Packaged JSON Schema source of truth
data/raw/                  Immutable public snapshots and original legacy seed bytes
data/staging/              Disposable extraction/repair work (ignored by Git)
data/curated/              Shared registry, histories, assessment layers and evidence
data/releases/             Frozen local release manifests; generated bundles ignored
data/registry/             Preserved earlier research and compatible legacy seed inputs
collectors/                Existing standalone collectors, retained during migration
analysis/                  Analysis code; interpretation remains source/scope specific
docs/                      Methods, state profiles and earlier research reports
tests/                     Schema, population, time, missingness and provenance checks
```

## Source collection and releases

The checked-in public snapshots and reviewed research inputs are sufficient to rebuild the dataset offline. A new acquisition must use a new vintage directory:

```bash
.venv/bin/dl-outcomes collect-wa-pilot
.venv/bin/dl-outcomes collect-wa-pilot --destination data/raw/wa/another_vintage
.venv/bin/dl-outcomes build
.venv/bin/dl-outcomes release my-reviewed-release
```

Cached snapshots are hash-checked and never overwritten. Changes to the configured query require a new vintage. A frozen release bundles the exact source inputs, configs, pipeline, contracts and curated outputs. The command creates a local artifact; it does not publish or push anything. Frozen release IDs cannot be reused.

For larger analytical extracts:

```bash
.venv/bin/python -m pip install -r requirements-analytics-lock.txt -e .
.venv/bin/dl-outcomes export-analytics --destination data/releases/analytics_v1
```

This exports separate typed Parquet tables and a DuckDB database. Keep large future source snapshots/bundles in versioned artifact storage and retain their manifests and checksums. Source vintages remain distinct: analyses must explicitly select releases and compatible definitions.

Earlier Texas and five-state checkpoints remain in their original locations. Their integrated records retain closures, future proposals, funding/content candidates, continuity reviews and source-specific design dates. California's historical CDE school leads and Oregon's related language-class listings remain screening evidence rather than extra confirmed programs. The five national seed CSVs have standardized headers and whitespace; their original bytes and migration checksums are in [the legacy snapshot](data/raw/legacy_registry/pre_schema_v1/manifest.json).
