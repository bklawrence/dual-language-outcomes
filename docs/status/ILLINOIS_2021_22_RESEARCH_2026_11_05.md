# Illinois historical research and programme changes

The integration adds **144 user-researched rows for 2021–22**, collected from district websites in 2022, while retaining later structural evidence. It also records the user’s IPA and Urbana clarifications. The national working inventory still represents **25 states**. New proficiency collection remains deferred.

## Source and identities

The [source guide and combined CSVs](../../data/registry/illinois_2021_22_user_2026_11_05/README.md) expose the original table, reviewed mappings and historical model labels. The original TSV and both user clarifications are archived with provenance and checksums. Original webpage URLs and webpage publication dates were not supplied.

Of the 144 source rows, 96 reuse existing school identities, including two Talcott aliases for one school. Forty-one rows add historical school units. The other seven unmatched rows remain screening evidence for enrichment, preschool-only provision or missing language. Four matched mixed-language rows remain school-level claims pending verification of instructional strands.

There are 42 new historical programme groups: 41 at additional schools and one Spanish group at Countryside, whose existing tracked group teaches Mandarin. The combined CSVs contain 175 programme-host units and 178 programme records. These counts include historical-only candidates and are not current public-programme counts. The registry retains one additional original school without a programme row.

## Resolved model histories

| Programme | Earlier evidence | Current interpretation |
|---|---|---|
| International Prep Academy (IPA) | 50/50 in the 2021–22 compilation | User confirms an allocation change; the preserved 2025–26 school plan supports 90/10. Exact first change year is unknown. |
| Urbana Spanish | DPW and Leal historical programmes; later undated Yankee Ridge webpage describes 90/10 | Programmes consolidated at Yankee Ridge in 2024–25, with Spanish 80/20 from that year, as confirmed by the user. |
| Yankee Ridge French | 50/50 in the 2021–22 compilation and later district/school description | User confirms 50/50 throughout the programme’s existence. No origin date is inferred. |

The [policy decisions](../../data/reports/illinois_2021_22_user_2026_11_05_policy_decisions.csv) select the supported current model for each of these three programmes. Earlier source descriptions remain recorded. The reference elementary report uses those selections; its all-recorded-history view retains earlier labels.

The [Urbana host lineage](../../data/reports/illinois_2021_22_user_2026_11_05_urbana_lineage.csv) links both Dr. Preston L. Williams Jr. (DPW) and Leal to Yankee Ridge. Their Spanish programme sites end after 2023–24 and have relocation statuses in 2024–25. This records a many-to-one programme consolidation without labelling either school closed or assuming a stable student cohort. Spanish and French remain separate programmes in the same building. The 80/20 entry-model policy does not supply the later-grade progression.

## Elementary information coverage

| Measure | Earlier Great Lakes checkpoint | After historical integration |
|---|---:|---:|
| Confirmed qualifying 2025–26 hosts | 123 | 123 |
| Elementary hosts in the denominator | 104 | 104 |
| Elementary hosts with numerical model information | 48 | 64 |
| Numerical model information coverage | 46.2% | 61.5% |
| Elementary hosts missing numerical model information | 56 | 40 |
| Secondary-only hosts excluded | 19 | 19 |

The historical source supplies model information for 16 already-confirmed elementary hosts. Its 86 numerical model rows retain **2021–22**, even where they fill a current working-inventory information gap. Coverage measures availability across cited periods; it does not certify that each historical policy still operates unchanged in 2025–26. Elementary includes any K–5 grade, including K–8 and upper-elementary combinations. Secondary-only programmes remain in the inventory.

The [current national summary](../../data/reports/structural_inventory_2026_11_05_illinois_2022_by_state.csv), [elementary percentages](../../data/reports/elementary_allocation_coverage_2026_11_05_illinois_2022_reference_by_state.csv) and [school evidence](../../data/reports/elementary_allocation_coverage_2026_11_05_illinois_2022_by_school.csv) use the new report vintage. The earlier [Great Lakes findings](GREAT_LAKES_2026_11_05.md) and dated reports remain preserved as the previous checkpoint.

## Qualifications and follow-up

Historical-only schools still need current-operation checks. The [follow-up CSV](../../data/reports/illinois_2021_22_user_2026_11_05_followup.csv) retains row-specific language, identity, sector and grade qualifications, as well as resolved change notes. An additional listed language does not establish a separate immersion programme. A private/public/charter code is a historical source claim; blanks remain unknown and conflicting codes remain flagged.

All 86 historical numerical schedules remain model labels without invented named-language share rows. Strand/whole-school codes do not establish one-way/two-way participation. School-level codes are grade proxies; Verda’s historical preschool code is not a kindergarten allocation, and Whittier Intermediate’s middle code does not establish exact grades. Reported calendar start years are not expanded into fabricated annual observations.

## Validation

The build audits all 144 source rows, their 86 numerical labels, school/programme mappings, dates and the three current policy selections. It preserves the original Illinois canonical rows, all earlier Great Lakes research inputs, 98 prior dated reports and all 12 existing assessment/context/EL/SEDA outputs. Schema, attribution, offline rebuild and analytical-export checks cover the combined dataset. These checks establish preservation and recorded scope; they do not establish statewide completeness or independently verify every source claim.
