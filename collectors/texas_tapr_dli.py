
#!/usr/bin/env python3
"""Collect Texas TAPR campus dual-language assessment subgroups.

Targets 2023-24 TAPR. DQ = two-way DLI; DT = one-way DLI.
N/D/R suffixes identify numerator, denominator and rate.

These are assessment subgroup statistics, not program enrollment.
The collector fails safely when TEA refuses connections or when
the required BE/ESL reporting group cannot be confirmed.
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
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

NEW_URL = (
    "https://rptsvr1.tea.texas.gov/perfreport/tapr/"
    "tapr_dd_download.html?year=2024"
)
OLD_URL = (
    "https://rptsvr1.tea.texas.gov/perfreport/tapr/2024/"
    "Advance%20Download/download-data-adv.html"
)

GROUPS = {
    "DQ": "two_way_dli",
    "DT": "one_way_dli",
}
METRICS = {
    "N": "numerator",
    "D": "denominator",
    "R": "rate",
}

CODE = re.compile(
    r"^[A-Z]D([QT])[A-Z0-9_]+([NDR])$",
    re.I,
)


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def csv_write(path, rows, names):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)


def hash_file(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024), b""
        ):
            h.update(chunk)
    return h.hexdigest()


def controls(page):
    return page.evaluate(
        """() => Array.from(document.querySelectorAll(
          'select,input,button,a'
        )).slice(0,500).map((x,i)=>({
          index:i,
          tag:x.tagName,
          type:x.type||'',
          id:x.id||'',
          name:x.name||'',
          value:x.value||'',
          checked:!!x.checked,
          disabled:!!x.disabled,
          label:(
            x.labels?.[0]?.innerText ||
            x.getAttribute('aria-label') ||
            x.parentElement?.innerText || ''
          ).replace(/\\s+/g,' ').slice(0,130),
          text:(x.innerText||'')
            .replace(/\\s+/g,' ').slice(0,100),
          options:x.tagName==='SELECT'
            ? Array.from(x.options).map(o=>({
                label:o.label.trim(),
                value:o.value,
                selected:o.selected
              })).slice(0,250)
            : undefined
        }))"""
    )


def snapshot(page, out, name, log):
    try:
        (out / f"{name}.html").write_text(
            page.content(), encoding="utf-8"
        )
        page.screenshot(
            path=str(out / f"{name}.png"),
            full_page=True,
            timeout=12000,
        )
        log["snapshots"].append(name)
        save_json(
            out / f"{name}_controls.json",
            controls(page),
        )
    except Exception as exc:
        log["events"].append({
            "snapshot_failure": str(exc)
        })


def probe(url, seconds=12):
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; research data collection)"
                )
            },
        )
        with urllib.request.urlopen(
            request, timeout=seconds
        ) as response:
            return {
                "url": url,
                "http_status": response.status,
                "final_url": response.url,
                "content_type": response.headers.get(
                    "Content-Type", ""
                ),
            }
    except Exception as exc:
        return {
            "url": url,
            "error": f"{type(exc).__name__}: {exc}",
        }


def choose_select(page, patterns, step):
    """Choose a uniquely identified dropdown option."""
    matches = []

    for i in range(page.locator("select").count()):
        sel = page.locator("select").nth(i)

        if not sel.is_visible() or not sel.is_enabled():
            continue

        options = sel.evaluate(
            """e=>Array.from(e.options).map(o=>({
              label:o.label.trim(),
              value:o.value
            }))"""
        )

        found = [
            option for option in options
            if any(
                re.search(pattern, option["label"], re.I)
                for pattern in patterns
            )
        ]

        if len(found) == 1:
            matches.append((i, found[0]))

    if len(matches) > 1:
        raise RuntimeError(
            f"Ambiguous {step} dropdowns: {matches}"
        )

    if not matches:
        return False

    index, option = matches[0]

    page.locator("select").nth(index).select_option(
        value=option["value"]
    )
    page.wait_for_timeout(700)

    return {
        "step": step,
        "select": index,
        "label": option["label"],
        "value": option["value"],
    }


def choose_labeled_control(page, patterns):
    candidates = page.locator(
        'input[type="checkbox"],input[type="radio"]'
    )

    hits = []

    for i in range(candidates.count()):
        loc = candidates.nth(i)

        if not loc.is_visible() or not loc.is_enabled():
            continue

        description = loc.evaluate(
            """e=>(
              e.labels?.[0]?.innerText ||
              e.parentElement?.innerText || ''
            ).trim()"""
        )

        if any(
            re.search(pattern, description, re.I)
            for pattern in patterns
        ):
            hits.append((i, description))

    if len(hits) != 1:
        return False

    index, description = hits[0]

    candidates.nth(index).check(force=True)
    page.wait_for_timeout(500)

    return {
        "control": index,
        "label": description[:180],
    }


def select_options(page, log):
    """Navigate form without assuming HTML control positions."""
    actions = log["selections"]

    selected = {
        "year": False,
        "advanced": False,
        "campus": False,
        "grades": False,
        "be_esl": False,
    }

    targets = [
        (
            "year",
            [r"2023\s*[-–/]\s*24", r"^2024$"],
        ),
        (
            "advanced",
            [
                r"advanced.*(?:data|download)",
                r"^advanced$",
            ],
        ),
        (
            "campus",
            [
                r"^campus(?:es)?$",
                r"^all campuses$",
            ],
        ),
        (
            "grades",
            [
                r"grades?\s*3\s*(?:-|–|to)\s*8",
                r"grades? 3 to 8",
            ],
        ),
        (
            "be_esl",
            [
                r"\bBE\s*[/&-]\s*ESL\b",
                r"bilingual.*ESL",
                r"dual.language.*(?:one.way|two.way)",
            ],
        ),
    ]

    for _ in range(9):
        progress = False

        for key, patterns in targets:
            if selected[key]:
                continue

            result = choose_select(
                page, patterns, key
            )

            if not result and key in (
                "campus", "grades", "be_esl"
            ):
                result = choose_labeled_control(
                    page, patterns
                )

            if result:
                actions.append(result)
                selected[key] = True
                progress = True

        if selected["be_esl"] and selected["campus"]:
            break

        if not progress:
            buttons = page.get_by_role(
                "button",
                name=re.compile(
                    r"^(next|continue)$", re.I
                ),
            )

            if (
                buttons.count() == 1
                and buttons.first.is_enabled()
            ):
                buttons.first.click()
                page.wait_for_timeout(650)
                actions.append({"step": "next"})
            else:
                break

    if (
        not selected["year"]
        and "year=2024" in page.url
    ):
        selected["year"] = True
        actions.append({
            "step": "year",
            "label": "2024 URL parameter",
        })

    log["selected"] = selected

    if not selected["be_esl"]:
        raise RuntimeError(
            "Could not explicitly select BE/ESL group. "
            "Captured form for review; no download requested."
        )

    if not selected["campus"]:
        raise RuntimeError(
            "Campus reporting level not confirmed"
        )

    if not selected["grades"]:
        raise RuntimeError(
            "Grades 3-8 assessment category not confirmed"
        )

    for pattern in (
        r"^numerators?$",
        r"^denominators?$",
    ):
        result = choose_labeled_control(
            page, [pattern]
        )
        if result:
            actions.append(result)


def fetch_public(out, wait_seconds):
    from playwright.sync_api import sync_playwright

    log = {
        "utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "urls": [NEW_URL, OLD_URL],
        "events": [],
        "snapshots": [],
        "selections": [],
        "probes": [
            probe(NEW_URL),
            probe(OLD_URL),
        ],
    }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )

            context = browser.new_context(
                accept_downloads=True
            )

            downloads = []

            context.on(
                "page",
                lambda p: p.on(
                    "download",
                    lambda d: downloads.append(d),
                ),
            )

            page = context.new_page()

            page.on(
                "download",
                lambda d: downloads.append(d),
            )

            page.on(
                "requestfailed",
                lambda request: log["events"].append({
                    "request_failed": request.url[:200],
                    "reason": request.failure,
                }),
            )

            reached = False

            for label, url in (
                ("new", NEW_URL),
                ("legacy", OLD_URL),
            ):
                try:
                    response = page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    page.wait_for_timeout(700)

                    log["events"].append({
                        "page": label,
                        "status": (
                            response.status
                            if response else None
                        ),
                        "final_url": page.url,
                    })

                    snapshot(
                        page,
                        out,
                        f"tx_tapr_{label}_before",
                        log,
                    )

                    reached = True
                    break

                except Exception as exc:
                    log["events"].append({
                        "page": label,
                        "navigation_error": str(exc)[:700],
                    })

            if not reached:
                raise RuntimeError(
                    "TEA refused or failed both browser "
                    "connections. This is a network/access "
                    "failure, not a form-selector failure."
                )

            select_options(page, log)

            snapshot(
                page,
                out,
                "tx_tapr_after_selection",
                log,
            )

            button = page.get_by_role(
                "button",
                name=re.compile(
                    r"^(download|export|generate|"
                    r"download data|download csv|submit)$",
                    re.I,
                ),
            )

            if button.count() == 1:
                button.first.click()
            else:
                submit = page.locator(
                    'input[type="submit"]'
                )

                if submit.count() == 1:
                    submit.first.click()
                else:
                    raise RuntimeError(
                        "No unambiguous export button found"
                    )

            deadline = (
                time.monotonic() + wait_seconds
            )

            while (
                not downloads
                and time.monotonic() < deadline
            ):
                page.wait_for_timeout(900)

            if not downloads:
                snapshot(
                    page,
                    out,
                    "tx_tapr_after_submit_no_download",
                    log,
                )
                raise RuntimeError(
                    "No browser download emitted by TEA"
                )

            destination = (
                out / "tx_tapr_2023_24_campus_raw.csv"
            )

            log["suggested_filename"] = (
                downloads[0].suggested_filename
            )

            downloads[0].save_as(
                str(destination)
            )

            with destination.open("rb") as f:
                head = f.read(400).lstrip().lower()

            if (
                len(head) < 20
                or head.startswith((
                    b"<!doctype",
                    b"<html",
                    b"pk\x03\x04",
                ))
            ):
                raise RuntimeError(
                    "Downloaded file is not recognized "
                    "as CSV; inspect source file"
                )

            log["download_bytes"] = (
                destination.stat().st_size
            )

            context.close()
            browser.close()

            return destination

    except Exception as exc:
        log["failure"] = (
            f"{type(exc).__name__}: {exc}"
        )
        raise

    finally:
        save_json(
            out / "tx_tapr_download_debug.json",
            log,
        )


def read_roster(roster):
    with roster.open(
        newline="",
        encoding="utf-8-sig",
    ) as f:
        rows = csv.DictReader(f)

        if "texas_campus_id" not in (
            rows.fieldnames or []
        ):
            raise ValueError(
                "Texas roster lacks texas_campus_id"
            )

        return {
            row["texas_campus_id"].strip()
            for row in rows
        }


def number(raw):
    return bool(
        re.fullmatch(
            r"(?:\d+(?:\.\d*)?|\.\d+)",
            raw.replace(",", "").strip(),
        )
    )


def audit_csv(source, out, roster):
    ids = read_roster(roster)

    if not ids:
        raise ValueError("Empty Texas roster")

    with source.open(
        newline="",
        encoding="utf-8-sig",
        errors="replace",
    ) as f:
        reader = csv.reader(f)

        first_rows = []

        for _ in range(5):
            try:
                first_rows.append(next(reader))
            except StopIteration:
                break

        scored = []

        for i, row in enumerate(first_rows):
            matches = [
                code.strip().upper()
                for code in row
                if CODE.fullmatch(code.strip())
            ]
            scored.append((len(matches), i))

        nfields, header_index = max(
            scored, default=(0, 0)
        )

        if nfields == 0:
            save_json(
                out / "tx_tapr_header_audit.json",
                {
                    "first_rows_samples": [
                        row[:60]
                        for row in first_rows
                    ],
                    "first_rows_lengths": [
                        len(row)
                        for row in first_rows
                    ],
                    "note": (
                        "No DQ/DT variable codes "
                        "in first five rows"
                    ),
                },
            )
            raise ValueError(
                "No DQ/DT headers found; "
                "check download category"
            )

        f.seek(0)
        reader = csv.reader(f)

        for _ in range(header_index):
            next(reader)

        headers = next(reader)

        selected = [
            (
                i,
                code.strip(),
                GROUPS[code.strip()[1:3].upper()],
                METRICS[code.strip()[-1].upper()],
            )
            for i, code in enumerate(headers)
            if CODE.fullmatch(code.strip())
        ]

        if not selected:
            raise ValueError(
                "Header identification failed"
            )

        id_index = next(
            (
                i for i, name in enumerate(headers)
                if re.search(
                    r"campus.*(?:id|number)|^campus$",
                    name,
                    re.I,
                )
            ),
            0,
        )

        dictionary = [
            {
                "variable_code": code,
                "student_group": group,
                "statistic": metric,
            }
            for _, code, group, metric in selected
        ]

        csv_write(
            out / (
                "tx_tapr_2023_24_"
                "dli_variable_dictionary.csv"
            ),
            dictionary,
            [
                "variable_code",
                "student_group",
                "statistic",
            ],
        )

        fields = [
            "texas_campus_id",
            "school_year",
            "student_group",
            "variable_code",
            "statistic",
            "raw_value",
            "numeric_value",
            "value_status",
            "in_roster",
        ]

        counts = Counter()

        seen = defaultdict(
            lambda: {
                "one_way_dli": set(),
                "two_way_dli": set(),
            }
        )

        rows_seen = 0
        invalid = 0

        with gzip.open(
            out / (
                "tx_tapr_2023_24_"
                "dli_variable_values.csv.gz"
            ),
            "wt",
            newline="",
            encoding="utf-8",
        ) as gz:

            writer = csv.DictWriter(
                gz, fieldnames=fields
            )
            writer.writeheader()

            for row in reader:
                if (
                    not row
                    or len(row) <= id_index
                ):
                    continue

                rows_seen += 1

                cid = (
                    row[id_index]
                    .strip()
                    .lstrip("'\u2019")
                )

                if not re.fullmatch(
                    r"\d{9}", cid
                ):
                    invalid += 1
                    continue

                for i, code, group, metric in selected:
                    raw = (
                        row[i].strip()
                        if i < len(row)
                        else ""
                    )

                    if not raw:
                        continue

                    status = (
                        "numeric"
                        if number(raw)
                        else "masked_or_other"
                    )

                    writer.writerow({
                        "texas_campus_id": cid,
                        "school_year": "2023-24",
                        "student_group": group,
                        "variable_code": code,
                        "statistic": metric,
                        "raw_value": raw,
                        "numeric_value": (
                            raw
                            if status == "numeric"
                            else ""
                        ),
                        "value_status": status,
                        "in_roster": (
                            "yes"
                            if cid in ids
                            else "no"
                        ),
                    })

                    counts[
                        (group, metric, status)
                    ] += 1

                    if (
                        metric == "denominator"
                        and status == "numeric"
                        and float(raw) > 0
                    ):
                        seen[cid][group].add(code)

        campus_rows = [
            {
                "texas_campus_id": cid,
                "school_year": "2023-24",
                "one_way_positive_denominator_variables":
                    len(groups["one_way_dli"]),
                "two_way_positive_denominator_variables":
                    len(groups["two_way_dli"]),
                "in_2024_25_campus_roster": (
                    "yes"
                    if cid in ids
                    else "no"
                ),
            }
            for cid, groups in sorted(seen.items())
        ]

        csv_write(
            out / (
                "tx_tapr_2023_24_"
                "dli_campus_evidence.csv"
            ),
            campus_rows,
            [
                "texas_campus_id",
                "school_year",
                "one_way_positive_denominator_variables",
                "two_way_positive_denominator_variables",
                "in_2024_25_campus_roster",
            ],
        )

        result = {
            "status": "extracted",
            "source_file": str(source),
            "sha256": hash_file(source),
            "header_row_number": header_index + 1,
            "campus_id_field": headers[id_index],
            "records_seen": rows_seen,
            "invalid_campus_ids": invalid,
            "dli_columns": len(selected),
            "campuses_with_positive_dli_test_denominators":
                len(campus_rows),
            "values": {
                "|".join(key): value
                for key, value in sorted(counts.items())
            },
            "warning": (
                "Assessment subgroup records, not "
                "program enrollment. Suppressed or "
                "missing values are not zero."
            ),
        }

        save_json(
            out / "tx_tapr_2023_24_report.json",
            result,
        )

        return result


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--roster",
        type=Path,
        default=Path(
            "output/texas/"
            "tx_2024_25_all_campuses.csv"
        ),
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=Path("output/texas/tapr"),
    )

    parser.add_argument(
        "--input",
        type=Path,
        help=(
            "Parse an existing TEA CSV "
            "without opening the browser"
        ),
    )

    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=180,
    )

    args = parser.parse_args()

    args.out.mkdir(
        parents=True, exist_ok=True
    )

    try:
        csvfile = (
            args.input
            or fetch_public(
                args.out,
                args.wait_seconds,
            )
        )

        report = audit_csv(
            csvfile,
            args.out,
            args.roster,
        )

        print(json.dumps(report, indent=2))

    except Exception as exc:
        save_json(
            args.out / (
                "tx_tapr_collector_failure.json"
            ),
            {
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "traceback": (
                    traceback.format_exc()[-4500:]
                ),
                "new_url": NEW_URL,
                "legacy_url": OLD_URL,
                "note": (
                    "Network failure cannot be repaired "
                    "by changing form selectors."
                ),
            },
        )
        raise


if __name__ == "__main__":
    main()
