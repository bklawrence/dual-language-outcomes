
# Texas language-program research — Pass 48 (2026-11-03)

This is an **additive, provisional research checkpoint** in the existing `dual-language-outcomes` repository, not a verified Texas census. It does not overwrite Passes 44–46, existing Texas collectors, national registry tables, or TAPR outcome joins.

## Files and locations

- `data/registry/texas/texas_language_program_tracks_pass48.csv`: 1,862 provisional track evidence records, derived from 1,856 campus × TAPR reporting groups across 1,610 Texas campuses.
- `data/registry/texas/texas_k_allocation_evidence_pass48.csv`: 970 historical kindergarten-model policy observations, of which 673 have an unambiguous provisional language-track link and 297 have no such link.
- `data/registry/texas/manifest_pass48.json`: source provenance, expected counts, original SHA-256 checksums, and newline-normalized text checksums for copy/paste uploads.
- `docs/texas/SCHEMA_LANGUAGE_TRACKS_PASS48.md`: entity definitions and restrictions on outcome attribution.
- `scripts/validate_texas_pass48.py`: standalone validation using only Python standard-library modules.

## Interpretation

The unit for language classification is a **provisional instructional language track within a campus**, not the campus itself. The track ID is a research record key, not an official or durable program identifier. A campus can have multiple distinct bilingual tracks. The partner language may be Spanish, Vietnamese, Mandarin, French, Arabic, or another language; this study is not limited to Spanish–English. The 975 `UNVERIFIED` language-track rows must not be treated as verified Spanish–English programs.

Keep language pairing, kindergarten starting allocation, one-way/two-way TAPR reporting category, campus structure (whole-school versus strand), and dates separate. Policy evidence about a kindergarten model is not proof that a particular tested student cohort experienced that model. None of the 970 allocation observations in this snapshot establishes confirmed tested-cohort exposure. Later campus-language listings do not by themselves establish 2023–24 operation.

Do **not** distribute an aggregated TAPR reporting-group outcome to multiple tracks. Where a reporting category combines several languages, preserve the group-level value as combined/cannot-disaggregate unless dated, affirmative evidence supports unique attribution. Schoolwide SEDA data are a separate outcome layer, not individual program-participant results.

## Validation

After all six files in this checkpoint have been committed, from the repository root run:

```bash
python3 scripts/validate_texas_pass48.py
```

The script checks the documented snapshot, including parent links, unique IDs, language-status safeguards, unresolved allocation links, and cohort-exposure flags. It validates **newline-normalized** text checksums so copy/paste through GitHub's editor works regardless of CRLF versus LF line endings. Original byte-for-byte SHA-256 values are retained for provenance but are not required to match a copy/paste upload.

This validation does **not** independently verify that any campus offered a particular language in 2023–24, that a district policy covered a given campus, or that TEA program-group results identify specific language-track participants.

## Next passes

Continue date- and campus-specific language-pair verification; attribute each historical kindergarten schedule to a track only where supported. Retain the distinction between a policy model and tested-cohort exposure. Leave collectors and existing outcome joins unchanged until separate reviewed work explicitly adds track-aware integration.
