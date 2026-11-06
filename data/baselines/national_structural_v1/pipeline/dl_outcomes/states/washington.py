"""Washington source-native metadata, school outcomes and enrollment pilot."""
from collections import defaultdict
import json

from ..io import grade_scope, nullable, record_id, school_year
from ..measurements import parse_value, ratio


ACADEMIC_PERCENT_FIELDS = {
    "percent_consistent_grade": "consistent_grade_or_above",
    "percent_foundational_grade": "foundational_grade_or_above",
    "percentlevel1_including": "performance_level_1",
    "percentlevel2_including": "performance_level_2",
    "percentlevel3_including": "performance_level_3",
    "percentlevel4_including": "performance_level_4",
    "percent_participation": "participation",
    "percent_no_score": "no_score",
    "percent_taking_alternative": "alternate_assessment",
}
ACADEMIC_COUNT_FIELDS = ["count_of_students_tested", "count_of_students_expected", "count_consistent_grade_level", "count_foundational_grade"]
DEMOGRAPHIC_FIELDS = ["all_students", "female", "male", "gender_x", "american_indian_alaskan_native", "asian", "black_african_american",
                      "hispanic_latino_of_any_race", "native_hawaiian_pacific_islander", "two_or_more_races", "white",
                      "english_language_learners", "non_english_language_learners", "low_income", "non_low_income",
                      "students_with_disabilities", "students_without_disabilities"]
LANGUAGE_CODES = {"Spanish": "es", "Chinese- Mandarin": "cmn", "Japanese": "ja", "Russian": "ru", "Vietnamese": "vi", "Korean": "ko", "Arabic": "ar"}


def raw_source(b, dataset, path, key):
    raw_path, meta_path = path / (key + ".json"), path / (key + ".metadata.json")
    source = b.source_file(dataset, raw_path, metadata=meta_path)
    rows = json.loads(raw_path.read_text())
    b.tables["sources"][(source,)]["data_as_of_raw"] = " | ".join(sorted({r["dataasof"] for r in rows if r.get("dataasof")})) or None
    return source, rows


def migrate(b):
    dataset = b.dataset("WA_PROGRAMS", "WA", "inventory", "OSPI Report Card language programs", "https://data.wa.gov/d/d4w4-82bk", publisher="Washington OSPI", native_id="d4w4-82bk")
    sites_by_school_year = defaultdict(set)
    raw_dirs = sorted(path.parent for path in (b.root / "data/raw/wa").glob("*/programs.metadata.json"))
    if not raw_dirs:
        raise ValueError("Washington pilot sources missing; run dl-outcomes collect-wa-pilot")
    for path in raw_dirs:
        source, rows = raw_source(b, dataset, path, "programs")
        for row in rows:
            if row["organizationlevel"].casefold() != "school":
                raise ValueError("Washington school metadata selection contains another aggregation unit")
            native = row["schoolorganizationid"]
            if native != row["programschoolorganizationid"]:
                raise ValueError("Washington school/program school identifier mismatch")
            year, locator = school_year(row["schoolyear"]), "rowid=" + row["rowid"]
            sid = b.resolve("school", "WA_OSPI_school_organization_id", native, year=year, default="WA-S" + native)
            did = b.resolve("district", "WA_OSPI_LEA_organization_id", row["leaorganziationid"], year=year, default="WA-D" + row["leaorganziationid"])
            b.school(sid, "WA", row["schoolname"], source, namespace="WA_OSPI_school_organization_id", native_id=native, year=year)
            b.district(did, "WA", row["leaname"], source, namespace="WA_OSPI_LEA_organization_id", native_id=row["leaorganziationid"], year=year)
            b.membership(sid, did, source, locator, year=year)
            b.identifier("school", sid, "WA_OSPI_school_code", row["schoolcode"], source, year=year)
            b.claim("school", sid, "school_name", row["schoolname"], source, locator + ":name", year=year, status="documented")
            kind = row["programdesigntype"].casefold()
            if kind != "dual language program":
                b.claim("school", sid, "related_language_program_screening", json.dumps({k: row.get(k) for k in ["programdesigntype", "programdesign", "instructionallanguage", "programmodel"]}, sort_keys=True),
                        source, locator, year=year, status="unverified", method="eligibility_requires_review",
                        notes="Heritage/tribal categories retained for review. This is neither confirmation nor permanent exclusion of immersion eligibility.")
                continue
            language = nullable(row["instructionallanguage"])
            if not language:
                raise ValueError("DL source row lacks instructional-language label")
            program_namespace = "WA_OSPI_program_rowid@" + source
            program = b.resolve("program", program_namespace, row["rowid"], year=year, default=record_id("program_candidate", "WA", native, language))
            site = record_id("site_candidate", program, sid)
            if (program,) not in b.tables["programs"]:
                b.add("programs", program_id=program, state_code="WA", program_name=row["schoolname"] + " / " + language,
                      identity_status="provisional_evidence_group", screening_status="state_reported_dl_metadata",
                      notes="School/language evidence group across reported years, not proof of a unique continuing program or cohort.")
            if (site,) not in b.tables["program_sites"]:
                b.add("program_sites", site_id=site, program_id=program, school_id=sid, link_status="provisional", source_id=source)
            sites_by_school_year[(sid, year)].add(site)
            b.identifier("program", program, program_namespace, row["rowid"], source, year=year, status="source_evidence_record_not_official_program_id")
            b.add("program_languages", language_record_id=record_id("language", site, year, source, locator), site_id=site,
                  language_name=language, language_code=LANGUAGE_CODES.get(language), language_role="reported_instruction_language",
                  valid_from_year=year, valid_to_year=year, evidence_period_raw=year, verification_status="documented",
                  source_id=source, source_locator=locator, notes="Second instructional language is not explicitly reported; English is not inferred.")
            design = row["programdesign"].casefold()
            model = "two_way" if "two-way" in design else "one_way" if "one-way" in design else "unknown"
            b.add("program_configurations", configuration_id=record_id("configuration", site, year, source, locator), site_id=site,
                  school_year=year, grade_scope="not_reported", population_model=model, delivery_structure="unknown",
                  program_kind=row["programdesign"], reported_model_label=nullable(row["programmodel"]), evidence_period_raw=year,
                  verification_status="documented", source_id=source, source_locator=locator,
                  notes="State school-year metadata. Model is not a grade-specific or entering-cohort schedule; no named-language percentages inferred.")
        if (path / "academics.metadata.json").exists():
            academics(b, path, sites_by_school_year)
        if (path / "demographics.metadata.json").exists():
            demographics(b, path, sites_by_school_year)
    b.notes.append("Washington has source-native 2023–24 through 2025–26 program metadata. Academic/enrollment outcomes are a two-school pilot, not statewide outcome coverage or DL-participant results. No English partner, whole-school structure, cohort exposure or NCES match is inferred.")


def population_scope(label):
    lower = label.casefold()
    if "former" in lower or "exited" in lower:
        return "former_el"
    if "non-english" in lower or "non english" in lower:
        return "non_el"
    if "english" in lower and "learner" in lower:
        return "current_el"
    return "all_students"


def number_or_none(value):
    parsed = parse_value(value)
    return parsed["value_numeric"] if parsed["value_status"] == "observed" else None


def contextual_links(b, table, oid, sid, year, source, sites):
    for site in sorted(sites.get((sid, year), [])):
        b.link(table, oid, site, source, "schoolwide_context", "School/year association only. The reported population is not identified as DL participants and is not assigned a track-specific score.")


def academics(b, path, sites):
    dataset = b.dataset("WA_ACADEMICS", "WA", "state_assessments", "OSPI Report Card assessment results", "https://data.wa.gov/d/9fjj-2374", publisher="Washington OSPI", native_id="9fjj-2374")
    source, rows = raw_source(b, dataset, path, "academics")
    assessment = "WA_SBAC_TEST_VERSION_NOT_REPORTED"
    if (assessment,) not in b.tables["assessments"]:
        b.add("assessments", assessment_id=assessment, state_code="WA", assessment_name="Smarter Balanced as reported by OSPI",
              assessment_family="SBAC", construct="academic_achievement", assessment_version="not_reported",
              scale_description="Reported performance levels; published source fractions converted to percentages. Source vintage is separate from test version.", source_id=source)
    for index, row in enumerate(rows, 1):
        if row["organizationlevel"].casefold() != "school":
            raise ValueError("Academic pilot contains a non-school reporting unit")
        year = school_year(row["schoolyear"])
        sid = b.resolve("school", "WA_OSPI_school_organization_id", row["schoolorganizationid"], year=year, default="WA-S" + row["schoolorganizationid"])
        if (sid,) not in b.tables["schools"]:
            raise ValueError("Academic source school missing from identity registry")
        grade = grade_scope(row["gradelevel"])
        pop = b.population("WA", row["studentgroup"], population_scope(row["studentgroup"]), source,
                           group_type=row["studentgrouptype"], definition="OSPI school-level student subgroup; DL enrollment is not identified.")
        rid = b.reporting_unit("WA", "school", sid, b.tables["schools"][(sid,)]["school_name"])
        common = dict(reporting_unit_id=rid, school_year=year, grade_scope=grade, population_id=pop,
                      assessment_id=assessment, administration=row["testadministration"] + " / " + row["test_administration_group"],
                      subject=row["testsubject"], source_population_raw=row["studentgroup"], source_grade_raw=row["gradelevel"],
                      source_id=source, tested_n=number_or_none(row.get("count_of_students_tested")),
                      expected_n=number_or_none(row.get("count_of_students_expected")),
                      notes="Source-defined reporting denominator retained without assuming tested_n is that denominator. DAT and source-vintage notes: " + str(row.get("dat", "not_reported")))
        for field, label in ACADEMIC_PERCENT_FIELDS.items():
            metric = b.metric("WA_" + label.upper() + "_PCT", label.replace("_", " "), "academic_proficiency", "percent",
                              "OSPI source-defined percentage denominator; tested/expected counts retained separately, not substituted.", "WA_SBAC_source_definitions_only")
            oid = b.observation("state_assessments", **common, metric_id=metric, source_value_unit="proportion",
                                source_locator=f"JSON record {index}, field {field}", **parse_value(row.get(field), source_unit="proportion", target_unit="percent"))
            contextual_links(b, "state_assessments", oid, sid, year, source, sites)
        for field in ACADEMIC_COUNT_FIELDS:
            metric = b.metric("WA_" + field.upper(), field.replace("_", " "), "assessment_count", "count", "Not a rate", "WA_SBAC_source_counts")
            oid = b.observation("state_assessments", **common, metric_id=metric, source_value_unit="count",
                                source_locator=f"JSON record {index}, field {field}", **parse_value(row.get(field)))
            contextual_links(b, "state_assessments", oid, sid, year, source, sites)


def demographics(b, path, sites):
    dataset = b.dataset("WA_ENROLLMENT", "WA", "demographics", "OSPI Report Card enrollment", "https://data.wa.gov/d/rxjk-6ieq", publisher="Washington OSPI", native_id="rxjk-6ieq")
    source, rows = raw_source(b, dataset, path, "demographics")
    pop = b.population("WA", "All enrolled students in the reported school/grade", "all_students", source,
                       definition="Enrollment population, not an assessment-tested denominator or DL participant population.")
    for index, row in enumerate(rows, 1):
        if row["organizationlevel"].casefold() != "school":
            raise ValueError("Enrollment pilot contains a non-school reporting unit")
        year = school_year(row["schoolyear"])
        sid = b.resolve("school", "WA_OSPI_school_organization_id", row["schoolorganizationid"], year=year, default="WA-S" + row["schoolorganizationid"])
        if (sid,) not in b.tables["schools"]:
            raise ValueError("Enrollment school missing from identity registry")
        rid = b.reporting_unit("WA", "school", sid, b.tables["schools"][(sid,)]["school_name"])
        # Preserve the native label alongside a canonical grade; never allocate an aggregate across grades.
        common = dict(reporting_unit_id=rid, school_year=year, grade_scope=grade_scope(row["gradelevel"]), population_id=pop,
                      subject="enrollment", domain="not_applicable", administration="enrollment_snapshot",
                      source_population_raw="All enrolled students", source_grade_raw=row["gradelevel"], source_id=source,
                      notes="School enrollment demographics only. low_income retains the OSPI definition and is not automatically FRL eligibility. DAT: " + str(row.get("dat", "not_reported")))
        for field in DEMOGRAPHIC_FIELDS:
            metric = b.metric("WA_ENROLLMENT_" + field.upper() + "_N", "OSPI " + field.replace("_", " "), "demographic_count", "count",
                              "Not a rate; enrollment count in this reported school/grade.", "WA_OSPI_enrollment_source_definition")
            oid = b.observation("demographics", **common, metric_id=metric, source_value_unit="count",
                                source_locator=f"JSON record {index}, field {field}", **parse_value(row.get(field)))
            contextual_links(b, "demographics", oid, sid, year, source, sites)
        # Ratios are derived only from unsuppressed matching row counts, without reconstructing suppressed groups.
        for field in ["low_income", "english_language_learners", "hispanic_latino_of_any_race"]:
            metric = b.metric("WA_ENROLLMENT_" + field.upper() + "_SHARE_PCT", "OSPI " + field.replace("_", " ") + " share", "demographic_rate", "percent",
                              "Reported all_students count from the identical source school/year/grade enrollment row.", "WA_OSPI_enrollment_derived_share")
            parsed = ratio(row.get(field), row.get("all_students"))
            oid = b.observation("demographics", **common, metric_id=metric, source_value_unit="derived_from_counts",
                source_locator=f"JSON record {index}, fields {field}/all_students", denominator_status="derived_matching_population" if parsed["value_status"] == "derived" else "not_applicable" if parsed["value_status"] == "not_applicable" else "not_reported",
                numerator=number_or_none(row.get(field)), denominator=number_or_none(row.get("all_students")),
                derivation_method="100 * reported subgroup count / reported all_students count in the same school/year/grade; no imputation", **parsed)
            contextual_links(b, "demographics", oid, sid, year, source, sites)
