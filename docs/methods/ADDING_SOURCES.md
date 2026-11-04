# Adding states, sources and historical vintages

Start from the [national model](NATIONAL_DATA_MODEL.md) and [table contracts](../../schemas/README.md). Collection and analytical eligibility are different tasks: a collected record may still have unresolved language, population or cohort scope.

## Add a state adapter

1. Review the state's existing research and `config/states/<state>.json`. Do not interpret `not_migrated` as no existing data. Coverage currently recognizes earlier state-directory research without claiming a completed migration.
2. Save original public source bytes under a new `data/raw/<state>/<vintage>/` directory. Keep source URL, exact query/selection, retrieval timestamp, data-as-of/version, row count, completeness limits and SHA-256 in metadata. Preserve earlier snapshots. For large future downloads, use versioned artifact storage and a reproducible download manifest; the current pilot uses small local snapshots.
3. Add a module under `src/dl_outcomes/states/` exposing `migrate(build)`. Configure its module name in the state JSON `adapter` field. The offline builder discovers enabled adapters from these configs.
4. Register datasets and saved source releases with `Build.dataset` and `Build.source_file`. Citation-only documents use `Build.citation` and remain explicitly metadata-only. Do not fabricate retrieval dates for older research.
5. Preserve native identifiers and labels. Add research entities and dated identifier aliases, with unresolved identity matches left provisional. Accepted aliases in `config/identity_mappings.csv` require evidence and are applied only in their documented validity period. Program source-row IDs are not official enduring program identities.
6. Add program languages, designs and allocation evidence at their actual scope. Retain unknowns. Annual model labels alone do not establish English as a second language, kindergarten percentages, entering-cohort exposure or whole-school delivery. Related heritage/tribal programs require evidence-based eligibility review rather than automatic classification by their names.
7. Import each reported outcome once, with reporting unit, grade scope, population definition, metric, instrument/version, administration, assessed language and source vintage. Add context/attribution links separately. Preserve district/state aggregates and all-grade results at those units.
8. Rebuild, regenerate the dictionary if contracts changed, validate, and run tests. Add a state profile describing native definitions, source availability and remaining gaps.

The Illinois, Texas and Washington adapters demonstrate legacy migration, narrow participant-group reports, annual metadata, school-grade academic results, enrollment counts and derived shares. Existing standalone collectors can continue producing source files while common adapters are added; they do not need to be rewritten simultaneously.

## Add another source vintage

Never edit a saved raw release in place. The Washington collector validates cached hashes and selections; a changed query or refreshed acquisition needs a new directory:

```bash
dl-outcomes collect-wa-pilot --destination data/raw/wa/new_vintage
dl-outcomes build
dl-outcomes validate
```

The Washington adapter discovers saved vintage directories. Observation IDs include source vintage, so corrected results for the same performance year remain distinguishable. A source's data-as-of date is not the assessment year or the beginning of a program. Analyses must choose source vintages explicitly to avoid counting revisions as separate samples.

## Population and metric decisions

Use layer 1 only when the source identifies DL participants. Preserve whether it reports all participants, current ELs within DL, non-EL participants or another explicitly defined group. Mixed bilingual-service categories cannot automatically become DL-only data. Schoolwide and general EL outcomes belong to state/context layers even when the school hosts DL programs.

The metric definition must preserve scale, units and denominator meaning. Keep counts tested/expected separate from a proficiency denominator unless the source establishes equivalence. Percentages stored as proportions require explicit conversion; suppressed cells and bounds are not zeros. Derive a rate only from known matching-population counts and record the formula. Do not derive actual EL exits from cut-score attainment or changes in enrollment.

## EL proficiency, exit rules and SEDA

These tables currently have headers and contracts but no collected pilot values. Their coverage status remains `not_collected`, not `searched_not_found` or `not_publicly_reported`.

For ELP, register the actual instrument, assessment/scoring version, English-language domain/composite measure, source population and applicable period. WIDA ACCESS, TELPAS and ELPAC are distinct instruments. For exit policy, preserve grade-specific domain/composite thresholds and additional requirements in structured JSON alongside the source. Import officially reported exit counts/rates separately, retaining the source denominator definition.

For SEDA, select an actual public product/release and retain its geography, school/district identifiers, grade coverage, reporting years or pooled periods, measure type, scale and uncertainty where supplied. Establish a dated, reviewed identifier crosswalk. Do not assume every SEDA product offers school × grade × year observations or that schoolwide estimates identify DL participants. SEDA and state-assessment layers share underlying information and are not independent testing samples.

## Releases and analysis exports

`dl-outcomes release <id>` first validates the build, then creates a local frozen manifest/bundle containing exact input, config, code, contract and output bytes. It refuses an existing ID and does not publish. Uploading a release to external storage is a separate action.

The optional analytics export keeps each observation layer and relationship table separate. Joining source/population/reporting-unit dimensions preserves one row per observation. Joining program links expands context associations and must not be treated as new independent scores or track-specific participant outcomes. Preserve source vintage and attribution status in any analysis extract.
