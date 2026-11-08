# Live research views

`programs.csv` is the selected 2025-26 program site view, with `hand_coded`, `hand_coded_variables` and `hand_coded_review_ids` flags. Program records are evidence groups, not guaranteed distinct programs. Operation, eligibility, source dates and missingness remain explicit.

`reviews.csv` contains all published hand-coded reviews, including other reference years, researcher and authenticated GitHub account, timestamps, sources, notes, quotations and coding method. Immutable journal files are in `data/registry/hand_coded_reviews/`. Original observations and the frozen national baseline are retained. Reviewed-year bounds are not program start or end dates.

`study_scope_exclusions.csv` documents schools removed from active research views and Fieldnotes under `config/study_scope.json`, including the reason and supporting sources. Source-history tables and frozen releases retain those identities for audit. Apply the current program-school cohort when joining archived assessment data. Scope exclusions are not program closures.
