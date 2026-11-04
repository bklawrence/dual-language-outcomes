# Dual-language outcomes

A longitudinal research dataset for dual-language programs across all **50 US states**, including all instructional languages. The national model separates school/program histories from three assessment layers: DL-participant reports, state assessments and context, and Stanford SEDA estimates.

**Current status: a validated national structure with Illinois seed data and Texas/Washington pilots.** State configurations and coverage tracking include all 50 states. This is not a completed national program census. ELP assessments, EL exit policies/rates and SEDA have contracts and empty tables; they have not yet been collected into this pipeline.

## Start here

- [Architecture and interpretation](docs/methods/NATIONAL_DATA_MODEL.md)
- [Table contracts and data dictionary](schemas/README.md)
- [State/year/layer coverage](data/curated/coverage/state_year_layer_coverage.csv)
- [Allocation coverage by state](docs/status/ALLOCATION_COVERAGE_2026_11_04.md)
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

`build` is offline and deterministic for the saved input/config/code bytes. It creates all contract tables, including headers for uncollected layers, and validates them. `validate` checks source hashes, reporting grain, populations, identities, dates and attribution. It does not independently verify every reported research claim.

The pilot currently contains eight Texas subject results from four published one-way-DL/current-EL reporting groups, plus Washington school-level academic and enrollment observations for two multilingual elementary schools across 2023–24, 2024–25 and 2025–26. Washington program metadata covers a broader set of schools and preserves related heritage/tribal records for review. Program evidence groups are not verified distinct program counts.

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

The checked-in small public snapshots are sufficient to rebuild the pilot. A new acquisition must use a new vintage directory:

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

Earlier Texas and five-state checkpoints remain in their original locations. The five national seed CSVs have standardized headers and whitespace; their original bytes and migration checksums are in [the legacy snapshot](data/raw/legacy_registry/pre_schema_v1/manifest.json).
