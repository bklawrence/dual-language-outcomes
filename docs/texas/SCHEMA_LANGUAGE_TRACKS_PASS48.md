
# Texas program-language schema (Pass 48 working export)

**Unit of analysis:** campus -> instructional program track -> dated allocation schedule. A campus can host multiple partner-language tracks; a language pairing alone may also support multiple tracks (e.g., separate one-way and two-way programs).

## 1. Language tracks
`texas_language_program_tracks_pass48.csv` contains 1,862 provisional track rows expanded from 1,856 2023–24 campus × TAPR program-category registry rows. Each track carries its own campus identifier, candidate partner-language pairing, evidence level and source, and parent TAPR program-group identifier. `language_track_id` is a provisional evidence-record key, **not** a state-assigned program identifier. `UNVERIFIED` means there is no independently supported partner-language pairing in the current audit; do not automatically label it Spanish.

Where source evidence identifies two partner-language programs under one reported TAPR category, there are two track rows with the same `registry_record_id` / TAPR group. This is intentional. A school's entire language inventory may be incomplete until school-specific verification. Labels with `(later)` are not established for 2023–24.

## 2. Historical kindergarten allocation evidence
`texas_k_allocation_evidence_pass48.csv` holds all **970 known historical master allocation observations** without copying a model automatically into every proposed language track. Its row key is `allocation_record_id`; the link to a specific language track is blank if attribution is ambiguous or the partner language is unverified. `entry_school_year` is unconfirmed for tested cohorts. For subsequent passes, use one row **per dated track-specific allocation policy** with distinct `allocation_record_id` values; one campus can then have separate Spanish–English and French–English schedules and multiple historical model periods.

**Recommended finalized schedule table:** `language_track_id`, `entry_cohort_school_year`, `grade`, `instruction_language`, `instruction_share_pct`, `start_date`, `end_date`, `evidence_type`, `source_url`, `verification_status`. Thus 90/10 Spanish–English kindergarten would be two rows, Spanish=90 and English=10. French–English 50/50 at the same campus would be two different rows keyed to a different language track.

## 3. Outcomes are a separate evidence layer
TAPR bilingual results are campus × school year × DQ/DT program-category × subject and often **do not distinguish partner language**. Keep this source-level grain. Join a TAPR observation to a language track only when there is affirmative evidence that the reported category contains **only that track**. Where several tracks share a category, show the TAPR group outcome as *combined / cannot disaggregate*; never duplicate it across tracks. Do not infer a school is whole-school from language or DQ/DT metadata.

## 4. Current verification limits
This is a working audit, **not** a verified 1,610-campus census. District-program definitions are weaker than contemporary campus-level sources. Campus structure (whole-school, same-grade strands), program histories, and kindergarten allocation sources require independent dated evidence. Programs with more than one language pairing **within a campus** are within the study; that does not imply instruction in three languages within a single class.
