"""Build reviewed national tables from immutable, explicitly selected pilot inputs."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import re
import subprocess

from .contracts import catalog
from .io import digest, record_id, write_csv


class Build:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.schema = catalog()
        self.tables = {name: {} for name in self.schema["$defs"]}
        self.inputs = {}
        self.notes = []
        from .registry import IdentityResolver
        self.identity = IdentityResolver(self.track_input("config/identity_mappings.csv"))

    def resolve(self, entity_type, namespace, native_id, *, year=None, default):
        return self.identity.resolve(entity_type, namespace, native_id, year, default)

    def add(self, table, **values):
        definition = self.schema["$defs"][table]
        fields = definition["properties"]
        extra = set(values) - set(fields)
        if extra:
            raise ValueError(f"Unexpected {table} fields: {extra}")
        row = {field: values.get(field) for field in fields}
        key = tuple(row[field] for field in definition["x-primary-key"])
        previous = self.tables[table].get(key)
        if previous is not None and previous != row:
            raise ValueError(f"Conflicting {table} identity: {key}")
        self.tables[table][key] = row
        return key[0] if len(key) == 1 else key

    def rows(self, table):
        return list(self.tables[table].values())

    def track_input(self, path):
        path = Path(path)
        if not path.is_absolute():
            path = self.root / path
        self.inputs[str(path.relative_to(self.root))] = digest(path)
        return path

    def dataset(self, dataset_id, state, layer, name, url, publisher=None, native_id=None, notes=None):
        return self.add("datasets", dataset_id=dataset_id, state_code=state, layer=layer, dataset_name=name,
                        publisher=publisher, source_url=url, native_dataset_id=native_id, notes=notes)

    def source_file(self, dataset_id, path, *, url=None, metadata=None):
        path = self.track_input(path)
        fingerprint = digest(path)
        sid = record_id("source", dataset_id, fingerprint)
        if metadata is not None:
            metadata = self.track_input(metadata)
            meta = json.loads(metadata.read_text())
            if fingerprint != meta["sha256"]:
                raise ValueError(f"Raw source checksum mismatch: {path}")
            source_url = meta["url"]
            retrieved = meta["retrieved_at"]
            kind = "saved_public_source"
            version = fingerprint[:16]
        else:
            source_url = url or "repo:" + str(path.relative_to(self.root))
            retrieved = None
            kind = "legacy_snapshot"
            version = "legacy_snapshot_" + fingerprint[:16]
        # Equal bytes can have distinct capture metadata. Retain and validate
        # every receipt before deduplicating the source identity so portable
        # bundles contain all files that an adapter reads.
        if (sid,) in self.tables["sources"]:
            return sid
        return self.add("sources", source_id=sid, dataset_id=dataset_id, source_url=source_url,
                        version_label=version, retrieved_at=retrieved,
                        snapshot_path=str(path.relative_to(self.root)), sha256=fingerprint, snapshot_kind=kind,
                        notes="Hash identifies the saved source bytes. Legacy import dates are not fabricated.")

    def citation(self, dataset_id, url, *, key=None, period=None, retrieved=None, remote_hash=None):
        sid = record_id("citation", dataset_id, key or url, period)
        if (sid,) in self.tables["sources"]:
            return sid
        return self.add("sources", source_id=sid, dataset_id=dataset_id, source_url=url,
                        version_label=period or "undated_or_not_reported", retrieved_at=retrieved,
                        evidence_period_raw=period, sha256=remote_hash, snapshot_kind="metadata_only",
                        notes="Citation metadata retained; original document bytes are not asserted to be archived here.")

    def identifier(self, entity_type, entity_id, namespace, native_id, source, *, year=None, status="source_identifier"):
        if not native_id:
            return
        self.add("identifiers", identifier_id=record_id("identifier", entity_type, entity_id, namespace, native_id, year, source),
                 entity_type=entity_type, entity_id=entity_id, namespace=namespace, native_id=str(native_id),
                 valid_from_year=year, valid_to_year=year, match_status=status, source_id=source)

    def school(self, sid, state, name, source, *, namespace=None, native_id=None, year=None, status="state_identifier", screening="candidate"):
        if (sid,) not in self.tables["schools"]:
            self.add("schools", school_id=sid, state_code=state, school_name=name,
                     identity_status=status, screening_status=screening)
        if namespace:
            self.identifier("school", sid, namespace, native_id, source, year=year)
        return sid

    def district(self, did, state, name, source, *, namespace=None, native_id=None, year=None, status="state_identifier"):
        if (did,) not in self.tables["districts"]:
            self.add("districts", district_id=did, state_code=state, district_name=name, identity_status=status)
        if namespace:
            self.identifier("district", did, namespace, native_id, source, year=year)
        return did

    def membership(self, school, district, source, locator, *, year=None):
        mid = record_id("membership", school, district, year, source)
        if (mid,) in self.tables["school_district_history"]:
            return mid
        return self.add("school_district_history", membership_id=mid,
                 school_id=school, district_id=district, school_year=year,
                 validity_status="source_year" if year else "snapshot_only", source_id=source, source_locator=locator)

    def claim(self, entity_type, entity, attribute, value, source, locator, *, year=None, period=None, status="provisional", method="source_record", import_source=None, notes=None):
        self.add("evidence_claims", claim_id=record_id("claim", entity_type, entity, attribute, source, locator),
                 entity_type=entity_type, entity_id=entity, attribute=attribute, reported_value=value,
                 valid_from_year=year, valid_to_year=year, grade_scope="not_reported", verification_status=status,
                 confirmation_method=method, source_id=source, source_locator=locator,
                 import_source_id=import_source, notes=notes, evidence_period_raw=period)

    def reporting_unit(self, state, entity_type, entity, label, *, group=None):
        rid = record_id("reporting_unit", state, entity_type, entity, group)
        if (rid,) not in self.tables["reporting_units"]:
            self.add("reporting_units", reporting_unit_id=rid, state_code=state, entity_type=entity_type,
                     entity_id=entity, program_reporting_group=group, source_unit_label=label,
                     reporting_scope="program_reporting_group" if group else "entity_wide")
        return rid

    def population(self, state, label, scope, source, *, group_type=None, definition=None):
        pid = record_id("population", state, label, scope, group_type, source)
        if (pid,) not in self.tables["populations"]:
            self.add("populations", population_id=pid, state_code=state, population_label=label,
                     population_scope=scope, native_group_type=group_type, native_group_label=label,
                     definition=definition or "Source-reported population; no DL membership inferred.", source_id=source)
        return pid

    def metric(self, mid, name, family, unit, denominator, group, notes=None):
        if (mid,) not in self.tables["metrics"]:
            self.add("metrics", metric_id=mid, metric_name=name, metric_family=family, value_unit=unit,
                     denominator_definition=denominator, comparability_group=group, notes=notes)
        return mid

    def observation(self, table, **values):
        values.setdefault("cohort_status", "repeated_cross_section")
        values.setdefault("period_basis", "school_year" if values.get("school_year") else "not_reported")
        values.setdefault("administration", "not_reported")
        values.setdefault("domain", "not_reported")
        values.setdefault("assessed_language", "not_reported")
        values.setdefault("denominator_status", "not_reported")
        grain = self.schema["$defs"][table]["x-unique"][0]
        oid = record_id("observation", table, *[values.get(k) for k in grain])
        return self.add(table, observation_id=oid, **values)

    def link(self, table, oid, site, source, status, note):
        self.add("observation_program_links", link_id=record_id("outcome_link", table, oid, site),
                 observation_table=table, observation_id=oid, site_id=site,
                 attribution_status=status, attribution_basis="context_only" if status == "schoolwide_context" else "combined_source_group" if status == "combined_reporting_group" else "unresolved",
                 evidence_source_id=source, notes=note)

    def finish(self):
        from .coverage import build_coverage
        if (self.root/'config/research_migrations/elementary_allocation_audit_2026_11_04.json').exists():
            from .elementary_audit import prepare_grade_context
            prepare_grade_context(self)
        if (self.root/'config/research_migrations/ut_tx_allocations_2026_11_05.json').exists():
            from .allocation_enrichment import migrate as enrich_allocations
            enrich_allocations(self)
        if (self.root/'config/research_migrations/tx_allocation_review_2026_11_05.json').exists():
            from .allocation_review import migrate as apply_allocation_review
            apply_allocation_review(self)
        if (self.root/'config/research_migrations/structural_gaps_pilot_2026_11_06.json').exists():
            from .gap_pilot import migrate as apply_gap_pilot
            apply_gap_pilot(self)
        for mapping in self.identity.rows:
            if mapping["review_status"] != "accepted":
                continue
            dataset = self.dataset("REVIEWED_IDENTITY_MAPPINGS", None, "inventory", "Reviewed identity continuity decisions", "repo:config/identity_mappings.csv")
            source = self.citation(dataset, mapping["evidence_url"], key=mapping["namespace"] + ":" + mapping["native_id"], period=mapping["valid_from_year"] or "undated")
            self.add("identifiers", identifier_id=record_id("reviewed_identifier", *mapping.values()),
                     entity_type=mapping["entity_type"], entity_id=mapping["research_entity_id"], namespace=mapping["namespace"],
                     native_id=mapping["native_id"], valid_from_year=mapping["valid_from_year"] or None,
                     valid_to_year=mapping["valid_to_year"] or None, match_status="reviewed_identity_mapping", source_id=source)
        from .edc import register as register_edc
        register_edc(self)
        build_coverage(self)
        for name, definition in self.schema["$defs"].items():
            rows = sorted(self.rows(name), key=lambda r: tuple(str(r[k]) for k in definition["x-primary-key"]))
            write_csv(self.root / definition["x-path"], rows, list(definition["properties"]))
        code = {}
        for path in sorted((self.root / "src/dl_outcomes").rglob("*")):
            if path.suffix in {".py", ".json"}:
                code[str(path.relative_to(self.root))] = digest(path)
        for path in sorted((self.root / "config").rglob("*.json")):
            self.track_input(path)
        for name in ["pyproject.toml", "requirements-lock.txt"]:
            self.track_input(self.root / name)
        analytics_lock = self.root / "requirements-analytics-lock.txt"
        if analytics_lock.exists():
            self.track_input(analytics_lock)
        for path in (self.root / "data/raw/legacy_registry/pre_schema_v1").glob("*"):
            self.track_input(path)
        fingerprint = record_id("build", sorted(self.inputs.items()), sorted(code.items()))
        try:
            git_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            git_revision = None
        outputs = {definition["x-path"]: {"sha256": digest(self.root / definition["x-path"]), "rows": len(self.rows(name))}
                   for name, definition in self.schema["$defs"].items()}
        manifest = {"schema_version": self.schema["x-schema-version"], "build_id": fingerprint,
                    "built_at": datetime.now(timezone.utc).isoformat(), "base_git_revision": git_revision,
                    "inputs": dict(sorted(self.inputs.items())), "pipeline_files": code, "outputs": outputs,
                    "limitations": self.notes, "release_status": "pilot_partial_not_a_national_census"}
        from .edc import COLLECTION
        collection_manifest = self.root / COLLECTION / "manifest.json"
        if collection_manifest.exists():
            manifest["assessment_collections"] = {"edc_v3_1_2022_2025": {
                "manifest_path": str(collection_manifest.relative_to(self.root)),
                "manifest_sha256": digest(collection_manifest),
                "result_rows": json.loads((collection_manifest.parent / "summary.json").read_text())["result_rows"],
                "scope": "schoolwide_state_assessment_context_not_DL_participants"}}
        path = self.root / "data/curated/manifest.json"
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        if json.loads((self.root / "config/project.json").read_text()).get("structural_review_report"):
            from .structural import generate_report, report_prefix
            report = generate_report(self.root)
            report_paths = [*report["reports"], report_prefix(self.root) + ".json"]
            manifest["reports"] = {rel: {"sha256": digest(self.root / rel)} for rel in report_paths}
            path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        return {"build_id": fingerprint, "table_rows": {name: len(self.rows(name)) for name in self.tables}, "limitations": self.notes}


def build(root: Path):
    output = Build(root)
    adapters = []
    for path in sorted((root / "config/states").glob("*.json")):
        state = json.loads(path.read_text())
        output.add("states", state_code=state["state_code"], state_name=state["state_name"], state_fips=state["state_fips"])
        if state.get("adapter"):
            name = state["adapter"]
            if not re.fullmatch(r"[a-z_]+", name):
                raise ValueError(f"Invalid state adapter module: {name}")
            adapters.append(name)
    for name in adapters:
        importlib.import_module("dl_outcomes.states." + name).migrate(output)
    return output.finish()
