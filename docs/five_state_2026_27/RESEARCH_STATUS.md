# Five-state dual-language inventory: access-blocked checkpoint

Assignment research date: November 3, 2026. Reference school year: 2026–27.
Branch: `research/five-state-inventory-2026-27`.

The requested program research could not begin because the running environment's
network proxy denied access to all five state education-agency sites. No source
page content was retrieved, no program classifications were made, and no
statewide completeness claim is possible. This checkpoint is **not a completed
inventory**. The lack of collected records is not evidence that a state has no
qualifying programs.

## Observed access results

Read-only HTTPS HEAD requests used the inherited environment proxy and normal
certificate verification. Each failed with
`<urlopen error Tunnel connection failed: 403 Forbidden>`.

| State | Official agency entry point attempted | Result | Program records collected |
|---|---|---|---:|
| Wyoming | https://edu.wyoming.gov/ | Proxy denied connection | 0 |
| Montana | https://opi.mt.gov/ | Proxy denied connection | 0 |
| Idaho | https://www.sde.idaho.gov/ | Proxy denied connection | 0 |
| Nevada | https://doe.nv.gov/ | Proxy denied connection | 0 |
| California | https://www.cde.ca.gov/ | Proxy denied connection | 0 |

The managed runtime reports current, enforced **restricted** networking, with
the package-manager preset and no custom allowed hosts. This is a connection
denial by the environment proxy, not a finding that the agencies lack
directories or that a particular school program does not exist. No web-search
or browser tool is exposed in this session to supply an independent research
route. Private credentials are not required to investigate these public sites.

## Coverage and source quality

For **each of the five states**, candidate-school counts, distinct-program
counts, confirmed 2026–27 operations, established language pairings, supported
kindergarten allocations, supported school structures, programs with all five
essential fields, and programs requiring follow-up are **not assessed**.
Kindergarten-model and instructional-language distributions are also not
assessed. The machine-readable report uses JSON `null` for these unknown
research quantities, distinct from the observed zero records collected.

No campus-specific, district-wide, historical, or current-year program evidence
was accessed. Thus there is no basis to classify a school as whole-school or
strand, infer any language pairing, assign a starting model, identify an
Indigenous program, or confirm current operation. No empty state inventory
CSVs or invented evidence-ledger claims were generated.

All five states need source collection. California's statewide roster and
district policy documents will require substantial coverage work; no district
has yet been inspected closely enough to rank its evidence gaps.

## Repository inspection completed

Read the repository README, national registry documentation, existing school,
program, source, and instructional-history tables, Oregon extraction fields,
Washington model normalization, and Texas track/provenance safeguards.

The existing national school table contains Illinois records; Oregon and Texas
have separate research datasets. No existing inventory for these five requested
states or additional local source documents were found in the inspected project
and attached files. Existing datasets and collectors were left unchanged.

Future collected records should remain additive, following the existing
`data/registry/state_dl_programs_<state>.csv` convention, with one record per
school and distinct program. The requested allocation and structure fields
correspond to Oregon's `instructional_allocation` and `program_structure`;
document the mapping when actual inventories are written. Do not invent state
or NCES identifiers from a school name or reuse a provisional program key as an
official identifier.

Apply the assignment's evidence hierarchy: an explicit kindergarten schedule
overrides a conventional published model designation; an official conventional
90/10, 80/20, or 50/50 designation otherwise supports the starting allocation.
Do not substitute pre-K or later-grade percentages. Keep undated or older
operation evidence separate from confirmed 2026–27 operation, and preserve
multiple language programs at one campus. These rules have not yet been
applied to any new source records.

## Saved access requirements and next action

Added these hosts to the environment configuration **draft**, preserving the
previous eight custom draft entries and the package-manager preset:

- `edu.wyoming.gov`
- `opi.mt.gov`
- `www.sde.idaho.gov`
- `doe.nv.gov`
- `www.cde.ca.gov`
- `www.google.com`
- `www.bing.com`

The five agency hosts were tested and denied. The two search hosts are requested
for source discovery; their availability was not tested. Draft persistence was
confirmed. Saving a draft does not apply the rules to the running instance or
publish an environment.

Review and save the network changes in environment settings, then publish the
environment. Research will also require access to district/campus sites and
document hosts discovered from official sources; these cannot be enumerated
from inaccessible directories. After settings are applied, recheck runtime
policy and the affected requests, then continue the broad roster pass in all
five states before spending extensive time on individual programs.

## Files and validation

- `data/registry/five_state_2026_27/source_access.csv`: five actual access
  outcomes. `recorded_at_utc` records when the audit was written, not a source
  publication date or a claimed program-verification time.
- `data/registry/five_state_2026_27/research_status.json`: machine-readable
  blocked status and unknown coverage measures.
- This report: findings, limitations, and the precise prerequisite for resuming.

Audit validation checked the five unique state entries, HTTPS agency URLs,
matching JSON/CSV states, all five documented connection denials, and the
distinction between zero records collected and unknown statewide quantities.
Program-inventory validation (duplicates, shares summing to 100%, date evidence,
school structure, and source-count reconciliation) **did not run**, because no
program records could be collected. No changes were committed, pushed, or merged.
