"""Verify the new research artifacts against archived sources and inventory snapshots."""
import csv
from decimal import Decimal
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
LA = ROOT / 'data/registry/literature/lausd_twdl_2026_11_07'
PB = ROOT / 'data/registry/palm_beach_admissions_2026_11_07'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def csv_rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_files(receipt):
    for name, expected in receipt['files'].items():
        assert digest(ROOT / name) == expected, name


def cell_text(cell):
    return ' '.join(''.join(t.text or '' for t in p.iter(W + 't'))
                    for p in cell.findall(W + 'p')).strip()


def check_la():
    receipt = json.loads((LA / 'source_manifest.json').read_text())
    check_files(receipt)
    source = ROOT / receipt['source_artifact']['path']
    assert digest(source) == receipt['source_artifact']['sha256']
    with ZipFile(source) as archive:
        document = ET.fromstring(archive.read('word/document.xml'))
    tables = document.find(W + 'body').findall(W + 'tbl')
    observations = csv_rows(LA / 'lausd_supplement_tables.csv')
    assert len(tables) == 4 and len(observations) == 396
    index = 0
    for number, table in enumerate(tables, 1):
        source_rows = table.findall(W + 'tr')
        groups = [cell_text(c) for c in source_rows[0].findall(W + 'tc')][1:]
        years = [cell_text(c) for c in source_rows[1].findall(W + 'tc')][1:]
        row_group = ''
        for ri, row in enumerate(source_rows[2:]):
            cells = row.findall(W + 'tc')
            row_group = cell_text(cells[0]) or row_group
            for ci, cell in enumerate(cells[1:]):
                item = observations[index]
                index += 1
                raw = cell_text(cell)
                shading = cell.find(W + 'tcPr/' + W + 'shd')
                shaded = shading is not None and shading.get(W + 'fill', '').upper() == 'BFBFBF'
                suppressed = raw.startswith('<') or (not raw and shaded)
                expected_status = 'suppressed' if suppressed else 'reported' if raw else 'not_reported'
                count = number == 1 or (number in (3, 4) and ri % 2 == 0)
                assert item['table_id'] == f'A-{number}'
                assert item['row_group'] == row_group and item['column_group'] == groups[ci // 3]
                assert item['source_school_year_raw'] == years[ci]
                assert item['value_raw'] == raw and item['value_status'] == expected_status
                assert item['statistic'] == ('count' if count else 'percentage')
                assert item['source_sha256'] == receipt['source_artifact']['sha256']
                assert item['aggregation_level'] == 'study_cohort_aggregate_no_school_identifiers'
                if expected_status == 'reported':
                    assert Decimal(item['value']) == Decimal(raw.replace(',', '').replace('%', '').strip())
                else:
                    assert item['value'] == ''
    snapshot = csv_rows(LA / 'lausd_elementary_inventory_snapshot.csv')
    assert len(snapshot) == receipt['inventory_snapshot']['program_records']
    assert len({r['school_id'] for r in snapshot}) == receipt['inventory_snapshot']['school_identities']
    schools = {}
    for row in snapshot:
        schools.setdefault(row['school_id'], set()).update(
            x for x in row['reported_instruction_languages'].split(' | ') if x and x != 'English')
    candidates = csv_rows(LA / 'lausd_language_combination_candidates.csv')
    assert len(candidates) == 8
    for row in candidates:
        assert set(row['partner_language_combination'].split(' + ')) == schools[row['school_id']]
        assert row['match_status'] == 'candidate_language_combination_only_not_a_verified_study_school'
        assert row['classification_changed'] == 'false'
    assert receipt['updates_to_canonical_school_classifications'] == 0


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, value):
        self.parts.append(value)


def html_text(value):
    parser = Text()
    parser.feed(value)
    return ' '.join(''.join(parser.parts).split())


def check_pb():
    check_files(json.loads((PB / 'manifest.json').read_text()))
    sources = json.loads((PB / 'sources.json').read_text())
    for source in sources:
        assert digest(ROOT / source['path']) == source['sha256'], source['key']
    source = next(s for s in sources if s['key'] == 'district-dl')
    html = (ROOT / source['path']).read_text()
    html = html[html.index('id="fsEl_15722"'):]
    source_rows = [html_text(li) for li in re.findall(r'<li\b[^>]*>(.*?)</li>', html, re.S)
                   if re.search(r'Elementary|Middle|High', html_text(li))]
    rows = csv_rows(PB / 'program_admissions.csv')
    snapshot = {r['site_id']: r for r in csv_rows(PB / 'inventory_snapshot.csv')}
    assert len(rows) == len(source_rows) == 40
    assert len({r['school_id'] for r in rows}) == 40
    for row in rows:
        text = row['source_roster_text']
        assert text in source_rows
        assert snapshot[row['site_id']]['school_id'] == row['school_id']
        marker = '+' if text.endswith('+') else '*' if text.endswith('*') else ''
        assert row['source_marker'] == marker
        assert row['admissions_label'] == {'+': 'full_choice_program', '*': 'in_house_program', '': 'unmarked_on_source'}[marker]
        assert row['delivery_structure_update'] == ''
        assert row['review_status'] == 'campus_participation_evidence_still_needed'
    elementary = [r for r in rows if r['school_level'] == 'elementary']
    assert len(elementary) == 27
    assert sum(r['source_marker'] == '*' for r in elementary) == 11
    assert sum(r['source_marker'] == '+' for r in elementary) == 6
    assert sum(r['source_marker'] == '' for r in elementary) == 10
    assert json.loads((PB / 'summary.json').read_text())['canonical_delivery_updates'] == 0


if __name__ == '__main__':
    check_la()
    check_pb()
    print('PASS: source hashes; all 396 supplement cells and suppression; eight candidate identities; all 40 admissions markers; no unsupported delivery assignments.')
