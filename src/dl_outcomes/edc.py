"""Partitioned school/grade EDC assessment layer and explicit identity audit.

Native results are stored once per EDC reporting unit, independently of the
number of DL research identities or language strands associated with a campus.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
from itertools import zip_longest
import json
from pathlib import Path
import re
import unicodedata

from .collectors.edc import ATTRIBUTION, IDENTITY_FIELDS, SUBJECTS, VERSION, YEARS, sha256_file
from .io import digest, read_csv, record_id, write_csv
from .collection_provenance import ARCHIVES, pinned_dependency

COLLECTION = "data/assessments/edc_v3_1_2022_2025"
BASELINE = "data/baselines/national_structural_v1"
GROUPS = {"All Students", "EL Status", "Economic Status", "RaceEth", "Disability Status", "Gender"}
MEASURES = ["StudentGroup_TotalTested", "StudentSubGroup_TotalTested",
            "ProficientOrAbove_count", "ProficientOrAbove_percent", "ParticipationRate",
            "AvgScaleScore", "AvgSS_SD"] + [f"Lev{i}_{unit}" for i in range(1, 6) for unit in ("count", "percent")]
SUBJECT_MAP = {"ela": "ELA", "math": "math", "read": "reading", "eng": "English", "wri": "writing"}
MATCH_FIELDS = ["school_id", "state_code", "school_name", "district_names", "school_year",
                "match_status", "match_method", "edc_unit_id", "NCESSchoolID", "StateAssignedSchID",
                "NCESDistrictID", "StateAssignedDistID", "edc_school_name", "edc_district_name",
                "identity_source", "notes"]
VALUE_FIELDS = ["raw", "numeric", "status", "lower_bound", "upper_bound", "lower_inclusive", "upper_inclusive"]


def normal_name(value):
    """Conservative spelling normalization; it never selects an identity alone."""
    text = value or ""
    for _ in range(4):
        if not any(c in text for c in ["Ã", "Â"]):
            break
        try:
            text = text.encode("latin1").decode("utf8")
        except (UnicodeError, ValueError):
            break
    text = re.sub("['’ʻʼ]", "", text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\bp\s*[.]?\s*s\b[.]?", "public school", text)
    tokens = re.findall(r"[a-z]+|\d+", text)
    aliases = {"el": "elementary", "elem": "elementary", "es": "elementary", "ms": "middle",
               "hs": "high", "intl": "international", "sch": "school", "ctr": "center",
               "isd": "independent school district", "sd": "school district",
               "dist": "district", "csd": "central school district", "acad": "academy"}
    tokens = [str(int(t)) if t.isdigit() else aliases.get(t, t) for t in tokens]
    return " ".join(t for t in tokens if t not in {"school", "the"})


def district_name(value):
    # NCES legal suffixes often name the district's number and county. This
    # spelling rule only proposes a directory match; the source-year NCES ID
    # and source school name must still corroborate it before an outcome join.
    value = re.split(r"\bdistrict\s+(?:no\.?|r[- ]?\d|re[- ]?\d)", value, flags=re.I)[0]
    words = normal_name(value).split()
    words = ["saint" if word == "st" else word for word in words]
    stop = {"schools", "school", "district", "public", "unified", "independent", "community", "comm",
            "central", "consolidated", "unit", "area", "no", "number", "of", "the", "state", "department",
            "joint", "corp", "corporation", "con", "com", "ccsd", "cusd", "cisd", "usd", "re", "r", "elementary"}
    return " ".join(w for w in words if w not in stop and not w.isdigit())


def source_name(row):
    name = row["SchName"]
    if row["StateAbbrev"] in {"FL", "SD"}:
        suffix = row["StateAssignedSchID"].split("-")[-1]
        match = re.search(r"\s*-\s*(\d+)\s*$", name)
        if suffix.isdigit() and match and int(match[1]) == int(suffix):
            name = name[:match.start()]
    return normal_name(name)


def directory_name(row, state):
    name = row.get("school_name", "")
    if state == "SD":
        suffix = str(row.get("seasch", "")).split("-")[-1]
        match = re.search(r"\s*-\s*(\d+)\s*$", name)
        if suffix.isdigit() and match and int(match[1]) == int(suffix):
            name = name[:match.start()]
    return normal_name(name)


def elementary_name_core(value):
    """Omission of 'elementary' is allowed only with a corroborated district/ID."""
    return " ".join(word for word in value.split() if word != "elementary")


def native_id(value):
    return re.sub(r"[^A-Za-z0-9]", "", value or "").upper()


def nces_id(value, length=12):
    """GCS CSV exports sometimes omit the first zero; retain native cells too."""
    value = str(value or "")
    return value.zfill(length) if value.isdigit() and len(value) in {length-1, length} else ""


def unit_id(row):
    nces = nces_id(row.get("NCESSchoolID", ""))
    # Missing NCES IDs are not combined into a single fictitious school.
    key = nces if re.fullmatch(r"\d{12}", nces) else [row.get(k, "") for k in IDENTITY_FIELDS[3:8]]
    return record_id("edc_unit", row["StateAbbrev"], key)


def source_index(entries):
    index = {"year": entries[0]["SchYear"] if entries else "", "entries": entries,
             "nces": defaultdict(list), "native": defaultdict(list), "name": defaultdict(list)}
    for row in entries:
        index["nces"][nces_id(row["NCESSchoolID"])].append(row)
        key = native_id(row["StateAssignedSchID"])
        if row["StateAbbrev"] == "TX" and key.isdigit():
            key = key.zfill(9)
        if row["StateAbbrev"] == "CA" and key.isdigit():
            key = key.zfill(14)
        index["native"][key].append(row)
        index["name"][source_name(row)].append(row)
    return index


def parse_edc_value(raw, *, proportion=False):
    """Keep suppression, missingness, exact zero and bounds distinguishable."""
    original = "" if raw is None else str(raw)
    value = original.strip()
    result = dict(raw=original, numeric="", status="not_reported", lower_bound="",
                  upper_bound="", lower_inclusive="", upper_inclusive="")
    if value in {"", "--", "NA", "N/A", "Missing/not reported"}:
        return result
    if value in {"*", "**", "***", "Suppressed"}:
        return result | {"status": "suppressed"}
    if value.lower() in {"not applicable", "n/a - not applicable"}:
        return result | {"status": "not_applicable"}
    multiplier = Decimal(100) if proportion else Decimal(1)
    def number(text):
        n = Decimal(text) * multiplier
        if not n.is_finite():
            raise ValueError("Nonfinite EDC value: " + value)
        return format(n, "f")
    decimal = r"(?:\d+(?:\.\d*)?|\.\d+)"
    bounded = re.fullmatch(r"(<=|>=|<|>|≤|≥)\s*(" + decimal + r")", value)
    interval = re.fullmatch(r"(" + decimal + r")\s*[-–]\s*(" + decimal + r")", value)
    if bounded:
        op, n = bounded.groups()
        side = "upper" if op in {"<", "<=", "≤"} else "lower"
        result.update(status="bounded")
        result[side + "_bound"] = number(n)
        result[side + "_inclusive"] = "1" if op in {"<=", ">=", "≤", "≥"} else "0"
    elif interval:
        low, high = map(Decimal, interval.groups())
        if low > high:
            raise ValueError("Reversed EDC interval: " + value)
        result.update(status="bounded", lower_bound=number(str(low)), upper_bound=number(str(high)),
                      lower_inclusive="1", upper_inclusive="1")
    else:
        try:
            result.update(status="reported", numeric=number(value))
        except InvalidOperation:
            return result | {"status": "unrecognized_source_token"}
    return result


def target_rows(root):
    """Save the cohort and the exact identifier/directory evidence being checked."""
    schools = read_csv(root / BASELINE / "schools.csv")
    wanted = {r["school_id"] for r in schools}
    identifiers, directory = defaultdict(list), defaultdict(list)
    for row in read_csv(root / "data/curated/registry/identifier_crosswalk.csv"):
        if row["entity_type"] == "school" and row["entity_id"] in wanted:
            if row["namespace"] in {"NCES_school_id", "TX_TEA_campus_id", "CA_CDS", "WA_OSPI_school_code", "IL_state_school_id", "NYC_DBN"}:
                identifiers[row["entity_id"]].append(row)
    with (root / "data/curated/sources/evidence_claims.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["entity_type"] == "school" and row["entity_id"] in wanted and row["attribute"] in {"elementary_audit_school_grade_context", "school_grade_context"}:
                try:
                    value = json.loads(row["reported_value"])
                except (ValueError, TypeError):
                    continue
                if isinstance(value, dict) and value.get("ncessch"):
                    directory[row["entity_id"]].append(dict(value, claim_id=row["claim_id"], source_id=row["source_id"]))
    # Additional directory corroboration is separate from the frozen grade-context
    # candidates. Require unique school AND district agreement, then confirm the
    # resulting NCES identity again in each year's EDC source.
    state_by_fips = {int(r["state_fips"]): r["state_code"] for r in read_csv(root / "data/curated/registry/states.csv")}
    lookup = defaultdict(dict)
    by_name = defaultdict(dict)
    by_core, core_lookup = defaultdict(dict), defaultdict(dict)
    for path in sorted((root / "data/raw").glob("**/*ccd*.json")):
        if "metadata" in path.name:
            continue
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict):
            continue
        fingerprint = digest(path)
        for d in payload.get("results", []):
            if not isinstance(d, dict) or not d.get("ncessch") or d.get("year") != 2024:
                continue
            state = state_by_fips.get(int(d.get("fips", -1)))
            if state:
                key = (state, directory_name(d, state), district_name(d.get("lea_name", "")))
                lookup[key][d["ncessch"]] = dict(d, snapshot_path=str(path.relative_to(root)), snapshot_sha256=fingerprint,
                                                match_method="unique_directory_school_and_district_then_EDC_ID_corroboration")
                by_name[(state, directory_name(d, state))][d["ncessch"]] = lookup[key][d["ncessch"]]
                core = elementary_name_core(directory_name(d, state))
                by_core[(state, core)][d["ncessch"]] = lookup[key][d["ncessch"]]
                core_lookup[(state, core, key[2])][d["ncessch"]] = lookup[key][d["ncessch"]]
    alias_path = root / "config/edc_district_identity_reviews.csv"
    district_reviews = {(r["state_code"], r["research_district_name"]): r for r in read_csv(alias_path)} if alias_path.exists() else {}
    for target in schools:
        if directory[target["school_id"]]:
            continue
        found = {}
        for name in target["district_names"].split(" | "):
            core = district_name(name)
            if core:
                found.update(lookup.get((target["state_code"], normal_name(target["school_name"]), core), {}))
            review = district_reviews.get((target["state_code"], name))
            if review:
                for nces, candidate in by_name.get((target["state_code"], normal_name(target["school_name"])), {}).items():
                    if nces.startswith(review["nces_district_id"]):
                        found[nces] = dict(candidate, district_identity_review=review)
        if not found and target["school_level"] == "elementary":
            core = elementary_name_core(normal_name(target["school_name"]))
            for name in target["district_names"].split(" | "):
                district = district_name(name)
                if district:
                    found.update(core_lookup.get((target["state_code"], core, district), {}))
                review = district_reviews.get((target["state_code"], name))
                if review:
                    found.update({nces: candidate for nces, candidate in by_core.get((target["state_code"], core), {}).items()
                                  if nces.startswith(review["nces_district_id"])})
            if len(found) == 1:
                nces = next(iter(found))
                found[nces] = dict(found[nces], match_method="unique_directory_elementary_name_core_and_district_then_EDC_ID_corroboration")
        if len(found) == 1:
            directory[target["school_id"]].append(next(iter(found.values())))
    return [dict(r, official_identifiers_json=json.dumps(identifiers[r["school_id"]], sort_keys=True),
                 directory_evidence_json=json.dumps(directory[r["school_id"]], sort_keys=True)) for r in schools]


def choose_match(target, entries, overrides=None):
    """Corroborate candidate IDs with named, dated source identities; no fuzzy join."""
    index = entries if isinstance(entries, dict) else source_index(entries)
    year = index["year"]
    if overrides and (target["school_id"], year) in overrides:
        choice = overrides[(target["school_id"], year)]
        candidates = index["nces"].get(nces_id(choice["nces_school_id"]), [])
        if len({unit_id(r) for r in candidates}) != 1 or not choice["evidence"]:
            raise ValueError("Reviewed EDC identity is missing or ambiguous: " + str(choice))
        return candidates[0], "matched", "reviewed_identity", choice["evidence"]
    ids = json.loads(target["official_identifiers_json"])
    directory = json.loads(target["directory_evidence_json"])
    nces = {i["native_id"] for i in ids if i["namespace"] == "NCES_school_id"}
    nces |= {d["ncessch"] for d in directory}
    nces |= set(filter(None, target.get("grade_context_nces_candidate", "").split(" | ")))
    names = {normal_name(target["school_name"])} | {directory_name(d, target["state_code"]) if d.get("school_name") else normal_name(d.get("source_school_name", "")) for d in directory}
    districts = {district_name(d) for d in target["district_names"].split(" | ")}
    districts |= {district_name(d.get("lea_name") or d.get("source_lea_name", "")) for d in directory}
    official = {i["namespace"]: set() for i in ids}
    for i in ids:
        official[i["namespace"]].add(native_id(i["native_id"]))
    selected = {}
    for key in nces:
        for row in index["nces"].get(nces_id(key), []):
            selected[tuple(row.items())] = row
    for values in official.values():
        for key in values:
            for row in index["native"].get(key, []):
                selected[tuple(row.items())] = row
    for key in names:
        for row in index["name"].get(key, []):
            selected[tuple(row.items())] = row
    strong, pending = {}, {}
    for row in selected.values():
        native = native_id(row["StateAssignedSchID"])
        if target["state_code"] == "TX" and native.isdigit():
            native = native.zfill(9)
        if target["state_code"] == "CA" and native.isdigit():
            native = native.zfill(14)
        state_id_match = any(native in official.get(ns, set()) for ns in ["TX_TEA_campus_id", "CA_CDS", "IL_state_school_id"])
        # WA school codes are district-local, so they never select a campus alone.
        known_nces = nces_id(row["NCESSchoolID"]) in nces
        name_agrees = source_name(row) in names
        district_agrees = district_name(row["DistName"]) in districts - {""}
        nces_district_agrees = bool(nces_id(row["NCESSchoolID"])) and nces_id(row["NCESSchoolID"])[:7] == nces_id(row["NCESDistrictID"], 7)
        if (state_id_match or known_nces) and name_agrees and nces_district_agrees:
            method = "official_state_id_and_source_name" if state_id_match else "candidate_nces_corroborated_by_source_name_and_district_id"
            strong[unit_id(row)] = (row, method)
        elif state_id_match or known_nces or (name_agrees and district_agrees):
            pending[unit_id(row)] = row
    if len(strong) == 1:
        row, method = next(iter(strong.values()))
        return row, "matched", method, "Source-year EDC ID/name checked against saved research and directory evidence. DL operation and historical programme exposure are unverified."
    if len(strong) > 1:
        return None, "ambiguous", "multiple_corroborated_identities", json.dumps(sorted(strong))
    if pending:
        return None, "review_needed", "candidate_requires_identity_review", json.dumps(list(pending.values()), sort_keys=True)
    return None, "no_school_result_found", "no_corroborated_school_identity", "No matching school-level EDC identity for this year; absence does not establish school closure or lack of a DL programme."


def match_sources(root, cache, destination):
    targets = target_rows(root)
    write_csv(destination / "targets.csv", targets, list(targets[0]))
    by_state = defaultdict(list)
    for target in targets:
        by_state[target["state_code"]].append(target)
    override_path = root / "config/edc_identity_reviews.csv"
    reviews = read_csv(override_path) if override_path.exists() else []
    overrides = {(r["school_id"], r["school_year"]): r for r in reviews if r["review_status"] == "accepted"}
    if len(overrides) != sum(r["review_status"] == "accepted" for r in reviews):
        raise ValueError("Duplicate accepted EDC identity decisions for the same school/year")
    matches, identities, sources = [], [], []
    for state, state_targets in sorted(by_state.items()):
        for year in YEARS:
            meta = json.loads((cache / f"{state}_{year}.json").read_text())
            sources.append(meta)
            entries = read_csv(cache / f"{state}_{year}.schools.csv") if meta["status"] == "downloaded" else []
            identities.extend(dict(e, edc_unit_id=unit_id(e)) for e in entries)
            index = source_index(entries)
            for target in state_targets:
                row, status, method, notes = choose_match(target, index, overrides)
                matches.append(dict(school_id=target["school_id"], state_code=state, school_name=target["school_name"],
                                    district_names=target["district_names"], school_year=f"{year-1}-{year%100:02d}",
                                    match_status=status if entries else "no_school_results_in_source",
                                    match_method=method, edc_unit_id=unit_id(row) if row else "",
                                    **{k: row.get(k, "") if row else "" for k in ["NCESSchoolID", "StateAssignedSchID", "NCESDistrictID", "StateAssignedDistID"]},
                                    edc_school_name=row["SchName"] if row else "", edc_district_name=row["DistName"] if row else "",
                                    identity_source=f"sources/{state}_{year}.json", notes=notes))
    write_csv(destination / "school_matches.csv", matches, MATCH_FIELDS)
    write_csv(destination / "identity_review_queue.csv", [r for r in matches if r["match_status"] != "matched"], MATCH_FIELDS)
    with gzip_csv(destination / "source_school_index.csv.gz", IDENTITY_FIELDS + ["edc_unit_id"]) as writer:
        writer.writerows(identities)
    return targets, matches, sources


class gzip_csv:
    """Stable gzip bytes and ordinary CSV rows, without timestamped headers."""
    def __init__(self, path, fields):
        self.path, self.fields = Path(path), fields
    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.raw = self.path.open("wb")
        self.gz = gzip.GzipFile(fileobj=self.raw, filename="", mode="wb", mtime=0, compresslevel=6)
        self.text = io.TextIOWrapper(self.gz, encoding="utf-8", newline="")
        self.writer = csv.DictWriter(self.text, fieldnames=self.fields, lineterminator="\n")
        self.writer.writeheader()
        return self.writer
    def __exit__(self, *args):
        self.text.close()
        self.raw.close()


def iter_gzip_csv(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        yield from csv.DictReader(stream)


def count_provenance(state, year, group):
    """Documented substitution risk; the export has no row-level origin flag.

    EDC v3.1 Technical Documentation, Table 21, pp. 23–24. These labels
    describe EDC's documented policy, not an independent headcount audit.
    """
    if state == "UT":
        return "documented_CCD_enrollment_proxy", "", "EDC Table 21: school/district counts use CCD enrollment in 2022–2025; the exact count-source year is not identified for each exported row."
    if state in {"KS", "ND"}:
        return ("documented_CCD_enrollment_proxy", "2025", "EDC Table 21: 2024–25 CCD enrollment substituted for spring 2025.") if year == 2025 else (
            "documented_EDFacts_2022_substitute", "2022", "EDC Table 21: spring 2022 EDFacts counts reused for 2022, 2023 and 2024.")
    if state == "AR" and year <= 2024 and group != "All Students":
        return "possible_EDFacts_2022_subgroup_substitute", "2022", "EDC Table 21: partial counts; 2022 EDFacts subgroup counts applied to 2022–2024. No row-specific origin flag."
    if state == "IL" and year == 2022:
        return "documented_EDFacts_substitute_exact_source_year_not_row_identified", "", "EDC Table 21 lists EDFacts substitutions through 2021–22; the export does not identify each row's count origin."
    return "EDC_reported_valid_score_count_origin_not_row_identified", "", "EDC may derive counts; do not interpret this field as total grade enrollment or an independently verified SEA tested headcount."


def normalized_row(row, row_id):
    basis, source_year, count_notes = count_provenance(row["StateAbbrev"], int(row["SchYear"][:4]) + 1 if row["SchYear"] else 2025, row["StudentGroup"])
    measurement = record_id("edc_measurement", unit_id(row), *[row.get(k, "") for k in ["SchYear", "AssmtName", "AssmtType", "Subject", "GradeLevel", "StudentGroup", "StudentSubGroup"]])
    result = dict(edc_result_id=row_id, edc_measurement_id=measurement, edc_unit_id=unit_id(row), state_code=row["StateAbbrev"],
                  school_year=row["SchYear"], nces_school_id=nces_id(row["NCESSchoolID"]),
                  state_school_id=row["StateAssignedSchID"], school_name=row["SchName"],
                  district_name=row["DistName"], subject=SUBJECT_MAP[row["Subject"]],
                  source_subject=row["Subject"], grade_scope="all_tested_grades" if row["GradeLevel"] == "G38" else str(int(row["GradeLevel"][1:])) if re.fullmatch(r"G0[3-8]", row["GradeLevel"]) else row["GradeLevel"],
                  source_grade=row["GradeLevel"], student_group=row["StudentGroup"],
                  student_subgroup=row["StudentSubGroup"], assessment_name=row["AssmtName"],
                  assessment_type=row["AssmtType"], proficiency_criteria=row["ProficiencyCriteria"],
                  assessment_name_change=row["Flag_AssmtNameChange"],
                  cut_score_change=row.get("Flag_CutScoreChange_" + ("math" if row["Subject"] == "math" else "ELA"), ""),
                  count_basis=basis, count_proxy_source_spring_year=source_year, count_provenance_note=count_notes,
                  outcome_scope="schoolwide_not_DL_participants", cohort_status="repeated_cross_section",
                  assessed_language="not_reported", cross_state_norming="none", source_version=VERSION)
    for field in MEASURES:
        parsed = parse_edc_value(row.get(field, ""), proportion=field.endswith("percent") or field == "ParticipationRate")
        for key, value in parsed.items():
            result[field + "_" + key] = value
    return result


def extract(root, cache=None, destination=None, reuse=None):
    """Build an immutable, offline-reproducible collection from cached originals."""
    root = Path(root)
    cache = Path(cache or root / ".cache/edc_v3_1")
    destination = Path(destination or root / COLLECTION)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("EDC destination must be empty; use a new collection vintage")
    destination.mkdir(parents=True, exist_ok=True)
    targets, matches, sources = match_sources(root, cache, destination)
    reuse = Path(reuse) if reuse else None
    prior_units = defaultdict(set)
    if reuse:
        for prior in read_csv(reuse / "school_matches.csv"):
            if prior["match_status"] == "matched":
                prior_units[(prior["state_code"], prior["school_year"])].add(prior["edc_unit_id"])
    matched = defaultdict(set)
    for match in matches:
        if match["match_status"] == "matched":
            matched[(match["state_code"], match["school_year"])].add(match["edc_unit_id"])
    source_records, partitions, coverage, conflicts, anomalies = [], [], [], [], []
    school_stats = defaultdict(Counter)
    subgroup_stats = defaultdict(Counter)
    for meta in sources:
        state, year = meta["state_code"], meta["spring_year"]
        school_year = f"{year-1}-{year%100:02d}"
        path = cache / f"{state}_{year}.csv"
        if meta["status"] != "downloaded":
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            source_rel = f"native/{state}_{year}.csv.gz"
            normalized_rel = f"school_grade_results/{state}_{year}.csv.gz"
            native_fields = ["edc_result_id", "source_csv_record"] + fields
            normalized_fields = list(normalized_row({field: "" for field in fields} | dict(StateAbbrev=state, GradeLevel="G03", Subject="ela"), "").keys())
            seen, rows, duplicate_rows, counters, grains = {}, 0, 0, Counter(), defaultdict(list)
            records = enumerate(reader, start=1)
            prior_path = reuse / "sources" / f"{state}_{year}.json" if reuse else None
            if prior_path and prior_path.exists() and prior_units[(state, school_year)] == matched[(state, school_year)]:
                prior = json.loads(prior_path.read_text())
                selection = dict(subjects=sorted(SUBJECTS), groups=sorted(GROUPS))
                if (prior.get("selection") == selection and prior["sha256"] == meta["sha256"]
                        and prior["extract_sha256"] == sha256_file(reuse / prior["extract_path"])):
                    records = ((int(r["source_csv_record"]), {f: r[f] for f in fields})
                               for r in iter_gzip_csv(reuse / prior["extract_path"]))
                    duplicate_rows = prior["identical_duplicate_rows_removed"]
            with gzip_csv(destination / source_rel, native_fields) as native_writer, gzip_csv(destination / normalized_rel, normalized_fields) as normalized_writer:
                for position, row in records:
                    if row["DataLevel"] != "School" or row["Subject"] not in SUBJECTS or row["StudentGroup"] not in GROUPS:
                        continue
                    if unit_id(row) not in matched[(state, school_year)]:
                        continue
                    # Source-grain identity includes all native cells. Identical duplicate
                    # rows are not additional samples; conflicting rows are retained.
                    fingerprint = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                    if fingerprint in seen:
                        duplicate_rows += 1
                        continue
                    row_id = f"edc-{state}-{year}-{fingerprint[:24]}"
                    seen[fingerprint] = row_id
                    native_writer.writerow(dict(edc_result_id=row_id, source_csv_record=position, **row))
                    normalized = normalized_row(row, row_id)
                    normalized_writer.writerow(normalized)
                    grains[normalized["edc_measurement_id"]].append(row_id)
                    rows += 1
                    is_grade = normalized["grade_scope"] in {str(i) for i in range(3, 9)}
                    stat = school_stats[(unit_id(row), school_year)]
                    stat["grade_rows" if is_grade else "aggregate_rows"] += 1
                    if is_grade:
                        stat[row["StudentGroup"] + "_grade_rows"] += 1
                        if row["StudentGroup"] == "EL Status" and row["StudentSubGroup"] == "English Learner":
                            stat["current_el_grade_rows"] += 1
                        if row["StudentGroup"] == "All Students" and row["Subject"] in {"ela", "math"}:
                            stat[row["Subject"] + "_all_students_grade_rows"] += 1
                            if normalized["ProficientOrAbove_percent_status"] in {"reported", "bounded"}:
                                stat[row["Subject"] + "_all_students_usable_proficiency_rows"] += 1
                    substat = subgroup_stats[(unit_id(row), school_year, normalized["grade_scope"], row["Subject"], row["StudentGroup"])]
                    substat["rows"] += 1
                    substat["proficiency_" + normalized["ProficientOrAbove_percent_status"] + "_rows"] += 1
                    substat["subgroup_count_" + normalized["StudentSubGroup_TotalTested_status"] + "_rows"] += 1
                    for field in MEASURES:
                        status = normalized[field + "_status"]
                        numeric = normalized[field + "_numeric"]
                        problem = "unrecognized_source_token" if status == "unrecognized_source_token" else ""
                        if numeric and (field.endswith("percent") or field == "ParticipationRate") and not 0 <= Decimal(numeric) <= 100:
                            problem = "source_fraction_outside_0_1"
                        if problem:
                            anomalies.append(dict(edc_result_id=row_id, state_code=state, school_year=school_year,
                                                  field=field, raw=row.get(field, ""), issue=problem))
                    counters[(row["StudentGroup"], row["StudentSubGroup"], row["Subject"], row["GradeLevel"],
                              normalized["ProficientOrAbove_percent_status"], normalized["StudentSubGroup_TotalTested_status"])] += 1
            for grain, row_ids in grains.items():
                if len(row_ids) > 1:
                    conflicts.append(dict(state_code=state, school_year=school_year, edc_measurement_id=grain,
                                          result_ids=" | ".join(row_ids), rows=len(row_ids),
                                          action="Retain conflicting source rows; do not average or count as independent samples."))
            receipt = dict(meta, extract_path=source_rel, extract_sha256=sha256_file(destination / source_rel),
                           retained_rows=rows, identical_duplicate_rows_removed=duplicate_rows,
                           selection=dict(subjects=sorted(SUBJECTS), groups=sorted(GROUPS)),
                           source_fields=fields, scope="matched_school_context_only",
                           extract_method="CSV rows selected and reserialized; field values retained verbatim; original full-file bytes are in local cache, not asserted to be archived in Git.")
            (destination / "sources").mkdir(exist_ok=True)
            (destination / "sources" / f"{state}_{year}.json").write_text(json.dumps(receipt, indent=2) + "\n")
            source_records.append(receipt)
            partitions.append(dict(state_code=state, school_year=school_year, native_path=source_rel,
                                   results_path=normalized_rel, rows=rows))
            for (group, subgroup, subject, grade, prof_status, count_status), n in sorted(counters.items()):
                coverage.append(dict(state_code=state, school_year=school_year, student_group=group, student_subgroup=subgroup,
                                     source_subject=subject, source_grade=grade, proficiency_status=prof_status,
                                     subgroup_count_status=count_status, rows=n))
            print(json.dumps(dict(state_code=state, spring_year=year, retained_rows=rows)), flush=True)
    write_csv(destination / "field_coverage.csv", coverage, ["state_code", "school_year", "student_group", "student_subgroup", "source_subject", "source_grade", "proficiency_status", "subgroup_count_status", "rows"])
    write_csv(destination / "partitions.csv", partitions, ["state_code", "school_year", "native_path", "results_path", "rows"])
    write_csv(destination / "source_grain_conflicts.csv", conflicts, ["state_code", "school_year", "edc_measurement_id", "result_ids", "rows", "action"])
    write_csv(destination / "value_anomalies.csv", anomalies, ["edc_result_id", "state_code", "school_year", "field", "raw", "issue"])
    stat_fields = ["grade_rows", "aggregate_rows", "ela_all_students_grade_rows", "math_all_students_grade_rows",
                   "ela_all_students_usable_proficiency_rows", "math_all_students_usable_proficiency_rows",
                   "current_el_grade_rows"] + [group + "_grade_rows" for group in sorted(GROUPS)]
    audit_rows = [dict(m, **{field: school_stats[(m["edc_unit_id"], m["school_year"])][field] for field in stat_fields}) for m in matches]
    write_csv(destination / "school_year_coverage.csv", audit_rows, MATCH_FIELDS + stat_fields)
    status_fields = ["rows"] + [prefix + status + "_rows" for prefix in ["proficiency_", "subgroup_count_"]
                                for status in ["reported", "bounded", "suppressed", "not_reported", "not_applicable", "unrecognized_source_token"]]
    with gzip_csv(destination / "school_grade_subgroup_coverage.csv.gz", ["edc_unit_id", "school_year", "grade_scope", "source_subject", "student_group"] + status_fields) as writer:
        for key, counts in sorted(subgroup_stats.items()):
            writer.writerow(dict(zip(["edc_unit_id", "school_year", "grade_scope", "source_subject", "student_group"], key)) | {f: counts[f] for f in status_fields})
    state_rows = []
    states = read_csv(root / "data/curated/registry/states.csv")
    for state in states:
        state_targets = [r for r in targets if r["state_code"] == state["state_code"]]
        for year in YEARS:
            school_year = f"{year-1}-{year%100:02d}"
            records = [r for r in audit_rows if r["state_code"] == state["state_code"] and r["school_year"] == school_year]
            state_rows.append(dict(state_code=state["state_code"], school_year=school_year, target_research_school_identities=len(state_targets),
                                   research_identities_matched=sum(r["match_status"] == "matched" for r in records),
                                   unique_EDC_school_units_matched=len({r["edc_unit_id"] for r in records if r["match_status"] == "matched"}),
                                   research_identities_with_grade_rows=sum(r["grade_rows"] > 0 for r in records),
                                   research_identities_with_ELA_proficiency=sum(r["ela_all_students_usable_proficiency_rows"] > 0 for r in records),
                                   research_identities_with_math_proficiency=sum(r["math_all_students_usable_proficiency_rows"] > 0 for r in records),
                                   research_identities_needing_identity_review=sum(r["match_status"] in {"review_needed", "ambiguous"} for r in records),
                                   source_scope="EDC_grades_3_8_only;_schoolwide;_cohort_membership_not_verified"))
    write_csv(destination / "state_coverage.csv", state_rows, list(state_rows[0]))
    aliases = defaultdict(list)
    for m in matches:
        if m["match_status"] == "matched":
            aliases[(m["state_code"], m["school_year"], m["edc_unit_id"])].append(m["school_id"])
    alias_rows = [dict(state_code=k[0], school_year=k[1], edc_unit_id=k[2], research_school_ids=" | ".join(sorted(ids)),
                       interpretation="One source reporting unit; research aliases are not merged and results are not duplicated.") for k, ids in sorted(aliases.items()) if len(ids) > 1]
    write_csv(destination / "shared_source_unit_aliases.csv", alias_rows, ["state_code", "school_year", "edc_unit_id", "research_school_ids", "interpretation"])
    summary = dict(version=VERSION, spring_years=list(YEARS), target_school_research_identities=len(targets),
                   school_year_match_status=dict(Counter(m["match_status"] for m in matches)),
                   research_identities_with_any_match=len({m["school_id"] for m in matches if m["match_status"] == "matched"}),
                   unique_source_units_with_any_match=len({m["edc_unit_id"] for m in matches if m["match_status"] == "matched"}),
                   result_rows=sum(p["rows"] for p in partitions), attribution=ATTRIBUTION,
                   source_grain_conflicts=len(conflicts), value_anomalies=len(anomalies),
                   norming="none", population_scope="schoolwide_context_not_DL_participants",
                   source_years_are_not_DL_operating_years=True)
    (destination / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    files = {str(p.relative_to(destination)): sha256_file(p) for p in sorted(destination.rglob("*")) if p.is_file()}
    inputs = {rel: digest(root / rel) for rel in [BASELINE + "/schools.csv", "data/curated/registry/identifier_crosswalk.csv", "data/curated/sources/evidence_claims.csv"]}
    manifest = dict(collection_schema_version="1.0.0", collection_id=destination.name, dataset_version=VERSION,
                    inputs=inputs, files=files, partitions=partitions, attribution=ATTRIBUTION,
                    assessment_scope="Grades 3–8 as supplied by EDC; grade aggregates remain separate; no secondary-only grade 9–12 outcomes provided by this source.")
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return summary


def finalize(root, collection=None):
    """Pin reference documents, identity decisions and reproducible transforms."""
    root = Path(root)
    base = Path(collection or root / COLLECTION)
    derive_audits(base)
    path = base / "manifest.json"
    manifest = json.loads(path.read_text())
    paths = [root / BASELINE / "schools.csv", root / "data/curated/registry/identifier_crosswalk.csv",
             root / "data/curated/sources/evidence_claims.csv", root / "config/edc_identity_reviews.csv",
             root / "config/edc_district_identity_reviews.csv"]
    paths.extend((root / "data/raw").glob("**/*ccd*.json"))
    manifest["inputs"] = {str(p.relative_to(root)): sha256_file(p) for p in sorted(set(paths)) if p.is_file()}
    manifest["pipeline_files"] = {p: digest(root / p) for p in ["src/dl_outcomes/edc.py", "src/dl_outcomes/collectors/edc.py", "src/dl_outcomes/io.py", "src/dl_outcomes/collection_provenance.py"]}
    manifest["files"] = {str(p.relative_to(base)): sha256_file(p) for p in sorted(base.rglob("*")) if p.is_file() and p != path}
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest


def derive_audits(base):
    """Reproduce cohort-wide gap summaries and compact table contracts."""
    base = Path(base)
    targets, matches = read_csv(base / "targets.csv"), read_csv(base / "school_matches.csv")
    coverage = read_csv(base / "school_year_coverage.csv")
    by_school = defaultdict(list)
    for row in matches:
        by_school[row["school_id"]].append(row)
    gaps = []
    for target in targets:
        rows = by_school[target["school_id"]]
        missing = [r["school_year"] for r in rows if r["match_status"] != "matched"]
        if not missing:
            continue
        low, high = target["school_grade_low"], target["school_grade_high"]
        reason = "identity_or_source_coverage_unresolved"
        if low.isdigit() and int(low) >= 9:
            reason = "saved_grade_context_suggests_grade_9_plus_only"
        elif high.isdigit() and int(high) < 3:
            reason = "saved_grade_context_suggests_before_grade_3_only"
        gaps.append(dict(school_id=target["school_id"], state_code=target["state_code"], school_name=target["school_name"],
                         district_names=target["district_names"], missing_school_years=" | ".join(missing),
                         matched_other_years=" | ".join(r["school_year"] for r in rows if r["match_status"] == "matched"),
                         school_level=target["school_level"], saved_grade_low=low, saved_grade_high=high,
                         grade_context_years=target["grade_context_years"], review_category=reason,
                         note="Saved grade context is not an annual testing-year observation. An unmatched identity is not proof of nonpublication, closure or lack of a DL programme."))
    fields = ["school_id", "state_code", "school_name", "district_names", "missing_school_years", "matched_other_years",
              "school_level", "saved_grade_low", "saved_grade_high", "grade_context_years", "review_category", "note"]
    write_csv(base / "school_match_gaps.csv", gaps, fields)
    summary = json.loads((base / "summary.json").read_text())
    summary["research_identities_with_grade_specific_rows"] = len({r["school_id"] for r in coverage if int(r["grade_rows"]) > 0})
    for source_subject, label in [("ela", "ELA"), ("math", "math")]:
        summary[f"research_identities_with_all_students_{label}_grade_proficiency"] = len({r["school_id"] for r in coverage if int(r[f"{source_subject}_all_students_usable_proficiency_rows"]) > 0})
    summary["research_identities_with_all_four_years_matched"] = sum(all(r["match_status"] == "matched" for r in rows) for rows in by_school.values())
    summary["school_research_identities_without_any_match"] = len(targets) - summary["research_identities_with_any_match"]
    summary["saved_grade_context_among_never_matched"] = dict(Counter(r["review_category"] for r in gaps if not r["matched_other_years"]))
    (base / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    part = read_csv(base / "partitions.csv")[0]
    headers = {}
    for name, rel in [("native", part["native_path"]), ("results", part["results_path"])]:
        with gzip.open(base / rel, "rt", encoding="utf-8", newline="") as stream:
            headers[name] = next(csv.reader(stream))
    contract = dict(schema_version="1.0.0", physical_format="UTF-8 CSV, gzip-compressed for large result partitions",
                    native=dict(primary_key=["edc_result_id"], fields=headers["native"],
                                semantics="Source-native cells plus result key and one-based original CSV data-record position."),
                    school_grade_results=dict(primary_key=["edc_result_id"], fields=headers["results"],
                        measurement_grain=["edc_unit_id", "school_year", "assessment_name", "assessment_type", "source_subject", "source_grade", "student_group", "student_subgroup", "source_version"],
                        percentage_numeric_unit="percent_0_100", raw_percentage_unit="source_proportion_0_1",
                        values="reported / bounded / suppressed / not_reported / not_applicable / unrecognized_source_token"),
                    school_matches=dict(primary_key=["school_id", "school_year"], source_unit_key=["edc_unit_id", "school_year"],
                        relationship="Many research identities may point to one source unit; do not duplicate outcomes through the association."),
                    cohorts="Repeated school/grade cross-sections; school matches do not certify historical DL programme operation or participant membership.")
    (base / "table_contracts.json").write_text(json.dumps(contract, indent=2) + "\n")


def check(root, collection=None, *, reproduce=False):
    """Validate receipts and joins; optionally reproduce every normalized cell."""
    root = Path(root)
    base = Path(collection or root / COLLECTION)
    manifest = json.loads((base / "manifest.json").read_text())
    for rel, expected in manifest["files"].items():
        if not (base / rel).is_file() or sha256_file(base / rel) != expected:
            raise ValueError("EDC collection file changed: " + rel)
    for rel, expected in manifest["inputs"].items():
        pinned_dependency(root, base, 'input', rel, expected)
    for rel, expected in manifest.get("pipeline_files", {}).items():
        pinned_dependency(root, base, 'pipeline', rel, expected)
    targets = read_csv(base / "targets.csv")
    matches = read_csv(base / "school_matches.csv")
    target_ids = {r["school_id"] for r in targets}
    pairs = {(r["school_id"], r["school_year"]) for r in matches}
    expected_pairs = {(sid, f"{year-1}-{year%100:02d}") for sid in target_ids for year in YEARS}
    if len(targets) != len(target_ids) or len(pairs) != len(matches) or pairs != expected_pairs:
        raise ValueError("EDC cohort or school/year audit is incomplete or duplicated")
    allowed = defaultdict(set)
    for row in matches:
        if row["match_status"] == "matched":
            if not row["edc_unit_id"] or not nces_id(row["NCESSchoolID"]):
                raise ValueError("EDC match has no source identity")
            allowed[(row["state_code"], row["school_year"])].add(row["edc_unit_id"])
    rows = 0
    for part in manifest["partitions"]:
        state, year = part["state_code"], part["school_year"]
        spring = int(year[:4]) + 1
        receipt = json.loads((base / "sources" / f"{state}_{spring}.json").read_text())
        if not receipt.get("server_md5_verified") or receipt["extract_sha256"] != sha256_file(base / part["native_path"]):
            raise ValueError("EDC source/extract integrity is unverified: " + state + "/" + year)
        if reproduce:
            count = 0
            seen = set()
            for native, actual in zip_longest(iter_gzip_csv(base / part["native_path"]), iter_gzip_csv(base / part["results_path"])):
                if native is None or actual is None:
                    raise ValueError("EDC native/normalized row conservation failed")
                original = {field: native[field] for field in receipt["source_fields"]}
                if original["DataLevel"] != "School" or original["StateAbbrev"] != state or original["SchYear"] != year:
                    raise ValueError("EDC district/state/year result leaked into a school partition")
                if unit_id(original) not in allowed[(state, year)] or original["StudentGroup"] not in GROUPS or original["Subject"] not in SUBJECTS:
                    raise ValueError("EDC result has no corroborated school/year association or falls outside requested scope")
                fingerprint = hashlib.sha256(json.dumps(original, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                expected_id = f"edc-{state}-{spring}-{fingerprint[:24]}"
                if native["edc_result_id"] != expected_id or expected_id in seen:
                    raise ValueError("EDC source row identity/hash is invalid or duplicated")
                seen.add(expected_id)
                expected = normalized_row(original, expected_id)
                if actual != expected:
                    raise ValueError("EDC normalized cells differ from saved native row: " + expected_id)
                count += 1
            if count != int(part["rows"]) or count != receipt["retained_rows"]:
                raise ValueError("EDC partition row count differs from its receipt")
        rows += int(part["rows"])
    return dict(status="PASS", source_partitions=len(manifest["partitions"]), school_research_identities=len(targets),
                rows=rows, normalized_cells_reproduced=reproduce)


def register(build):
    """Register partitioned EDC observations without rewriting earlier pilots."""
    base = build.root / COLLECTION
    if not (base / "manifest.json").exists():
        return
    manifest = json.loads((base / "manifest.json").read_text())
    build.track_input(base / "manifest.json")
    for rel in manifest["files"]:
        build.track_input(base / rel)
    # The collection is immutable while live structural evidence may evolve.
    # Track the exact old inputs/code, not a mutable canonical output path.
    for kind, section in [('input', 'inputs'), ('pipeline', 'pipeline_files')]:
        for rel, expected in manifest.get(section, {}).items():
            path = pinned_dependency(build.root, base, kind, rel, expected)
            build.track_input(path)
            if path != build.root / rel:
                build.track_input(ARCHIVES)
    dataset = build.dataset("EDC_SADR_V3_1_SCHOOL_GRADES", None, "state_assessments",
                            "EDC v3.1 school/grade ELA and math with demographic subgroups, spring 2022–2025",
                            "https://www.eddatacenter.org/data", publisher="Education Data Center / NCCI",
                            native_id="SADR v3.1", notes=ATTRIBUTION + " Partitioned collection: " + COLLECTION +
                            ". Counts refer to valid scores or documented proxies, not grade enrollment. Schoolwide context; no DL participant attribution or cross-state norming.")
    build.edc_source_ids = {}
    for path in sorted((base / "sources").glob("*.json")):
        receipt = json.loads(path.read_text())
        source = record_id("edc_release", VERSION, receipt["state_code"], receipt["spring_year"], receipt["sha256"])
        snapshot = base / receipt["extract_path"]
        build.add("sources", source_id=source, dataset_id=dataset, source_url=receipt["url"],
                  version_label="SADR 3.1", retrieved_at=receipt["retrieved_at"],
                  snapshot_path=str(snapshot.relative_to(build.root)), sha256=receipt["extract_sha256"],
                  snapshot_kind="saved_source_extract", evidence_period_raw=f"Spring {receipt['spring_year']}",
                  notes="Verbatim-valued CSV row subset reserialized and compressed; not the full original file. Original SHA-256=" + receipt["sha256"] + "; receipt=" + str(path.relative_to(build.root)))
        build.edc_source_ids[(receipt["state_code"], f"{receipt['spring_year']-1}-{receipt['spring_year']%100:02d}")] = source
    build.edc_coverage = {(r["state_code"], r["school_year"]): r for r in read_csv(base / "state_coverage.csv")}
    build.notes.append("EDC native school/grade results are in " + COLLECTION +
                       "; original assessment pilot tables remain separate. Public EDC data cover grades 3–8 only, with source-defined subgroups, suppression and documented count substitutions.")


def export_analytics(root, destination, connection):
    """Expose partitioned school results and the separate identity bridge."""
    root, destination = Path(root), Path(destination)
    base = root / COLLECTION
    if not (base / "manifest.json").exists():
        return {}
    result = {}
    inputs = {"edc_school_grade_results": str(base / "school_grade_results/*.csv.gz"),
              "edc_school_matches": str(base / "school_matches.csv"),
              "edc_school_year_coverage": str(base / "school_year_coverage.csv")}
    for name, path in inputs.items():
        # Reading as strings preserves leading zeros, suppressed tokens and
        # exact published decimals; users can cast the explicit numeric fields.
        connection.execute(f'CREATE TABLE "{name}" AS SELECT * FROM read_csv(?, header=true, all_varchar=true, union_by_name=true)', [path])
        target = destination / (name + ".parquet")
        quoted = str(target).replace("'", "''")
        connection.execute(f'COPY "{name}" TO \'{quoted}\' (FORMAT PARQUET, COMPRESSION ZSTD)')
        result[name] = connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    return result
