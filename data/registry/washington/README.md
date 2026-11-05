# Washington structural CSV exports

These checked-in CSVs are rebuilt offline from the [saved OSPI JSON](../../raw/wa/pilot_2026_11_04/programs.json), not fetched each time someone opens the repository.

- [wa_programs.csv](wa_programs.csv): all **1,002 native school-level records**, retaining 2023–24, 2024–25 and 2025–26. Includes **528 DL records** and 474 separately classified heritage/tribal screening records. Those screening categories do not automatically prove or rule out immersion eligibility.
- [wa_dl_programs_2025_26.csv](wa_dl_programs_2025_26.csv): **195 DL source records across 175 schools**. Multiple records can represent languages/designs at one campus; these are source records, not verified unique continuing programmes. The case variant `Dual language Program` is included.
- [WA school-level K-coverage review](../../reports/washington_kindergarten_allocation_coverage_2026_11_04.csv): all 177 school units with DL evidence across the saved years; the reference-working-set flag selects 175 in 2025–26.

Every native column is preserved, including annual school/district identifiers, instructional language, design/model labels and `dataasof`. Added columns link DL rows to national school/programme/site IDs and preserve source ID, snapshot path, SHA-256, retrieval time, exact query URL and `rowid` locator. Heritage/tribal screening rows have no invented DL-programme ID. Treat identifiers as text when opening in spreadsheet software.

The source does **not** report programme grades, grade-by-grade time shares or an explicit second instructional language. `programmodel` is a source label; it is not converted to named-language percentages or a kindergarten schedule. The earlier 100% figure described annual model-label completeness. Kindergarten coverage is **not established**, because K eligibility and allocation scope still require evidence. See the [revised denominator rules](../../../docs/status/KINDERGARTEN_ALLOCATION_COVERAGE_2026_11_04.md).

Regenerate both CSVs with `dl-outcomes build`, or regenerate review views alone with `python scripts/build_structural_integration_report.py` after a current validated build. Both exports are included in build/report hashes and portable release bundles. These files contain structural metadata; the existing two-school assessment pilot remains separate.
