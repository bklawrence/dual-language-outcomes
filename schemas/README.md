# National table contracts

The machine-readable source of truth is the packaged [JSON Schema catalog](../src/dl_outcomes/schemas/catalog.json), version **1.0.0**, using JSON Schema Draft 2020-12. Packaging the contract with the code lets installed commands validate the same schema as a checkout.

Each `$defs` entry describes one table row and includes its output path, primary key, additional uniqueness constraints and foreign keys. All CSV headers are required and ordered; additional columns require a contract change. Empty cells become JSON null for validation. Numeric columns are converted explicitly; identifier columns remain strings, preserving leading zeros. An uncollected table contains its complete header and no fabricated rows.

Current schema: **1.2.0**, with 28 tables. `program_status_history` separates reference-year operation/eligibility from source-dated structural choices. `evidence_claims.evidence_period_raw` retains fiscal, multi-year and undated applicability without inventing annual validity. Allocation review qualifiers distinguish model-only, conflicting and composite source evidence from explicit grade plans. Null means a qualifier was not collected, not that the schedule was confirmed. Earlier frozen releases retain their original contracts.

See the generated [data dictionary](DATA_DICTIONARY.md) for every field, enum, key and reference. Regenerate it after changing the catalog:

```bash
python scripts/generate_national_data_dictionary.py
```

The six observation tables share exactly the same column contract. Their physical separation preserves the distinction between DL participants, state academic results, enrollment context, English-language proficiency, actual EL exits and SEDA estimates. The latter four state/context tables belong to the second conceptual assessment layer; they do not create new definitions of DL participation.

Cross-table rules in [validation.py](../src/dl_outcomes/validation.py) additionally check population scope, source-grain uniqueness, masked values, rate denominators, reporting-unit attribution, time-dependent identifier ambiguity, named-language allocation totals and source/code/output hashes. Schema validity alone is not factual verification of a published value.

The dictionary is descriptive; edit the JSON catalog and adapters, not generated curated CSVs. A reviewed schema change must rebuild the tables, update the dictionary and run validation/tests. Preserve earlier frozen release contracts with their original source/code bundles.
