
#!/usr/bin/env python3
"""Collect TEA 2023-24 TAPR BE/ESL campus assessment data.

Verified from TEA's captured form:
    #ccyy = 2024
    #tapr = all_c
    SASoutput iframe
    dsname = BIL1
    Next

Later stages are navigated conservatively. Unrecognized
controls are recorded rather than guessed.

DQ = two-way DLI
DT = one-way DLI

Assessment denominators are test-taker counts, not
whole-program enrollment.
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


URL = (
    "https://rptsvr1.tea.texas.gov/perfreport/tapr/"
    "tapr_dd_download.html?year=2024"
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
    r"^[A-Z]D[QT][A-Z0-9_]+[NDR]$",
    re.I,
)


def save_json(path, item):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            item, indent=2, default=str
        ) + "\n",
        encoding="utf-8",
    )


def save_csv(path, rows, columns):
    with path.open(
        "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.DictWriter(
            f, fieldnames=columns
        )
        w.writeheader()
        w.writerows(rows)


def fingerprint(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(
            lambda: f.read(1024 * 1024), b""
        ):
            h.update(block)

    return h.hexdigest()


def inventory(frame):
    return frame.evaluate(
        """() => [...document.querySelectorAll(
            'input,select,button,a'
        )].slice(0,600).map((e,i)=>({
            i,
            tag:e.tagName,
            type:e.type||'',
            name:e.name||'',
            id:e.id||'',
            value:e.value||'',
            checked:!!e.checked,
            disabled:!!e.disabled,
            visible:!!(
                e.offsetWidth ||
                e.offsetHeight ||
                e.getClientRects().length
            ),
            label:(
                e.labels?.[0]?.innerText ||
                e.getAttribute('aria-label') ||
                e.parentElement?.innerText ||
                ''
            ).replace(/\\s+/g,' ').slice(0,160),
            text:(e.innerText||'')
                .replace(/\\s+/g,' ')
                .slice(0,130),
            options:e.tagName==='SELECT'
                ? [...e.options].map(o=>({
                    label:o.label,
                    value:o.value,
                    selected:o.selected
                })).slice(0,250)
                : undefined
        }))"""
    )


def step_value(frame):
    try:
        x = frame.locator(
            'input[name="step"]'
        )
        return (
            x.first.input_value(timeout=1500)
            if x.count()
            else ""
        )
    except Exception:
        return ""


def capture(frame, out, label, report):
    try:
        (
            out / f"tx_tapr_{label}.html"
        ).write_text(
            frame.content(),
            encoding="utf-8",
        )

        save_json(
            out / f"tx_tapr_{label}_controls.json",
            inventory(frame),
        )

        report["stages"].append({
            "stage": label,
            "url": frame.url,
            "step": step_value(frame),
        })

    except Exception as exc:
        report["events"].append({
            "capture_error": (
                f"{label}: {exc}"
            )
        })


def get_sas(page, timeout=60):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        frame = page.frame(
            name="SASoutput"
        )

        if (
            frame
            and "/cgi/sas/broker" in frame.url
        ):
            try:
                selector = frame.locator(
                    'input[name="dsname"]'
                    '[value="BIL1"]'
                )

                if selector.count():
                    return frame
            except Exception:
                pass

        page.wait_for_timeout(700)

    raise RuntimeError(
        "SASoutput did not reach TEA's "
        "Step 3 BIL1 form"
    )


def advance(frame, page, report, label):
    before_step = step_value(frame)
    before_url = frame.url
    old = frame.content()

    nexts = frame.locator(
        'input[type="submit"],'
        'button[type="submit"]'
    )

    choices = []

    for i in range(nexts.count()):
        el = nexts.nth(i)

        desc = (
            (el.get_attribute("value") or "")
            + " "
            + (el.inner_text() or "")
        )

        if re.search(
            r"next|continue", desc, re.I
        ):
            choices.append(i)

    if len(choices) != 1:
        raise RuntimeError(
            f"{label}: expected one "
            f"Next/Continue button; "
            f"found {choices}"
        )

    nexts.nth(choices[0]).click(
        timeout=20000
    )

    for _ in range(50):
        page.wait_for_timeout(450)

        current = page.frame(
            name="SASoutput"
        )

        if not current:
            continue

        try:
            changed = (
                step_value(current) != before_step
                or current.url != before_url
                or current.content() != old
            )

            if changed:
                report["events"].append({
                    "advance": label,
                    "from_step": before_step,
                    "to_step": step_value(current),
                })

                return current

        except Exception:
            pass

    raise RuntimeError(
        f"{label}: TEA did not advance "
        f"from step {before_step}"
    )


def select_all_checkboxes(frame, report):
    checks = frame.locator(
        'input[type="checkbox"]'
    )

    available = []

    for i in range(checks.count()):
        el = checks.nth(i)

        if (
            el.is_enabled()
            and el.is_visible()
        ):
            available.append(i)

    if len(available) > 200:
        raise RuntimeError(
            "Too many selectable fields; "
            "review controls before proceeding"
        )

    for i in available:
        checks.nth(i).check(
            timeout=10000
        )

    report["events"].append({
        "checkboxes_selected": len(available)
    })

    return bool(available)


def format_choices(frame, report):
    """Select CSV if an explicit format choice exists."""

    matched = 0

    selects = frame.locator("select")

    for i in range(selects.count()):
        el = selects.nth(i)

        if (
            not el.is_visible()
            or not el.is_enabled()
        ):
            continue

        options = el.evaluate(
            """e => [...e.options].map(o=>({
                label:o.label,
                value:o.value
            }))"""
        )

        csvs = [
            o for o in options
            if re.search(
                r"csv|comma.delimited",
                o["label"],
                re.I,
            )
        ]

        if len(csvs) == 1:
            el.select_option(
                value=csvs[0]["value"]
            )

            matched += 1

            report["events"].append({
                "selected_format": csvs[0]
            })

    radios = frame.locator(
        'input[type="radio"]'
    )

    radio_options = []

    for i in range(radios.count()):
        item = radios.nth(i)

        if (
            not item.is_enabled()
            or not item.is_visible()
        ):
            continue

        desc = item.evaluate(
            """e =>
                e.labels?.[0]?.innerText ||
                e.parentElement?.innerText ||
                ''
            """
        )

        if re.search(
            r"csv|comma.delimited",
            desc,
            re.I,
        ):
            radio_options.append(i)

    if len(radio_options) == 1:
        radios.nth(
            radio_options[0]
        ).check()

        report["events"].append({
            "selected_csv_radio":
                radio_options[0]
        })

        matched += 1

    return bool(matched)


def click_export(frame, page, report):
    """Click a clearly identified download control."""

    submits = frame.locator(
        'input[type="submit"],'
        'button[type="submit"]'
    )

    choices = []

    for i in range(submits.count()):
        el = submits.nth(i)

        desc = (
            (el.get_attribute("value") or "")
            + " "
            + (el.inner_text() or "")
        )

        if re.search(
            r"download|export|generate|get data",
            desc,
            re.I,
        ):
            choices.append(i)

    if len(choices) == 1:
        submits.nth(
            choices[0]
        ).click()

        report["events"].append({
            "clicked_export": True
        })

        return True

    links = frame.locator('a[href]')
    found = []

    for i in range(links.count()):
        link = links.nth(i)

        href = (
            link.get_attribute("href") or ""
        )

        label = (
            link.inner_text() or ""
        )

        is_file = re.search(
            r"\.(?:csv|dat|txt)(?:[?#]|$)",
            href,
            re.I,
        )

        is_export = re.fullmatch(
            r"\s*download(?: csv| data)?\s*",
            label,
            re.I,
        )

        if is_file or is_export:
            found.append(i)

    if len(found) == 1:
        links.nth(found[0]).click()

        report["events"].append({
            "clicked_export_link": True
        })

        return True

    return False


def fetch(out, wait_seconds):
    from playwright.sync_api import sync_playwright

    report = {
        "started_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "source": URL,
        "events": [],
        "stages": [],
        "verified_category": "BIL1",
    }

    downloads = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )

            context = browser.new_context(
                accept_downloads=True,
            )

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

            response = page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            report["http_status"] = (
                response.status
                if response
                else None
            )

            if (
                not response
                or response.status != 200
            ):
                raise RuntimeError(
                    "TEA main page returned "
                    f"{report['http_status']}"
                )

            # Step 1: 2023-24 school year.
            page.locator(
                "#ccyy"
            ).select_option(value="2024")

            # Step 2: All Campuses.
            page.locator(
                "#tapr"
            ).select_option(value="all_c")

            frame = get_sas(page)

            capture(
                frame,
                out,
                "step3_BIL1_choices",
                report,
            )

            # Step 3: BE/ESL achievement category.
            category = frame.locator(
                'input[name="dsname"]'
                '[value="BIL1"]'
            )

            category.check()

            if not category.is_checked():
                raise RuntimeError(
                    "BIL1 radio was not selected"
                )

            frame = advance(
                frame,
                page,
                report,
                "select_BIL1",
            )

            capture(
                frame,
                out,
                "step4_after_BIL1",
                report,
            )

            # Proceed only through identifiable controls.
            # Later TEA stages are not yet independently
            # verified. Their HTML is captured.
            for stage in range(4, 9):
                if downloads:
                    break

                current_step = step_value(frame)

                summary_text = (
                    frame.locator("body")
                    .inner_text(timeout=10000)[:1500]
                )

                report["events"].append({
                    "stage_loop": stage,
                    "site_step": current_step,
                    "body_excerpt":
                        summary_text[:350],
                })

                if click_export(
                    frame, page, report
                ):
                    break

                chosen = select_all_checkboxes(
                    frame, report
                )

                chosen = (
                    format_choices(frame, report)
                    or chosen
                )

                if not chosen:
                    raise RuntimeError(
                        "Cannot safely select options "
                        f"at TEA step {current_step}; "
                        "inspect saved SAS controls. "
                        "No guessed submission."
                    )

                capture(
                    frame,
                    out,
                    f"step{stage}_selected",
                    report,
                )

                frame = advance(
                    frame,
                    page,
                    report,
                    f"next_after_step{stage}",
                )

                capture(
                    frame,
                    out,
                    f"step{stage + 1}_after_next",
                    report,
                )

            deadline = (
                time.monotonic() + wait_seconds
            )

            while (
                not downloads
                and time.monotonic() < deadline
            ):
                page.wait_for_timeout(700)

            if not downloads:
                capture(
                    page.frame(name="SASoutput")
                    or page,
                    out,
                    "final_no_download",
                    report,
                )

                raise RuntimeError(
                    "TEA did not emit a download; "
                    "inspect final controls"
                )

            download = downloads[0]

            suggested = (
                download.suggested_filename
            )

            destination = out / (
                "tx_tapr_2023_24_campus_raw"
                + Path(suggested).suffix.lower()
            )

            download.save_as(
                str(destination)
            )

            report["download_filename"] = (
                suggested
            )

            report["download_bytes"] = (
                destination.stat().st_size
            )

            if destination.stat().st_size < 200:
                raise RuntimeError(
                    "Downloaded file unexpectedly short"
                )

            with destination.open("rb") as f:
                head = (
                    f.read(150)
                    .lower()
                    .lstrip()
                )

            if head.startswith((
                b"<html",
                b"<!doctype",
            )):
                raise RuntimeError(
                    "TEA returned HTML, not data"
                )

            return destination

    except Exception as exc:
        report["error"] = (
            f"{type(exc).__name__}: {exc}"
        )
        raise

    finally:
        save_json(
            out / "tx_tapr_download_debug.json",
            report,
        )


def parse_download(path, out, roster):
    """Extract reported DQ/DT TAPR variables."""

    if path.suffix.lower() not in (
        ".csv", ".txt", ".dat"
    ):
        raise RuntimeError(
            "Unsupported TEA download type "
            f"{path.suffix}; original preserved"
        )

    delimiter = (
        "\t"
        if path.suffix.lower() in (
            ".txt", ".dat"
        )
        else ","
    )

    with roster.open(
        newline="",
        encoding="utf-8-sig",
    ) as f:
        reader = csv.DictReader(f)

        if "texas_campus_id" not in (
            reader.fieldnames or []
        ):
            raise ValueError(
                "Roster lacks texas_campus_id"
            )

        roster_ids = {
            x["texas_campus_id"].strip()
            for x in reader
        }

    with path.open(
        newline="",
        encoding="utf-8-sig",
        errors="replace",
    ) as f:
        reader = csv.reader(
            f, delimiter=delimiter
        )

        head = [
            next(reader, [])
            for _ in range(5)
        ]

        ranked = [
            (
                sum(
                    bool(CODE.fullmatch(c.strip()))
                    for c in row
                ),
                i,
            )
            for i, row in enumerate(head)
        ]

        n, ix = max(
            ranked,
            default=(0, 0),
        )

        if n == 0:
            save_json(
                out / "tx_tapr_header_audit.json",
                {
                    "sample": [
                        x[:80]
                        for x in head
                    ],
                    "sample_widths": [
                        len(x)
                        for x in head
                    ],
                },
            )

            raise ValueError(
                "No DQ/DT fields found "
                "in first five rows"
            )

        f.seek(0)

        reader = csv.reader(
            f, delimiter=delimiter
        )

        for _ in range(ix):
            next(reader)

        columns = next(reader)

        selected = [
            (
                i,
                c.strip(),
                GROUPS[
                    c.strip()[1:3].upper()
                ],
                METRICS[
                    c.strip()[-1].upper()
                ],
            )
            for i, c in enumerate(columns)
            if CODE.fullmatch(c.strip())
        ]

        id_index = next(
            (
                i
                for i, c in enumerate(columns)
                if re.search(
                    (
                        r"campus.*(?:id|number)"
                        r"|^campus$"
                    ),
                    c,
                    re.I,
                )
            ),
            0,
        )

        save_csv(
            out / (
                "tx_tapr_2023_24_"
                "dli_variable_dictionary.csv"
            ),
            [
                {
                    "variable_code": code,
                    "student_group": group,
                    "statistic": kind,
                }
                for _, code, group, kind in selected
            ],
            [
                "variable_code",
                "student_group",
                "statistic",
            ],
        )

        output_fields = [
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

        numeric = re.compile(
            r"\d+(?:\.\d+)?$"
        )

        groups = defaultdict(
            lambda: {
                "two_way_dli": set(),
                "one_way_dli": set(),
            }
        )

        value_counts = Counter()
        source_rows = 0
        invalid_ids = 0

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
                gz,
                fieldnames=output_fields,
            )
            writer.writeheader()

            for row in reader:
                if (
                    not row
                    or len(row) <= id_index
                ):
                    continue

                source_rows += 1

                cid = (
                    row[id_index]
                    .strip()
                    .lstrip("'\u2019")
                )

                if not re.fullmatch(
                    r"\d{9}", cid
                ):
                    invalid_ids += 1
                    continue

                for (
                    i,
                    code,
                    group,
                    kind,
                ) in selected:
                    raw = (
                        row[i].strip()
                        if i < len(row)
                        else ""
                    )

                    if not raw:
                        continue

                    value = raw.replace(
                        ",", ""
                    )

                    is_numeric = bool(
                        numeric.fullmatch(value)
                    )

                    status = (
                        "numeric"
                        if is_numeric
                        else "masked_or_other"
                    )

                    writer.writerow({
                        "texas_campus_id": cid,
                        "school_year": "2023-24",
                        "student_group": group,
                        "variable_code": code,
                        "statistic": kind,
                        "raw_value": raw,
                        "numeric_value": (
                            value
                            if is_numeric
                            else ""
                        ),
                        "value_status": status,
                        "in_roster": (
                            "yes"
                            if cid in roster_ids
                            else "no"
                        ),
                    })

                    value_counts[
                        (group, kind, status)
                    ] += 1

                    if (
                        kind == "denominator"
                        and is_numeric
                        and float(value) > 0
                    ):
                        groups[cid][group].add(
                            code
                        )

        campus_rows = [
            {
                "texas_campus_id": cid,
                "school_year": "2023-24",
                "two_way_positive_denominator_variables":
                    len(g["two_way_dli"]),
                "one_way_positive_denominator_variables":
                    len(g["one_way_dli"]),
                "in_2024_25_campus_roster": (
                    "yes"
                    if cid in roster_ids
                    else "no"
                ),
            }
            for cid, g in sorted(
                groups.items()
            )
        ]

        save_csv(
            out / (
                "tx_tapr_2023_24_"
                "dli_campus_evidence.csv"
            ),
            campus_rows,
            [
                "texas_campus_id",
                "school_year",
                "two_way_positive_denominator_variables",
                "one_way_positive_denominator_variables",
                "in_2024_25_campus_roster",
            ],
        )

        result = {
            "status": "extracted",
            "source_file": str(path),
            "source_sha256":
                fingerprint(path),
            "source_rows": source_rows,
            "invalid_campus_ids": invalid_ids,
            "header_row": ix + 1,
            "id_column":
                columns[id_index],
            "DLI_fields": len(selected),
            "campuses_with_positive_test_denominators":
                len(campus_rows),
            "metric_status_counts": {
                "|".join(k): v
                for k, v in sorted(
                    value_counts.items()
                )
            },
            "caution": (
                "Test-taker subgroup figures "
                "are not program enrollments; "
                "masking is not zero."
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
        "--out",
        type=Path,
        default=Path(
            "output/texas/tapr"
        ),
    )

    parser.add_argument(
        "--roster",
        type=Path,
        default=Path(
            "output/texas/"
            "tx_2024_25_all_campuses.csv"
        ),
    )

    parser.add_argument(
        "--input",
        type=Path,
        help=(
            "Use an official TAPR CSV "
            "already downloaded"
        ),
    )

    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=180,
    )

    args = parser.parse_args()

    args.out.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        path = (
            args.input
            or fetch(
                args.out,
                args.wait_seconds,
            )
        )

        print(
            json.dumps(
                parse_download(
                    path,
                    args.out,
                    args.roster,
                ),
                indent=2,
            )
        )

    except Exception as exc:
        save_json(
            args.out / (
                "tx_tapr_collector_failure.json"
            ),
            {
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "traceback":
                    traceback.format_exc()[-4500:],
                "source": URL,
            },
        )

        raise


if __name__ == "__main__":
    main()
