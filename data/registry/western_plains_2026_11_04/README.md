# Utah, Colorado, New Mexico, Arizona, Nebraska and Kansas

Reviewed structural first pass, November 4, 2026. Reference school year: **2025–26**.
Earlier, undated and later evidence keeps its own period. None of the six state
inventories is asserted complete. Additional assessment/proficiency/context/EL/SEDA
collection remains deferred.

The six `*_programmes.json` files are the reviewed build inputs. Each provisional
school/track evidence group retains a separate reference-year assessment, source
observations, grade-specific allocation descriptions/plans and change events.
Observation periods do not inherit the reference year. Numeric plans require
named instructional languages and supported grade scope; unknown or unequal
model-ordering labels remain descriptions without manufactured shares.

- `sources.json` and `sources.csv`: 96 saved public sources with URLs, retrieval
  times and byte hashes. Raw responses and metadata are under
  [the batch source directory](../../raw/western_plains_2026_11_04/).
- `*_screening.json`: original source observations, including non-DL bilingual
  models and unreviewed third-party leads. These are not additional programmes.
- `extractions/`: 280 Utah school rows / 348 language cells, 52 Colorado listing
  rows, 419 New Mexico report school rows / 137 DL flags, 398 university map
  records and 138 Arizona discovery records. Printed New Mexico district/model
  totals reconcile after the documented merged-cell repair on PDF page 104.
- `identity_decisions.csv`: reviewed aliases, source-name matches and authorizer
  corrections. These do not claim native state or NCES identifiers.
- `reviews.json` and `search_results.json`: bounded continuity/change reviews,
  programme membership, queries and discovery results. Search snippets are not
  programme-attribute evidence or proof that a programme did not end.
- `retrieval_log.csv`: public retrieval attempts, including failures, empty pages,
  redirects and browser-rendered captures. A successful HTTP request alone does
  not make a page substantive evidence.
- `selection_summary.json`: selected-input counts; generated national/batch views
  and the remaining field-level gaps are in `data/reports/`.

The university map is non-exhaustive and often not phone-verified. Composite
language/model cells are not expanded into a DL track for every language. The
Arizona JavaScript snapshot is the **exact school-array excerpt**, excluding
unneeded application configuration; its full-response hash is separately saved.
HTML captures marked as rendered HTML are browser snapshots, not original HTTP
response bytes. Both distinctions are explicit in source metadata.

The New Mexico annual report is archived as a complete primary document, but
only its structural Appendix F is extracted here. No report scores or other new
assessment observations are imported. Existing assessment pilot tables retain
their prior bytes.

Rebuild and verify from the repository root:

```sh
dl-outcomes build
python scripts/validate_western_plains_inventory.py
python scripts/validate_structural_integration.py
python -m unittest discover -s tests -v
```
