# Texas staff-directory delivery review — November 7, 2026

This pass screens all **1,610 Texas campuses / 1,863 program-site records in 196 districts** already in the inventory. It adds **14 provisional strand classifications, covering 16 existing program-site records**, and retains **8 ambiguous campus cases** for follow-up. The two program records at Central Elementary and at Jesus Moroles are existing one-way/two-way records; they are not extra schools. No school or program is added.

The scope is the inventory, including historical and unverified candidates, rather than a census of currently operating Texas DL schools. A staff label does not resolve a candidate's DL eligibility or confirm operation in 2025–26.

## Files

- [Campus audit](campus_audit.csv): one row for every campus, discovery URLs, retrieval counts, access outcomes, pagination limits and the adjudicated outcome.
- [Access log](access_log.csv): URL/capture-level receipts, actual access times, HTTP outcomes, saved-body hashes and repository archive paths where retained. A blank archive path means the body is not preserved in this evidence package.
- [Decision CSV](decisions.csv) and [reviewed observations](observations.json): source fragments, campus/program keys, interpretation, grade scope and separate source/reference dates.
- [Cases for review](review_cases.csv): source links, the unresolved issue and the reason no model was assigned.
- [Summary](summary.json), [frozen campus targets](campus_targets.json) and [discovery mappings](mapped_campus_leads.json.gz). Mapping candidates are leads, not accepted identity changes.
- [Source register](sources.json) and `evidence/`: 22 staff/grade-team sources supporting decisions or ambiguous cases, plus five TEA school-web-directory responses used only to locate campus websites. Bodies are losslessly compressed, with hashes and capture metadata. Staff-source text extractions accompany the original bodies.
- [Vetted staff links](vetted_staff_leads.json): individually checked campus links supplied to Fieldnotes; broad automated name matches are not exported as vetted evidence.

## Coding rule and review

The researcher supplied the rule that distinct monolingual and bilingual program staff support strand delivery. This pass also recognizes explicit general-education/regular-program and bilingual/DL academic classroom assignments, including separate self-contained classrooms. It uses academic roles, rather than staff language skills, bilingual certification or support services.

The reviewed campuses are Montana Vista, Red Sands, Desert Hills and Carroll T. Welch in Clint ISD; Gabe P. Allen, W. A. Blair, John W. Carpenter, Jesus Moroles, Reinhardt, Central and Personalized Learning Academy at Highland Meadows in Dallas ISD; Sam Rosen and Manuel Jara in Fort Worth ISD; and Laura Welch Bush in Pasadena ISD. Each campus identity and the source's actual classroom role labels were checked individually. The claims preserve the exact relevant role fragments without adding individual staff names to the coding notes. Highland Meadows explicitly distinguishes classroom 3A's Bilingual Group from classroom 3D's General Ed assignment; an ESL title alone is not the basis of its classification.

These descriptions support a **researcher interpretation of strand delivery**; the source need not literally use the word “strand.” The new observations are provisional. Their presence does not make strict documented-only coverage complete, and Fieldnotes can continue to present provisional values for confirmation. They are research observations, not human Fieldnotes submissions, and add no leaderboard credit.

No assignment is made from generic “teacher” beside “bilingual teacher,” an English partner within DL, preschool-only bilingual staffing, specials/ESL/special-education staffing, a school name, an inaccessible directory or the absence of a monolingual label. Secondary schools remain in the audit, but English-subject teachers alone do not establish non-DL program participation. An absence of qualifying labels never implies whole-school delivery.

Cottonwood Creek's “DL Support (Mono)” could be the English partner within DL. Frank Macias and Arturo Salazar show preschool evidence that does not establish separate K–5 programs. Parkview's explicit monolingual role is also confined to preschool; its kindergarten page has a Vietnamese BIL label and otherwise unlabelled teachers. Natha Howell has an explicit regular-program role without a matched academic bilingual role. Harry C. Withers, Alex Sanger and Justiss have suggestive parallel-program navigation, but the linked descriptions failed to load. These remain review cases.

## Dates and preservation

The user authorized a clearly marked 2025–26 inference from a directory dated 2026–27. The sources supporting this pass's codes are **undated rosters captured November 7, 2026**. Their actual capture dates remain intact. A site copyright, district budget year or general navigation date is not assigned to a roster as its publication year.

Current staff descriptions are used as provisional retrospective structural evidence **for 2025–26 only**. They do not establish the actual 2025–26 staffing, historical student exposure, earlier models or continuing annual operation. The reviewed reference window is a selection bound, not a program start/end date. The original observations remain in the history; allocation, population model, languages, operation, eligibility, assessments and earlier/later reference selections are preserved. Human Fieldnotes decisions retain precedence.

An empty earlier reference can now be flagged `later_only` instead of `not_reported`, because later evidence exists. Its selected value and evidence remain empty; this is a missingness explanation, not a historical classification.

## Acquisition limits and reproducibility

The pass uses the public TEA 2024–25 web directory, previous district-navigation leads, current campus pages, staff directories and linked grade-team pages. Normal browser rendering was tried for dynamic navigation and inaccessible pages. Access errors and blocking were retained; no CAPTCHA or authentication barrier was bypassed. Search results and two Wisconsin method controls are excluded from Texas evidence and counts.

**An inventory-wide screen is not an exhaustive reading of every staff roster.** Many links fail, redirect to district portals or expose only generic job titles. Some directories are paginated or image-based. In particular, simple pagination requests for Red Sands and C. T. Welch repeated page one. The accessible first page already supplies positive academic roles, but the audit does not pretend those requests retrieved every constituent. Uninformative and inaccessible cases remain unresolved, with usable follow-up links retained.

Staff/grade-team leads were attempted for 850 campuses. Pages were retrieved for 585; 455 had automatically campus-matched staff text, which still requires interpretation. The 22 positive/ambiguous cases were individually reviewed. For the other 760 campuses, this pass did not retrieve a staff lead; 95 had only an accessible candidate campus page, and 665 had unresolved campus links or access. These are acquisition gaps, not proof of a particular delivery model.

The full acquisition workspace is not checked into Git. The evidence needed for every positive decision and selected ambiguous case is archived here; access-only receipts for other pages are not canonical evidence of a program's absence.

`scripts/collect_texas_staff_directories.py` can collect and rescan public pages into a separate cache. It never assigns delivery models. Its `homes`, `discover`, `urls --file …`, `enrich` and `staff-followups` stages preserve bodies and access metadata. Use a new cache for a new research vintage. Optional `--legacy-discovery-cache` reads previously saved district navigation.

`python scripts/build_texas_staff_directory_audit.py --cache CACHE` freezes the access/campus audit from that workspace and the separately adjudicated observations. The canonical build is offline: `dl-outcomes build` followed by `dl-outcomes validate`. Regression checks cover source quotes and hashes, campus/program identities, the complete target roster, ambiguous cases, human-review separation, other variables and reference-year limits.
