
#!/usr/bin/env python3
"""Inspect the next stage of TEA's public 2023-24 campus TAPR download.

This is a diagnostic collector. It uses the verified Step 3 form,
selects Grade 3, and saves the following page without importing data.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

LANDING = (
    "https://rptsvr1.tea.texas.gov/perfreport/tapr/2024/"
    "Advance%20Download/download-data-adv.html"
)
SAS = "https://rptsvr1.tea.texas.gov/cgi/sas/broker"
VERSION = "2026-11-03-stable-step3-v5"

STEP3_PARAMS = {
    "_service": "marykay",
    "_program": "perfrept.perfmast.sas",
    "_debug": "0",
    "ccyy": "2024",
    "tapr": "all_c",
    "prgopt": "reports/tapr/dd/dd_tapr.sas",
}
STEP3_URL = SAS + "?" + urlencode(STEP3_PARAMS)

RADIO = 'input[name="dsname"][value="STAAR_GR3"]'
NEXT = 'input[type="submit"][value^="Next"]'


def save_diagnostics(page, folder: Path, prefix: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)

    for index, frame in enumerate(page.frames):
        label = "main" if frame == page.main_frame else f"iframe_{index}"
        stem = folder / f"{prefix}_{label}"

        try:
            stem.with_suffix(".html").write_text(
                frame.content(),
                encoding="utf-8",
            )

            inputs = frame.locator(
                "input,button,select"
            ).evaluate_all(
                """els => els.map(e => ({
                  tag: e.tagName,
                  type: e.type || '',
                  name: e.name || '',
                  value: e.value || '',
                  label: e.closest('tr,li,label,fieldset')
                    ?.innerText?.trim()?.slice(0,180) || '',
                  options: e.tagName === 'SELECT'
                    ? Array.from(e.options).map(o => ({
                        value: o.value,
                        text: o.text.trim()
                      })) : null
                }))"""
            )

            stem.with_name(
                stem.name + "_controls.json"
            ).write_text(
                json.dumps(
                    {
                        "url": frame.url,
                        "controls": inputs,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        except Exception as exc:
            print(
                f"Could not save {label}: {exc}",
                flush=True,
            )

    try:
        page.screenshot(
            path=str(folder / f"{prefix}.png"),
            full_page=True,
        )
    except Exception:
        pass


def collect(outdir: Path) -> None:
    folder = outdir / "diagnostics"
    folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    sas_events = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            accept_downloads=True
        )

        page = context.new_page()
        page.set_default_timeout(20000)

        downloads = []

        page.on(
            "download",
            lambda item: downloads.append(item),
        )

        def log_response(response):
            if response.url.startswith(SAS):
                sas_events.append({
                    "method": response.request.method,
                    "status": response.status,
                    "content_type": response.headers.get(
                        "content-type", ""
                    ),
                })
                print(
                    f"SAS {response.request.method}: "
                    f"HTTP {response.status}",
                    flush=True,
                )

        page.on("response", log_response)

        try:
            page.goto(
                LANDING,
                wait_until="load",
                timeout=90000,
            )

            page.locator("#ccyy").select_option(
                value="2024"
            )

            # Allow the year-change reset to finish
            # before submitting the campus selection.

            frame = page.frame(
                name="SASoutput"
            )

            if frame is None:
                raise RuntimeError(
                    "SASoutput iframe not found"
                )

            frame.wait_for_url(
                re.compile(
                    r"tapr_dd_blank_iframe\.html\?year=2024"
                ),
                timeout=30000,
            )

            frame.wait_for_load_state(
                "load",
                timeout=30000,
            )

            page.locator("#tapr").select_option(
                value="all_c"
            )

            print(
                "Selected 2023-24 / All Campuses",
                flush=True,
            )

            frame = page.frame(
                name="SASoutput"
            )

            save_diagnostics(
                page,
                folder,
                "01_submitted",
            )

            # Wait for the verified Grade 3 control.
            # If the iframe was reset again, reload
            # TEA's previously verified Step 3 URL.

            try:
                frame.locator(RADIO).wait_for(
                    state="visible",
                    timeout=20000,
                )

            except PlaywrightTimeout:
                print(
                    "Step 3 was replaced or delayed; "
                    "opening TEA's verified public "
                    "Step 3 URL in the same iframe.",
                    flush=True,
                )

                frame.goto(
                    STEP3_URL,
                    wait_until="domcontentloaded",
                    timeout=90000,
                )

                frame.locator(RADIO).wait_for(
                    state="visible",
                    timeout=45000,
                )

            print(
                "Verified Step 3: Grade 3 option "
                "is visible",
                flush=True,
            )

            save_diagnostics(
                page,
                folder,
                "02_step3",
            )

            frame.locator(RADIO).check()

            next_button = frame.locator(NEXT)

            if next_button.count() != 1:
                raise RuntimeError(
                    "Step 3 Next button not "
                    "uniquely identified"
                )

            next_button.click(
                timeout=30000
            )

            # The form submits back into the same
            # iframe. Wait until the old Grade 3
            # option disappears.

            frame.locator(RADIO).wait_for(
                state="detached",
                timeout=90000,
            )

            frame.wait_for_load_state(
                "domcontentloaded",
                timeout=45000,
            )

            save_diagnostics(
                page,
                folder,
                "03_after_next",
            )

            body = frame.locator(
                "body"
            ).inner_text(
                timeout=20000
            )

            print(
                "=== NEXT TEA FORM ===",
                flush=True,
            )

            print(
                body[:5000],
                flush=True,
            )

            print(
                "=== END NEXT FORM ===",
                flush=True,
            )

            for i, download in enumerate(downloads):
                path = (
                    folder / f"download_{i}.bin"
                )

                download.save_as(path)

                print(
                    "Unexpected file saved "
                    f"for review: {path}",
                    flush=True,
                )

            # Stop for a documentation check
            # before importing any outcome data.

            raise RuntimeError(
                "Captured TEA's next form. "
                "Please upload "
                "03_after_next_iframe_1.html and "
                "03_after_next_iframe_1_controls.json "
                "from the diagnostics artifact. "
                "No data imported."
            )

        except Exception:
            save_diagnostics(
                page,
                folder,
                "error",
            )
            raise

        finally:
            (
                folder / "sas_responses.json"
            ).write_text(
                json.dumps(
                    sas_events,
                    indent=2,
                ),
                encoding="utf-8",
            )

            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path(
            "results/texas/tapr_download"
        ),
    )

    args = parser.parse_args()

    print(
        f"Collector version: {VERSION}",
        flush=True,
    )

    collect(args.outdir)


if __name__ == "__main__":
    main()
