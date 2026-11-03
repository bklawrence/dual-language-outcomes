
#!/usr/bin/env python3
"""Check the additive Texas Pass 48 snapshot without modifying repo files.

From repository root: python3 scripts/validate_texas_pass48.py
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import sys

DATA = Path('data/registry/texas')
TRACK = 'texas_language_program_tracks_pass48.csv'
ALLOC = 'texas_k_allocation_evidence_pass48.csv'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(data: bytes) -> bytes:
    """Ignore only newline style and number of trailing newlines."""
    data = data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    return data.rstrip(b'\n') + b'\n'


def csv_rows(path: Path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f'Invalid or duplicate CSV headers: {path}')
        return list(reader)


def validate(root: Path):
    d = root / DATA
    manifest = json.loads((d / 'manifest_pass48.json').read_text(encoding='utf-8'))
    problems = []
    for rel, meta in manifest['files'].items():
        target = root / rel
        if not target.is_file():
            problems.append(f'Missing file: {rel}')
            continue
        data = target.read_bytes()
        if digest(canonical_bytes(data)) != meta['sha256_canonical_text']:
            problems.append(f'Text-content checksum mismatch: {rel}')
    if problems:
        raise ValueError('\n'.join(problems))

    tracks = csv_rows(d / TRACK)
    allocations = csv_rows(d / ALLOC)
    track_index = {}
    groups = collections.defaultdict(list)
    for lineno, row in enumerate(tracks, 2):
        tid, rid = row['language_track_id'], row['registry_record_id']
        if not tid or tid in track_index:
            problems.append(f'Track row {lineno}: blank/duplicate track ID')
        else:
            track_index[tid] = row
        if not rid or row['campus_id'] != rid.split(':', 1)[0]:
            problems.append(f'Track row {lineno}: invalid parent/campus ID')
        if row['TAPR_program_group'] not in {'one_way','two_way'}:
            problems.append(f'Track row {lineno}: invalid TAPR group')
        if row['language_pair'] == 'UNVERIFIED' and row['language_evidence_level'] != 'unverified_default':
            problems.append(f'Track row {lineno}: unverifiable language not flagged correctly')
        if row['track_identity_status'] != 'PROVISIONAL_LANGUAGE_TRACK_NOT_STABLE_PROGRAM_ID':
            problems.append(f'Track row {lineno}: claims stable program ID')
        groups[rid].append(row)
    for rid, siblings in groups.items():
        if len({r['language_track_id'] for r in siblings}) != len(siblings):
            problems.append(f'Duplicate track ID within TAPR reporting group {rid}')

    allocation_ids = set()
    linked = unlinked = 0
    for lineno, row in enumerate(allocations, 2):
        aid, rid = row['allocation_record_id'], row['registry_record_id']
        if not aid or aid in allocation_ids:
            problems.append(f'Allocation row {lineno}: blank/duplicate allocation ID')
        allocation_ids.add(aid)
        if rid not in groups or row['campus_id'] != (groups[rid][0]['campus_id'] if rid in groups else None):
            problems.append(f'Allocation row {lineno}: mismatched/absent parent group')
        if row['TAPR_program_group'] not in {'one_way','two_way'} or row['grade'] != 'K':
            problems.append(f'Allocation row {lineno}: unexpected grade/reporting group')
        if row['verified_tested_cohort_exposure'].casefold() == 'yes':
            problems.append(f'Allocation row {lineno}: exposure not verified by this snapshot')
        tid = row['language_track_id_if_unambiguous']
        if tid:
            linked += 1
            if tid not in track_index or track_index[tid]['registry_record_id'] != rid:
                problems.append(f'Allocation row {lineno}: ambiguous/wrong track link')
            elif track_index[tid]['language_pair'] == 'UNVERIFIED':
                problems.append(f'Allocation row {lineno}: linked to unverified language')
        else:
            unlinked += 1
            if row['partner_language_attribution'] != 'REQUIRES_REVIEW':
                problems.append(f'Allocation row {lineno}: unresolved language not flagged for review')

    result = {
        'campuses': len({r['campus_id'] for r in tracks}),
        'registry_groups': len(groups),
        'language_tracks': len(tracks),
        'reporting_groups_with_multiple_tracks': sum(len(v)>1 for v in groups.values()),
        'unverified_language_tracks': sum(r['language_pair']=='UNVERIFIED' for r in tracks),
        'allocation_observations': len(allocations),
        'allocations_linked_to_track': linked,
        'allocations_without_unambiguous_track_link': unlinked,
        'verified_tested_cohort_exposures': sum(r['verified_tested_cohort_exposure'].casefold()=='yes' for r in allocations),
    }
    for key, expected in manifest['expected_counts'].items():
        if result.get(key) != expected:
            problems.append(f'Unexpected {key}: {result.get(key)} (expected {expected})')
    if problems:
        raise ValueError('\n'.join(problems))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=p.parse_args()
    try:
        results=validate(args.root.resolve())
    except (OSError,KeyError,ValueError,csv.Error) as err:
        print(f'FAIL: {err}',file=sys.stderr)
        return 1
    print('PASS: Texas Pass 48 snapshot and linkage checks')
    print(json.dumps(results,indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
