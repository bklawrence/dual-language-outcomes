Keep tracked build inputs and generated data consistent in every commit.

Before committing a change to any path listed in `inputs` or `pipeline_files`
in `data/curated/manifest.json`, run `dl-outcomes build` followed by
`dl-outcomes validate`. Commit the changed inputs together with the resulting
manifest, curated tables, and generated reports. This includes reviewer-list
changes in `config/hand_coding.json`. The national workflow validates the pushed
commit before the separate Fieldnotes workflow rebuilds it.

Preserve frozen research reports and source snapshots. The builder writes
updated hand-coded views under `data/reports/hand_coding/current/`.
