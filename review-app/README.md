# Fieldnotes

A GitHub-hosted research desk for the dual-language inventory. School and district
filters, source leads, program-specific coding, local draft recovery, notes,
source URLs and year context support frequent research sessions. A persistent
houseplant receives a little water on each saved decision or research note, loses
leaves and gathers cobwebs over idle hours, and recovers with renewed work. After
three hours without a saved entry, even a fully watered plant has one faded leaf
and full cobwebs. The open page updates it every minute; elapsed time also counts
while the site is closed. Saving adds a little water and clears some webs.
Plant state is a personal interface feature, separate from research data.

The interface uses a restrained, paper-like layout: compact school rows,
directly labeled values, simple radio controls, and source excerpts in the
margin. Interface copy uses American English. Original quotations retain
their source wording.

The app requires no embedded credentials. A researcher saves reviews locally,
then publishes a small batch through a prepared GitHub submission using their
normal GitHub sign-in. The trusted workflow accepts only accounts listed in
`config/hand_coding.json`, validates identities and values, creates an immutable
journal, rebuilds the canonical data, commits the journal and derived outputs
together, and refreshes the Pages website. Until the refreshed dataset confirms
the review IDs, the app does not mark a batch as published. Parked cases retain
notes without filling unknown structural values. Original observations remain.

The journal and the explicit `hand_coded_review` claims identify manual coding,
reviewer, authenticated submitting account, timestamp, evidence URL, note,
quotation, method and school year. Explicit statements and interpretations remain
distinct. Before submission, **My reviews** offers school/district search,
district and status filters, complete evidence, and **Edit review**. Edits reuse
the local review ID, keep each variable's program scope, and resume after a
reload without overwriting an unrelated school draft. **Publish** opens a full
preview with another edit action; unsaved edits must be saved or discarded
before that review can be handed off to GitHub.

A batch already handed to GitHub retains its submitted version while awaiting
acknowledgement. For a published decision, **Add a correction** creates another
journal record linked to the original; the latest authenticated decision selects
that variable for its reviewed year only. Earlier evidence remains in the history.

To invite a contributor, share the Pages URL, add their GitHub username to
`authorized_reviewers` in `config/hand_coding.json`, and commit that configuration.
They need a GitHub account and should enter their own reviewer name in the app's
profile menu. Repository write access, access tokens, and software installation
are not required. Anyone can research and save local drafts, but only approved
GitHub accounts can publish accepted batches. Drafts, unpublished reviews, and
plant state are personal to each browser; published coding is shared. Assigning
districts to contributors can help avoid overlapping work.

Development:

```sh
python -m dl_outcomes.review_site export
npm --prefix review-app ci
npm --prefix review-app run dev
```

Production assets:

```sh
npm --prefix review-app run test
npm --prefix review-app run build
```

The GitHub Pages workflow builds `review-app/dist`. The generated queue is
excluded from Git: it is derived from the canonical tables at publication.
Browser drafts and reviews persist on the same device; the profile menu can
export and restore backups. Publish or export before clearing browser data.

For the initial deployment, set the repository's **Settings → Pages → Build and
deployment → Source** to **GitHub Actions**, then run the **Fieldnotes website
and hand-coded reviews** workflow (or rerun its deployment job). The site uses
the repository URL configured in `config/hand_coding.json`. Hosting settings
are separate from repository content permissions. The build artifact and data
intake do not require Pages to be enabled; the deployment job does.
