# Texas dual-language research data

**Current cleanup: [Pass 51 (2026-11-04)](README_PASS51.md).** Use the [campus language table](../../data/registry/texas/texas_campus_language_inventory_pass51.csv), [provisional language-track data](../../data/registry/texas/texas_language_program_tracks_pass51.csv), and [allocation evidence](../../data/registry/texas/texas_k_allocation_evidence_pass51.csv). [current_inventory.json](../../data/registry/texas/current_inventory.json) identifies the preferred files. Pass 51 repairs citations and qualifies grade/model evidence; the [Pass 50 language audit](README_PASS50.md) and earlier snapshots remain intact.

The inventory includes English with Spanish, Mandarin, Vietnamese, French, Arabic, and unresolved language pairs. A campus may have separate tracks. Read source dates and confirmation scope before using a label; district policy support is not campus/year confirmation.

## Historical working files — Passes 44–46 (2026-11-02)

These are research working files, not definitive campus-program census data. This update is designed to be merged into the existing `dual-language-outcomes` project without replacing `collectors/texas.py`, `collectors/texas_tapr_dli.py`, or the national `data/registry/` tables.

## Snapshot inventory

| File (under `data/registry/texas/`) | Contents | Records |
|---|---|---:|
| `texas_master_pass44.csv` | Wide Texas master, retaining prior classification and evidence fields | 1,856 |
| `historical_cohorts_pass44.csv` | Campus/test-grade historical K policy evidence | 142 |
| `school_scope_pass44.csv` | La Joya and Round Rock structural audit | 34 |
| `structure_sources_pass44.csv` | Dated structural evidence and public source URLs | 49 |
| `tapr_pilot_join_pass45.csv` | Houston, La Joya, Round Rock outcome-join pilot | 134 |
| `tprs_verified_observations_pass45.csv` | Published all-grade TPRS observations, including one district aggregate | 4 |
| `tapr_pilot_campuses_pass46.csv` | Unique campus IDs for the public-data pilot | 66 |
| `tea_data_spec_pass46.csv` | Requested variable specification for public-data search | 18 |
| `tea_source_availability_pass46.csv` | Source availability audit (NOT downloaded extracts) | Source inventory |

The accompanying `manifest.json` lists original filenames, row counts, and SHA-256 checksums. Do not sum rows across files as if they represented distinct campuses.

## Classification and coverage

- **97 of 142** historical evidence records are labeled `DATED_POLICY`, across **40 distinct campuses**. Starting model distribution among these 97 records: 90/10 = 29; 80/20 = 1; 70/30 = 0; 50/50 = 67. This identifies *documented policy*, not verified individual student exposure.
- The **134-record pilot** comprises 90 dated-policy candidate cohorts and 44 provisional records (32 preliminary Houston, 12 Round Rock prospective schedules), across **66 campuses**.
- The **four all-grade observations** are **not** 2023–24 grade-three/four/five treatment-group results; one is a districtwide aggregate. They are useful context only.
- Whole-school / strand evidence may refer to a different school year or grade. `unknown` must remain unknown until dated evidence supports an update.
- The labels 90/10, 80/20, 70/30, 50/50 refer to the **non-English partner/English allocation in kindergarten in the cohort's entry year**, not pre-K or tested-grade ratios. Verify the partner language for the particular track; a numeric model does not establish Spanish. A marketing/program title is not a substitute for an explicit contradictory timetable.
- Schoolwide SEDA outcomes and program-specific TEA outcomes are analytically different measures; they are never merged into a single undifferentiated outcome.

## Public TAPR collector / importer

The file `collectors/texas_tapr_public_import.py` imports **manually downloaded public TEA campus CSVs or ZIP files**. It does not use an authenticated service or request restricted records. It does not attempt to automate TEA's interactive form because no stable direct download URL has been verified.

1. Obtain the campus public export from [TEA's 2023–24 TAPR advanced download](https://rptsvr1.tea.texas.gov/perfreport/tapr/2024/Advance%20Download/download-data-adv.html).
2. Put the downloaded **public** CSV or ZIP in `data/raw/texas/`.
3. Run from repository root:

   ```bash
   python3 collectors/texas_tapr_public_import.py \
     --csv data/raw/texas/YOUR_TEA_CAMPUS_FILE.csv \
     --outdir results/texas/tapr_public
   ```

4. Read `import_log.csv`, `column_inventory.csv`, `candidate_program_cells.csv`, and `cohort_register_with_tapr_flags.csv`. **A candidate is not a confirmed grade-by-program observation.** The importer does not impute outcomes or translate masked/suppressed cells to zeros.

The workflow `.github/workflows/import-texas-tapr-public.yml` runs the importer manually on a public CSV or ZIP that you have placed in `data/raw/texas/`. It uploads results as a downloadable GitHub Actions artifact and does not automatically commit or overwrite research data.

Tests and snapshot validation:

```bash
python3 -m unittest discover -s tests -p 'test_texas_tapr_public_import.py' -v
python3 scripts/validate_texas_snapshots.py
```

## Interpretation safeguards

A TEA header containing candidate code `DQ` or `DT` is **not**, by itself, proof of a reported campus × grade × program × student-group metric. Verify the exact metric and included student population against the corresponding TEA data-element guide before applying a treatment or grade label. This is crucial for English-dominant two-way dual-language students, who may be outside an emergent-bilingual subgroup table.

Do not commit restricted/student-level source data, credentials, or private records in this repository. This package includes only previously collected, school-level research working files and source URLs.
