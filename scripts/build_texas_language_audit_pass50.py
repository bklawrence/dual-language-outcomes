#!/usr/bin/env python3
"""Build the Texas language correction pass from reviewed, portable evidence.

No network, inferred Spanish default, outcome copying, or historical snapshot edits.
The JSON/CSV decisions in data/registry/texas/pass50 are the reviewed inputs.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/registry/texas"
INPUT = DATA / "pass50"
PRIOR = ROOT / "data/registry/texas_language_program_tracks_pass49_provisional.csv"
TRACKS = DATA / "texas_language_program_tracks_pass50.csv"
ALLOCATIONS = DATA / "texas_k_allocation_evidence_pass50.csv"
AUDIT = DATA / "texas_language_classification_audit_pass50.csv"
ROLE_REVIEWS = DATA / "texas_language_role_reviews_pass50.csv"
CAMPUS_VIEW = DATA / "texas_campus_language_inventory_pass50.csv"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def canonical_pair(pair):
    return pair.removesuffix(" (later)")


def scope_applies(rule, row):
    """Conservative scope screen; an elementary policy never proves a secondary pair."""
    scope = rule["scope"]
    if "elementary" in scope and int(row["campus_id"][-3:]) < 100:
        return False
    if "one_way" in scope and row["TAPR_program_group"] != "one_way":
        return False
    if "two_way" in scope and row["TAPR_program_group"] != "two_way":
        return False
    return True


def source_fields(ids, sources):
    return {
        "audit_source_ids": ";".join(ids),
        "evidence_source_url": " ; ".join(sources[key]["url"] for key in ids),
    }


def base_row(old, *, added=False):
    row = dict(old)
    for key in ("language_pair", "language_evidence_level", "evidence_source_url", "evidence_period"):
        row["previous_" + key] = old[key]
    row["previous_notes"] = old["notes"]
    row.update(
        previous_language_track_id="" if added else old["language_track_id"],
        derived_from_language_track_id=old["language_track_id"],
        partner_language="",
        instruction_languages="",
        pair_verification_scope="UNVERIFIED",
        language_pair_verified_in_source="NO",
        historical_2023_24_pair_status="NOT_ESTABLISHED",
        audit_source_ids="",
        additional_language_role="",
        correction_reason="",
        audit_change="ADDED_LANGUAGE_TRACK" if added else "REVIEWED",
        audit_date="2026-11-04",
        outcome_attribution="NOT_ESTABLISHED_DO_NOT_DISAGGREGATE",
    )
    # A source's language description is never a language-specific TAPR result.
    row["language_specific_2023_24_TAPR_result_available"] = "NOT_ESTABLISHED"
    return row


def set_pair(row, pair):
    row["language_pair"] = pair
    if pair != "UNVERIFIED":
        row["partner_language"] = pair.split("–", 1)[0]
        row["instruction_languages"] = "English;" + row["partner_language"]


def make_tracks(prior, decisions, policies, sources, reviews):
    groups = collections.defaultdict(list)
    for old in prior:
        groups[old["registry_record_id"]].append(old)
    output = []
    reviews_by_campus = {r["campus_id"]: r for r in reviews if r["campus_id"]}
    for rid, siblings in groups.items():
        first = siblings[0]
        decision = decisions.get(first["campus_id"])
        if decision:
            by_pair = {canonical_pair(old["language_pair"]): old for old in siblings}
            used_ids = set()
            for pair in decision["language_pairs"]:
                matched = by_pair.get(pair)
                # An unknown row can be resolved into the first documented track.
                if matched is None and len(siblings) == 1 and not used_ids:
                    matched = siblings[0]
                added = matched is None
                old = matched or first
                row = base_row(old, added=added)
                if added:
                    seq = 1
                    existing = {r["language_track_id"] for r in siblings} | used_ids
                    while f"{rid}|language_track_{seq:02d}" in existing:
                        seq += 1
                    row["language_track_id"] = f"{rid}|language_track_{seq:02d}"
                used_ids.add(row["language_track_id"])
                set_pair(row, pair)
                row.update(source_fields(decision["source_ids"], sources))
                historical = decision["historical_2023_24_campus_pair_status"]
                row.update(
                    language_evidence_level="pass50_campus_language_documented",
                    evidence_period=decision["evidence_period"],
                    pair_verification_scope="CAMPUS_DOCUMENTED",
                    language_pair_verified_in_source="YES",
                    historical_2023_24_pair_status=historical,
                    campus_specific_2023_24_roster_confirmed="YES" if historical == "YES" else "NO",
                    additional_language_role=decision["additional_language_role"],
                    correction_reason=decision["rationale"],
                )
                if first["campus_id"] == "227901144":
                    row["historical_2023_24_pair_status"] = "LATER_EVIDENCE_ONLY"
                    row["language_evidence_level"] = "pass50_later_campus_language_not_2023_verified"
                if not added and old["language_pair"] != pair:
                    row["audit_change"] = "LANGUAGE_LABEL_CHANGED"
                elif not added:
                    row["audit_change"] = "LANGUAGE_LABEL_REAFFIRMED"
                output.append(row)
        else:
            for old in siblings:
                row = base_row(old)
                pair = old["language_pair"]
                policy = policies.get(old["district"])
                if pair == "UNVERIFIED":
                    set_pair(row, "UNVERIFIED")
                    row["correction_reason"] = "No affirmative campus/group language-pair evidence; no Spanish default applied."
                elif pair == "Spanish (English pairing unverified)":
                    set_pair(row, "UNVERIFIED")
                    row["language_evidence_level"] = "pass50_unsourced_pair_not_confirmed"
                    row["correction_reason"] = "Historical Spanish label lacks a source URL and independently established English pairing; raw label preserved in previous fields. Austin offers multiple partner languages."
                elif pair == "Spanish–English" and policy and scope_applies(policy, old):
                    set_pair(row, pair)
                    row.update(source_fields([policy["source_id"]], sources))
                    row.update(
                        language_evidence_level="pass50_district_pair_definition_campus_year_provisional",
                        evidence_period=sources[policy["source_id"]]["evidence_period"],
                        pair_verification_scope="DISTRICT_POLICY_ONLY",
                        language_pair_verified_in_source="YES",
                        correction_reason="Existing explicit Spanish label corroborated by a district instructional-language definition. This is not fresh campus/year confirmation. " + policy["note"],
                    )
                    if old["campus_specific_2023_24_roster_confirmed"] == "YES":
                        row["historical_2023_24_pair_status"] = "PRIOR_DATED_CAMPUS_EVIDENCE_RETAINED"
                elif not old["evidence_source_url"] or (policy and not scope_applies(policy, old)):
                    set_pair(row, "UNVERIFIED")
                    row.update(
                        language_evidence_level="pass50_insufficient_source_or_scope",
                        campus_specific_2023_24_roster_confirmed="NO",
                        correction_reason="Prior label lacks recoverable pair evidence for this row: " + ("available district definition has a different grade/program scope." if policy else "historical master contains no source URL. Label is withdrawn pending evidence; this does not establish a different language."),
                    )
                    if policy:
                        row.update(source_fields([policy["source_id"]], sources))
                else:
                    set_pair(row, canonical_pair(pair))
                    retained_ids = [key for key, source in sources.items() if source["url"] == old["evidence_source_url"]]
                    row.update(
                        pair_verification_scope="PRIOR_EVIDENCE_NOT_INDEPENDENTLY_RECONFIRMED",
                        audit_source_ids=";".join(retained_ids),
                        correction_reason="Prior explicit source retained as provisional evidence; this pass does not newly confirm its campus/year language attribution.",
                    )
                    if old["campus_specific_2023_24_roster_confirmed"] == "YES":
                        row["historical_2023_24_pair_status"] = "PRIOR_DATED_CAMPUS_EVIDENCE_RETAINED"
                if pair != row["language_pair"]:
                    row["audit_change"] = "LANGUAGE_LABEL_CHANGED"
                output.append(row)
        review = reviews_by_campus.get(first["campus_id"])
        if review:
            for row in output[-(len(decision["language_pairs"]) if decision else len(siblings)):]:
                ids = list(dict.fromkeys(filter(None, row["audit_source_ids"].split(";") + review["source_ids"])))
                row["audit_source_ids"] = ";".join(ids)
                row["additional_language_role"] = review["language_role"] + ": " + review["candidate_languages"]
                row["correction_reason"] += " " + review["decision"]
                # A current Spanish roster is not a resolution of a possible additional Mandarin track.
                if first["campus_id"] == "057909116":
                    row.update(source_fields(ids, sources))
    for row in output:
        row["notes"] = row["correction_reason"] + " Language-track identity and reporting-group association remain provisional; do not assign a TAPR result to this language from these sources."
    return output


def reconcile_allocations(prior, tracks):
    """Keep every original observation; never silently transfer a policy to a new language."""
    index = {r["language_track_id"]: r for r in tracks}
    groups = collections.defaultdict(list)
    for row in tracks:
        groups[row["registry_record_id"]].append(row)
    result = []
    for old in prior:
        row = dict(old)
        tid = old["language_track_id_if_unambiguous"]
        row["previous_language_track_id_if_unambiguous"] = tid
        row["language_link_audit"] = "UNLINKED_PRIOR_POLICY_REQUIRES_REVIEW"
        row["language_link_audit_note"] = "No new language attribution from a numeric allocation label."
        linked = index.get(tid)
        siblings = groups[old["registry_record_id"]]
        if tid and linked and len(siblings) == 1 and linked["language_pair"] == linked["previous_language_pair"] and linked["pair_verification_scope"] in {"CAMPUS_DOCUMENTED", "DISTRICT_POLICY_ONLY"} and linked["historical_2023_24_pair_status"] != "LATER_EVIDENCE_ONLY":
            row["language_link_audit"] = "PRIOR_LANGUAGE_POLICY_LINK_RETAINED_NOT_COHORT_VERIFIED"
            row["language_link_audit_note"] = "Language label survived the audit; original policy source/date retained. This is not affirmative source-specific cohort attribution."
        elif tid:
            row["language_track_id_if_unambiguous"] = ""
            row["partner_language_attribution"] = "REQUIRES_REVIEW"
            row["language_link_audit"] = "LINK_CLEARED_LANGUAGE_OR_SCOPE_UNRESOLVED"
            row["language_link_audit_note"] = "Track language is unresolved, changed, later-only, lacks fresh corroboration, or shares its TAPR group with multiple languages. Review original policy before linking."
        # The old Wimbish note limited the study to Spanish, contradicting multilingual scope.
        if old["campus_id"] == "220901166":
            row["evidence_note"] = "Official campus description: separate Spanish/English and French/English 50/50 core-content tracks; Mandarin is FLES. This single campus-policy record is not assigned to either language-specific cohort."
            row["language_link_audit_note"] = "Both documented tracks are retained in the multilingual inventory; no Spanish-only study exclusion or duplicate outcome is introduced."
        row["verified_tested_cohort_exposure"] = "NO"
        result.append(row)
    return result


def campus_view(tracks):
    """Readable campus table; repeated TAPR categories never become extra programs."""
    grouped = collections.defaultdict(list)
    for row in tracks:
        grouped[row["campus_id"]].append(row)
    result = []
    for campus_id, rows in grouped.items():
        def joined(field, subset=rows):
            return " | ".join(sorted({r[field] for r in subset if r[field]}))
        documented = [r for r in rows if r["pair_verification_scope"] == "CAMPUS_DOCUMENTED"]
        district = [r for r in rows if r["pair_verification_scope"] == "DISTRICT_POLICY_ONLY"]
        prior = [r for r in rows if r["pair_verification_scope"] == "PRIOR_EVIDENCE_NOT_INDEPENDENTLY_RECONFIRMED"]
        result.append({
            "campus_id": campus_id,
            "district": rows[0]["district"],
            "campus": rows[0]["campus"],
            "TAPR_reporting_categories": joined("TAPR_program_group"),
            "campus_documented_language_pairs": joined("language_pair", documented),
            "district_policy_supported_pairs_campus_year_unconfirmed": joined("language_pair", district),
            "prior_pair_labels_not_independently_reconfirmed": joined("language_pair", prior),
            "has_unverified_pair_record": "YES" if any(r["language_pair"] == "UNVERIFIED" for r in rows) else "NO",
            "documented_non_spanish_partner": "YES" if any(r["partner_language"] != "Spanish" for r in documented) else "NO",
            "historical_2023_24_pair_status": joined("historical_2023_24_pair_status"),
            "additional_language_roles_or_unresolved_leads": joined("additional_language_role"),
            "evidence_periods": joined("evidence_period"),
            "evidence_source_urls": joined("evidence_source_url"),
            "interpretation": "Language evidence summary only; separate pairs are separate candidate tracks. No language-specific TAPR outcome or track-count estimate.",
        })
    return result


def main():
    prior = read_csv(PRIOR)
    source_rows = read_csv(INPUT / "source_register.csv")
    sources = {r["source_id"]: r for r in source_rows}
    decisions = {r["campus_id"]: r for r in json.loads((INPUT / "campus_language_decisions.json").read_text())}
    policies = {r["district"]: r for r in read_csv(INPUT / "district_language_rules.csv")}
    reviews = json.loads((INPUT / "language_role_reviews.json").read_text())
    tracks = make_tracks(prior, decisions, policies, sources, reviews)
    allocations = reconcile_allocations(read_csv(DATA / "texas_k_allocation_evidence_pass48.csv"), tracks)
    write_csv(TRACKS, tracks)
    write_csv(ALLOCATIONS, allocations)
    audit_fields = ["language_track_id", "previous_language_track_id", "registry_record_id", "campus_id", "district", "campus", "TAPR_program_group", "previous_language_pair", "language_pair", "audit_change", "pair_verification_scope", "historical_2023_24_pair_status", "evidence_period", "audit_source_ids", "evidence_source_url", "additional_language_role", "correction_reason"]
    write_csv(AUDIT, [{k: r[k] for k in audit_fields} for r in tracks])
    write_csv(ROLE_REVIEWS, [{**r, "source_ids": ";".join(r["source_ids"])} for r in reviews])
    write_csv(CAMPUS_VIEW, campus_view(tracks))
    summary = {
        "audit_date": "2026-11-04",
        "track_records": len(tracks),
        "parent_reporting_groups": len({r["registry_record_id"] for r in tracks}),
        "campuses": len({r["campus_id"] for r in tracks}),
        "language_pair_counts": dict(collections.Counter(r["language_pair"] for r in tracks)),
        "verification_scope_counts": dict(collections.Counter(r["pair_verification_scope"] for r in tracks)),
        "audit_change_counts": dict(collections.Counter(r["audit_change"] for r in tracks)),
        "spanish_pair_labels_withdrawn_pending_evidence": sum(r["previous_language_pair"] == "Spanish–English" and r["language_pair"] == "UNVERIFIED" for r in tracks),
        "partial_spanish_labels_marked_pair_unverified": sum(r["previous_language_pair"] == "Spanish (English pairing unverified)" and r["language_pair"] == "UNVERIFIED" for r in tracks),
        "previously_unverified_rows_with_documented_pair": sum(r["previous_language_pair"] == "UNVERIFIED" and r["language_pair"] != "UNVERIFIED" and r["audit_change"] != "ADDED_LANGUAGE_TRACK" for r in tracks),
        "campus_source_decisions": len(decisions),
        "district_policy_rules": len(policies),
        "source_retrievals": len(sources),
        "allocation_records": len(allocations),
        "allocation_links_retained": sum(bool(r["language_track_id_if_unambiguous"]) for r in allocations),
        "allocation_links_cleared": sum(bool(r["previous_language_track_id_if_unambiguous"]) and not r["language_track_id_if_unambiguous"] for r in allocations),
        "non_spanish_documented_campuses": len({r["campus_id"] for r in tracks if r["partner_language"] not in {"", "Spanish"} and r["pair_verification_scope"] == "CAMPUS_DOCUMENTED"}),
        "verified_language_specific_tapr_outcomes": 0,
        "verified_tested_cohort_exposures": 0,
    }
    (DATA / "language_audit_summary_pass50.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    paths = [TRACKS, ALLOCATIONS, AUDIT, ROLE_REVIEWS, CAMPUS_VIEW, DATA / "language_audit_summary_pass50.json", *sorted(INPUT.glob("*"))]
    manifest = {"audit_date": "2026-11-04", "files": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, "input_snapshots": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [PRIOR, DATA / "texas_language_program_tracks_pass48.csv", DATA / "texas_k_allocation_evidence_pass48.csv"]}}
    (DATA / "manifest_pass50.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (DATA / "current_inventory.json").write_text(json.dumps({"version": "pass50", "campus_language_inventory": str(CAMPUS_VIEW.relative_to(ROOT)), "language_tracks": str(TRACKS.relative_to(ROOT)), "k_allocation_evidence": str(ALLOCATIONS.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "source_register": str((INPUT / "source_register.csv").relative_to(ROOT)), "assessment_year": "2023-24", "evidence_dates": "Source-specific; do not backdate later offerings", "status": "PROVISIONAL_RESEARCH_NOT_VERIFIED_CENSUS"}, indent=2) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
