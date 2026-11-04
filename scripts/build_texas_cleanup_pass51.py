#!/usr/bin/env python3
"""Build the bounded Texas cleanup from saved, reviewed decisions; no network."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/registry/texas'
INPUT = DATA / 'pass51'


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_tracks(prior, decisions, sources):
    decisions_by_id = {r['language_track_id']: r for r in decisions}
    if len(decisions_by_id) != len(decisions):
        raise ValueError('Duplicate language decision')
    known = {r['language_track_id'] for r in prior}
    if not set(decisions_by_id) <= known:
        raise ValueError('Decision invents a language-track identity')
    output = []
    for old in prior:
        row = dict(old)
        row.update(pass51_previous_language_pair=old['language_pair'],
                   pass51_previous_verification_scope=old['pair_verification_scope'],
                   pass51_reviewed='NO', pass51_change_note='')
        decision = decisions_by_id.get(row['language_track_id'])
        if decision:
            if old['language_pair'] != decision['expected_previous_pair']:
                raise ValueError('Language decision has stale baseline: ' + row['language_track_id'])
            ids = decision['source_ids']
            if not ids or any(sources[key]['http_status'] != '200' for key in ids):
                raise ValueError('Language decision lacks successfully retrieved sources')
            pair = decision['language_pair']
            partner = pair.split('–')[0]
            historical = decision['historical_2023_24_pair_status']
            # Preserve a previously documented date; policy evidence cannot create one.
            if historical == 'NOT_ESTABLISHED' and old['campus_specific_2023_24_roster_confirmed'] == 'YES':
                historical = old['historical_2023_24_pair_status']
            row.update(language_pair=pair, partner_language=partner,
                       instruction_languages='English;' + partner,
                       language_evidence_level='pass51_' + decision['verification_scope'].lower(),
                       evidence_source_url=' ; '.join(sources[key]['url'] for key in ids),
                       evidence_period='; '.join(dict.fromkeys(sources[key]['evidence_period'] for key in ids)),
                       audit_source_ids=';'.join(ids),
                       pair_verification_scope=decision['verification_scope'],
                       language_pair_verified_in_source='YES',
                       historical_2023_24_pair_status=historical,
                       campus_specific_2023_24_roster_confirmed='YES' if historical in {'YES', 'PRIOR_DATED_CAMPUS_EVIDENCE_RETAINED'} else 'NO',
                       correction_reason=decision['rationale'],
                       notes=decision['rationale'] + ' Provisional reporting-group association; no language-specific TAPR attribution.',
                       pass51_reviewed='YES', pass51_change_note=decision['rationale'])
        output.append(row)
    return output


def link_policy(row, partner, groups):
    candidates = [r for r in groups[row['registry_record_id']] if r['partner_language'] == partner]
    if len(candidates) != 1 or candidates[0]['language_pair_verified_in_source'] != 'YES':
        raise ValueError('Policy does not identify one supported candidate: ' + row['allocation_record_id'])
    row.update(language_track_id_if_unambiguous=candidates[0]['language_track_id'],
               partner_language_attribution='SOURCE_SPECIFIC_POLICY_NOT_COHORT_OR_TAPR_MODEL_VERIFIED',
               language_link_audit='PASS51_SOURCE_SPECIFIC_POLICY_LINK_NOT_COHORT_VERIFIED',
               language_link_audit_note='Reviewed source names this instructional pair/model. Candidate association does not confirm campus/year delivery, reporting-category hosting or tested-cohort exposure.')


def make_allocations(prior, reviews, additions, tracks, sources):
    groups = defaultdict(list)
    for row in tracks:
        groups[row['registry_record_id']].append(row)
    by_id = {r['allocation_record_id']: r for r in reviews}
    if len(by_id) != len(reviews) or not set(by_id) <= {r['allocation_record_id'] for r in prior}:
        raise ValueError('Duplicate or invented allocation review identity')
    output, audit = [], []
    for old in prior:
        row = dict(old)
        row.update(pass51_observation_origin='PRESERVED_PASS50',
                   pass51_previous_source_url=old['source_url'],
                   pass51_previous_source_period=old['source_period'],
                   pass51_review_status='NOT_REVIEWED', pass51_k_support='NOT_REVIEWED',
                   pass51_source_ids='', pass51_source_locator='', pass51_change_note='')
        decision = by_id.get(row['allocation_record_id'])
        if decision:
            if decision['expected_previous_label'] != old['allocation_label']:
                raise ValueError('Allocation decision has stale baseline')
            updates = dict(decision['updates'])
            partner, clear = updates.pop('link_partner', None), updates.pop('clear_link', False)
            row.update(updates)
            row.update(evidence_note=decision['note'], pass51_review_status=decision['review_status'],
                       pass51_k_support=decision['k_support'],
                       pass51_source_ids=';'.join(decision['source_ids']),
                       pass51_source_locator=decision['source_locator'], pass51_change_note=decision['note'])
            if clear:
                row.update(language_track_id_if_unambiguous='', partner_language_attribution='REQUIRES_REVIEW',
                           language_link_audit='PASS51_UNSUPPORTED_K_LINK_WITHHELD',
                           language_link_audit_note=decision['note'])
            if partner:
                link_policy(row, partner, groups)
            audit.append(allocation_audit(old, row))
        output.append(row)
    template = dict.fromkeys(prior[0], '')
    for decision in additions:
        ids = decision['source_ids']
        row = dict(template)
        row.update({key: decision[key] for key in ('allocation_record_id', 'registry_record_id', 'campus_id', 'TAPR_program_group', 'grade', 'allocation_label', 'source_period')})
        row.update(entry_school_year='NOT_CONFIRMED_FOR_TESTED_COHORT',
                   allocation_interpretation='non-English partner / English (published policy label; not measured shares)',
                   source_url=sources[ids[0]]['url'], classification_status='current_district_PK5_policy_campus_year_unconfirmed',
                   evidence_note=decision['note'], verified_tested_cohort_exposure='NO', allow_multiple_k_models_same_campus='YES',
                   pass51_observation_origin='ADDED_PASS51', pass51_previous_source_url='', pass51_previous_source_period='',
                   pass51_review_status='ADDED_CURRENT_POLICY_OBSERVATION', pass51_k_support=decision['k_support'],
                   pass51_source_ids=';'.join(ids), pass51_source_locator=decision['source_locator'], pass51_change_note=decision['note'])
        link_policy(row, decision['link_partner'], groups)
        output.append(row)
        audit.append(allocation_audit({}, row))
    return output, audit


def allocation_audit(old, row):
    fields = ('source_url', 'source_period', 'classification_status', 'language_track_id_if_unambiguous', 'evidence_note')
    return dict(allocation_record_id=row['allocation_record_id'], campus_id=row['campus_id'],
                TAPR_program_group=row['TAPR_program_group'], allocation_label=row['allocation_label'],
                **{'old_' + key: old.get(key, '') for key in fields},
                **{'new_' + key: row[key] for key in fields},
                review_status=row['pass51_review_status'], k_support=row['pass51_k_support'],
                source_ids=row['pass51_source_ids'], source_locator=row['pass51_source_locator'])


def campus_view(tracks):
    grouped = defaultdict(list)
    for row in tracks:
        grouped[row['campus_id']].append(row)
    result = []
    for cid, rows in grouped.items():
        def joined(field, subset=None):
            return ' | '.join(sorted({r[field] for r in (rows if subset is None else subset) if r[field]}))
        result.append(dict(campus_id=cid, district=rows[0]['district'], campus=rows[0]['campus'],
            TAPR_reporting_categories=joined('TAPR_program_group'),
            campus_documented_language_pairs=joined('language_pair', [r for r in rows if r['pair_verification_scope']=='CAMPUS_DOCUMENTED']),
            district_policy_supported_pairs_campus_year_unconfirmed=joined('language_pair', [r for r in rows if r['pair_verification_scope']=='DISTRICT_POLICY_ONLY']),
            prior_pair_labels_not_independently_reconfirmed=joined('language_pair', [r for r in rows if r['pair_verification_scope']=='PRIOR_EVIDENCE_NOT_INDEPENDENTLY_RECONFIRMED']),
            has_unverified_pair_record='YES' if any(r['language_pair']=='UNVERIFIED' for r in rows) else 'NO',
            documented_non_spanish_partner='YES' if any(r['pair_verification_scope']=='CAMPUS_DOCUMENTED' and r['partner_language'] not in {'','Spanish'} for r in rows) else 'NO',
            historical_2023_24_pair_status=joined('historical_2023_24_pair_status'),
            additional_language_roles_or_unresolved_leads=joined('additional_language_role'),
            evidence_periods=joined('evidence_period'), evidence_source_urls=joined('evidence_source_url'),
            interpretation='Language evidence summary; district policy is not campus/year confirmation. No distinct-program or language-specific TAPR count.'))
    return result


def coverage(allocations):
    cited = [r for r in allocations if r['source_url']]
    linked = [r for r in cited if r['language_track_id_if_unambiguous']]
    return dict(allocation_records=len(allocations), campuses_with_any_label=len({r['campus_id'] for r in allocations}),
                campuses_with_any_citation=len({r['campus_id'] for r in cited}),
                campuses_with_cited_candidate_language_link=len({r['campus_id'] for r in linked}),
                cited_candidate_language_link_rows=len(linked))


def main():
    prior_tracks = read_csv(DATA / 'texas_language_program_tracks_pass50.csv')
    prior_allocations = read_csv(DATA / 'texas_k_allocation_evidence_pass50.csv')
    sources = {r['source_id']: r for r in read_csv(INPUT / 'source_register.csv')}
    decisions = json.loads((INPUT / 'language_decisions.json').read_text())
    tracks = make_tracks(prior_tracks, decisions, sources)
    allocations, allocation_changes = make_allocations(prior_allocations,
        json.loads((INPUT / 'allocation_reviews.json').read_text()),
        json.loads((INPUT / 'allocation_additions.json').read_text()), tracks, sources)
    track_path = DATA / 'texas_language_program_tracks_pass51.csv'
    allocation_path = DATA / 'texas_k_allocation_evidence_pass51.csv'
    campus_path = DATA / 'texas_campus_language_inventory_pass51.csv'
    language_audit = DATA / 'texas_language_classification_audit_pass51.csv'
    allocation_audit_path = DATA / 'texas_allocation_cleanup_audit_pass51.csv'
    write_csv(track_path, tracks)
    write_csv(allocation_path, allocations)
    write_csv(campus_path, campus_view(tracks))
    audit_fields = ('language_track_id', 'registry_record_id', 'campus_id', 'district', 'campus', 'TAPR_program_group', 'pass51_previous_language_pair', 'language_pair', 'pass51_previous_verification_scope', 'pair_verification_scope', 'historical_2023_24_pair_status', 'evidence_period', 'audit_source_ids', 'pass51_change_note')
    write_csv(language_audit, [{k: row[k] for k in audit_fields} for row in tracks if row['pass51_reviewed']=='YES'])
    write_csv(allocation_audit_path, allocation_changes)
    summary = dict(audit_date='2026-11-04', pass_id='pass51',
        track_records=len(tracks), parent_reporting_groups=len({r['registry_record_id'] for r in tracks}),
        campuses=len({r['campus_id'] for r in tracks}),
        language_pair_counts=dict(Counter(r['language_pair'] for r in tracks)),
        verification_scope_counts=dict(Counter(r['pair_verification_scope'] for r in tracks)),
        language_records_reviewed=len(decisions),
        unknown_pair_records_resolved=sum(r['pass51_previous_language_pair']=='UNVERIFIED' and r['language_pair']!='UNVERIFIED' for r in tracks),
        original_allocation_records_preserved=len(prior_allocations),
        original_allocation_records_reviewed=sum(r['pass51_observation_origin']=='PRESERVED_PASS50' and r['pass51_review_status']!='NOT_REVIEWED' for r in allocations),
        new_current_policy_observations=len(allocations)-len(prior_allocations),
        previously_uncited_allocation_rows_recovered=sum(not r['pass51_previous_source_url'] and bool(r['source_url']) and r['pass51_observation_origin']=='PRESERVED_PASS50' for r in allocations),
        reviewed_k_support_counts=dict(Counter(r['pass51_k_support'] for r in allocations if r['pass51_review_status']!='NOT_REVIEWED')),
        original_coverage=coverage(prior_allocations), current_coverage=coverage(allocations),
        newly_archived_sources=sum(bool(r.get('archive_path')) for r in sources.values()),
        verified_tested_cohort_exposures=0, verified_language_specific_tapr_outcomes=0,
        coverage_caution='Citation/link counts are comparable research-policy coverage measures across mixed source periods, not verified K schedules or a 2025-26 operating census. Rejected old Spring rows and pre-K proxies remain visible; consult review status before analysis.')
    summary_path = DATA / 'cleanup_summary_pass51.json'
    write_json(summary_path, summary)
    write_json(DATA / 'current_inventory.json', dict(version='pass51',
        campus_language_inventory=str(campus_path.relative_to(ROOT)), language_tracks=str(track_path.relative_to(ROOT)),
        k_allocation_evidence=str(allocation_path.relative_to(ROOT)), audit=str(language_audit.relative_to(ROOT)),
        allocation_audit=str(allocation_audit_path.relative_to(ROOT)), source_register=str((INPUT / 'source_register.csv').relative_to(ROOT)),
        assessment_year='2023-24', evidence_dates='Source-specific; new current policy observations are not backdated to reporting year',
        status='PROVISIONAL_RESEARCH_NOT_VERIFIED_CENSUS'))
    outputs = [track_path, allocation_path, campus_path, language_audit, allocation_audit_path, summary_path, DATA / 'current_inventory.json']
    input_paths = [DATA / 'texas_language_program_tracks_pass50.csv', DATA / 'texas_k_allocation_evidence_pass50.csv',
                   ROOT / 'scripts/validate_texas_cleanup_pass51.py', *sorted(INPUT.glob('*')), *sorted((ROOT / 'data/raw/tx/pass51').glob('*'))]
    write_json(DATA / 'manifest_pass51.json', dict(audit_date='2026-11-04',
        files={str(p.relative_to(ROOT)): sha(p) for p in outputs},
        inputs={str(p.relative_to(ROOT)): sha(p) for p in input_paths},
        build_script={str(Path(__file__).resolve().relative_to(ROOT)): sha(Path(__file__).resolve())}))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
