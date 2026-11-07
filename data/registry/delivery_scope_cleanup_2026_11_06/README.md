# Whole-school / strand delivery review

This pass investigates delivery structure among existing elementary programme
sites that already have a selected numeric language allocation. The fixed
pre-pass live cohort contains 1,906 programme sites at 1,742 schools. It includes
source-reported ratios requiring further allocation review; it is not a census
of all US DL schools. Secondary-only sites are excluded from this work queue.

`observations.json` contains 42 manual programme-site decisions at 35 schools:
11 whole-school and 24 strand schools. Every decision has a source quote,
locator, campus identity, method, grade context and reference-use bound.
`sources.json` identifies primary source bytes and extractions. Existing NYC CEP
and Austin archives are reused rather than relabelled as new collections.
`review_cases.json` records unresolved district-wide scope questions.

Whole-school means that the campus student body receives academic DL. A campus
can offer alternative Spanish and Japanese DL pathways and still satisfy that
definition; this does not make the entire student body participants in each
individual language track. Explicit parallel DL and monolingual programmes
support strand coding. Admissions choice, a lottery, a bilingual school name,
a language ratio, an English-speaking teacher in a side-by-side DL model, or
stand-alone ENL services alone do not establish strand or whole-school delivery.
Special education/ICT classes can themselves be DL.

The decisions are reviewed for **2025–26 only**. Dated CEPs remain dated 2025–26;
undated standing campus descriptions remain undated. A current description and
the absence of an announced change do not establish historical tested-grade
participation. No new decision is eligible for the spring 2025 (2024–25) or
earlier proficiency analyses, or carried forward into a later reference without
another review. An upper reference-use bound does not assert a programme end
date. The Academy for Global Citizenship's earlier
provisional strand observation survives alongside its current explicit
all-student DL description; the transition date is not established. Reilly's
2026–27 move remains separate from its predecessor's 2025–26 scope.

`cohort.json` freezes the live pre-pass work queue. `preservation.json` checks
all prior canonical evidence and assessment/context rows plus archived reports
and the frozen national baseline. `original_keys.json.gz` identifies the exact
pre-pass rows, so this audit can permit evidence appended by later research.
`before_non_delivery_fields.json` provides
field-specific checks that allocation, language, population, grade and operation
selections did not change. Source screening counts are explicitly distinguished
from manually adjudicated campus decisions in `screening.json`.

Rebuild offline with `dl-outcomes build`. Current decisions, a school-level
comparison, state coverage, remaining queue and review cases are generated under
`data/reports/delivery_scope_cleanup_2026_11_06*`. Earlier report receipts are
preserved; changed derived versions are written to the new `revised/` directory.

All-student achievement still requires whole-school scope appropriate to the
assessment year and tested grades. EL subgroup outcomes may include strand
schools, but the subgroup does not identify DL participants. A structural
classification alone does not demonstrate student exposure or causal effects.
