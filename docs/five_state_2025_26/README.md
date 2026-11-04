# Five-state inventory: 2025–26 confirmation pass

Research recheck: **November 4, 2026**. “2025” is interpreted as **school year
2025–26**. This additive snapshot preserves the earlier 2026–27 research files.

The revised inventory contains **338 school–program records**, including
candidates, closed programs and a future opening. **269 qualifying programs are
confirmed for 2025–26 under the requested rule: 26 with year-specific evidence
and 243 by continuity after targeted change/closure review.** The larger confirmed
count reflects the revised reference year and confirmation rule, not measured
growth in program provision.

## Confirmation rule

The user authorized confirmation when an established program has an older or
undated description and targeted research finds no indication it ended. This
pass applies that rule and labels it `continuity_no_end_indication`. It does not
present the absence of an ending report as a government certification or a newly
observed classroom. Each continuity assessment links to a saved review with its
queries, sources read, outcome, and limitations.

`confirmed_2025_26` is the operating-status value; `confirmation_basis` separates
explicit year offerings, contemporary reporting/announcements, a reference-year
charter offering, and continuity. **Older kindergarten allocation evidence does
not prevent confirmation of program operation.** Conversely, confirmation of
operation does not establish an unknown ratio or refresh the date of an older
school-structure description.

The rule does not automatically establish that a proposal opened, that a language
elective is academic immersion, or that a privately operated program meets the
public-funding criterion. `inclusion_status`, `instructional_scope`, and
`public_funding_status` retain these separate questions. Candidates are excluded
from qualifying confirmed totals, even if their school or pathway listing has
current-year evidence.

## Results and files

| State | Inventory | Records | Confirmed qualifying programs |
|---|---|---:|---:|
| Wyoming | [CSV](../../data/registry/state_dl_programs_wyoming_2025_26.csv) | 13 | 11 |
| Montana | [CSV](../../data/registry/state_dl_programs_montana_2025_26.csv) | 9 | 5 |
| Idaho | [CSV](../../data/registry/state_dl_programs_idaho_2025_26.csv) | 18 | 18 |
| Nevada | [CSV](../../data/registry/state_dl_programs_nevada_2025_26.csv) | 6 | 5 |
| California | [CSV](../../data/registry/state_dl_programs_california_2025_26.csv) | 292 | 230 |

[Coverage report](COVERAGE_REPORT.md) provides the direct/continuity breakdown,
essential-field completeness, kindergarten models, and language counts. There
are **231 supported kindergarten allocations, 34 structure classifications, and
30 records with all five fields**, subject to their documented temporal limits.
Later-only 2026–27 schedules are not backdated. This remains a partial inventory;
no statewide completeness or coverage percentage is established.

[Montana review](MONTANA_REVIEW.md) distinguishes academic immersion, separate
language/culture specials, funding uncertainty, and closures. [Change findings](CHANGE_FINDINGS.md)
explains model changes, relocations, nonreopening, and unrelated closure leads.

Supporting files are in [data/registry/five_state_2025_26](../../data/registry/five_state_2025_26/):

- `evidence_ledger.csv`: **3,480 attribute claims**, with source dates, applicable
  years, excerpts/paraphrases, classification, and conflicts.
- `continuity_reviews.csv` and `.json`: **37 district/operator review scopes**
  containing **53 distinct search queries**.
  The JSON preserves full structured query results and program membership.
- `change_search_results.csv`: discovery/screening results, clearly separated
  from substantive source evidence. Automated search summaries were not used
  to establish program attributes.
- `change_events.csv` and `.json`: **29 sourced program-level findings**,
  distinguishing actual changes from unresolved dates and classification gaps.
- `sources.csv` and `source_index.json`: **115 registered source documents**,
  including reused first-pass sources and new documents. Not every registered
  source directly supports a program attribute; some support screening/context.
- `curated_claims.json`: reproducible curation input, preserving earlier claims
  and the new assessments. Historical 80/20 evidence is retained alongside the
  dated SFUSD change rather than silently erased.
- `kindergarten_instruction_languages.csv`: normalized selected K shares.
- `coverage_summary.json`, `language_pairing_counts.csv`: machine-readable counts.
- `fresno_roster_crosswalk.csv`: all **25** 2025–26 source rows reconciled to
  **24** programs, merging Wawona elementary/middle grade sections. The original
  official PDF is retained in `source_snapshots/` with a checksum.
- `validation_results.json` and `research_status.json`: completed-pass status.

The 24 added records comprise 21 Fresno Spanish pathways, Afflerbach in Wyoming,
Hardin Primary's new Montana classroom, and the closed Chickadee Lodge school.
They are not 24 newly opened qualifying programs. The existing historical CDE
screening roster still supplies at least 1,310 California school leads; it is not
added to the curated program count.

## Reading the data

School–program IDs are stable research keys, not official program identifiers.
Official California CDS IDs are retained where previously matched; identifiers
for new schools remain blank unless verified. Distinct languages/tracks at the
same campus remain separate. Reference-year operating status, primary source
publication date, applicable school year of each claim, and field applicability
are separate columns.

`previous_inventory_status_2026_27`, `previous_kindergarten_allocation`, and
`previous_inventory_notes` permit comparison with the first pass; they do not
describe the new reference year. `allocation_change_notes` explains resolved
temporal changes; `allocation_conflict_notes` explains unresolved schedules.
`later_documented_kindergarten_allocation` preserves useful later evidence
without selecting it for 2025–26. A range in `kindergarten_share_ranges_json`
does not supply a selected point allocation.

Unknown or empty percentages are not zero. A middle/high-school continuation
does not inherit an elementary K ratio. Nk̓ʷusm's curriculum-category percentages
are not language-time percentages. Closed/future programs and unresolved
content/funding candidates remain available for audit and filtering.

## Validation and reproduction

From the repository root, with standard-library Python:

```sh
python3 scripts/build_five_state_inventory_2025_26.py
python3 scripts/validate_five_state_inventory_2025_26.py
python3 -m unittest discover -s tests -v
```

Data validation and **all 12 regression tests passed**. Checks cover duplicates,
source identity, required field evidence, valid models/percentages, reference-year
evidence, continuity-review scope, closure/future exclusions, curriculum-share
misclassification, later-year backdating, and source-count reconciliation.
The exporter does not rerun network research. The earlier 2026–27 files remain
unchanged; nothing was pushed, merged, or published.

The change search is bounded: district/operator and selected campus/language
queries, with likely official and news documents inspected. It is not a complete
search of every board packet or school archive. Search-service failures and
unavailable pages are not treated as proof of no closure. Most remaining gaps
are secondary content-course scope, Indigenous-program funding/grade coverage,
school structure, and uncollected districts in the historical California leads.
