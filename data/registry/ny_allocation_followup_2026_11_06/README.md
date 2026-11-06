# New York school-specific allocation review

This follow-up reviews all 200 primary hosts in the original NY inventory, including 187 NYC Language Allocation Policies for 2025–26. See the [findings and current coverage](../../../docs/status/NY_ALLOCATION_FOLLOWUP_2026_11_06.md).

- `baseline/` freezes the original NY JSON inputs and first-pass school/programme exports before this pass. These are historical comparison files, not current inputs.
- `school_reviews.json` records one review per original primary school, with attempted sources, archived evidence, methods and unresolved questions.
- `review_decisions.json` records reviewed school/strand allocation selections. Original city language labels and programme IDs are preserved; explicit source refinements stay attached to observations.
- `discovery_leads.json` separates later or insufficiently verified hosts from the reference inventory.
- `retrieval_log.csv` records the additional public acquisitions, including searches, failed requests and sign-in responses. A successful HTTP response alone is not programme evidence.

Current inputs and CSVs remain in [the six-state registry](../mid_atlantic_ct_2026_11_05/README.md). New source snapshots are in [the follow-up raw archive](../../raw/ny_allocation_followup_2026_11_06/), and the shared source index links their URLs and checksum metadata. Full original annual plans are retained, alongside searchable text extractions. Incidental assessment material in a source is not imported as outcome data.

`classification_method` distinguishes documented policies, inferred kindergarten subject distributions and inferred language cycles. Source passages, source dates, grade scope, service scope and assumptions accompany each new allocation in the reviewed programme JSON. The [allocation CSV](../../reports/ny_allocation_followup_2026_11_06_allocations.csv) provides these selections in a readable view. Inferences are approximate; English-only supplements, period lengths and pupil services can affect actual exposure.

Schema 1.4.0 adds `inferred_plan` and `conflicting_documented_plan` schedule statuses, `researcher_inference` allocation evidence and `inferred` claim verification. It preserves the 28-table structure. These additions keep estimates and contradictory published models distinguishable in CSV, Parquet and DuckDB.
