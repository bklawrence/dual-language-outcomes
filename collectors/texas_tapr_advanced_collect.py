
#!/usr/bin/env python3
"""Retrieve 2023-24 Texas TAPR campus data via TEA's dropdown interface.

The initial TEA page uses year/download-type dropdowns and
submits into an iframe. Downloaded files must be checked before
being treated as research data.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path

URL = (
    "https://rptsvr1.tea.texas.gov/perfreport/tapr/2024/"
    "Advance%20Download/download-data-adv.html"
)
VERSION = "2026-11-02-dropdown-iframe-v2"
FILE_NAME = "tapr_2024_campus_additional_grades3to8.csv"


def controls(frame):
    """Record form controls and dropdown options."""
    return frame.locator(
        "input,select,button,a"
    ).evaluate_all(
        """els => els.map(e => ({
            tag: e.tagName,
            id: e.id || '',
            name: e.name || '',
            type: e.type || '',
            value: e.value || '',
            text: (e.innerText || '').trim().slice(0,180),
            label: e.labels
                ? Array.from(e.labels)
                    .map(x => x.innerText.trim()).join(' ')
                : '',
            context: (
                e.closest('tr,li,label,fieldset')?.innerText || ''
            ).trim().slice(0,220),
            options: e.tagName === 'SELECT'
                ? Array.from(e.options).map(o => ({
                    value: o.value,
                    text: o.text.trim()
                }))
                : undefined
        }))"""
    )


def snapshot(page, folder, name, frame=None):
    folder.mkdir(parents=True, exist_ok=True)

    try:
        (folder / f"{name}_main.html").write_text(
            page.content(), encoding="utf-8"
        )
        (folder / f"{name}_main_controls.json").write_text(
            json.dumps(
                controls(page.main_frame), indent=2
            ),
            encoding="utf-8"
        )
        page.screenshot(
            path=str(folder / f"{name}.png"),
            full_page=True,
            timeout=15000,
        )
    except Exception as exc:
        print(
            f"Main-page diagnostic warning: {exc}",
            flush=True
        )

    if frame is not None:
        try:
            (folder / f"{name}_iframe.html").write_text(
                frame.content(), encoding="utf-8"
            )
            (folder / f"{name}_iframe_controls.json").write_text(
                json.dumps(
                    controls(frame), indent=2
                ),
                encoding="utf-8"
            )

            print(
                f"Iframe URL: {frame.url}",
                flush=True
            )
            print(
                "Iframe text preview:",
                frame.locator("body").inner_text(
                    timeout=10000
                )[:1400],
                flush=True
            )
        except Exception as exc:
            print(
                f"Iframe diagnostic warning: {exc}",
                flush=True
            )


def wait_for_results_frame(page, timeout_seconds=90):
    """Wait for the embedded SAS form to replace its placeholder."""
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        frame = page.frame(name="SASoutput")

        if (
            frame
            and frame.url != "about:blank"
            and "tapr_dd_blank_iframe" not in frame.url
        ):
            try:
                frame.wait_for_load_state(
                    "domcontentloaded", timeout=10000
                )
                return frame
            except Exception:
                pass

        page.wait_for_timeout(700)

    raise RuntimeError(
        "SAS download iframe did not load in 90 seconds"
    )


def select_additional_groups(frame):
    """Select grade-specific Additional Student Groups when identifiable."""

    # Some interfaces provide the data group in a dropdown.
    for menu in frame.locator("select").all():
        candidates = menu.locator(
            "option"
        ).evaluate_all(
            """els => els.map(e => ({
                value: e.value,
                text: e.text.trim()
            }))"""
        )

        matches = [
            option for option in candidates
            if re.search(
                r"additional.*student|student.*additional",
                option["text"],
                re.I
            )
            and re.search(
                r"staar|assessment|grade",
                option["text"],
                re.I
            )
        ]

        if len(matches) == 1:
            menu.select_option(
                value=matches[0]["value"]
            )
            print(
                f"Selected data group: {matches[0]['text']}",
                flush=True
            )
            return True

    # Other interfaces provide radio buttons or checkboxes.
    choices = frame.locator(
        "input[type=radio],input[type=checkbox]"
    )
    matches = []

    for index in range(min(choices.count(), 300)):
        el = choices.nth(index)

        desc = el.evaluate(
            """e => [
                e.labels
                    ? Array.from(e.labels)
                        .map(l => l.innerText).join(' ')
                    : '',
                e.closest('tr,li,label')?.innerText || ''
            ].join(' ').replace(/\\s+/g, ' ').trim()"""
        )

        if (
            re.search(
                r"additional.*student|student.*additional",
                desc,
                re.I
            )
            and re.search(
                r"grade.?3.*8|3.*8|staar",
                desc,
                re.I
            )
        ):
            matches.append((el, desc))

    if len(matches) == 1:
        matches[0][0].check()
        print(
            f"Selected: {matches[0][1][:180]}",
            flush=True
        )
        return True

    return False


def click_action(frame):
    """Click a visible download or continuation control."""
    patterns = (
        r"download|export|generate",
        r"continue|next|submit",
    )

    for pattern in patterns:
        buttons = frame.locator(
            "button,"
            "input[type=submit],"
            "input[type=button],"
            "a"
        )

        for index in range(min(buttons.count(), 100)):
            el = buttons.nth(index)

            title = (
                (el.get_attribute("value") or "")
                + " "
                + (el.inner_text(timeout=2000) or "")
            )

            if (
                re.search(pattern, title, re.I)
                and el.is_visible()
                and el.is_enabled()
            ):
                print(
                    f"Activating: {title.strip()[:100]}",
                    flush=True
                )
                el.click(timeout=15000)
                return True

    return False


def collect(outdir):
    from playwright.sync_api import sync_playwright

    outdir.mkdir(parents=True, exist_ok=True)
    diagnostics = outdir / "diagnostics"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            accept_downloads=True
        )
        page = context.new_page()
        page.set_default_timeout(15000)

        downloads = []

        page.on(
            "download",
            lambda download: downloads.append(download)
        )

        frame = None

        try:
            page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=90000
            )

            page.wait_for_selector(
                "#ccyy", timeout=30000
            )

            snapshot(
                page, diagnostics, "01_initial"
            )

            # Actual control IDs from the TEA HTML.
            # 2024 = school year 2023-24.
            # all_c = all campuses statewide.

            page.locator("#ccyy").select_option(
                value="2024"
            )

            page.locator("#tapr").select_option(
                value="all_c"
            )

            print(
                "Selected school year 2023-24 "
                "and All -> Campuses.",
                flush=True
            )

            frame = wait_for_results_frame(page)

            snapshot(
                page,
                diagnostics,
                "02_after_campus_selection",
                frame
            )

            if not select_additional_groups(frame):
                raise RuntimeError(
                    "Reached TEA's embedded download form "
                    "but cannot safely identify the STAAR "
                    "Additional Student Groups selection. "
                    "See 02_after_campus_selection_iframe.html "
                    "and its controls JSON."
                )

            snapshot(
                page,
                diagnostics,
                "03_group_selected",
                frame
            )

            if not click_action(frame):
                raise RuntimeError(
                    "Data group selected but no download "
                    "or continuation control identified. "
                    "Inspect 03_group_selected diagnostics."
                )

            deadline = time.monotonic() + 120

            while (
                time.monotonic() < deadline
                and not downloads
            ):
                page.wait_for_timeout(500)

            if not downloads:
                frame = (
                    page.frame(name="SASoutput")
                    or frame
                )

                snapshot(
                    page,
                    diagnostics,
                    "04_after_submit",
                    frame
                )

                raise RuntimeError(
                    "No browser download occurred after "
                    "submitting the selection. See "
                    "04_after_submit iframe diagnostics."
                )

            download = downloads[0]
            result = outdir / FILE_NAME

            download.save_as(result)

            if result.stat().st_size < 100:
                raise RuntimeError(
                    "Downloaded response is unexpectedly small"
                )

            with result.open(
                encoding="utf-8-sig",
                errors="replace",
                newline=""
            ) as handle:
                header = next(
                    csv.reader(handle), []
                )

            if len(header) < 2:
                raise RuntimeError(
                    "TEA response is not a normal CSV"
                )

            fields = [
                name for name in header
                if re.search(
                    r"(?<![A-Z])(?:C)?D[QT]",
                    name,
                    re.I
                )
            ]

            receipt = {
                "collector_version": VERSION,
                "source": URL,
                "download_name":
                    download.suggested_filename,
                "bytes": result.stat().st_size,
                "number_of_header_fields": len(header),
                "header_preview": header[:20],
                "candidate_dual_language_fields":
                    len(fields),
                "interpretation":
                    "UNVERIFIED: check TEA glossary "
                    "and program columns",
            }

            (
                outdir / "download_receipt.json"
            ).write_text(
                json.dumps(receipt, indent=2),
                encoding="utf-8"
            )

            print(
                json.dumps(receipt, indent=2),
                flush=True
            )

            return result

        except Exception:
            try:
                snapshot(
                    page, diagnostics, "error", frame
                )
            except Exception as exc:
                print(
                    f"Could not save final diagnostics: {exc}",
                    flush=True
                )
            raise

        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path(
            "results/texas/tapr_download"
        )
    )

    args = parser.parse_args()

    print(
        f"Collector version: {VERSION}",
        flush=True
    )
    print(
        f"Collecting public TEA TAPR from {URL}",
        flush=True
    )

    result = collect(args.outdir)

    print(
        f"Downloaded: {result}",
        flush=True
    )


if __name__ == "__main__":
    main()
