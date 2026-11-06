"""Schema, identity, time, missingness, population and attribution validation."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator

from .contracts import catalog, typed_row
from .io import digest, grade_scope, read_csv, school_year
from .measurements import parse_value

OBSERVATIONS = ["dl_participant_outcomes", "state_assessments", "demographics", "el_proficiency", "el_exit_outcomes", "seda"]


def load(root):
    definition = catalog()
    tables = {}
    for name, schema in definition["$defs"].items():
        path = root / schema["x-path"]
        rows = read_csv(path)
        # Empty tables still require the complete contract header.
        import csv
        with path.open(encoding="utf-8-sig", newline="") as stream:
            if next(csv.reader(stream)) != list(schema["properties"]):
                raise ValueError(f"Header differs from contract: {path}")
        tables[name] = [typed_row(row, schema) for row in rows]
    return definition, tables


def validate_tables(tables, definition=None):
    definition = definition or catalog()
    errors = []
    indices = {}
    for name, schema in definition["$defs"].items():
        validator = Draft202012Validator(schema)
        primary = schema["x-primary-key"]
        index = {}
        unique = [set() for _ in schema.get("x-unique", [])]
        for number, row in enumerate(tables[name], 2):
            for error in validator.iter_errors(row):
                errors.append(f"{name}:{number}: {'.'.join(map(str, error.path))}: {error.message}")
            key = tuple(row.get(k) for k in primary)
            if key in index:
                errors.append(f"{name}: duplicate primary key {key}")
            index[key] = row
            for fields, seen in zip(schema.get("x-unique", []), unique):
                value = tuple(row.get(k) for k in fields)
                if value in seen:
                    errors.append(f"{name}: duplicate reporting grain {fields}: {value}")
                seen.add(value)
            for field, value in row.items():
                if value and (field.endswith("_year") or field == "school_year"):
                    try:
                        school_year(value)
                    except ValueError:
                        errors.append(f"{name}: invalid academic year in {field}: {value}")
                if value and field in {"publication_date", "last_reviewed_date"}:
                    try:
                        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                            raise ValueError()
                        date.fromisoformat(value)
                    except ValueError:
                        errors.append(f"{name}: invalid calendar date in {field}: {value}")
                if value and field == "retrieved_at":
                    try:
                        if datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
                            raise ValueError()
                    except ValueError:
                        errors.append(f"{name}: retrieval timestamp must include a timezone: {value}")
            if row.get("valid_from_year") and row.get("valid_to_year") and row["valid_from_year"] > row["valid_to_year"]:
                errors.append(f"{name}: reversed validity interval")
        indices[name] = index
    for name, schema in definition["$defs"].items():
        for row in tables[name]:
            for field, ref in schema["x-foreign-keys"].items():
                if row.get(field) is not None and (row[field],) not in indices[ref["table"]]:
                    errors.append(f"{name}: missing {field} -> {ref['table']}: {row[field]}")
    # Validate polymorphic identity references rather than accepting any nonempty ID.
    entity_tables = {"school": "schools", "district": "districts", "program": "programs", "site": "program_sites", "schedule": "allocation_schedules", "state": "states"}
    for table in ["identifiers", "evidence_claims", "reporting_units"]:
        for row in tables[table]:
            target = entity_tables.get(row["entity_type"])
            if not target or (row["entity_id"],) not in indices[target]:
                errors.append(f"{table}: unknown polymorphic entity {row['entity_type']}:{row['entity_id']}")
    identifiers = defaultdict(list)
    for row in tables["identifiers"]:
        identifiers[(row["namespace"], row["native_id"])].append(row)
    for key, rows in identifiers.items():
        for i, left in enumerate(rows):
            for right in rows[i+1:]:
                if left["entity_id"] == right["entity_id"]:
                    continue
                # Unknown validity cannot establish two disjoint identities for a reused code.
                lo = max(left["valid_from_year"] or "0000-00", right["valid_from_year"] or "0000-00")
                hi = min(left["valid_to_year"] or "9999-99", right["valid_to_year"] or "9999-99")
                if lo <= hi:
                    errors.append(f"identifiers: ambiguous time-overlapping mapping for {key}")
    allocations = defaultdict(list)
    for row in tables["instructional_allocations"]:
        allocations[row["schedule_id"]].append(row)
    for sid, rows in allocations.items():
        if abs(sum(row["instruction_share_pct"] for row in rows) - 100) > 0.001:
            errors.append(f"instructional_allocations: named-language shares do not sum to 100: {sid}")
        schedule = indices["allocation_schedules"].get((sid,))
        if schedule and schedule["schedule_status"] == "reported_policy_requires_review":
            errors.append(f"instructional_allocations: unreviewed model label converted to named-language shares: {sid}")
        if schedule and ((schedule["schedule_status"] == "inferred_plan") != any(row["evidence_type"] == "researcher_inference" for row in rows)):
            errors.append(f"instructional_allocations: inferred schedule/evidence type mismatch: {sid}")
    for row in tables["program_languages"]:
        if row["language_name"].casefold() in {"unknown", "unverified", "not_reported"}:
            errors.append("program_languages: unknown language is a fabricated named-language record")
        match = re.match(r"^(20\d{2}-\d{2}) roster", row["evidence_period_raw"] or "")
        if match and row["valid_from_year"] and row["valid_from_year"] < match[1]:
            errors.append("program_languages: later roster backdated to an earlier school year")
    for row in tables["program_status_history"]:
        reference = re.fullmatch(r"confirmed_(\d{4})_(\d{2})", row["operating_status"])
        if reference and row["school_year"] != reference[1] + "-" + reference[2]:
            errors.append("program_status_history: confirmation assigned to a different reference year")
        if row["confirmation_method"] == "continuity_no_end_indication":
            site = indices["program_sites"].get((row["site_id"],))
            evidence = [claim for claim in tables["evidence_claims"] if site and claim["entity_type"] == "program" and claim["entity_id"] == site["program_id"] and claim["attribute"] == "continuity_review" and claim["valid_from_year"] == row["school_year"] and claim["confirmation_method"] == "continuity_review"]
            if not evidence:
                errors.append("program_status_history: continuity confirmation lacks its saved review")
    for row in tables["allocation_schedules"]:
        if row.get("grade_support_status") in {"EARLIER_GRADE_PROXY_NOT_TARGET_QUANTIFIED", "MODEL_LABEL_MINUTES_DIFFER", "SOURCE_DOES_NOT_SUPPORT_PROGRAM_GRADE_PERIOD", "UNRECOVERED", "PUBLISHED_MODEL_ONLY", "CONFLICTING_SOURCE_CLAIMS", "SOURCE_GRADE_SCOPE_NOT_REPORTED", "COMPOSITE_TRACK_SCOPE_UNRESOLVED"}:
            if row["schedule_status"] != "reported_policy_requires_review" or allocations.get(row["schedule_id"]):
                errors.append("allocation_schedules: unresolved grade evidence promoted to an accepted numeric schedule")
        if row["tested_cohort_exposure"] == "verified":
            evidence = [r for r in tables["evidence_claims"] if r["entity_type"] == "schedule" and r["entity_id"] == row["schedule_id"] and r["attribute"] == "tested_cohort_exposure" and r["verification_status"] == "documented"]
            if not row["entry_cohort_year"] or not evidence:
                errors.append("allocation_schedules: policy promoted to tested-cohort exposure without cohort evidence")
    metric_families = {"demographics": {"demographic_count", "demographic_rate"}, "el_exit_outcomes": {"el_exit_count", "el_exit_rate"},
                       "seda": {"seda_achievement", "seda_growth"}, "el_proficiency": {"english_proficiency", "assessment_count"},
                       "state_assessments": {"academic_proficiency", "assessment_count"},
                       "dl_participant_outcomes": {"academic_proficiency", "assessment_count", "english_proficiency", "partner_proficiency"}}
    for table in OBSERVATIONS:
        for row in tables[table]:
            oid = row["observation_id"]
            unit = indices["reporting_units"].get((row["reporting_unit_id"],))
            population = indices["populations"].get((row["population_id"],))
            metric = indices["metrics"].get((row["metric_id"],))
            assessment = indices["assessments"].get((row["assessment_id"],))
            if not row["school_year"] and not (row["period_start"] and row["period_end"]):
                errors.append(f"{table}: observation lacks a year or complete reporting period: {oid}")
            if row["period_start"] and row["period_end"] and row["period_start"] > row["period_end"]:
                errors.append(f"{table}: reversed reporting period: {oid}")
            if row["period_start"] or row["period_end"]:
                if not row["period_start"] or not row["period_end"]:
                    errors.append(f"{table}: incomplete reporting period: {oid}")
                for field in ["period_start", "period_end"]:
                    if not row[field]:
                        continue
                    try:
                        if row["period_basis"] == "school_year":
                            school_year(row[field])
                        elif row["period_basis"] == "calendar_year":
                            if not re.fullmatch(r"\d{4}", row[field]):
                                raise ValueError()
                        elif row["period_basis"] == "calendar_date":
                            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[field]):
                                raise ValueError()
                            date.fromisoformat(row[field])
                        else:
                            raise ValueError()
                    except ValueError:
                        errors.append(f"{table}: period value conflicts with its time basis: {oid}")
            if row["cohort_status"] == "identified_cohort" and not (row["entry_cohort_year"] or row["cohort_label"]):
                errors.append(f"{table}: cohort claim has no identified cohort: {oid}")
            try:
                native_grade = grade_scope(row["source_grade_raw"])
            except ValueError:
                native_grade = None
            if native_grade and row["grade_scope"] != native_grade:
                errors.append(f"{table}: grade scope is finer than/different from the source: {oid}")
            if table == "dl_participant_outcomes" and population and population["population_scope"] not in {"dl_all_participants", "dl_current_el_only", "dl_non_el"}:
                errors.append(f"{table}: non-DL population mislabeled as participants: {oid}")
            if table not in {"demographics", "el_exit_outcomes"} and not assessment:
                errors.append(f"{table}: missing assessment definition: {oid}")
            if unit and population and unit["state_code"] != population["state_code"]:
                errors.append(f"{table}: population and reporting unit state mismatch: {oid}")
            if unit and assessment and assessment["state_code"] and unit["state_code"] != assessment["state_code"]:
                errors.append(f"{table}: assessment and reporting unit state mismatch: {oid}")
            if metric and metric["metric_family"] not in metric_families[table]:
                errors.append(f"{table}: incompatible metric family: {oid}")
            value = row["value_numeric"]
            if row["value_status"] in {"observed", "derived"} and value is None:
                errors.append(f"{table}: numeric observation has no value: {oid}")
            if row["value_status"] not in {"observed", "derived"} and value is not None:
                errors.append(f"{table}: masked/missing/bounded value became a point estimate: {oid}")
            if row["value_status"] == "bounded" and row["value_lower_bound"] is None and row["value_upper_bound"] is None:
                errors.append(f"{table}: bounded value lost its bound: {oid}")
            if metric and value is not None:
                if metric["value_unit"] == "percent" and not 0 <= value <= 100:
                    errors.append(f"{table}: percentage outside 0–100: {oid}")
                if metric["value_unit"] == "count" and (value < 0 or value != int(value)):
                    errors.append(f"{table}: invalid count: {oid}")
                if metric["value_unit"] == "percent" and row["source_value_unit"] == "proportion" and row["value_status"] == "observed":
                    expected_value = parse_value(row["value_raw"], source_unit="proportion", target_unit="percent")["value_numeric"]
                    if expected_value is None or abs(value - expected_value) > 1e-6:
                        errors.append(f"{table}: source proportion was not converted to percent: {oid}")
            if row["numerator"] is not None and row["denominator"] is not None and row["numerator"] > row["denominator"]:
                errors.append(f"{table}: numerator exceeds denominator: {oid}")
            if row["value_status"] == "derived":
                if not row["derivation_method"] or row["denominator_status"] != "derived_matching_population" or row["denominator"] in {None, 0} or row["numerator"] is None:
                    errors.append(f"{table}: derived rate lacks observed matching counts: {oid}")
                elif metric and metric["value_unit"] == "percent" and abs(value - 100 * row["numerator"] / row["denominator"]) > 1e-6:
                    errors.append(f"{table}: derived rate disagrees with numerator/denominator: {oid}")
    linked = defaultdict(list)
    for row in tables["observation_program_links"]:
        observation = indices[row["observation_table"]].get((row["observation_id"],))
        site = indices["program_sites"].get((row["site_id"],))
        if not observation:
            errors.append("observation_program_links: missing observation")
            continue
        unit = indices["reporting_units"].get((observation["reporting_unit_id"],))
        if not unit or not site:
            continue
        if unit["entity_type"] != "school" or unit["entity_id"] != site["school_id"]:
            errors.append("observation_program_links: source result assigned below/across its reporting unit")
        if row["attribution_status"] == "schoolwide_context" and unit["reporting_scope"] != "entity_wide":
            errors.append("observation_program_links: reporting group relabeled as schoolwide")
        if row["attribution_status"] == "direct_program":
            population = indices["populations"].get((observation["population_id"],))
            if not population or not population["population_scope"].startswith("dl_"):
                errors.append("observation_program_links: schoolwide/non-DL outcome promoted to program outcome")
            if row["attribution_basis"] not in {"explicit_program_identifier", "explicit_single_track_population"}:
                errors.append("observation_program_links: direct attribution lacks an explicit basis")
            evidence = [claim for claim in tables["evidence_claims"] if claim["entity_type"] == "site" and claim["entity_id"] == row["site_id"] and claim["attribute"] == "outcome_population" and claim["source_id"] == row["evidence_source_id"] and claim["verification_status"] == "documented" and claim["valid_from_year"] == observation["school_year"]]
            if not evidence:
                errors.append("observation_program_links: direct attribution lacks dated population evidence")
        linked[(row["observation_table"], row["observation_id"])].append(row)
    for rows in linked.values():
        if sum(row["attribution_status"] == "direct_program" for row in rows) > 1:
            errors.append("observation_program_links: one source observation disaggregated across programs")
    for row in tables["el_exit_policies"]:
        for field in ["domain_cut_scores_json", "additional_requirements_json"]:
            try:
                value = json.loads(row[field])
                if not isinstance(value, (dict, list)):
                    raise ValueError()
            except (ValueError, TypeError):
                errors.append("el_exit_policies: invalid structured policy requirements")
    return errors


def validate(root: Path, *, verify_manifest=True):
    definition, tables = load(root)
    errors = validate_tables(tables, definition)
    if len(tables["states"]) != 50:
        errors.append("Expected all 50 state identities")
    expected = len(tables["states"]) * len({r["school_year"] for r in tables["coverage"]}) * 8
    if len(tables["coverage"]) != expected:
        errors.append("Coverage matrix is incomplete")
    if verify_manifest:
        manifest = json.loads((root / "data/curated/manifest.json").read_text())
        for section in ["inputs", "pipeline_files"]:
            for relative, expected_hash in manifest[section].items():
                path = root / relative
                if not path.is_file() or digest(path) != expected_hash:
                    errors.append(f"Manifest input/code changed: {relative}; rebuild before validating")
        for relative, info in manifest["outputs"].items():
            if digest(root / relative) != info["sha256"]:
                errors.append(f"Manifest output changed: {relative}")
        for relative, info in manifest.get("reports", {}).items():
            if not (root / relative).is_file() or digest(root / relative) != info["sha256"]:
                errors.append(f"Manifest review report changed: {relative}")
    for source in tables["sources"]:
        if source["snapshot_path"]:
            path = root / source["snapshot_path"]
            if not path.is_file() or digest(path) != source["sha256"]:
                errors.append(f"Source snapshot differs from archived bytes: {source['snapshot_path']}")
    if errors:
        raise ValueError("\n".join(errors[:80]) + (f"\n... {len(errors)} total errors" if len(errors) > 80 else ""))
    return {"status": "PASS", "schema_version": definition["x-schema-version"], "tables": len(tables), "rows": {name: len(rows) for name, rows in tables.items()}}
