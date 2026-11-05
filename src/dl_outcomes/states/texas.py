"""Migrate Texas evidence groups and published DL-current-EL results at native scope."""
from collections import defaultdict
import json
import re
from urllib.parse import parse_qs, urlsplit

from ..io import read_csv, record_id, school_year
from ..measurements import parse_value

GRADE_SUPPORT = {
    "NOT_REVIEWED": "NOT_REVIEWED",
    "DISTRICT_PK5_MODEL": "DISTRICT_GRADE_BAND_MODEL",
    "CAMPUS_K5_MODEL": "CAMPUS_GRADE_BAND_MODEL",
    "EXPLICIT_K": "EXPLICIT_GRADE",
    "EXPLICIT_K_WITHIN_PK5": "EXPLICIT_GRADE",
    "DISTRICT_K_ENTRY_MODEL": "DISTRICT_ENTRY_GRADE_MODEL",
    "PREK_PROXY_NOT_K_QUANTIFIED": "EARLIER_GRADE_PROXY_NOT_TARGET_QUANTIFIED",
    "MODEL_LABEL_MINUTES_DIFFER": "MODEL_LABEL_MINUTES_DIFFER",
    "SOURCE_DOES_NOT_SUPPORT_PROGRAM_GRADE_PERIOD": "SOURCE_DOES_NOT_SUPPORT_PROGRAM_GRADE_PERIOD",
    "UNRECOVERED": "UNRECOVERED",
}


def period_year(text):
    for match in re.finditer(r"(20\d{2})[-–](\d{2})(?!\d)", text or ""):
        try:
            return school_year(match[1] + "-" + match[2])
        except ValueError:
            pass
    return None


def migrate(b):
    config = json.loads((b.root / "config/states/tx.json").read_text())["pilot"]
    metadata = b.dataset("TX_TRACK_RESEARCH", "TX", "inventory", "Texas " + config["research_version"] + " instructional-language evidence", "repo:data/registry/texas/", notes="Provisional reporting-group evidence; not a campus-program census.")
    track_source = b.source_file(metadata, config["tracks"])
    allocation_source = b.source_file(metadata, config["allocations"])
    b.source_file(metadata, config["source_register"])
    # Save review decisions, extracts and public evidence in the portable build.
    review_manifest = b.track_input(config["review_manifest"])
    review_provenance = json.loads(review_manifest.read_text())
    for section in ("inputs", "files", "build_script"):
        for path in review_provenance[section]:
            b.track_input(path)
    citations = {}
    for row in read_csv(b.root / config["source_register"]):
        if row.get("archive_path"):
            source = b.source_file(metadata, row["archive_path"], metadata=row["archive_metadata_path"])
            b.tables["sources"][(source,)]["evidence_period_raw"] = row["evidence_period"]
            b.tables["sources"][(source,)]["notes"] = "Saved public evidence; capture method: " + row["capture_method"] + ". Scope and limitations are in the Texas source register."
            citations[row["source_id"]] = source
        else:
            citations[row["source_id"]] = b.citation(metadata, row["url"], key=row["source_id"],
                period=row["evidence_period"] or "not_reported", retrieved=row["accessed_at_utc"] or None,
                remote_hash=row["sha256_download"] or None)
    tracks = read_csv(b.root / config["tracks"])
    by_parent = defaultdict(set)
    track_sites = {}
    for row in tracks:
        native = row["campus_id"]
        if not re.fullmatch(r"\d{9}", native):
            raise ValueError(f"Not a Texas campus identifier: {native}")
        sid = b.resolve("school", "TX_TEA_campus_id", native, year=row["assessment_year"], default="TX-S" + native)
        did = b.resolve("district", "TX_TEA_district_id", native[:6], year=row["assessment_year"], default="TX-D" + native[:6])
        b.school(sid, "TX", row["campus"], track_source, namespace="TX_TEA_campus_id", native_id=native,
                 year=row["assessment_year"], status="state_identifier", screening="provisional_reporting_group_evidence")
        b.district(did, "TX", row["district"], track_source, namespace="TX_TEA_district_id", native_id=native[:6], year=row["assessment_year"])
        # Identity in the research snapshot does not date a current language offering to 2023–24.
        b.membership(sid, did, track_source, row["language_track_id"], year=row["assessment_year"])
        program = b.resolve("program", "TX_P50_language_track_id", row["language_track_id"], year=row["assessment_year"], default=record_id("program_candidate", "TX", row["language_track_id"]))
        site = record_id("site_candidate", program, sid)
        track_sites[row["language_track_id"]] = site
        by_parent[row["registry_record_id"]].add(site)
        if (program,) not in b.tables["programs"]:
            b.add("programs", program_id=program, state_code="TX", program_name=row["campus"] + " / " + row["language_pair"],
                  identity_status="provisional_evidence_group", screening_status="requires_program_identity_review",
                  notes="Original research key: " + row["language_track_id"] + ". This is not a verified distinct program or durable official program ID.")
        b.identifier("program", program, "TX_P50_language_track_id", row["language_track_id"], track_source, status="provisional_evidence_group")
        b.add("program_sites", site_id=site, program_id=program, school_id=sid, link_status="provisional", source_id=track_source)
        ids = [key for key in row["audit_source_ids"].split(";") if key]
        source = citations.get(ids[0], track_source) if ids else track_source
        historical = row["historical_2023_24_pair_status"]
        # A year mentioned in a district's program history is not a campus validity year.
        year = "2023-24" if historical in {"YES", "PRIOR_DATED_CAMPUS_EVIDENCE_RETAINED"} else period_year(row["evidence_period"]) if row["pair_verification_scope"] == "CAMPUS_DOCUMENTED" else None
        if historical == "LATER_EVIDENCE_ONLY":
            year = "2026-27"
        status = {"CAMPUS_DOCUMENTED": "documented", "DISTRICT_POLICY_ONLY": "district_policy_only",
                  "UNVERIFIED": "unverified"}.get(row["pair_verification_scope"], "provisional")
        b.claim("program", program, "language_pair", row["language_pair"], source, row["language_track_id"],
                year=year, status=status, import_source=track_source,
                notes=row["correction_reason"] + " Source scope: " + row["pair_verification_scope"])
        b.claim("program", program, "TAPR_reporting_category", row["TAPR_program_group"], track_source,
                row["language_track_id"] + ":category", year=row["assessment_year"], status="provisional",
                notes="Reporting-category association, not independent proof that this campus hosted that instructional model.")
        if row["language_pair"] != "UNVERIFIED":
            for language in row["instruction_languages"].split(";"):
                b.add("program_languages", language_record_id=record_id("language", site, language, source, row["language_track_id"]),
                      site_id=site, language_name=language, language_code={"English": "en", "Spanish": "es", "French": "fr", "Mandarin": "cmn", "Vietnamese": "vi", "Arabic": "ar"}.get(language),
                      language_role="instruction_language", valid_from_year=year, valid_to_year=year,
                      evidence_period_raw=row["evidence_period"], verification_status=status, source_id=source,
                      source_locator=row["language_track_id"], notes="Campus, policy and year scope remain distinct; no tested-population attribution.")
        b.add("program_configurations", configuration_id=record_id("configuration", site, track_source, row["language_track_id"]),
              site_id=site, grade_scope="not_reported", population_model=row["TAPR_program_group"], delivery_structure="unknown",
              program_kind="provisional_TAPR_category_association", evidence_period_raw=row["assessment_year"],
              verification_status="provisional", source_id=track_source, source_locator=row["language_track_id"],
              notes="One-way/two-way is the source reporting category. Instructional hosting, grades, cohort and delivery structure require separate evidence.")
    for row in read_csv(b.root / config["allocations"]):
        parent_year = row["registry_record_id"].split(":")[1]
        school = b.resolve("school", "TX_TEA_campus_id", row["campus_id"], year=parent_year, default="TX-S" + row["campus_id"])
        reviewed_ids = list(filter(None, row.get("pass51_source_ids", "").split(";")))
        source = citations[reviewed_ids[0]] if reviewed_ids else allocation_source
        review_note = (" Pass 51 review: " + row["pass51_review_status"] + "; K support: " + row["pass51_k_support"] +
                       "; origin: " + row["pass51_observation_origin"] + ".") if row.get("pass51_review_status") else ""
        locator = row["allocation_record_id"] + ("; " + row["pass51_source_locator"] if row.get("pass51_source_locator") else "")
        b.add("allocation_schedules", schedule_id=record_id("schedule", "TX", row["allocation_record_id"]),
              school_id=school, site_id=track_sites.get(row["language_track_id_if_unambiguous"]),
              grade_scope=row["grade"], reported_model_label=row["allocation_label"], percentage_basis=row["allocation_interpretation"],
              schedule_status="reported_policy_requires_review", evidence_period_raw=row["source_period"],
              evidence_review_status=row.get("pass51_review_status"),
              grade_support_status=GRADE_SUPPORT.get(row.get("pass51_k_support")),
              tested_cohort_exposure="not_established", source_id=source, source_locator=locator,
              notes=row["evidence_note"] + review_note + " Raw entry year: " + row["entry_school_year"] + "; cohort exposure remains unverified. Model label has not been converted to named-language shares.")
    # Preserve school-level structural evidence without assigning whole-school status to each language track.
    structure_path = "data/registry/texas/texas_structure_evidence_pass44.csv"
    structure_source = b.source_file(metadata, structure_path)
    for i, row in enumerate(read_csv(b.root / structure_path, legacy=True), 2):
        sid = "TX-S" + row["campus_id"]
        if (sid,) not in b.tables["schools"]:
            continue
        b.claim("school", sid, "reported_delivery_structure", json.dumps(row, ensure_ascii=False, sort_keys=True),
                structure_source, f"CSV record {i}", year=period_year(row["evidence_period"]),
                notes="Campus structural evidence only; whole-school DL does not mean each language track is whole-school.")
    migrate_outcomes(b, by_parent, track_source)
    migrate_grade_context(b)
    b.notes.append("Texas migrates " + str(len(tracks)) + " provisional evidence groups and preserved/reviewed policy observations. Pass 51 adds separate current Spring policy evidence and qualifies unsupported K labels; no tested-cohort or language-specific outcome attribution is inferred. The eight subject results cover four current-EL one-way DL reporting groups, including one district aggregate.")


def migrate_grade_context(b):
    from ..collectors.texas_grades import LAYER
    config = json.loads((b.root / 'config/states/tx.json').read_text())['campus_grade_context']
    dataset = b.dataset('TX_CAMPUS_GRADE_CONTEXT', 'TX', 'inventory',
        '2024–25 AskTED-derived campus grade ranges', LAYER,
        notes='Directory context for excluding non-K campuses from allocation coverage. A K-serving campus does not establish K participation in its DL programme; no historical grade extrapolation.')
    paths = sorted((b.root / config['raw_directory']).glob('page_*.metadata.json'))
    if not paths:
        raise ValueError('Texas grade context missing; collect a public directory snapshot first')
    seen = set()
    for page, metadata in enumerate(paths):
        path = metadata.with_name(metadata.name.replace('.metadata.json', '.json'))
        meta = json.loads(metadata.read_text())
        if meta['school_year'] != config['school_year'] or meta['selection']['resultOffset'] != page * 2000:
            raise ValueError('Directory year/pagination does not match the selected vintage')
        source = b.source_file(dataset, path, metadata=metadata)
        b.tables['sources'][(source,)]['evidence_period_raw'] = config['school_year']
        payload = json.loads(path.read_text())
        for feature in payload['features']:
            row = feature['attributes']
            native = (row['USER_School_Number'] or '').lstrip("'")
            if not re.fullmatch(r'\d{9}', native) or native in seen:
                raise ValueError('Invalid/duplicate campus directory identity: ' + native)
            seen.add(native)
            sid = b.resolve('school', 'TX_TEA_campus_id', native,
                year=config['school_year'], default='TX-S' + native)
            if (sid,) in b.tables['schools']:
                b.claim('school', sid, 'campus_grade_range_context', json.dumps(row, sort_keys=True),
                    source, 'ObjectID=' + str(row['ObjectID']), year=config['school_year'], status='documented',
                    notes='Campus directory range only. A K-serving campus is an eligibility proxy, not proof of a kindergarten DL programme. The 2024–25 range is not assigned to the 2023–24 TAPR reporting group.')
    if len(seen) != config['expected_directory_rows'] or payload.get('exceededTransferLimit'):
        raise ValueError('Campus directory snapshot is incomplete')


def migrate_outcomes(b, by_parent, track_source):
    config = json.loads((b.root / "config/states/tx.json").read_text())["pilot"]
    dataset = b.dataset("TX_TPRS_DL_PILOT", "TX", "dl_participants", "Public TPRS BE-Dual One-Way current-EL observations", "https://rptsvr1.tea.texas.gov/", publisher="Texas Education Agency",
                        notes="All tested grades and current ELs only; four existing verified reporting-group observations.")
    source = b.source_file(dataset, config["dl_outcomes"])
    assessment = "TX_STAAR_TPRS_VERSION_NOT_REPORTED"
    b.add("assessments", assessment_id=assessment, state_code="TX", assessment_name="STAAR results reported in TPRS",
          assessment_family="STAAR", construct="academic_achievement", assessment_version="not_reported",
          scale_description="Percent meeting grade level or above; preserve source grade/population scope.", source_id=source)
    population = b.population("TX", "Current emergent bilingual/EL in BE-Dual One-Way", "dl_current_el_only", source,
                              definition="Source BE-Dual One-Way reporting group restricted to current emergent bilingual/EL students. Does not include all DL participants.")
    metric = b.metric("TX_STAAR_MEETS_OR_ABOVE_PCT", "Meets Grade Level or above", "academic_proficiency", "percent",
                      "Source program/current-EL all-tested-grades denominator; numeric denominator not supplied in the saved extract.", "TX_STAAR_source_standard_only")
    for index, row in enumerate(read_csv(b.root / config["dl_outcomes"], legacy=True), 2):
        if row["scope"] == "campus":
            entity_type, entity = "school", b.resolve("school", "TX_TEA_campus_id", row["campus_id"], year=row["year"], default="TX-S" + row["campus_id"])
        elif row["scope"] == "district":
            native = parse_qs(urlsplit(row["source_url"]).query)["id"][0]
            entity_type, entity = "district", b.resolve("district", "TX_TEA_district_id", native, year=row["year"], default="TX-D" + native)
            b.district(entity, "TX", row["district"], source, namespace="TX_TEA_district_id", native_id=native, year=row["year"])
        else:
            raise ValueError("Unrecognized TPRS aggregation scope")
        rid = b.reporting_unit("TX", entity_type, entity, row["campus"] or row["district"], group=row["program"])
        for subject, field in [("ELA", "ela_meets_pct"), ("Math", "math_meets_pct")]:
            oid = b.observation("dl_participant_outcomes", reporting_unit_id=rid, school_year=row["year"], grade_scope="all_tested_grades",
                population_id=population, assessment_id=assessment, subject=subject, metric_id=metric,
                source_value_unit="percent", source_population_raw=row["program"] + " / " + row["student_group"], source_grade_raw=row["grades"],
                source_id=source, source_locator=f"CSV record {index}, {field}; {row['source_reference']}; {row['source_url']}",
                notes=row["notes"] + " No grade, instructional-language, cohort or non-EL participant disaggregation.", **parse_value(row[field]))
            if entity_type == "school":
                parent = row["campus_id"] + ":" + row["year"] + ":one_way"
                sites = by_parent.get(parent, [])
                for site in sites:
                    b.link("dl_participant_outcomes", oid, site, track_source,
                           "combined_reporting_group" if len(sites) > 1 else "unresolved",
                           "Source reporting-category match only. Not affirmative attribution to this instructional-language track.")
