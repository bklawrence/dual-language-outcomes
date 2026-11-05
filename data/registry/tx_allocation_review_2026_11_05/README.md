# Texas allocation user review, round 1

These are the additive inputs for the [review results](../../../docs/status/TEXAS_ALLOCATION_REVIEW_2026_11_05.md).

- `decisions.json`: exact existing programme sites receiving a model, including population type, classification language family, user/inference/source basis, donor IDs, original donor quality, grade scope and limitations.
- `case_resolutions.json`: the current outcome for each of the original fourteen cases. An unresolved data question is distinguished from a pending approval request.
- `sources.json`: original saved public sources, the preserved legacy claims used as donors, and one newly saved Denton programme-family page. Reused snapshots are referenced without rewriting their bytes.
- `retrieval_receipts.json`: current checks of donor citations, including unavailable original Denton/Irving links. A failed citation does not erase the old reported label, and an inference from that label does not make it a newly confirmed fact.

The [configuration](../../../config/research_migrations/tx_allocation_review_2026_11_05.json) preserves the user's instructions and freezes earlier report/decision bytes. The build validates each assignment against the existing school, programme type and any known language evidence. It rejects secondary-only hosts, changed identities, different languages, different population models and ambiguous model choices.

School-year applicability and exact kindergarten time allocations are not inferred. Neither programme-language observations nor historical operating statuses are overwritten. Current reports use the `2026_11_05_reviewed` edition; the original November 5 checkpoint remains intact.
