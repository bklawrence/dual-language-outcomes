# Palm Beach admissions labels and delivery review

The district's dual-language page lists 40 existing school identities: 27 elementary/K–8 hosts and 13 secondary hosts. `program_admissions.csv` records each school's literal asterisk, plus sign, or unmarked status, together with its existing school/program-site ID and the school website lead supplied by the district.

Among the elementary hosts, 11 are marked in-house, six full-choice program, and ten unmarked. Across all levels the counts are 14, 11, and 15. Unmarked status does not establish an admissions category. The page's introductory sentence says 24 elementary schools while its actual list contains 27; both facts are preserved in `summary.json`.

The 2025–26 Choice and Career Academy Booklet defines in-house programs as available only to students zoned for the school, and choice programs as available regardless of attendance zone (printed page 1; PDF page 8). It separately lists full-choice schools without attendance boundaries (printed page 3; PDF page 10). That school list is distinct from the dual-language programs marked with a plus sign. The booklet was already archived in the preceding delivery review; `sources.json` references its original bytes rather than copying or changing them.

The current procedures manual, adopted July 15, 2026, states in Section 3.1 (PDF pages 7–8) that the district offers both total-school choice and program-within-a-school options. Its categories concern admissions and attendance boundaries. A separate use of “strand” in Section 8.9 describes a lottery preference for students continuing a program pathway; it is not a classification of campus instructional delivery.

These admissions labels do not independently establish whether every student receives DL instruction. The four campus pages reviewed describe DL offerings and eligibility without establishing elementary whole-school versus strand participation. New Horizons lists ISA/DL and STEAM, but separate program names alone do not prove that students follow mutually exclusive academic pathways. `delivery_structure_update` is therefore blank for every row; no school delivery model was assigned from a marker.

The supplied older BoardDocs manual returned HTTP 403 and is not represented as reviewed. The district FAQ provided the accessible current manual. Its 2026 adoption date and the 2026 Spanish guidelines are retained as current context, without backdating them to the 2025–26 inventory. The district roster is undated; listed grade spans have not overwritten canonical historical grade information. Secondary hosts remain included without an elementary language-allocation assignment.

Source snapshots are under `data/raw/palm_beach_admissions_2026_11_07/`. Source URLs, archive hashes, dates and roles are in `sources.json`; extraction hashes are in `manifest.json`. This package adds admissions observations and documented research limits, not confirmed whole-school/strand coverage. Further classification needs campus participation evidence, such as explicit program scope or DL and non-DL academic classes within the same grades.

Run `python scripts/validate_lausd_palm_beach_sources_2026_11_07.py` from the repository root to check source hashes, school IDs and the marker extraction alongside the LAUSD supplement transcription.
