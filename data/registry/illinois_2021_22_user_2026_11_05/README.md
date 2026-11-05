# Illinois: 2021–22 research and later programme corrections

The user compiled district website information in calendar year 2022 and explicitly assigned it to **school year 2021–22**. All 144 original rows and 11 source fields are preserved, including spelling, blanks and codes. Original webpage URLs were not supplied. The source is a user research compilation; the archived bytes do not represent independently retrieved district webpages.

| File | Purpose |
|---|---|
| [il_schools.csv](il_schools.csv) | Combined Illinois inventory, one row per programme-host research unit; 175 rows |
| [il_programmes.csv](il_programmes.csv) | Combined 178 programme records, with source periods and explicit current policy selections |
| [inventory_2021_22.csv](inventory_2021_22.csv) | All 144 original source rows with row IDs and the assigned school year |
| [identity_reconciliation.csv](identity_reconciliation.csv) | Original names/districts, reviewed aliases, school/programme/site IDs, dispositions and later comparisons |
| [historical_models.csv](historical_models.csv) | All 86 numerical model entries from the source; model labels without invented named-language shares |
| [records.json](records.json) | Reviewed row-by-row mappings and decoding used by the offline build |
| [new_schools.json](new_schools.json), [new_programmes.json](new_programmes.json) | 41 additional historical school units and 42 programme groups |
| [codebook.json](codebook.json) | Source codes, reviewed district aliases and interpretation limits |
| [policy_decisions.json](policy_decisions.json) | Explicit current IPA and Yankee Ridge Spanish/French selections |

The [original TSV](../../raw/illinois_2021_22_user_2026_11_05/inventory.tsv), [metadata](../../raw/illinois_2021_22_user_2026_11_05/metadata.json) and [user clarifications](../../raw/illinois_2021_22_user_2026_11_05/clarifications.json) are archived separately. The earlier [Great Lakes registry and reports](../great_lakes_2026_11_05/README.md) remain a preserved checkpoint.

Filter `confirmed_qualifying_2025_26` in the school CSV before reference-year analysis. The confirmed working set stays at **123 hosts**. The 41 new historical school units do not become current confirmations. Numerical model information is available for **64 of 104 elementary hosts (61.5%)**, with actual source periods retained in the [elementary evidence report](../../reports/elementary_allocation_coverage_2026_11_05_illinois_2022_by_school.csv). Secondary-only continuations remain recorded outside that denominator.

Of the 144 rows, 96 match existing schools; two Talcott names share one school/programme identity. Forty-one rows add historical school units. The remaining seven unmatched rows retain enrichment, preschool-only or blank-language screening dispositions. Four matched composite-language rows remain school-level claims without fabricated immersion strands. Countryside’s reported historical Spanish programme remains distinct from its existing Mandarin programme.

Source code `Strand 0/Whole 1` describes delivery structure, not one-way/two-way participation. Blank sector values remain unknown. Source codes identify preschool, elementary, middle, high or elementary-plus-middle; they do not supply exact grades. In particular, a middle-school label does not establish a grade-6 minimum. Reported start years remain calendar-year claims. Numerical model labels do not establish exact kindergarten timetables, daily minutes or tested-cohort exposure.

The latest [findings](../../../docs/status/ILLINOIS_2021_22_RESEARCH_2026_11_05.md), [follow-up table](../../reports/illinois_2021_22_user_2026_11_05_followup.csv), [policy decisions](../../reports/illinois_2021_22_user_2026_11_05_policy_decisions.csv) and [Urbana predecessor/successor table](../../reports/illinois_2021_22_user_2026_11_05_urbana_lineage.csv) explain the dated changes. New proficiency collection remains deferred.
