# LAUSD article supplement extraction

Source: user-supplied `sj-docx-1-edr-10.3102_0013189x261493743.docx`, supplement to DOI 10.3102/0013189X261493743. The original file's SHA-256 is recorded in every CSV row and in `extraction_summary.json`.

The [source supplement](../../../raw/literature/lausd_twdl_2026_11_07/sj-docx-1-edr-10.3102_0013189x261493743.docx) is preserved in the repository. `source_manifest.json` records acquisition, source roles, scope and hashes. These are literature-derived participant aggregates at the study-cohort level, available for longitudinal research with their scope retained; they are not campus demographic or proficiency observations.

`lausd_supplement_tables.csv` transcribes all 396 data cells in Tables A-1 through A-4. It preserves source labels and school years, counts versus percentages, exact zeros, blank cells, and suppression. Gray shaded blanks in Table A-4 are marked suppressed according to the document's note; unshaded blanks remain not reported. Published `<21` counts remain suppressed. No suppressed value is reconstructed. Percentages are recorded in percentage points, without conversion into proportions or assumed denominators.

The tables report aggregates for the study's LAUSD elementary TWDL population. Table A-1 distinguishes all elementary students and first grade. The other tables do not separately label their grade scope. Their percentages describe enrollment in TWDL for the named group; they should not automatically be interpreted as demographic composition within TWDL. EL, FRPL, and race categories overlap and should not be summed across rows as mutually exclusive groups.

The supplement describes 144 schools but supplies no campus names or school identifiers, no campus delivery-model lookup, and no external hyperlinks. Figures A-1 to A-3 and B-1 to B-3 were inspected; they show aggregates and language combinations, not named schools. The document does not supply ELA or math proficiency outcomes or language-allocation ratios.

For four unnamed campuses offering Spanish plus another language, student records could not distinguish language-program enrollment. The authors therefore put all their TWDL students in the Non-Spanish category. Those aggregate language categories cannot be mapped directly to individual language strands in our school inventory.

`lausd_language_combination_candidates.csv` lists eight current inventory schools with the language combinations appearing in Figure A-3. These are candidates for source checking, not identified members of the study's four-school set: the figure concerns 2022, while our inventory reference year is 2025–26. Kittridge Street is the current inventory's sole Armenian/Spanish combination; this is a useful lead, not a confirmed historical identity match. Existing provisional delivery values and their statuses are retained as context, not upgraded.

`lausd_elementary_inventory_snapshot.csv` preserves the 165 program records across 151 school identities used for that candidate search. It is a dated research snapshot, not the live inventory; subsequent verified coding belongs in the selected current tables. The manifest also records the companion article's actual replication-deposit link. Its four listed files require an ICPSR sign-in and have not been downloaded or asserted inspected.

This is an extracted research artifact, separate from canonical school classifications. It does not establish that all 144 schools are strands, identify which schools are exceptions, or establish delivery models for 2025–26. No school classifications or production data were changed.

Run `python scripts/validate_lausd_palm_beach_sources_2026_11_07.py` from the repository root to verify the transcription cell by cell against the archived DOCX, including gray shading, suppression, source labels and years, and to check the research candidate identities.
