
#!/usr/bin/env python3
"""Collect public 2023-24 Texas TAPR campus assessment data.

Uses browser automation to retrieve a public TEA CSV. The separate
texas_tapr_public_import.py script parses and joins downloaded data.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

URL = (
    "https://rptsvr1.tea.texas.gov/perfreport/tapr/2024/"
    "Advance%20Download/download-data-adv.html"
)
COLLECTOR_VERSION = "2026-11-02-download-handler-fix"


def snapshot(page, folder: Path, name: str) -> None:
    """Save form HTML, input descriptions, and a screenshot for debugging."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.html").write_text(
        page.content(), encoding="utf-8"
    )
    elements = page.locator("input,button,select,a").evaluate_all(
        """xs => xs.map(x => ({
            tag: x.tagName,
            type: x.type || '',
            name: x.name || '',
            value: x.value || '',
            text: (x.innerText || '').trim().slice(0,100),
            label: x.labels
                ? Array.from(x.labels).map(y => y.innerText.trim()).join(' ')
                : ''
        }))"""
    )
    (folder / f"{name}.json").write_text(
        json.dumps(elements, indent=2), encoding="utf-8"
    )
    try:
        page.screenshot(
            path=str(folder / f"{name}.png"),
            full_page=True,
            timeout=15000,
        )
    except Exception:
        pass


def click(page, pattern: str) -> bool:
    for loc in (
        page.get_by_role("button", name=re.compile(pattern, re.I)),
        page.get_by_role("link", name=re.compile(pattern, re.I)),
    ):
        for index in range(min(loc.count(), 6)):
            el = loc.nth(index)
            if el.is_visible() and el.is_enabled():
                el.click(timeout=15000)
                return True

    loc = page.locator("input[type=submit],input[type=button]")
    for index in range(loc.count()):
        el = loc.nth(index)
        value = el.get_attribute("value") or ""
        if re.search(pattern, value, re.I) and el.is_visible():
            el.click(timeout=15000)
            return True
    return False


def choose_first_page(page) -> None:
    campus = page.get_by_role(
        "radio", name=re.compile("^Campus$", re.I)
    )
    if campus.count():
        campus.first.check()
    else:
        campus_text = page.get_by_text("Campus", exact=True)
        if campus_text.count():
            campus_text.first.click()
        else:
            radios = page.locator("input[type=radio]")
            if radios.count() < 10:
                raise RuntimeError("Cannot identify Campus choice")
            radios.nth(0).check(force=True)

    # Request grade 3-8 STAAR measures under Additional Student Groups.
    pattern = re.compile(
        r"Approaches.*Meets.*Masters.*Grades 3 to 8", re.I
    )
    grade = page.get_by_role("radio", name=pattern)
    if grade.count() >= 2:
        grade.nth(1).check()
    else:
        labels = page.locator("label").filter(has_text=pattern)
        if labels.count() >= 2:
            labels.nth(1).click()
        else:
            radios = page.locator("input[type=radio]")
            if radios.count() < 10:
                raise RuntimeError(
                    "Cannot identify Additional Student Groups choice"
                )
            radios.nth(9).check(force=True)


def select_all_and_csv(page) -> None:
    # Aim for a statewide campus CSV; filter to pilot campuses on import.
    for loc in (
        page.get_by_role(
            "checkbox", name=re.compile("select all|all campuses", re.I)
        ),
        page.get_by_role(
            "radio", name=re.compile("^all|statewide", re.I)
        ),
    ):
        if loc.count() and loc.first.is_visible():
            loc.first.check()

    click(page, "^select all$")
    csv_choice = page.get_by_role(
        "radio", name=re.compile("csv|comma", re.I)
    )
    if csv_choice.count() and csv_choice.first.is_visible():
        csv_choice.first.check()

    for item in page.locator("select").all():
        for option in item.locator("option").all_text_contents():
            if re.search("csv|comma.delimited", option, re.I):
                item.select_option(label=option)
                break


def collect(output: Path) -> Path:
    from playwright.sync_api import (
        sync_playwright,
        TimeoutError as PWTimeout,
    )

    output.mkdir(parents=True, exist_ok=True)
    diagnostics = output / "diagnostics"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(
            accept_downloads=True,
            viewport={"width": 1400, "height": 900},
        )
        page.set_default_timeout(15000)

        downloads = []

        # IMPORTANT: use a Python function, not the builtin list.append method.
        page.on("download", lambda download: downloads.append(download))

        try:
            page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=90000,
            )
            snapshot(page, diagnostics, "01_initial")
            choose_first_page(page)
            snapshot(page, diagnostics, "02_filters")

            if not click(page, "continue|next|submit"):
                raise RuntimeError("No Continue action on first TEA page")

            for step in range(3, 9):
                if downloads:
                    break
                page.wait_for_timeout(1000)
                snapshot(page, diagnostics, f"{step:02d}_before")
                select_all_and_csv(page)

                if downloads:
                    break
                if click(page, "download|export|generate"):
                    if not downloads:
                        try:
                            downloads.append(
                                page.wait_for_event(
                                    "download", timeout=120000
                                )
                            )
                        except PWTimeout as exc:
                            raise RuntimeError(
                                "TEA did not return a file"
                            ) from exc
                    break
                if not click(page, "continue|next|submit"):
                    raise RuntimeError("Cannot advance TEA form")

            if not downloads:
                raise RuntimeError("No file downloaded from TEA")

            download = downloads[0]
            result = output / (
                "tapr_2024_campus_additional_grades3to8.csv"
            )
            download.save_as(result)
            if result.stat().st_size < 100:
                raise RuntimeError("Downloaded file unexpectedly small")

            with result.open(
                encoding="utf-8-sig", errors="replace", newline=""
            ) as handle:
                header = next(csv.reader(handle), [])
            if len(header) < 2:
                raise RuntimeError("No valid CSV header found")

            program_fields = [
                name for name in header
                if re.match(r"^C(DQ|DT)", name.strip().upper())
            ]
            receipt = {
                "source_url": URL,
                "collector_version": COLLECTOR_VERSION,
                "original_filename": download.suggested_filename,
                "file_size": result.stat().st_size,
                "column_count": len(header),
                "first_columns": header[:15],
                "candidate_DQ_DT_columns": len(program_fields),
            }
            (output / "download_receipt.json").write_text(
                json.dumps(receipt, indent=2), encoding="utf-8"
            )
            print(json.dumps(receipt, indent=2), flush=True)

            if not program_fields:
                raise RuntimeError(
                    "CSV downloaded but DQ/DT columns not found; "
                    "inspect the selection"
                )
            return result

        except Exception:
            try:
                snapshot(page, diagnostics, "error")
            except Exception as snap_exc:
                print(f"Could not save final snapshot: {snap_exc}", flush=True)
            raise
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("results/texas/tapr_download"),
    )
    args = parser.parse_args()
    print(f"Collector version: {COLLECTOR_VERSION}", flush=True)
    print(f"Collecting public TEA TAPR from {URL}", flush=True)
    result = collect(args.outdir)
    print(f"Downloaded: {result}", flush=True)


if __name__ == "__main__":
    main()
