#!/usr/bin/env python3
"""Validate the five-state source-documented inventory without network access."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
STATES = {'WY': 'wyoming', 'MT': 'montana', 'ID': 'idaho', 'NV': 'nevada', 'CA': 'california'}
MODELS = {'90/10', '80/20', '50/50', 'other', 'unknown'}
STATUSES = {'confirmed_2026_27', 'probable_current_unconfirmed', 'historical_status_unknown',
            'confirmed_discontinued', 'planned_future'}


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f'Missing/duplicate CSV headers: {path}')
        rows = list(reader)
    if any(None in r for r in rows):
        raise ValueError(f'Extra CSV cells: {path}')
    return rows


def url_ok(url):
    try:
        u = urlsplit(url)
        return u.scheme in ('https', 'http') and bool(u.hostname) and not u.username and not u.password
    except ValueError:
        return False


def validate_rows(records, ledger, sources):
    errors = []
    seen_ids = set()
    seen_identity = set()
    sources_by_id = {r['source_id']: r for r in sources}
    by_program = collections.defaultdict(list)
    for claim in ledger:
        by_program[claim['program_id']].append(claim)
        if not url_ok(claim['source_url']) or not claim['evidence_excerpt_or_paraphrase'].strip():
            errors.append('Malformed source URL or empty evidence excerpt: ' + claim['evidence_id'])
        if claim['source_id'] not in sources_by_id:
            errors.append('Evidence references an unknown source: ' + claim['evidence_id'])
        elif claim['source_url'] != sources_by_id[claim['source_id']]['source_url']:
            errors.append('Evidence URL and source registry disagree: ' + claim['evidence_id'])
        if any(host in urlsplit(claim['source_url']).netloc for host in ('duckduckgo', 'bing.com')) or 'google.com/search' in claim['source_url']:
            errors.append('Search results cannot substitute for source evidence: ' + claim['evidence_id'])
    for row in records:
        pid = row['program_id']
        if not pid or pid in seen_ids:
            errors.append('Duplicate or missing program ID: ' + pid)
        seen_ids.add(pid)
        school = row['school_id'] or row['school_name'].strip().casefold()
        identity = (row['state'], row['district_name'].casefold(), school,
                    row['partner_language'], row['program_name'].casefold())
        if identity in seen_identity:
            errors.append('Duplicate school–program record: ' + pid)
        seen_identity.add(identity)
        for field in ('school_name', 'district_name', 'partner_language', 'instruction_languages'):
            if not row[field].strip():
                errors.append('Missing ' + field + ': ' + pid)
        if row['state'] not in STATES or row['reference_school_year'] != '2026-27':
            errors.append('Invalid state/reference year: ' + pid)
        if row['operating_status_2026_27'] not in STATUSES:
            errors.append('Invalid operating status: ' + pid)
        if row['school_structure'] not in ('whole_school', 'strand', 'unknown'):
            errors.append('Invalid school structure: ' + pid)
        if row['kindergarten_allocation'] not in MODELS:
            errors.append('Invalid kindergarten model: ' + pid)
        if not url_ok(row['source_url']):
            errors.append('Malformed primary source URL: ' + pid)
        if row['school_id'] and (row['school_id_namespace'] != 'CA_CDS'
                                 or not re.fullmatch(r'\d{14}', row['school_id'])):
            errors.append('Invalid school identifier/namespace: ' + pid)
        try:
            schedule = json.loads(row['kindergarten_language_shares_json'])
            if not isinstance(schedule, dict):
                raise ValueError('schedule must be a mapping')
            if schedule:
                numeric = {k: float(v) for k, v in schedule.items()}
                if any(v < 0 or v > 100 for v in numeric.values()) or abs(sum(numeric.values()) - 100) > 0.01:
                    errors.append('Invalid language percentages/sum: ' + pid)
                languages = set(row['instruction_languages'].split(' | '))
                if not set(numeric).issubset(languages):
                    errors.append('Allocation language not in instructional languages: ' + pid)
            for language, field in [(row['partner_language'], 'kindergarten_partner_language_pct'),
                                    ('English', 'kindergarten_english_pct')]:
                if row[field] != '' and float(row[field]) != float(schedule[language]):
                    errors.append('Scalar and normalized language shares disagree: ' + pid)
        except (ValueError, KeyError, TypeError):
            errors.append('Malformed language-share schedule: ' + pid)
            schedule = {}
        model = row['kindergarten_allocation']
        if model == 'unknown' and schedule:
            errors.append('Unknown allocation must not carry a selected complete schedule: ' + pid)
        if model in ('90/10', '80/20', '50/50'):
            expected = [int(v) for v in model.split('/')]
            try:
                if [float(row['kindergarten_partner_language_pct']), float(row['kindergarten_english_pct'])] != expected:
                    errors.append('Conventional model and percentages disagree: ' + pid)
            except ValueError:
                errors.append('Known conventional model missing percentages: ' + pid)
        if row['published_model_label'] in ('90/10', '80/20', '50/50') and model == 'unknown' and not row['allocation_conflict_notes']:
            errors.append('Published conventional model incorrectly left unknown without conflict: ' + pid)
        claims = by_program[pid]
        for field in ('school_name', 'district_name', 'partner_language', 'instruction_languages', 'operating_status_2026_27'):
            if not any(c['field_supported'] == field for c in claims):
                errors.append('Missing field-level evidence for ' + field + ': ' + pid)
        for field in ('kindergarten_allocation', 'school_structure'):
            if row[field] != 'unknown' and not any(c['field_supported'] == field for c in claims):
                errors.append('Unsupported classification for ' + field + ': ' + pid)
            values = {c['recorded_value'] for c in claims if c['field_supported'] == field}
            conflict_documented = field == 'kindergarten_allocation' and bool(row['allocation_conflict_notes'])
            if len(values - {'unknown'}) > 1 and not conflict_documented:
                errors.append('Unresolved conflicting classification: ' + pid)
        if model != 'unknown':
            if row['allocation_evidence_type'] not in ('explicit_kindergarten_schedule', 'published_model_designation',
                                                      'other_documented_kindergarten_evidence'):
                errors.append('Invalid allocation evidence type: ' + pid)
            relevant = ' '.join(c['evidence_excerpt_or_paraphrase'] for c in claims if c['field_supported'] == 'kindergarten_allocation').lower()
            if 'later_grade_only' in relevant or 'prekindergarten_only' in relevant:
                errors.append('Pre-K/later-grade allocation substituted for kindergarten: ' + pid)
        if row['operating_status_2026_27'] == 'confirmed_2026_27':
            dated = [c for c in claims if c['field_supported'] == 'operating_status_2026_27'
                     and c['applicable_school_year'] == '2026-27'
                     and c['evidence_classification'] not in ('research_status_assessment', 'historical_campus_specific_documentation')]
            if not dated:
                errors.append('Confirmed current program lacks applicable 2026–27 evidence: ' + pid)
        if row['operating_status_2026_27'] == 'planned_future' and row['operating_evidence_school_year'] == '2026-27':
            errors.append('Future opening incorrectly assigned current-year evidence: ' + pid)
    if set(by_program) - seen_ids:
        errors.append('Orphan evidence program IDs')
    if not records or not ledger:
        errors.append('Zero-record validation cannot establish readiness')
    for state in STATES:
        if not any(r['state'] == state for r in records):
            errors.append('No inventory records for ' + state)
    return errors


def validate(root=ROOT):
    base = root / 'data/registry/five_state_2026_27'
    records = [r for name in STATES.values() for r in csv_rows(root / f'data/registry/state_dl_programs_{name}_2026_27.csv')]
    ledger = csv_rows(base / 'evidence_ledger.csv')
    sources = csv_rows(base / 'sources.csv')
    errors = validate_rows(records, ledger, sources)
    for source in sources:
        if source.get('snapshot_path'):
            snapshot = root / source['snapshot_path']
            if not snapshot.is_file() or hashlib.sha256(snapshot.read_bytes()).hexdigest() != source['snapshot_sha256']:
                errors.append('Retained source snapshot checksum mismatch: ' + source['source_key'])
    cde = csv_rows(base / 'california_school_candidates_2024_25.csv')
    lausd = csv_rows(base / 'lausd_directory_snapshot.csv')
    if len(cde) != 1310 or len({r['school_id'] for r in cde}) != 1310:
        errors.append('CDE source-count reconciliation failed')
    if any(r['source_school_year'] != '2024-25' or r['operating_status_2026_27'] != 'historical_status_unknown' for r in cde):
        errors.append('Historical CDE candidates incorrectly marked current')
    if len(lausd) != 211:
        errors.append('LAUSD source-count reconciliation failed')
    language_rows = csv_rows(base / 'kindergarten_instruction_languages.csv')
    language_schedules = collections.defaultdict(dict)
    for row in language_rows:
        if row['instruction_language'] in language_schedules[row['program_id']]:
            errors.append('Duplicate normalized language share: ' + row['program_id'])
        language_schedules[row['program_id']][row['instruction_language']] = float(row['instruction_share_pct'])
    for row in records:
        expected_schedule = {k: float(v) for k, v in json.loads(row['kindergarten_language_shares_json']).items()}
        if language_schedules.get(row['program_id'], {}) != expected_schedule:
            errors.append('Normalized language table disagrees with inventory: ' + row['program_id'])
    expected = {r['source_row_id'] for r in lausd}
    observed = {v for r in records for v in r['source_row_ids'].split(' | ') if v}
    if observed != expected:
        errors.append('LAUSD source records lost or invented during consolidation')
    cover = json.loads((base / 'coverage_summary.json').read_text())
    for state, stats in cover.items():
        state_rows = [r for r in records if r['state'] == state]
        if len(state_rows) != stats['distinct_program_records_including_candidates']:
            errors.append('Coverage count mismatch: ' + state)
        eligible = [r for r in state_rows if r['inclusion_status'].startswith('documented_')
                    and r['operating_status_2026_27'] not in ('planned_future', 'confirmed_discontinued')]
        if sum(stats['kindergarten_model_distribution_any_source_year'].values()) != len(eligible):
            errors.append('Kindergarten distribution denominator mismatch: ' + state)
    if errors:
        raise ValueError('\n'.join(errors))
    return {'result': 'passed', 'program_records_checked': len(records), 'evidence_claims_checked': len(ledger),
            'source_documents_checked': len(sources), 'historical_CDE_school_candidates_checked': len(cde),
            'LAUSD_source_rows_reconciled': len(lausd),
            'statewide_completeness': 'not_established',
            'unresolved_classifications': 'retained explicitly; see coverage summary and research notes'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    result = validate(args.root)
    output = args.root / 'data/registry/five_state_2026_27/validation_results.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
