# Washington national-model pilot

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
