
#!/usr/bin/env python3
"""Collect 2023-24 public TEA campus TAPR DLI assessment results.

Uses browser automation because TEA supplies a data-selection form, not a
verified static CSV URL. Default is 2023-24 (TEA report-year 2024).
DLI outcomes are TEST-TAKER subgroup measures, NOT whole-program enrollment.

Outputs: raw download, compact DLI variables, campus evidence, audit, browser
capture on failure. Diagnostic files are saved even on site changes.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
import re
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

URL_2024 = (
    'https://rptsvr1.tea.texas.gov/perfreport/tapr/2024/'
    'Advance%20Download/download-data-adv.html'
)
GROUPS = {'DQ': 'two_way_dli', 'DT': 'one_way_dli'}
METRICS = {'N': 'numerator', 'D': 'denominator', 'R': 'rate'}


def write_csv(path: Path, rows, cols):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as file:
        w = csv.DictWriter(file, fieldnames=cols, extrasaction='raise')
        w.writeheader()
        w.writerows(rows)


def safe_text(path: Path, data: str):
    path.write_text(data, encoding='utf-8', errors='replace')


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def source_controls(page):
    """Control inventory for debugging a changed TEA form."""
    return page.evaluate('''() => Array.from(document.querySelectorAll(
        'input,select,button'
    )).map((x, i) => ({
        i, tag:x.tagName, type:x.type, name:x.name, id:x.id,
        value:x.value, checked: x.checked || false,
        nearby:(x.closest('label')?.innerText || x.parentElement?.innerText || '')
            .replace(/\\s+/g,' ').slice(0,150)
    }))''')


def select_legacy_form(page):
    """Select Campus and additional student group grade-3--8 category.

    The choices are made from the page DOM. We do not submit
    fabricated POST fields or hard-code an unverified endpoint.
    """
    return page.evaluate('''() => {
        const radios = Array.from(document.querySelectorAll(
            'input[type="radio"]'
        ));
        if (radios.length < 7) {
            throw new Error('Expected legacy radio form; got ' + radios.length);
        }
        const body = document.body.innerText || '';
        if (!body.includes('Campus') ||
            !body.includes('Additional Student Groups')) {
            throw new Error('Unexpected page content; legacy form not detected');
        }

        // Legacy form orders reporting levels:
        // Campus, District, Region, State.
        let campus = radios[0];
        let near = (campus.closest('label')?.innerText ||
                    campus.parentElement?.innerText || '').trim();
        if (near.length > 250) near = near.slice(0,250);
        campus.click();

        // Find the heading's actual text node, then its first radio.
        const walk = document.createTreeWalker(document.body,
            NodeFilter.SHOW_TEXT);
        let heading = null, node;
        while ((node = walk.nextNode())) {
            if (/STAAR Assessment Data:\\s*Additional Student Groups/i
                    .test(node.textContent || '')) {
                heading = node;
                break;
            }
        }
        if (!heading) {
            throw new Error('Additional-groups heading missing');
        }

        const following = radios.filter(r =>
            Boolean(heading.compareDocumentPosition(r) &
                Node.DOCUMENT_POSITION_FOLLOWING));

        if (!following.length) {
            throw new Error('No additional-group category');
        }

        const category = following[0];
        category.click();

        return {
            campus: {
                name: campus.name,
                value: campus.value,
                near
            },
            category: {
                name: category.name,
                value: category.value,
                near: (category.parentElement?.innerText || '').slice(0,250)
            }
        };
    }''')


def click_download(page):
    """Press an existing site's submit/download control."""
    return page.evaluate('''() => {
        const all = Array.from(document.querySelectorAll(
            'input[type="submit"],input[type="image"],input[type="button"],button'
        )).filter(x => !x.disabled);

        if (!all.length) {
            throw new Error('No form submission control found');
        }

        let button = all.find(x =>
            /download|get data|submit|continue|next|go/i.test(
                (x.value || '') + ' ' + (x.textContent || '')
            )
        );

        if (!button) button = all[all.length - 1];

        const detail = {
            tag: button.tagName,
            type: button.type,
            name: button.name,
            value: button.value,
            text: (button.innerText || '').slice(0,100)
        };

        button.click();
        return detail;
    }''')


def fetch_public_csv(out: Path, timeout_seconds: int = 240) -> Path:
    from playwright.sync_api import sync_playwright

    raw_path = out / 'tx_tapr_2023_24_campus_raw.csv'
    debug = {
        'page': URL_2024,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'events': []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox']
        )

        context = browser.new_context(
            accept_downloads=True,
            viewport={'width': 1440, 'height': 980}
        )

        downloads = []

        def watch(page):
            page.on('download', lambda d: downloads.append(d))

        context.on('page', watch)
        page = context.new_page()

        try:
            page.goto(
                URL_2024,
                wait_until='domcontentloaded',
                timeout=90000
            )
            page.wait_for_timeout(1500)

            debug['page_title'] = page.title()
            debug['before_controls'] = source_controls(page)

            safe_text(
                out / 'tx_tapr_form_before.html',
                page.content()
            )
            page.screenshot(
                path=str(out / 'tx_tapr_form_before.png'),
                full_page=True
            )

            debug['selection'] = select_legacy_form(page)
            debug['after_selection_controls'] = source_controls(page)
            debug['submit'] = click_download(page)

            deadline = time.monotonic() + timeout_seconds

            while not downloads and time.monotonic() < deadline:
                page.wait_for_timeout(1000)

            if not downloads:
                debug['after_submit_url'] = page.url
                debug['after_submit_controls'] = source_controls(page)

                safe_text(
                    out / 'tx_tapr_form_after.html',
                    page.content()
                )
                page.screenshot(
                    path=str(out / 'tx_tapr_form_after.png'),
                    full_page=True
                )

                raise RuntimeError(
                    'No CSV download emitted by TEA form; '
                    'see captured HTML/controls'
                )

            download = downloads[0]
            debug['suggested_filename'] = download.suggested_filename

            download.save_as(str(raw_path))

            if raw_path.stat().st_size < 1000:
                raise RuntimeError(
                    'TEA supplied an unexpectedly small file'
                )

            with raw_path.open('rb') as f:
                start = f.read(300).lstrip()

            if start.lower().startswith((b'<!doctype html', b'<html')):
                raise RuntimeError(
                    'TEA returned HTML instead of CSV'
                )

            if start.startswith((b'PK\x03\x04', b'\x1f\x8b')):
                raise RuntimeError(
                    'TEA returned compressed data; inspect raw file'
                )

            debug['download_bytes'] = raw_path.stat().st_size
            return raw_path

        except Exception as ex:
            debug['error'] = f'{type(ex).__name__}: {ex}'
            debug['traceback'] = traceback.format_exc()[-4000:]
            raise

        finally:
            safe_text(
                out / 'tx_tapr_download_debug.json',
                json.dumps(debug, indent=2, default=str) + '\n'
            )
            context.close()
            browser.close()


def usable_number(raw: str) -> bool:
    return bool(re.fullmatch(
        r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)',
        raw.strip().replace(',', '')
    ))


def audit_csv(source: Path, out: Path, roster: Path) -> dict:
    """Extract TEA variables without guessing subject or grade."""
    with roster.open(newline='', encoding='utf-8-sig') as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames or 'texas_campus_id' not in rd.fieldnames:
            raise ValueError(
                'Texas campus directory missing campus IDs'
            )
        roster_ids = {
            r['texas_campus_id']
            for r in rd
        }

    with source.open(
        newline='',
        encoding='utf-8-sig',
        errors='replace'
    ) as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError('TAPR file has no column names')

        fields = reader.fieldnames
        id_field = fields[0]

        selected = [
            (
                col,
                GROUPS[col[1:3].upper()],
                METRICS[col[-1].upper()]
            )
            for col in fields
            if re.fullmatch(
                r'[A-Za-z]D[QT][A-Za-z0-9_]+[NDR]',
                col,
                re.I
            )
            and col[1:3].upper() in GROUPS
        ]

        if not selected:
            safe_text(
                out / 'tx_tapr_header_audit.json',
                json.dumps({
                    'first_column': id_field,
                    'column_count': len(fields),
                    'first_80_columns': fields[:80],
                    'columns_containing_DQ_or_DT': [
                        x for x in fields
                        if 'DQ' in x.upper() or 'DT' in x.upper()
                    ][:100]
                }, indent=2) + '\n'
            )

            raise ValueError(
                'No CDQ/CDT numerator/denominator/rate fields '
                'found; see header audit'
            )

        columns = [
            'texas_campus_id',
            'school_year',
            'student_group',
            'variable_code',
            'statistic',
            'source_raw_value',
            'numeric_value',
            'value_status',
            'present_in_2024_25_roster'
        ]

        per_campus = defaultdict(lambda: {
            'one_way_dli': set(),
            'two_way_dli': set()
        })

        values = Counter()
        count_rows = 0
        invalid_ids = 0

        with gzip.open(
            out / 'tx_tapr_2023_24_dli_variable_values.csv.gz',
            'wt',
            encoding='utf-8',
            newline=''
        ) as z:
            w = csv.DictWriter(z, fieldnames=columns)
            w.writeheader()

            for r in reader:
                count_rows += 1
                cid = (
                    (r.get(id_field) or '')
                    .strip()
                    .lstrip("'\u2019")
                )

                if not re.fullmatch(r'\d{9}', cid):
                    invalid_ids += 1
                    continue

                for code, group, metric in selected:
                    raw = (r.get(code) or '').strip()

                    if not raw:
                        continue

                    state = (
                        'numeric'
                        if usable_number(raw)
                        else 'masked_or_other'
                    )

                    w.writerow({
                        'texas_campus_id': cid,
                        'school_year': '2023-24',
                        'student_group': group,
                        'variable_code': code,
                        'statistic': metric,
                        'source_raw_value': raw,
                        'numeric_value': (
                            raw if state == 'numeric' else ''
                        ),
                        'value_status': state,
                        'present_in_2024_25_roster': (
                            'yes' if cid in roster_ids else 'no'
                        )
                    })

                    values[(group, metric, state)] += 1

                    if (
                        metric == 'denominator'
                        and state == 'numeric'
                        and float(raw) > 0
                    ):
                        per_campus[cid][group].add(code)

        by_campus = []

        for cid, groups in sorted(per_campus.items()):
            by_campus.append({
                'texas_campus_id': cid,
                'school_year': '2023-24',
                'two_way_positive_assessment_denominator_variables':
                    len(groups['two_way_dli']),
                'one_way_positive_assessment_denominator_variables':
                    len(groups['one_way_dli']),
                'campus_in_2024_25_roster': (
                    'yes' if cid in roster_ids else 'no'
                ),
                'classification_caution':
                    'TAPR test-taker subgroup; not DLI enrollment'
            })

        write_csv(
            out / 'tx_tapr_2023_24_dli_campus_evidence.csv',
            by_campus,
            [
                'texas_campus_id',
                'school_year',
                'two_way_positive_assessment_denominator_variables',
                'one_way_positive_assessment_denominator_variables',
                'campus_in_2024_25_roster',
                'classification_caution'
            ]
        )

        write_csv(
            out / 'tx_tapr_2023_24_dli_variable_dictionary.csv',
            [
                {
                    'variable_code': c,
                    'student_group': g,
                    'statistic': m
                }
                for c, g, m in selected
            ],
            ['variable_code', 'student_group', 'statistic']
        )

        report = {
            'status': 'collected_and_extracted',
            'source_url': URL_2024,
            'source_sha256': sha(source),
            'download_bytes': source.stat().st_size,
            'source_rows': count_rows,
            'source_columns': len(fields),
            'source_id_column': id_field,
            'invalid_campus_ids': invalid_ids,
            'dli_variable_columns': len(selected),
            'campuses_with_positive_dli_assessment_denominators':
                len(by_campus),
            'group_metric_value_counts': {
                '|'.join(x): n
                for x, n in sorted(values.items())
            },
            'caution': (
                'These are test-taker group assessment statistics, '
                'not DLI enrollment counts. Nonappearance or masking '
                'does not imply a school lacks a program. '
                'Raw variable codes are not labeled ELA/math or '
                'grade until dictionary mapping is verified.'
            )
        }

        safe_text(
            out / 'tx_tapr_2023_24_report.json',
            json.dumps(report, indent=2) + '\n'
        )

        return report


def main():
    p = argparse.ArgumentParser()

    p.add_argument(
        '--out',
        type=Path,
        default=Path('output/texas/tapr')
    )

    p.add_argument(
        '--roster',
        type=Path,
        default=Path('output/texas/tx_2024_25_all_campuses.csv')
    )

    p.add_argument(
        '--input',
        type=Path,
        help='Use an existing official TAPR CSV instead of web automation'
    )

    p.add_argument(
        '--wait-seconds',
        type=int,
        default=240
    )

    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    try:
        source = args.input or fetch_public_csv(
            args.out,
            args.wait_seconds
        )

        report = audit_csv(
            source,
            args.out,
            args.roster
        )

        print(json.dumps(report, indent=2))

    except Exception as ex:
        safe_text(
            args.out / 'tx_tapr_collector_failure.json',
            json.dumps({
                'error': f'{type(ex).__name__}: {ex}',
                'source_url': URL_2024,
                'traceback': traceback.format_exc()[-4000:]
            }, indent=2) + '\n'
        )
        raise


if __name__ == '__main__':
    main()
