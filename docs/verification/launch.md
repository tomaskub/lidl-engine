# First-release launch checks

## Original-image evaluation

Select original retained flyer images containing at least 100 distinct eligible grocery offers. Include ordinary prices, category deals, multibuys, coupons, deposits, different validity periods, and brewing versus ready-to-drink tea and coffee. Annotate the original images before examining model output. Repeated advertisements support one reference offer rather than increasing its count.

Create `reference.json` with this shape, repeating reference rows for the full sample:

```json
{
  "images": {"page-0001.image": "sha256-of-original-file"},
  "offers": [{
    "id": "ref-001",
    "prices": {"advertised.amount": "3.99", "advertised.unit": "szt.", "deposit": null},
    "dates": {"start": "2026-10-12", "start_source": "explicit", "end": "2026-10-17", "end_source": "inferred"},
    "conditions": {"coupon": true, "lidl_plus": true, "required_quantity": "3 szt."},
    "categories": ["seafood"]
  }]
}
```

Image paths are relative to the reference file. Include every source-stated price, discount scope, deposit, date and condition as its own fact key. Unknown source facts may be null. Do not use unknown to excuse omitted printed information. Freeze the reference before processing:

```sh
uv run python -m lidl_engine.evaluation reference.json --freeze
```

The command requires at least 100 unique offer IDs, verifies original image hashes and creates `reference.sha256` exclusively. Keep the annotations, digest and source image hashes with the evaluation record.

Run the real collector with the selected models. Compare the distinct published offers and their source evidence to the frozen annotations. Create `predictions.json` with the same fact maps plus `reference_id` instead of `id`. Use a distinct unmatched ID for a hallucinated offer. Match reference IDs after collection without changing reference facts. Include unsupported extra assertions, not just the expected keys. Record model IDs, provider, prompts, processing contracts and the source flyer alongside the predictions.

```sh
uv run python -m lidl_engine.evaluation reference.json --predictions predictions.json > quality-results.json
```

The scorer checks the frozen reference digest. Wholly missed offers reduce distinct-offer recall. For captured offers it scores prices, dates and purchase conditions separately: correct expected facts divided by all expected facts plus unsupported extra assertions. Incorrect or missing values score zero. Category sets must agree exactly. Hallucinated offers add unsupported facts and category errors. Repeated output advertisements must be reconciled before scoring.

The gate requires recall ≥90%, price/date/condition accuracy ≥95% separately, and category-set accuracy ≥95%. A failed gate exits nonzero. Store the frozen references, matching decisions and results so another person can audit the measurement against the original images.

## Household-network desktop performance

Prepare a retained dataset with up to 1,000 matching rows, including conflict context. Run from a desktop on the household network against the deployed Ubuntu server:

```sh
uv run playwright install chromium
uv run python scripts/measure_browser.py http://<server-lan-ip>:8000/ \
  --query '<partial name matching the prepared dataset>' --category seafood \
  --output docs/verification/household-performance.json
```

The script measures initial navigation plus rendered results, searching, category filtering and sorting in Chromium. It writes seconds, actual row counts and a screenshot. Debounce, HTTP response and browser settlement are included. Each operation must finish within two seconds. Confirm the prepared row counts cover the agreed load; a fast empty table does not establish performance at 1,000 rows. Record desktop, server, network, dataset and application commit with the result.

## Operational checks on Ubuntu

- Recreate web and collection containers and verify offers, image previews and pending batch IDs survive.
- Confirm the timer's next invocation is Wednesday at 06:00 Warsaw time.
- Start a manual refresh while collection runs and confirm exit code 2 without extra provider submissions.
- Restore a backup into an isolated deployment and inspect the same offers and retained previews before relying on it for recovery.
- Keep the web application open during a failed or overdue refresh and confirm incomplete coverage remains visible.

The owner's 2–3 PLN weekly estimate remains an operating expectation. Record actual OpenRouter spend during the launch run rather than claiming fixture tests measure it.
