#!/usr/bin/env python3
"""Validate confirmation provenance, source links, models, and source reconciliation."""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
STATES = {'WY':'wyoming','MT':'montana','ID':'idaho','NV':'nevada','CA':'california'}
STATUSES = {'confirmed_2025_26','probable_current_unconfirmed','historical_status_unknown',
            'confirmed_discontinued','planned_future'}
BLOCKED_OUTCOMES = {'confirmed_discontinued','implementation_not_established','content_scope_unresolved','incomplete_search'}


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as handle:
        reader=csv.DictReader(handle)
        assert reader.fieldnames and len(set(reader.fieldnames))==len(reader.fieldnames),path
        rows=list(reader)
    assert not any(None in row for row in rows),path
    return rows


def valid_url(value):
    u=urlsplit(value)
    return u.scheme in ('http','https') and bool(u.hostname) and not u.username and not u.password


def validate_rows(rows,ledger,sources,reviews):
    errors=[];ids=set();identities=set();by_program=collections.defaultdict(list)
    source_ids={s['source_id']:s for s in sources};review_ids={r['review_id']:r for r in reviews}
    if len(source_ids)!=len(sources):errors.append('Duplicate source ID')
    for claim in ledger:
        by_program[claim['program_id']].append(claim)
        source=source_ids.get(claim['source_id'])
        if not source or source['source_url']!=claim['source_url']:errors.append('Source identity mismatch: '+claim['evidence_id'])
        if not valid_url(claim['source_url']) or not claim['evidence_excerpt_or_paraphrase'].strip():errors.append('Missing/malformed evidence: '+claim['evidence_id'])
        if any(host in urlsplit(claim['source_url']).netloc for host in ['search.yahoo','search.brave','duckduckgo','bing.com']):errors.append('Search results used as substantive evidence: '+claim['evidence_id'])
    for row in rows:
        pid=row['program_id'];claims=by_program[pid]
        if not pid or pid in ids:errors.append('Duplicate/missing program ID: '+pid)
        ids.add(pid)
        identity=(row['state'],row['district_name'].casefold(),row['school_id'] or row['school_name'].casefold(),row['partner_language'],row['program_name'])
        if identity in identities:errors.append('Duplicate school-program identity: '+pid)
        identities.add(identity)
        for f in ['school_name','district_name','partner_language','instruction_languages']:
            if not row[f].strip():errors.append('Missing '+f+': '+pid)
            if not any(c['field_supported']==f for c in claims):errors.append('Missing field evidence '+f+': '+pid)
        if row['state'] not in STATES or row['reference_school_year']!='2025-26':errors.append('Invalid state/reference year: '+pid)
        if row['operating_status_2025_26'] not in STATUSES:errors.append('Invalid status: '+pid)
        if row['school_structure'] not in ['whole_school','strand','unknown']:errors.append('Invalid structure: '+pid)
        if not valid_url(row['source_url']):errors.append('Malformed primary URL: '+pid)
        if row['school_id'] and (row['school_id_namespace']!='CA_CDS' or not re.fullmatch(r'\d{14}',row['school_id'])):errors.append('Malformed official school ID: '+pid)
        model=row['kindergarten_allocation']
        if model not in ['90/10','80/20','50/50','other','unknown']:errors.append('Invalid model: '+pid)
        try:
            schedule=json.loads(row['kindergarten_language_shares_json'])
            if not isinstance(schedule,dict):raise ValueError('Expected schedule mapping')
            if schedule:
                percentages=[float(v) for v in schedule.values()]
                if abs(sum(percentages)-100)>0.01 or any(v<0 or v>100 for v in percentages):errors.append('Invalid allocation sum: '+pid)
                if not set(schedule).issubset(set(row['instruction_languages'].split(' | '))):errors.append('Wrong allocation languages: '+pid)
            if model=='unknown' and schedule:errors.append('Unknown model has selected percentages: '+pid)
            if model in ['90/10','80/20','50/50']:
                if [float(row['kindergarten_partner_language_pct']),float(row['kindergarten_english_pct'])]!=[int(x) for x in model.split('/')]:errors.append('Model/percentage mismatch: '+pid)
            for language,field in [(row['partner_language'],'kindergarten_partner_language_pct'),('English','kindergarten_english_pct')]:
                if row[field]!='' and float(row[field])!=float(schedule[language]):errors.append('Normalized share mismatch: '+pid)
        except (ValueError,TypeError,KeyError):errors.append('Malformed allocation: '+pid)
        if model!='unknown' and not any(c['field_supported']=='kindergarten_allocation' and c['recorded_value']==model for c in claims):errors.append('Selected K model lacks supporting claim: '+pid)
        if model=='unknown' and row['published_model_label'] in ['90/10','80/20','50/50'] and not row['allocation_conflict_notes']:errors.append('Conventional model dropped without documented exception: '+pid)
        if row['school_structure']!='unknown' and not any(c['field_supported']=='school_structure' and c['recorded_value']==row['school_structure'] for c in claims):errors.append('Structure lacks matching evidence: '+pid)
        model_values={c['recorded_value'] for c in claims if c['field_supported']=='kindergarten_allocation'}-{'unknown'}
        if len(model_values)>1 and not(row['allocation_change_notes'] or row['allocation_conflict_notes']):errors.append('Undocumented model conflict: '+pid)
        operating=[c for c in claims if c['field_supported']=='operating_status_2025_26' and c['recorded_value']==row['operating_status_2025_26']]
        if not operating:errors.append('Operating status lacks evidence/assessment: '+pid)
        linked=[review_ids.get(k) for k in row['continuity_review_ids'].split(' | ') if k]
        if any(r is None or pid not in r['program_ids'] for r in linked):errors.append('Review scope mismatch: '+pid)
        if row['operating_status_2025_26']=='confirmed_2025_26':
            if row['confirmation_basis']=='continuity_no_end_indication':
                if row['previous_inventory_status_2026_27']=='planned_future':errors.append('Future opening promoted by continuity: '+pid)
                if not linked or any(r['outcome'] in BLOCKED_OUTCOMES for r in linked):errors.append('Continuity confirmation lacks an eligible review: '+pid)
                if not all(any(q['usable'] for q in r['queries']) and r['source_keys_read'] for r in linked):errors.append('Continuity confirmation relies on incomplete search: '+pid)
                if not any(c['evidence_classification']=='user_authorized_continuity_assessment' for c in operating):errors.append('Continuity mislabeled as direct evidence: '+pid)
            elif not any(c['applicable_school_year']=='2025-26' and c['evidence_classification']=='explicit_reference_year_evidence' for c in operating):errors.append('Direct confirmation lacks reference-year evidence: '+pid)
        if row['allocation_applicability_2025_26']=='later_2026_27_schedule_not_verified_for_2025_26' and model!='unknown':errors.append('Later schedule retroactively assigned: '+pid)
    if set(by_program)-ids:errors.append('Orphan evidence IDs')
    if not rows or not ledger:errors.append('Empty inventory cannot pass')
    if {r['state'] for r in rows}!=set(STATES):errors.append('Missing state')
    return errors


def validate(root=ROOT):
    base=root/'data/registry/five_state_2025_26'
    rows=[r for s in STATES.values() for r in read_csv(root/f'data/registry/state_dl_programs_{s}_2025_26.csv')]
    ledger=read_csv(base/'evidence_ledger.csv');sources=read_csv(base/'sources.csv')
    reviews=json.loads((base/'continuity_reviews.json').read_text())
    errors=validate_rows(rows,ledger,sources,reviews)
    for s in sources:
        if s['snapshot_path']:
            path=root/s['snapshot_path']
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=s['snapshot_sha256']:errors.append('Snapshot checksum mismatch: '+s['source_key'])
    old=root/'data/registry/five_state_2026_27'
    lausd=read_csv(old/'lausd_directory_snapshot.csv')
    if {r['source_row_id'] for r in lausd}!={v for r in rows for v in r['source_row_ids'].split(' | ') if v}:errors.append('LAUSD source reconciliation failed')
    fresno=read_csv(base/'fresno_roster_crosswalk.csv')
    if len(fresno)!=25 or len({r['source_row_id'] for r in fresno})!=25 or len({r['program_id'] for r in fresno})!=24:errors.append('Fresno source reconciliation failed')
    if any(r['program_id'] not in {v['program_id'] for v in rows} for r in fresno):errors.append('Orphan Fresno crosswalk')
    for row in rows:
        if row['district_name']=='San Francisco Unified School District' and row['partner_language']=='Spanish' and row['kindergarten_allocation']!='50/50':errors.append('SFUSD 2025 Spanish policy not applied')
        if row['school_name']=='Hardin Primary School' and row['kindergarten_allocation']!='unknown':errors.append('Hardin Primary inherited an unsupported K model')
        if row['school_name']=='Chickadee Lodge Apsáalooke Language Immersion School' and row['operating_status_2025_26']!='confirmed_discontinued':errors.append('Chickadee closure overlooked')
    coverage=json.loads((base/'coverage_summary.json').read_text())
    for state,stats in coverage.items():
        selected=[r for r in rows if r['state']==state]
        confirmed=[r for r in selected if r['inclusion_status'].startswith('documented_') and r['operating_status_2025_26']=='confirmed_2025_26']
        if stats['distinct_program_records_including_candidates']!=len(selected) or stats['confirmed_2025_26']!=len(confirmed):errors.append('Coverage mismatch: '+state)
        if stats['confirmed_with_year_specific_evidence']+stats['confirmed_by_continuity_rule']!=len(confirmed):errors.append('Confirmation-basis denominator mismatch: '+state)
    if errors:raise ValueError('\n'.join(errors))
    return dict(result='passed',program_records_checked=len(rows),evidence_claims_checked=len(ledger),registered_sources=len(sources),
                review_scopes_checked=len(reviews),lausd_source_rows_reconciled=len(lausd),fresno_source_rows_reconciled=len(fresno),
                fresno_distinct_programs=24,statewide_completeness='not_established')


if __name__=='__main__':
    result=validate()
    (ROOT/'data/registry/five_state_2025_26/validation_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
