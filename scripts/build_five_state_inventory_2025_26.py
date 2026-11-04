#!/usr/bin/env python3
"""Export the additive 2025–26 review, retaining the basis for confirmation."""
from __future__ import annotations

import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/registry/five_state_2025_26'
DOCS = ROOT / 'docs/five_state_2025_26'
STATES = {'WY': 'wyoming', 'MT': 'montana', 'ID': 'idaho', 'NV': 'nevada', 'CA': 'california'}
FIELDS = '''program_id school_research_id state district_name district_id school_name school_id
school_id_namespace program_name program_name_is_working_label partner_language instruction_languages
kindergarten_allocation kindergarten_partner_language_pct kindergarten_english_pct
kindergarten_language_shares_json school_structure program_type grade_span reference_school_year
operating_status_2025_26 confirmation_basis inclusion_status instructional_scope public_funding_status
source_url source_title source_year evidence_level allocation_evidence_type allocation_source_url
structure_source_url operation_source_url operating_evidence_school_year verification_status
published_model_label allocation_conflict_notes allocation_change_notes allocation_applicability_2025_26
later_documented_kindergarten_allocation later_allocation_evidence_year kindergarten_share_ranges_json
previous_kindergarten_allocation previous_inventory_status_2026_27 continuity_review_ids
change_findings source_row_ids identifier_match_method notes previous_inventory_notes'''.split()


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def scalar(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value


def documented(row):
    return row['inclusion_status'].startswith('documented_')


def complete(row):
    return (bool(row['school_name'] and row['district_name'])
            and len(row['instruction_languages'].split(' | ')) >= 2
            and 'unconfirmed' not in row['instruction_languages']
            and row['kindergarten_allocation'] != 'unknown' and row['school_structure'] != 'unknown')


def build():
    raw = json.loads((BASE/'curated_claims.json').read_text())
    sources = json.loads((BASE/'source_index.json').read_text())
    reviews = json.loads((BASE/'continuity_reviews.json').read_text())
    events = json.loads((BASE/'change_events.json').read_text())
    by_key = {s['source_key']: s for s in sources}
    records, ledger, shares, review_rows, result_rows = [], [], [], [], []
    for original in raw:
        row = {f: scalar(original.get(f, '')) for f in FIELDS}
        primary = by_key[original['source_key']]
        row.update(source_url=primary['source_url'], source_title=primary['source_title'])
        school_key = '|'.join([row['state'], row['district_name'], row['school_id'] or row['school_name']])
        row['school_research_id'] = row['state']+'-S-'+hashlib.sha256(school_key.encode()).hexdigest()[:12]
        row['program_name_is_working_label'] = 'no' if original['source_key']=='ca_lausd' else 'yes'
        row['continuity_review_ids'] = ' | '.join(original['continuity_review_ids'])
        row['change_findings'] = ' | '.join(original['change_findings'])
        schedule = original.get('instruction_language_shares', {})
        if not schedule:
            schedule = {lang: pct for lang, pct in [(row['partner_language'], row['kindergarten_partner_language_pct']),
                         ('English', row['kindergarten_english_pct'])] if pct != ''}
        row['kindergarten_language_shares_json'] = json.dumps(schedule, ensure_ascii=False, sort_keys=True)
        for lang, pct in schedule.items():
            shares.append(dict(program_id=row['program_id'], grade='K', instruction_language=lang, instruction_share_pct=pct))
        for field, output in [('kindergarten_allocation','allocation_source_url'), ('school_structure','structure_source_url'),
                              ('operating_status_2025_26','operation_source_url')]:
            claims = [c for c in original['claims'] if c['field_supported']==field]
            row[output] = ' | '.join(dict.fromkeys(by_key[c['source_key']]['source_url'] for c in claims))
            if field=='operating_status_2025_26':
                row['operating_evidence_school_year'] = ' | '.join(dict.fromkeys(c['applicable_school_year'] for c in claims if c['applicable_school_year']))
        for n, c in enumerate(original['claims'], 1):
            source = by_key[c['source_key']]
            ledger.append(dict(evidence_id=row['program_id']+'-25-E-'+str(n), program_id=row['program_id'],
                school_research_id=row['school_research_id'], state=row['state'], school_name=row['school_name'],
                field_supported=c['field_supported'], recorded_value=scalar(c['value']), source_id=source['source_id'],
                source_url=source['source_url'], source_title=source['source_title'], source_date=c['source_date'],
                applicable_school_year=c['applicable_school_year'], evidence_excerpt_or_paraphrase=c['evidence_excerpt'],
                evidence_classification=c['evidence_classification'], conflicting_or_unresolved=c['conflicting_or_unresolved'],
                accessed_at_utc=source['accessed_at_utc']))
        records.append(row)
    records.sort(key=lambda r: (r['state'],r['district_name'],r['school_name'],r['partner_language'],r['program_name']))
    for state, name in STATES.items():
        write_csv(ROOT/f'data/registry/state_dl_programs_{name}_2025_26.csv', FIELDS, [r for r in records if r['state']==state])
    for review in reviews:
        review_rows.append(dict(review_id=review['review_id'], program_ids=' | '.join(review['program_ids']),
            search_queries=' | '.join(q['query'] for q in review['queries']),
            search_urls=' | '.join(q['search_url'] for q in review['queries']),
            usable_query_count=sum(q['usable'] for q in review['queries']), query_count=len(review['queries']),
            reviewed_source_urls=' | '.join(by_key[k]['source_url'] for k in review['source_keys_read']),
            reviewed_at_utc=review['reviewed_at_utc'], outcome=review['outcome'], finding=review['finding'], limitations=review['limitations']))
        for q in review['queries']:
            for rank, result in enumerate(q['results'], 1):
                result_rows.append(dict(review_id=review['review_id'],query_key=q['key'],query=q['query'],
                    search_url=q['search_url'],result_rank=rank,result_url=result['url'],
                    search_result_snippet=result['snippet'],evidence_use='discovery_and_change_screening_only'))
    for name, rows in [('evidence_ledger.csv',ledger),('sources.csv',sources),('kindergarten_instruction_languages.csv',shares),
                       ('continuity_reviews.csv',review_rows),('change_search_results.csv',result_rows),('change_events.csv',events)]:
        write_csv(BASE/name,list(rows[0]),rows)
    coverage={};language_rows=[]
    for state in STATES:
        selected=[r for r in records if r['state']==state]
        eligible=[r for r in selected if documented(r) and r['operating_status_2025_26'] not in ('planned_future','confirmed_discontinued')]
        confirmed=[r for r in eligible if r['operating_status_2025_26']=='confirmed_2025_26']
        direct=[r for r in confirmed if r['confirmation_basis']!='continuity_no_end_indication']
        coverage[state]=dict(distinct_program_records_including_candidates=len(selected),
            distinct_inventory_schools=len({r['school_research_id'] for r in selected}),
            documented_content_records_excluding_future_discontinued=len(eligible),
            confirmed_2025_26=len(confirmed),confirmed_with_year_specific_evidence=len(direct),
            confirmed_by_continuity_rule=len(confirmed)-len(direct),
            confirmed_year_listings_including_eligibility_candidates=sum(r['operating_status_2025_26']=='confirmed_2025_26' for r in selected),
            candidate_records=sum(not documented(r) for r in selected),
            candidate_schools_identified=1310 if state=='CA' else len({r['school_research_id'] for r in selected}),
            candidate_school_count_basis='historical_CDE_lower_bound_with_unresolved_overlap' if state=='CA' else 'curated_inventory_schools',
            language_pairings_established=sum(len(r['instruction_languages'].split(' | '))>=2 and 'unconfirmed' not in r['instruction_languages'] for r in eligible),
            kindergarten_allocations_established=sum(r['kindergarten_allocation']!='unknown' for r in eligible),
            structures_established=sum(r['school_structure']!='unknown' for r in eligible),
            all_five_fields=sum(complete(r) for r in eligible),
            confirmed_with_all_five_fields=sum(complete(r) for r in confirmed),
            records_requiring_further_research=sum(not(documented(r) and complete(r) and r['operating_status_2025_26']=='confirmed_2025_26') for r in selected),
            operating_status_counts=dict(collections.Counter(r['operating_status_2025_26'] for r in selected)),
            kindergarten_models={m:sum(r['kindergarten_allocation']==m for r in eligible) for m in ['90/10','80/20','50/50','other','unknown']},
            statewide_completeness='not_established')
        for lang in sorted({r['partner_language'] for r in selected}):
            language_rows.append(dict(state=state,partner_language=lang,all_records=sum(r['partner_language']==lang for r in selected),
                                     confirmed_2025_26=sum(r['partner_language']==lang for r in confirmed)))
    (BASE/'coverage_summary.json').write_text(json.dumps(coverage,indent=2,ensure_ascii=False)+'\n')
    write_csv(BASE/'language_pairing_counts.csv',list(language_rows[0]),language_rows)
    DOCS.mkdir(parents=True,exist_ok=True)
    lines=['# 2025–26 confirmation and change review','','Research recheck: November 4, 2026. Reference school year: **2025–26**.','',
        'Confirmed includes the user-requested continuity rule. Direct year evidence and continuity assessments remain separate. '
        'Content scope and public-funding eligibility are separate from operation; candidates are excluded from qualifying confirmed totals.','',
        '| State | Records incl. candidates | Confirmed qualifying programs | Year-specific evidence | Continuity rule | K allocation known | Structure known | All five fields |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for s,v in coverage.items():
        lines.append('| '+' | '.join([STATES[s].title(),*[str(v[k]) for k in ['distinct_program_records_including_candidates','confirmed_2025_26',
            'confirmed_with_year_specific_evidence','confirmed_by_continuity_rule','kindergarten_allocations_established','structures_established','all_five_fields']]])+' |')
    lines += ['', 'Field completeness uses supported classifications with the stated temporal limits, including older policies. '
        'Confirmed operation does not certify that an older model or structure was independently observed in 2025–26. '
        'Later-only schedules are not silently assigned to 2025–26. No statewide coverage percentage is established.','',
        '## Screening and remaining gaps','','| State | Candidate schools identified | Languages established, qualifying records | Records requiring further research |',
        '|---|---:|---:|---:|']
    for s,v in coverage.items():
        candidates=('≥' if s=='CA' else '')+str(v['candidate_schools_identified'])
        lines.append('| '+' | '.join([STATES[s].title(),candidates,str(v['language_pairings_established']),str(v['records_requiring_further_research'])])+' |')
    lines += ['', 'California’s school lead count is the 1,310 unique CDS IDs in the 2024–25 CDE screening extract, '
        'including 25 transitional-only listings. It is historical, overlaps the curated records, and must not be added to them. '
        'Other states count provisional distinct schools in this inventory. Further-research counts include every record '
        'without confirmed qualifying operation and all five fields, including retained closed/future records.','',
        '## Kindergarten models','','| State | 90/10 | 80/20 | 50/50 | Other | Unknown |','|---|---:|---:|---:|---:|---:|']
    for s,v in coverage.items():lines.append('| '+' | '.join([STATES[s].title(),*[str(v['kindergarten_models'][m]) for m in ['90/10','80/20','50/50','other','unknown']]])+' |')
    lines += ['', '## Instructional languages','','| State | Partner language / candidate language | All records | Confirmed qualifying programs |','|---|---|---:|---:|']
    for r in language_rows:lines.append('| '+' | '.join([r['state'],r['partner_language'],str(r['all_records']),str(r['confirmed_2025_26'])])+' |')
    lines += ['', 'See [README](README.md), [Montana instructional review](MONTANA_REVIEW.md), and [change findings](CHANGE_FINDINGS.md) for interpretation and limits.','']
    (DOCS/'COVERAGE_REPORT.md').write_text('\n'.join(lines))
    return dict(program_records=len(records),evidence_claims=len(ledger),registered_sources=len(sources),
                continuity_reviews=len(reviews),confirmed=sum(v['confirmed_2025_26'] for v in coverage.values()))


if __name__=='__main__':
    print(json.dumps(build(),indent=2))
