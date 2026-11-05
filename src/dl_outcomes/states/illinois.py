"""Migrate the existing Illinois seed without upgrading its provisional claims."""
from ..io import read_csv, record_id


def migrate(b):
    dataset = b.dataset("IL_LEGACY_REGISTRY", "IL", "inventory", "Existing Illinois research seed", "repo:data/registry/", notes="Provisional seed, not statewide coverage.")
    files = {name: b.source_file(dataset, f"data/registry/{name}.csv") for name in ["schools", "programs", "program_sites", "instructional_history", "sources"]}
    citations = {}
    for row in read_csv(b.root / "data/registry/sources.csv"):
        citations[row["source_id"]] = b.citation(dataset, row["url"], key=row["source_id"], period=row["publication_year"] or "undated")
    for row in read_csv(b.root / "data/registry/schools.csv"):
        source = files["schools"]
        sid = b.school(row["school_id"], "IL", row["school_name"], source, status="legacy_provisional", screening=row["screening_status"])
        b.identifier("school", sid, "legacy_inventory_id", row["legacy_inventory_id"], source, status=row["id_status"])
        b.identifier("school", sid, "IL_state_school_id", row["state_school_id"], source, status=row["id_status"])
        b.identifier("school", sid, "NCES_school_id", row["nces_school_id"], source, status=row["id_status"])
        did = record_id("district", "IL", row["district_name"])
        b.district(did, "IL", row["district_name"], source, status="provisional_name_group")
        b.membership(sid, did, source, row["school_id"])
    programs = {r["program_id"]: r for r in read_csv(b.root / "data/registry/programs.csv")}
    for row in programs.values():
        b.add("programs", program_id=row["program_id"], state_code="IL", program_name=row["program_name"],
              identity_status="legacy_provisional", screening_status=row["program_status"], notes=row["notes"])
    sites = {}
    for row in read_csv(b.root / "data/registry/program_sites.csv"):
        site = row["program_site_id"]
        sites[(row["program_id"], row["school_id"])] = site
        b.add("program_sites", site_id=site, program_id=row["program_id"], school_id=row["school_id"],
              valid_from_year=row["start_school_year"] or None, valid_to_year=row["end_school_year"] or None,
              link_status="legacy_provisional", source_id=files["program_sites"])
        program = programs[row["program_id"]]
        for language in (program["language_1"], program["language_2"]):
            b.add("program_languages", language_record_id=record_id("language", site, language, files["programs"]),
                  site_id=site, language_name=language, language_code={"Spanish": "es", "English": "en"}.get(language),
                  language_role="instruction_language", verification_status="unverified", source_id=files["programs"],
                  source_locator=program["program_id"], notes="Legacy label retained; no new pairing verification.")
    for row in read_csv(b.root / "data/registry/instructional_history.csv"):
        if row["other_instruction_pct"] and float(row["other_instruction_pct"]) != 0:
            raise ValueError("A positive legacy 'other' allocation needs a named-language review before migration")
        site = sites[(row["program_id"], row["school_id"])]
        year = f"{row['school_year_start']}-{(int(row['school_year_start']) + 1) % 100:02d}"
        cohort = f"{row['entry_cohort_start_year']}-{(int(row['entry_cohort_start_year']) + 1) % 100:02d}"
        source = citations[row["source_id"]]
        schedule = record_id("schedule", "IL", row["history_id"])
        b.add("allocation_schedules", schedule_id=schedule, school_id=row["school_id"], site_id=site,
              school_year=year, entry_cohort_year=cohort, grade_scope=row["grade"],
              reported_model_label=row["starting_model_label"], percentage_basis=row["percentage_basis"],
              schedule_status="documented_plan", evidence_period_raw=year, tested_cohort_exposure="not_established",
              source_id=source, source_locator=row["history_id"], notes=row["notes"])
        for language, field, code in [("Spanish", "spanish_instruction_pct", "es"), ("English", "english_instruction_pct", "en")]:
            if row[field] != "":
                b.add("instructional_allocations", allocation_id=record_id("allocation", schedule, language),
                      schedule_id=schedule, language_name=language, language_code=code, instruction_share_pct=float(row[field]),
                      evidence_type="documented_plan", source_id=source, source_locator=row["history_id"])
    if (b.root / 'config/research_migrations/great_lakes_2026_11_05.json').exists():
        from .great_lakes import migrate_reviewed_state
        b.notes.append("Illinois retains its original provisional seed alongside the expanded reviewed inventory. Published allocations are policies, not tested-cohort exposure.")
        migrate_reviewed_state(b, 'IL')
    else:
        b.notes.append("Illinois remains a provisional legacy seed. Its 2025–26 allocation is a published plan, not tested-cohort exposure.")
