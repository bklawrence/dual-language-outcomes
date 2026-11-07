# Delivery-structure cleanup, November 6, 2026

The first campus-scope pass adds **42 reviewed programme-site observations at
35 schools** that already have a numeric language allocation. Eleven schools
are whole-school DL and 24 contain DL strands alongside other instruction.
Every decision is accompanied by source text, a locator, a review method and
grade/reference context in the [decision CSV](../../data/reports/delivery_scope_cleanup_2026_11_06_decisions.csv).

| State | Schools resolved | Whole-school | Strand |
| --- | ---: | ---: | ---: |
| New York | 22 | 3 | 19 |
| Texas | 6 | 4 | 2 |
| California | 3 | 0 | 3 |
| Washington | 2 | 2 | 0 |
| Illinois | 1 | 1 | 0 |
| Wisconsin | 1 | 1 | 0 |
| Total | 35 | 11 | 24 |

Among the fixed live cohort's **1,742 schools / 1,906 allocation-bearing
programme sites**, schools with documented delivery for every allocation-bearing
site increase from **430 (24.68%) to 465 (26.69%)**. Another **1,277 schools**
remain incompletely documented. This denominator differs from the earlier
proficiency analysis's subset with usable assessment results. It also differs
from the frozen national baseline because the live cohort includes prior gap
pilot allocation additions. These figures describe research completeness, not
the prevalence of DL or a complete national school census.

The strongest distinctions are explicit campus descriptions. Wharton in Houston
says 100% of its pupils participate. Alice Contreras in Fort Worth describes
regular and DL programmes. LAUSD's Kingsley profile names an English strand
and a DL programme; Richland names French immersion and an English programme.
New York CEPs describe actual classroom composition, including parallel
monolingual classes at P.S. 189 and all-DL classrooms at Cypress Hills, Dos
Puentes and Castle Bridge. General-education or ICT classes can themselves be
DL, so those labels alone were not treated as non-DL instruction.

John Stanford and McDonald in Seattle illustrate why an individual language
pathway differs from campus-wide DL participation: all pupils receive DL, with
alternative Spanish and Japanese pathways. Such a classification does not
attribute every child's achievement to each individual language track.

The [review cases](../../data/reports/delivery_scope_cleanup_2026_11_06_review_cases.csv)
retain limits on district-wide inference. Dallas and Fort Worth programme
documents do not provide a campus delivery crosswalk. Palm Beach's CAL entry
checks both whole-school and strand delivery. Voluntary applications, lotteries
and limited places do not by themselves distinguish a strand from an entire
choice school. Scope therefore remains unresolved where the source only
describes the programme, rather than who at the campus receives it.

The new selections apply to **2025–26 only**. Source school years, publication
dates, undated descriptions and reference-use bounds remain separate. In
particular, the 2025–26 NYC CEPs have not been backdated into spring 2025
achievement comparisons. Earlier provisional AGC strand evidence is retained;
its current all-student description does not establish a transition date. The
later Reilly move is kept separate from its predecessor's documented scope.
The prior TeX report and its assessment samples remain unchanged.

The migration appends delivery-only configurations and evidence claims. It
preserves language allocations, languages, population models, grade spans,
operation histories, research identities, assessment/context observations, the
frozen baseline and earlier report versions. The assessment collection's
original pinned structural input and code are retained in a
[hash-verified archive](../../data/provenance/edc_v3_1_2022_2025/README.md), allowing
live structural updates without rewriting the assessment collection.

See the [registry guide](../../data/registry/delivery_scope_cleanup_2026_11_06/README.md),
[coverage by state](../../data/reports/delivery_scope_cleanup_2026_11_06_by_state.csv),
[remaining programme queue](../../data/reports/delivery_scope_cleanup_2026_11_06_remaining_queue.csv)
and [source register](../../data/reports/delivery_scope_cleanup_2026_11_06_sources.csv).

Validation passed: the offline build and collection checks, all **341 regression
tests**, and a fresh offline rebuild/release comparison. The latter reproduces
the canonical tables and report receipts from the saved inputs alone.
