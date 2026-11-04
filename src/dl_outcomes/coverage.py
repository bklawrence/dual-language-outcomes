"""Coverage is explicit collection status, never an inference from absent rows."""
from collections import defaultdict
import json
import re

from .io import read_csv, record_id


def build_coverage(b):
    config = json.loads((b.root / "config/project.json").read_text())
    years = {f"{year}-{(year+1) % 100:02d}" for year in range(config["coverage_start_year"], config["coverage_end_year"] + 1)}
    found = defaultdict(list)
    layer_tables = {"dl_participants": "dl_participant_outcomes", "state_assessments": "state_assessments", "demographics": "demographics",
                    "el_proficiency": "el_proficiency", "el_exit_outcomes": "el_exit_outcomes", "seda": "seda"}
    for layer, table in layer_tables.items():
        for row in b.rows(table):
            if row["school_year"]:
                unit = b.tables["reporting_units"][(row["reporting_unit_id"],)]
                population = b.tables["populations"][(row["population_id"],)]
                years.add(row["school_year"])
                found[(unit["state_code"], row["school_year"], layer)].append((unit["entity_type"], row["grade_scope"], population["population_scope"], row["source_id"]))
    for row in b.rows("program_configurations"):
        if row["school_year"]:
            site = b.tables["program_sites"][(row["site_id"],)]
            state = b.tables["schools"][(site["school_id"],)]["state_code"]
            years.add(row["school_year"])
            found[(state, row["school_year"], "inventory")].append(("school", row["grade_scope"], "program_metadata_only", row["source_id"]))
    for row in b.rows("evidence_claims"):
        if row["valid_from_year"] and row["entity_type"] == "program":
            state = b.tables["programs"][(row["entity_id"],)]["state_code"]
            year = row["valid_from_year"]
            years.add(year)
            found[(state, year, "inventory")].append(("school", row["grade_scope"], "provisional_evidence_only", row["source_id"]))
    for row in b.rows("allocation_schedules"):
        if row["school_year"]:
            state = b.tables["schools"][(row["school_id"],)]["state_code"]
            years.add(row["school_year"])
            found[(state, row["school_year"], "inventory")].append(("school", row["grade_scope"], "allocation_plan_only", row["source_id"]))
    # Recognize earlier research without pretending it has been migrated or searched anew.
    identified = {}
    state_names = {r["state_name"].lower().replace(" ", "_"): r["state_code"] for r in b.rows("states")}
    for path in sorted((b.root / "data/registry").glob("state_dl_programs_*.csv")):
        match = re.fullmatch(r"state_dl_programs_(.+?)(?:_(20\d{2})_(\d{2}))?\.csv", path.name)
        state = state_names.get(match[1]) if match else None
        if not state:
            continue
        if match[2]:
            year = match[2] + "-" + match[3]
        else:
            rows = read_csv(path, legacy=True)
            year = next((r.get("source_school_year") or r.get("school_year") for r in rows if r.get("source_school_year") or r.get("school_year")), None)
        if not year or not re.fullmatch(r"20\d{2}-\d{2}", year):
            continue
        years.add(year)
        dataset = b.dataset(state + "_EXISTING_RESEARCH", state, "inventory", "Existing state program research snapshots", "repo:data/registry/", notes="Recognized for coverage; not migrated by the Texas/Washington pilot.")
        identified[(state, year, "inventory")] = b.source_file(dataset, path)
    for state in b.rows("states"):
        for year in sorted(years):
            for layer in config["coverage_layers"]:
                key = (state["state_code"], year, layer)
                records = found.get(key, [])
                notes = "Not collected in the shared pipeline. This is not evidence that the state lacks publicly reported data."
                source, unit, grade, population, status = identified.get(key), "not_established", "not_established", "not_established", "not_collected"
                if source:
                    status = "source_identified"
                    notes = "Existing research file recognized; its records have not been migrated into the common registry. See the legacy file's own verification status."
                if records:
                    status = "pilot_partial"
                    unit = "school" if any(r[0] == "school" for r in records) else "district" if any(r[0] == "district" for r in records) else "state"
                    grade = " | ".join(sorted({r[1] for r in records}))
                    population = " | ".join(sorted({r[2] for r in records}))
                    source = sorted({r[3] for r in records})[0]
                    notes = "Pilot records exist at the stated scope; this does not establish statewide or historical completeness. Source-specific populations and vintages are retained."
                b.add("coverage", coverage_id=record_id("coverage", *key), state_code=key[0], school_year=year, layer=layer,
                      collection_status=status, smallest_available_unit=unit, grade_scope=grade, population_scope=population,
                      availability_basis="collected_source_scope" if records else "not_established",
                      source_id=source, last_reviewed_date=(b.tables["sources"][(source,)]["retrieved_at"] or "")[:10] or None if source else None,
                      notes=notes)
