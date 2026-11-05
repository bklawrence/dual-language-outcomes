# November 5 Utah/Texas allocation research inputs

This additive decision packet supports the [follow-up results](../../../docs/status/UT_TX_ALLOCATION_FOLLOWUP_2026_11_05.md). `dl-outcomes build` reads these files offline; it does not fetch district sites.

- `texas_598_targets.csv` freezes the missing-observation cohort from baseline build `build-d18d850ce4e3559eb5c5efc49de9fa7a`. Its checksum is pinned in the migration configuration. It excludes the separate 25 Aldine campuses with earlier-grade proxies.
- `texas_district_targets.json` groups those same campuses into 162 districts and preserves website-discovery leads. Directory domains identify research starting points, not language-allocation evidence.
- `texas_model_decisions.json` contains accepted model labels, exact target IDs, source/grade/year scope, excerpts and attribution limits. District policy is distinguished from named-campus evidence. No language-specific numerical plan is inferred from a model label.
- `texas_review_cases.json` retains unresolved source interpretations and questions. Pending cases add evidence claims, not allocation schedules. A separate question may coexist with a supported model label.
- `texas_research_log.json` records the bounded district-site pass, including successful/failed retrievals, URLs, timestamps, response hashes and limitations. Non-cited pages have receipts rather than committed full archives; a retrieval receipt does not imply a verified programme fact.
- `sources.json` points to the immutable [cited snapshots](../../raw/ut_tx_allocation_2026_11_05/) and metadata, including the newly downloaded Utah roster. `extractions/` contains reproducible derived text from embedded JSON page content. The HTTP source and derived text have separate hashes; rendered DOM snapshots are labelled in metadata.

The user-authorized Utah rule and source roles are in [the migration configuration](../../../config/research_migrations/ut_tx_allocations_2026_11_05.json). The fresh roster is byte-identical to the earlier 2026–27 snapshot, which permits reusing the existing extraction. A different PDF hash stops the build until it is re-extracted and reconciled.

Use a new dated research packet for another collection wave. Preserve the starting cohort, original sources, unresolved cases and source periods when recording later resolutions. Source capture dates are not operating years. Proficiency data remain outside this work.
