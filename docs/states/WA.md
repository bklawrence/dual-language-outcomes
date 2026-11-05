# Washington national-model pilot

The [elementary model-availability audit](../status/ELEMENTARY_ALLOCATION_AUDIT_2026_11_04.md) adds dated school-grade context: the 2025–26 working set contains **126 elementary-serving schools and 49 secondary-only schools**. All 126 elementary schools have a published numerical model label. This is 100% elementary **model-label availability**, distinct from verified K-programme grades or timetables.

The structural records are available as checked-in CSVs: [all 1,002 annual source rows](../../data/registry/washington/wa_programs.csv), [195 DL rows across 175 schools in 2025–26](../../data/registry/washington/wa_dl_programs_2025_26.csv), and [field/provenance notes](../../data/registry/washington/README.md). Rebuilding is offline. The [K-coverage school view](../../data/reports/washington_kindergarten_allocation_coverage_2026_11_04.csv) retains secondary candidates and unknown grade scopes.

The earlier **100%** meant every listed 2025–26 DL school had an annual model label. It did not establish kindergarten allocation coverage. The current K denominator remains unknown for these 175 schools because the source does not report programme grades; the revised percentage is blank, not 0% or 100%. See the [denominator rules](../status/KINDERGARTEN_ALLOCATION_COVERAGE_2026_11_04.md).

Three public OSPI/Socrata snapshots are saved with exact query, retrieval time, row count and SHA-256:

| Source | Native dataset | Pilot selection |
|---|---|---|
| Language programs | `d4w4-82bk` | All school-level source records returned for 2023–24 through 2025–26; includes separately classified heritage/tribal records |
| Academic assessment | `9fjj-2374` | Beacon Hill International and John Stanford International; grades 3–5, SBAC, three school years, selected all-student/EL/non-EL groups |
| Enrollment | `rxjk-6ieq` | The same two schools and three years, all returned grade rows |

The saved snapshots contain 1,002 program-source rows, 108 academic-source rows and 42 enrollment-source rows. The academic adapter preserves nine published rate fields and four count fields, producing 1,404 observations. Enrollment preserves 17 count fields and three explicitly derived shares, producing 840 observations. These counts are not independent student samples.

The program source reports an instructional language and annual design/model labels. It does not explicitly identify a second language or a grade-by-grade entering-cohort schedule. The migration therefore preserves each reported language and does not add English automatically or decompose model labels into language-specific shares. Related heritage/tribal categories are retained as school-level screening evidence; their classification is not an automatic permanent exclusion of immersion eligibility.

Source school/district organization IDs and school codes remain strings in the dated identifier crosswalk. Annual names/affiliations remain evidence. School/language program candidates are provisional, not independently verified unique continuing programs. No NCES match is fabricated.

The two outcome schools have multiple language candidates. Schoolwide assessment/enrollment observations remain stored once, with separate context links to candidate sites. English learner subgroups are not treated as DL participants. Native source population and grade labels remain alongside canonical grade codes. Assessment language/test version are unknown where the source selection does not explicitly specify them.

Academic percentages are published as fractions and normalized to 0–100 percent with the original fraction retained. Tested/expected counts remain separate; the migration does not assume a proficiency denominator where source definitions or revision history require further review. Low-income counts retain the native OSPI label and are not silently harmonized to FRL. Enrollment-derived shares use matching source-row counts and retain their formula.

This is a longitudinal **two-school outcome pilot**, not statewide assessment coverage. Source vintage/retrieval is separate from the performance year. Saved historical revisions remain distinct if another vintage is added; analysts must choose vintages explicitly. DL-participant outcomes, English-language proficiency, exit policies/rates and SEDA remain uncollected in this shared Washington pilot.
