#!/usr/bin/env python3
"""Validate Texas cleanup provenance, historical continuity and source-scope limits."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError('Duplicate CSV headers: ' + str(path))
        return list(reader)


def check_rows(tracks, allocations, prior_tracks, prior_allocations, decisions, reviews, additions, sources):
    errors = []
    old_tracks = {r['language_track_id']: r for r in prior_tracks}
    track_index = {r['language_track_id']: r for r in tracks}
    language_decisions = {r['language_track_id']: r for r in decisions}
    if len(track_index) != len(tracks) or set(track_index) != set(old_tracks):
        errors.append('Original track identities lost, invented or duplicated')
    for row in tracks:
        tid = row['language_track_id']
        old = old_tracks.get(tid)
        if old is None:
            continue
        for key in ('campus_id', 'registry_record_id', 'assessment_year', 'TAPR_program_group', 'raw_source_language_label', 'raw_historical_language_label', 'previous_language_pair', 'previous_language_track_id', 'derived_from_language_track_id'):
            if row[key] != old[key]:
                errors.append('Altered historical track identity/label: ' + tid + '/' + key)
        decision = language_decisions.get(tid)
        if decision:
            if row['language_pair'] != decision['language_pair'] or row['pair_verification_scope'] != decision['verification_scope']:
                errors.append('Language decision not applied at reviewed scope: ' + tid)
            if row['audit_source_ids'] != ';'.join(decision['source_ids']):
                errors.append('Language decision lost evidence lineage: ' + tid)
            expected_history = decision['historical_2023_24_pair_status']
            if expected_history=='NOT_ESTABLISHED' and old['campus_specific_2023_24_roster_confirmed']=='YES':
                expected_history=old['historical_2023_24_pair_status']
            if row['historical_2023_24_pair_status']!=expected_history:
                errors.append('Language evidence assigned an unsupported historical year: ' + tid)
            if row['language_pair_verified_in_source']!='YES':
                errors.append('Reviewed language evidence has inconsistent verification status: ' + tid)
            if decision['verification_scope']=='DISTRICT_POLICY_ONLY' and old['campus_specific_2023_24_roster_confirmed']!='YES':
                if row['campus_specific_2023_24_roster_confirmed']!='NO' or row['historical_2023_24_pair_status']!='NOT_ESTABLISHED':
                    errors.append('Policy evidence backdated to campus/year: ' + tid)
        elif any(row[key] != value for key, value in old.items()):
            errors.append('Changed an unreviewed language record: ' + tid)
        if row['language_pair']=='UNVERIFIED' and (row['partner_language'] or row['instruction_languages'] or row['language_pair_verified_in_source']!='NO'):
            errors.append('Unknown pair silently assigned a language: ' + tid)
        if row['language_pair']!='UNVERIFIED' and row['instruction_languages']!='English;'+row['partner_language']:
            errors.append('Inconsistent instructional languages: ' + tid)
        if row['language_specific_2023_24_TAPR_result_available']!='NOT_ESTABLISHED' or row['outcome_attribution']!='NOT_ESTABLISHED_DO_NOT_DISAGGREGATE':
            errors.append('Unsupported language-specific outcome: ' + tid)
        for key in filter(None,row['audit_source_ids'].split(';')):
            if key not in sources:
                errors.append('Unregistered language source: ' + key)
    old_allocations = {r['allocation_record_id']: r for r in prior_allocations}
    allocation_index = {r['allocation_record_id']: r for r in allocations}
    reviewed = {r['allocation_record_id']: r for r in reviews}
    added = {r['allocation_record_id']: r for r in additions}
    if len(allocation_index)!=len(allocations) or set(allocation_index)!=set(old_allocations)|set(added):
        errors.append('Allocation identity lost, invented or duplicated')
    for row in allocations:
        rid=row['allocation_record_id'];old=old_allocations.get(rid);decision=reviewed.get(rid) or added.get(rid)
        if old:
            for key in ('allocation_label','registry_record_id','campus_id','TAPR_program_group','grade','entry_school_year'):
                if row[key]!=old[key]:
                    errors.append('Altered original allocation identity/value: '+rid+'/'+key)
            if rid not in reviewed and any(row[key]!=value for key,value in old.items()):
                errors.append('Changed an unreviewed allocation: '+rid)
            if row['pass51_previous_source_url']!=old['source_url'] or row['pass51_previous_source_period']!=old['source_period']:
                errors.append('Lost previous allocation provenance: '+rid)
        if decision:
            if row['pass51_k_support']!=decision['k_support']:
                errors.append('K support promoted beyond reviewed evidence: '+rid)
            if row['pass51_source_ids']!=';'.join(decision['source_ids']):
                errors.append('Allocation decision lost evidence lineage: '+rid)
            for key in decision['source_ids']:
                if key not in sources or sources[key]['http_status']!='200':
                    errors.append('Allocation lacks retrieved evidence: '+rid)
            for key,value in decision.get('updates',{}).items():
                if key not in {'link_partner','clear_link'} and row[key]!=value:
                    errors.append('Reviewed allocation update missing: '+rid+'/'+key)
        tid=row['language_track_id_if_unambiguous']
        if tid:
            linked=track_index.get(tid)
            if not linked or linked['registry_record_id']!=row['registry_record_id'] or linked['language_pair']=='UNVERIFIED':
                errors.append('Unsupported allocation candidate link: '+rid)
            expected_partner=(decision or {}).get('link_partner') or (decision or {}).get('updates',{}).get('link_partner')
            if expected_partner and linked and linked['partner_language']!=expected_partner:
                errors.append('Wrong partner language on allocation policy: '+rid)
        if row['pass51_k_support'] in {'PREK_PROXY_NOT_K_QUANTIFIED','SOURCE_DOES_NOT_SUPPORT_PROGRAM_GRADE_PERIOD'} and tid:
            errors.append('Unsupported K proxy/citation acquired a language link: '+rid)
        if row['verified_tested_cohort_exposure']!='NO':
            errors.append('Unsupported tested-cohort exposure: '+rid)
        if rid in added:
            if row['pass51_observation_origin']!='ADDED_PASS51' or '2026-11-04' not in row['source_period']:
                errors.append('Current policy observation lost separate date/origin: '+rid)
            for key in ('campus_id','registry_record_id','TAPR_program_group','grade','allocation_label','source_period'):
                if row[key]!=added[rid][key]:
                    errors.append('Current policy observation changed scope/value: '+rid+'/'+key)
    # Additional languages and district models do not establish an exact campus
    # grade timetable or identify a tested participant cohort.
    for row in tracks:
        if row['district']=='YSLETA ISD' and int(row['campus_id'][-3:])<100 and row['language_pair']!='UNVERIFIED':
            errors.append('Elementary Ysleta policy applied to a secondary reporting group')
        if row['district']=='LA JOYA ISD' and row['language_pair']!='UNVERIFIED':
            errors.append('La Joya numeric model silently established the instructional pair')
    for row in allocations:
        if row['campus_id'].startswith('071905') and row['pass51_k_support']!='MODEL_LABEL_MINUTES_DIFFER':
            errors.append('Ysleta model label promoted to an exact K timetable')
        if row['campus_id']=='227901132' and row['language_track_id_if_unambiguous']:
            linked=track_index.get(row['language_track_id_if_unambiguous'])
            if not linked or linked['partner_language']!='Mandarin':
                errors.append('Reilly non-Spanish policy was assigned to Spanish')
    return errors


def validate(root=ROOT):
    data=root/'data/registry/texas';inputs=data/'pass51'
    manifest=json.loads((data/'manifest_pass51.json').read_text())
    errors=[]
    for section in ('files','inputs','build_script'):
        for rel,expected in manifest[section].items():
            path=root/rel
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                errors.append('Checksum mismatch or missing file: '+rel)
    tracks=read_csv(data/'texas_language_program_tracks_pass51.csv')
    allocations=read_csv(data/'texas_k_allocation_evidence_pass51.csv')
    sources={r['source_id']:r for r in read_csv(inputs/'source_register.csv')}
    errors.extend(check_rows(tracks,allocations,
        read_csv(data/'texas_language_program_tracks_pass50.csv'),read_csv(data/'texas_k_allocation_evidence_pass50.csv'),
        json.loads((inputs/'language_decisions.json').read_text()),json.loads((inputs/'allocation_reviews.json').read_text()),
        json.loads((inputs/'allocation_additions.json').read_text()),sources))
    for source in sources.values():
        if not source.get('archive_path'):
            continue
        archive=root/source['archive_path'];meta=json.loads((root/source['archive_metadata_path']).read_text())
        fingerprint=hashlib.sha256(archive.read_bytes()).hexdigest()
        if fingerprint!=source['sha256_archive'] or fingerprint!=meta['sha256']:
            errors.append('Archived source checksum differs from evidence register')
        if hashlib.sha256(archive.with_suffix('.txt').read_bytes()).hexdigest()!=meta['text_sha256']:
            errors.append('Extracted source text checksum mismatch')
    pointer=json.loads((data/'current_inventory.json').read_text())
    config=json.loads((root/'config/states/tx.json').read_text())['pilot']
    if pointer['version']!='pass51' or pointer['language_tracks']!=config['tracks'] or pointer['k_allocation_evidence']!=config['allocations'] or pointer['source_register']!=config['source_register']:
        errors.append('Current Texas pointer/config does not select Pass 51')
    campus=read_csv(data/'texas_campus_language_inventory_pass51.csv')
    if len(campus)!=len({r['campus_id'] for r in tracks}) or {r['campus_id'] for r in campus}!={r['campus_id'] for r in tracks}:
        errors.append('Campus view lost or duplicated campus identities')
    if errors:
        raise ValueError('\n'.join(errors))
    return dict(status='PASS',tracks=len(tracks),campuses=len(campus),allocation_records=len(allocations),archived_sources=sum(bool(r.get('archive_path')) for r in sources.values()))


if __name__=='__main__':
    print(json.dumps(validate(),indent=2))
