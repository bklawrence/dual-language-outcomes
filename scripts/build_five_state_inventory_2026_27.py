#!/usr/bin/env python3
"""Export the curated five-state claims; no network or inferred classifications.

Run from the repository root. Existing state research is not overwritten.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/registry/five_state_2026_27'
DOCS = ROOT / 'docs/five_state_2026_27'
STATES = {'WY': 'wyoming', 'MT': 'montana', 'ID': 'idaho', 'NV': 'nevada', 'CA': 'california'}
FIELDS = '''program_id school_research_id state district_name district_id school_name school_id
school_id_namespace program_name program_name_is_working_label partner_language instruction_languages
kindergarten_allocation kindergarten_partner_language_pct kindergarten_english_pct
kindergarten_language_shares_json school_structure program_type grade_span reference_school_year
operating_status_2026_27 inclusion_status source_url source_title source_year evidence_level
allocation_evidence_type allocation_source_url structure_source_url operation_source_url
operating_evidence_school_year verification_status published_model_label allocation_conflict_notes
source_row_ids identifier_match_method notes'''.split()


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def is_documented(row):
    return row['inclusion_status'].startswith('documented_')


def has_pair(row):
    return len(row['instruction_languages'].split(' | ')) >= 2 and 'unconfirmed' not in row['instruction_languages']


def complete(row):
    return (bool(row['school_name'] and row['district_name']) and has_pair(row)
            and row['kindergarten_allocation'] != 'unknown'
            and row['school_structure'] != 'unknown')


def build():
    inputs = json.loads((BASE / 'curated_claims.json').read_text())
    sources = json.loads((BASE / 'source_index.json').read_text())
    source_by_key = {s['source_key']: s for s in sources}
    ledger = []
    records = []
    shares = []
    for original in inputs:
        row = {k: original.get(k, '') for k in FIELDS}
        primary = source_by_key[original['source_key']]
        row.update(source_url=primary['source_url'], source_title=primary['source_title'])
        school_key = '|'.join([row['state'], row['district_name'], row['school_id'] or row['school_name']])
        row['school_research_id'] = row['state'] + '-S-' + hashlib.sha256(school_key.encode()).hexdigest()[:12]
        row['program_name_is_working_label'] = 'no' if original['source_key'] == 'ca_lausd' else 'yes'
        row['school_id_namespace'] = original.get('school_id_namespace', '')
        schedule = original.get('instruction_language_shares', {})
        if not schedule:
            schedule = {language: percent for language, percent in
                        [(row['partner_language'], row['kindergarten_partner_language_pct']),
                         ('English', row['kindergarten_english_pct'])] if percent != ''}
        for language, percent in schedule.items():
            shares.append({'program_id': row['program_id'], 'grade': 'K',
                           'instruction_language': language, 'instruction_share_pct': percent,
                           'allocation_evidence_type': row['allocation_evidence_type']})
        row['kindergarten_language_shares_json'] = json.dumps(schedule, ensure_ascii=False, sort_keys=True)
        claims = original['claims']
        for field, output in [('kindergarten_allocation', 'allocation_source_url'),
                              ('school_structure', 'structure_source_url'),
                              ('operating_status_2026_27', 'operation_source_url')]:
            supporting = [c for c in claims if c['field_supported'] == field]
            row[output] = ' | '.join(dict.fromkeys(source_by_key[c['source_key']]['source_url'] for c in supporting))
            if field == 'operating_status_2026_27':
                row['operating_evidence_school_year'] = ' | '.join(dict.fromkeys(
                    c['applicable_school_year'] for c in supporting if c['applicable_school_year']))
        for index, c in enumerate(claims, 1):
            source = source_by_key[c['source_key']]
            ledger.append({'evidence_id': row['program_id'] + '-E-' + str(index),
                           'program_id': row['program_id'], 'school_research_id': row['school_research_id'],
                           'state': row['state'], 'school_name': row['school_name'],
                           'field_supported': c['field_supported'],
                           'recorded_value': c['value'], 'source_id': source['source_id'],
                           'source_url': source['source_url'], 'source_title': source['source_title'],
                           'source_date': c['source_date'],
                           'applicable_school_year': c['applicable_school_year'],
                           'evidence_excerpt_or_paraphrase': c['evidence_excerpt'],
                           'evidence_classification': c['evidence_classification'],
                           'conflicting_or_unresolved': c['conflicting_or_unresolved'],
                           'accessed_at_utc': source['accessed_at_utc']})
        records.append(row)
    records.sort(key=lambda r: (r['state'], r['district_name'], r['school_name'], r['partner_language'], r['program_name']))
    for state, name in STATES.items():
        write_csv(ROOT / f'data/registry/state_dl_programs_{name}_2026_27.csv', FIELDS,
                  [r for r in records if r['state'] == state])
    write_csv(BASE / 'evidence_ledger.csv', list(ledger[0]), ledger)
    write_csv(BASE / 'kindergarten_instruction_languages.csv', list(shares[0]), shares)
    write_csv(BASE / 'sources.csv', list(sources[0]), sources)

    coverage = {}
    language_counts = []
    for state in STATES:
        state_rows = [r for r in records if r['state'] == state]
        eligible = [r for r in state_rows if is_documented(r)
                    and r['operating_status_2026_27'] not in ('planned_future', 'confirmed_discontinued')]
        confirmed = [r for r in eligible if r['operating_status_2026_27'] == 'confirmed_2026_27']
        schools = {r['school_research_id'] for r in state_rows}
        coverage[state] = {
            'distinct_inventory_schools': len(schools),
            'candidate_schools_identified': 1310 if state == 'CA' else len(schools),
            'candidate_count_basis': 'at_least_1310_historical_CDE_schools_unresolved_alias_overlap' if state == 'CA'
                                     else 'distinct_schools_in_curated_inventory',
            'distinct_program_records_including_candidates': len(state_rows),
            'documented_content_records_potentially_current': len(eligible),
            'candidate_or_unconfirmed_content_records': sum(not is_documented(r) for r in state_rows),
            'programs_confirmed_operating_2026_27': len(confirmed),
            'language_pairings_established': sum(has_pair(r) for r in eligible),
            'kindergarten_allocations_established_any_source_year': sum(r['kindergarten_allocation'] != 'unknown' for r in eligible),
            'school_structures_established_any_source_year': sum(r['school_structure'] != 'unknown' for r in eligible),
            'programs_with_all_five_essential_fields_any_source_year': sum(complete(r) for r in eligible),
            'programs_with_all_five_fields_and_confirmed_2026_27': sum(complete(r) for r in confirmed),
            'programs_requiring_further_research': sum(not (is_documented(r) and complete(r)
                and r['operating_status_2026_27'] == 'confirmed_2026_27') for r in state_rows),
            'operating_status_counts_all_records': dict(collections.Counter(r['operating_status_2026_27'] for r in state_rows)),
            'kindergarten_model_distribution_any_source_year': {k: sum(r['kindergarten_allocation'] == k for r in eligible)
                for k in ('90/10', '80/20', '50/50', 'other', 'unknown')},
            'kindergarten_model_distribution_confirmed_2026_27': {k: sum(r['kindergarten_allocation'] == k for r in confirmed)
                for k in ('90/10', '80/20', '50/50', 'other', 'unknown')},
            'statewide_completeness': 'not_established',
        }
        for language in sorted({r['partner_language'] for r in state_rows}):
            language_counts.append({'state': state, 'partner_language': language,
                'all_inventory_records': sum(r['partner_language'] == language for r in state_rows),
                'documented_potentially_current_records': sum(r['partner_language'] == language for r in eligible),
                'confirmed_2026_27_records': sum(r['partner_language'] == language for r in confirmed)})
    (BASE / 'coverage_summary.json').write_text(json.dumps(coverage, indent=2, ensure_ascii=False) + '\n')
    write_csv(BASE / 'language_pairing_counts.csv', list(language_counts[0]), language_counts)
    write_coverage_report(coverage, language_counts)
    return {'program_records': len(records), 'evidence_claims': len(ledger), 'source_documents': len(sources),
            'state_records': {s: len([r for r in records if r['state'] == s]) for s in STATES}}


def write_coverage_report(coverage, language_counts):
    """Keep the reviewable report and machine-readable denominators together."""
    names = {s: name.title() for s, name in STATES.items()}
    lines = [
        '# Five-state coverage report', '',
        'Reference year: **2026–27**. Research date: **November 3, 2026** '
        '(America/Chicago; source-access timestamps are November 4 UTC).', '',
        '**This is a partial, source-documented inventory, not an established statewide census.** '
        'A source being accessible today does not establish operation in the target school year.', '',
        '## Observed counts', '',
        'Counts of established fields below use documented content-instruction records, excluding '
        'unresolved inclusion candidates, discontinued programs, and future openings. Historical '
        'and undated evidence is included in the field-completeness columns and is explicitly '
        'separate from confirmed 2026–27 operation. Counts are programs, except the schools column.', '',
        '| Measure | Wyoming | Montana | Idaho | Nevada | California |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    metrics = [
        ('Candidate schools identified¹', 'candidate_schools_identified'),
        ('Distinct program records, including candidates', 'distinct_program_records_including_candidates'),
        ('Documented content programs, excluding future/discontinued²', 'documented_content_records_potentially_current'),
        ('Programs confirmed operating in 2026–27', 'programs_confirmed_operating_2026_27'),
        ('Programs with instructional languages established', 'language_pairings_established'),
        ('Kindergarten allocations established, any source year', 'kindergarten_allocations_established_any_source_year'),
        ('Whole-school/strand established, any source year', 'school_structures_established_any_source_year'),
        ('All five essential fields, any source year', 'programs_with_all_five_essential_fields_any_source_year'),
        ('All five fields AND confirmed 2026–27', 'programs_with_all_five_fields_and_confirmed_2026_27'),
        ('Records requiring further research³', 'programs_requiring_further_research'),
    ]
    for label, key in metrics:
        values = [str(coverage[s][key]) for s in STATES]
        if key == 'candidate_schools_identified':
            values[-1] = '≥' + values[-1]
        lines.append('| ' + ' | '.join([label, *values]) + ' |')
    lines += ['',
        '¹ California has 1,310 unique school CDS IDs in the **2024–25** CDE screening roster '
        '(302 districts), including 25 transitional-only listings. These are leads, not 1,310 '
        'verified current immersion programs. The curated California inventory has '
        f"{coverage['CA']['distinct_inventory_schools']} provisional distinct schools; it overlaps "
        'the roster and must not be added to it. Other states count distinct schools in the curated '
        'inventory only. These are observed lower bounds, with unresolved aliases and omitted districts.', '',
        '² “Potentially current” is a screening denominator, not a current-operation assertion; '
        'it includes historical-status-unknown records. No statewide coverage percentage is defensible.', '',
        '³ Conservative count: every record except a documented program with all five fields and '
        'confirmed 2026–27 operation. It therefore includes retained discontinued/future records '
        'that need no immediate operating-program follow-up.', '',
        '## Kindergarten starting models', '',
        'Each cell is **documented programs, any source year / confirmed 2026–27 subset**. '
        'Secondary continuations without a documented kindergarten starting model remain unknown. '
        'The denominator matches the documented-content row above, not all inventory records.', '',
        '| State | 90/10 | 80/20 | 50/50 | Other | Unknown |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for s, stats in coverage.items():
        values = [str(stats['kindergarten_model_distribution_any_source_year'][m]) + ' / ' +
                  str(stats['kindergarten_model_distribution_confirmed_2026_27'][m])
                  for m in ('90/10', '80/20', '50/50', 'other', 'unknown')]
        lines.append('| ' + ' | '.join([names[s], *values]) + ' |')
    lines += ['', '“Other” is the explicitly published LAUSD 70/30 model (12 records). '
              'Actual percentages are retained. Yu Ming’s conflicting kindergarten schedules '
              'are not assigned a selected model; see the research notes.', '',
              '## Language visibility', '',
              'Counts preserve source language names, including unspecified Armenian versus '
              'Eastern/Western Armenian. The instructional-language field identifies English '
              'where established; an Indigenous-language candidate does not establish that English '
              'also carries academic content. Candidate-only rows below are not verified pairings.', '',
              '| State | Partner language or candidate language | All records | Documented content² | Confirmed 2026–27 |',
              '|---|---|---:|---:|---:|']
    for r in language_counts:
        lines.append('| ' + ' | '.join([names[r['state']], r['partner_language'],
                     str(r['all_inventory_records']), str(r['documented_potentially_current_records']),
                     str(r['confirmed_2026_27_records'])]) + ' |')
    lines += ['', '## Operating-status reconciliation', '',
              'This table includes **all** records, including unresolved content-instruction '
              'candidates. Consequently a confirmed-year listing here can exceed the qualifying '
              'confirmed-program count above (Fresno’s Sequoia Middle School requires content-scope '
              'verification; Hillcrest in Idaho requires current language-track confirmation).', '',
              '| State | Confirmed 2026–27 | Probable, year unconfirmed | Historical, status unknown | Discontinued | Future |',
              '|---|---:|---:|---:|---:|---:|']
    for s, stats in coverage.items():
        counts = stats['operating_status_counts_all_records']
        values = [str(counts.get(k, 0)) for k in ('confirmed_2026_27', 'probable_current_unconfirmed',
                   'historical_status_unknown', 'confirmed_discontinued', 'planned_future')]
        lines.append('| ' + ' | '.join([names[s], *values]) + ' |')
    lines += ['', 'See [research notes](RESEARCH_NOTES.md) for state-specific source quality and '
              'verification priorities, and [README](README.md) for files, schema, and validation.', '']
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / 'COVERAGE_REPORT.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
