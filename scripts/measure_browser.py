"""Measure full desktop operations on the deployed household network."""

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("url")
parser.add_argument("--query", default="")
parser.add_argument("--category", default="")
parser.add_argument("--output", type=Path, default=Path("performance.json"))
args = parser.parse_args()
measurements = {}
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    started = time.perf_counter()
    page.goto(args.url, wait_until="load")
    page.evaluate("() => new Promise(requestAnimationFrame)")
    measurements["initial_seconds"] = time.perf_counter() - started
    measurements["initial_rows"] = page.locator("tr.offer").count()
    page.evaluate(
        "document.addEventListener('htmx:afterSettle',()=>window.settled=(window.settled||0)+1)"
    )
    actions = {
        "search": lambda: page.locator("input[name=q]").fill(args.query),
        "filter": lambda: page.locator("select[name=category]").select_option(args.category),
        "sort": lambda: page.locator("select[name=sort]").select_option("end"),
    }
    for name, action in actions.items():
        before = page.evaluate("window.settled||0")
        started = time.perf_counter()
        action()
        # Submit explicitly if the selected value was already current.
        page.locator("button[type=submit]").click()
        page.wait_for_function("(before) => (window.settled||0)>before", arg=before)
        page.evaluate("() => new Promise(requestAnimationFrame)")
        measurements[name + "_seconds"] = time.perf_counter() - started
        measurements[name + "_rows"] = page.locator("tr.offer").count()
    page.screenshot(path=str(args.output.with_suffix(".png")), full_page=True)
    browser.close()
measurements["passed"] = all(
    value <= 2 for key, value in measurements.items() if key.endswith("_seconds")
)
args.output.write_text(json.dumps(measurements, indent=2) + "\n")
print(json.dumps(measurements, indent=2))
raise SystemExit(0 if measurements["passed"] else 1)
