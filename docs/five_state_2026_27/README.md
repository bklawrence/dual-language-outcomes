# Five-state dual-language inventory, 2026–27

Research date: **November 3, 2026**, America/Chicago. Public sources were accessed
November 4 UTC. Branch: `research/five-state-inventory-2026-27`.

This research collected **314 school–program records across all five states**,
including explicitly flagged candidates, a discontinued program, and a future
opening. It establishes **16 qualifying programs with explicit 2026–27 evidence**.
It does **not** establish a complete statewide census. Most live district
directories do not identify the applicable school year, and whole-school/strand
evidence remains sparse. Read [the coverage report](COVERAGE_REPORT.md) before
using record counts as estimates of current provision.

Public internet access now works. The earlier [access-blocked checkpoint](RESEARCH_STATUS.md),
`source_access.csv`, and `research_status.json` are preserved historical artifacts;
they are superseded by this README and `research_status_resumed.json`.

## Deliverables

| State | Inventory CSV | Records |
|---|---|---:|
| Wyoming | [Wyoming](../../data/registry/state_dl_programs_wyoming_2026_27.csv) | 12 |
| Montana | [Montana](../../data/registry/state_dl_programs_montana_2026_27.csv) | 7 |
| Idaho | [Idaho](../../data/registry/state_dl_programs_idaho_2026_27.csv) | 18 |
| Nevada | [Nevada](../../data/registry/state_dl_programs_nevada_2026_27.csv) | 6 |
| California | [California](../../data/registry/state_dl_programs_california_2026_27.csv) | 271 |

Supporting files are under [data/registry/five_state_2026_27](../../data/registry/five_state_2026_27/):

- `evidence_ledger.csv`: one row per attribute claim, including source date,
  applicable school year, excerpt/paraphrase, classification, and conflicts.
- `sources.csv`: public source URLs, titles, types, access times, and hashes;
  `source_index.json` is its curated input.
- `curated_claims.json`: reproducible input records and their attribute claims.
- `kindergarten_instruction_languages.csv`: normalized language-share rows;
  the inventories also preserve the complete schedule as JSON.
- `coverage_summary.json` and `language_pairing_counts.csv`: exact report counts
  and denominators, including non-Spanish languages.
- `california_school_candidates_2024_25.csv`: **1,310 historical school leads**,
  not additional confirmed programs. The original CDE workbook is retained in
  `source_snapshots/` with its checksum.
- `lausd_directory_snapshot.csv`: 211 public source rows, reconciled to 209
  distinct program records. No private student information was collected.
- `screening_decisions.csv`: consequential exclusions and unresolved scope.
- `validation_results.json`: final program-data validation result.

[Research notes](RESEARCH_NOTES.md) explain source quality, conflicts, and the
highest-priority gaps in each state. [Coverage report](COVERAGE_REPORT.md) supplies
all required counts, kindergarten distributions, and language breakdowns.

## Schema and interpretation

The additive `state_dl_programs_<state>_2026_27.csv` files follow the existing
registry naming convention. The assignment's `kindergarten_allocation` maps to
Oregon's `instructional_allocation`, restricted here to the kindergarten starting
schedule. `school_structure` maps to `program_structure`; `program_type` records
one-way/two-way organization separately. Existing state collectors and datasets
were not changed.

One row is a school and distinct program, not a school, student cohort, or
achievement record. Separate languages and separately identified one-way/two-way
tracks remain separate. `program_name_is_working_label=yes` identifies research
labels rather than claimed official program names. Grade spans describe the
source evidence and are not automatically promoted to verified 2026–27 spans.

`program_id` and `school_research_id` are provisional research keys. Official
IDs remain blank when unverified. Matched California school IDs use the
14-digit `CA_CDS` namespace; matching required a unique normalized district and
school name while retaining elementary/middle/high distinctions. No NCES or
district identifiers were fabricated.

Use **both** eligibility and operating status when filtering:

- `inclusion_status` starting `documented_` establishes qualifying content
  instruction from the cited evidence. `candidate_` requires the stated follow-up.
- `confirmed_2026_27` requires applicable current-year evidence. A candidate can
  have a confirmed-year DLI listing while its content scope or language track
  remains unresolved; it is excluded from qualifying confirmed-program counts.
- `probable_current_unconfirmed` preserves plausible programs on live undated
  pages. `historical_status_unknown` does not establish present operation.
- `confirmed_discontinued` and `planned_future` are retained for audit and
  excluded from operating-program distributions.

`evidence_level` describes the primary source; the ledger is authoritative for
individual attributes supported by different sources. Publication dates and
applicable school years are distinct. Empty percentages mean unresolved, not
zero. Unknown structure does not mean strand or whole-school.

An official conventional 90/10, 80/20, or 50/50 model supports the kindergarten
starting allocation. An explicit kindergarten schedule overrides a general
label. Pre-K and later-grade shares never substitute for kindergarten. Conflicts
are recorded instead of silently resolved. “Other” retains actual percentages.

## Validation and reproduction

The exporter uses only the standard library and retained curated inputs; it does
not repeat network collection. From the repository root:

```sh
python3 scripts/build_five_state_inventory_2026_27.py
python3 scripts/validate_five_state_inventory_2026_27.py
python3 -m unittest discover -s tests -p 'test_five_state_inventory_validation.py' -v
python3 scripts/validate_texas_pass48.py
```

Validation passed for all records and evidence links, allocation percentages,
model labels and conflicts, current-year evidence, identifiers, normalized
language shares, retained workbook checksum, and source-row reconciliation.
Six regression tests passed, including deliberate duplicate, invalid-share,
false-current-status, missing-model, and wrong-source corruptions. The existing
Texas snapshot/linkage validation also passed.

Automated checks establish internal consistency, not statewide completeness or
independent truth of every source. Kindergarten and structure classifications
were reviewed against source excerpts; unresolved cases remain explicit. No
changes were pushed or merged, and the environment draft was not changed or
published during this research run.
