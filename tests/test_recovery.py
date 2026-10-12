import json
from dataclasses import replace
from datetime import timedelta

import httpx
import pytest
from bs4 import BeautifulSoup
from conftest import NOW

from lidl_engine.cli import run
from lidl_engine.db import connect
from lidl_engine.web import create_app


def refresh(settings, external, now=NOW):
    return run(["refresh"], settings=settings, client=external.client(), now=lambda: now)


def browser(settings, now=NOW):
    return create_app(settings, now=lambda: now).test_client()


def add_page(external, number=2):
    external.metadata["flyer"]["pages"].append(
        {"number": number, "image": f"https://imgproxy.leaflets.schwarz/page-{number}.jpg"}
    )
    external.images[number] = external.images[1]
    external.extractions[number] = external.extractions[1]


def test_revisions_signed_urls_and_model_invalidation(settings, external):
    assert refresh(settings, external) == 0
    preview = BeautifulSoup(browser(settings).get("/").data, "html.parser").select_one(
        "a.preview-link"
    )["href"]
    external.metadata["flyer"]["pages"][0]["image"] += "?signature=changed"
    assert refresh(settings, external) == 0
    assert len(external.submissions) == 2
    # New content with existing descriptions must trigger both stages.
    external.images[1] += b"revised"
    external.extractions[1]["offers"][0]["prices"][0]["amount"] = "22.99"
    assert refresh(settings, external) == 0
    assert len(external.submissions) == 4
    html = browser(settings).get("/").get_data(as_text=True)
    assert "22,99" in html and "19,99" not in html
    assert browser(settings).get(preview).status_code == 200  # retained audit evidence
    assert refresh(replace(settings, extraction_model="fixture/new-text"), external) == 0
    assert len(external.submissions) == 5
    assert (
        refresh(
            replace(
                settings,
                extraction_model="fixture/new-text",
                description_model="fixture/new-vision",
            ),
            external,
        )
        == 0
    )
    # The new image model produced identical description text, so extraction is reusable.
    assert len(external.submissions) == 6
    external.description += " Nowy szczegół wydrukowany na stronie."
    assert (
        refresh(
            replace(
                settings,
                extraction_model="fixture/new-text",
                description_model="fixture/newer-vision",
            ),
            external,
        )
        == 0
    )
    assert len(external.submissions) == 8


def test_failed_reread_preserves_previous_offer_then_zero_retires_it(settings, external):
    assert refresh(settings, external) == 0
    external.images[1] += b"changed"
    external.failures["/api/v1/batches"] = 503
    assert refresh(settings, external) == 1
    assert "19,99" in browser(settings).get("/").get_data(as_text=True)
    assert "Niekompletne" in browser(settings).get("/").get_data(as_text=True)
    assert len(external.submissions) == 6  # 2 original + 4 bounded attempts
    external.failures.clear()
    external.extractions[1] = {"offers": []}
    assert refresh(settings, external) == 0
    html = browser(settings).get("/").get_data(as_text=True)
    assert "Łosoś świeży" not in html
    assert "1 z 1 stron przetworzono" in html


def test_shared_occurrences_merge_and_survive_page_replacement(settings, external):
    add_page(external)
    assert refresh(settings, external) == 0
    soup = BeautifulSoup(browser(settings).get("/").data, "html.parser")
    assert len(soup.select("tr.offer")) == 1
    assert len(soup.select("a.preview-link")) == 2
    external.images[1] += b"removed"
    external.extractions[1] = {"offers": []}
    assert refresh(settings, external) == 0
    soup = BeautifulSoup(browser(settings).get("/").data, "html.parser")
    assert len(soup.select("tr.offer")) == 1
    assert len(soup.select("a.preview-link")) == 1
    assert "strony 2" in soup.get_text()


def test_partial_publication_and_recovery(settings, external):
    add_page(external)
    external.failures["/page-2.jpg"] = 503
    assert refresh(settings, external) == 1
    html = browser(settings).get("/").get_data(as_text=True)
    assert "Łosoś świeży" in html and "1 z 2 stron przetworzono" in html
    assert "Ostatnie pełne zebranie" in html and "Niekompletne" in html
    assert len([r for r in external.requests if r.url.path == "/page-2.jpg"]) == 4
    external.failures.clear()
    assert refresh(settings, external) == 0
    assert len(external.submissions) == 4
    assert "2 z 2 stron przetworzono" in browser(settings).get("/").get_data(as_text=True)


def test_pending_batch_resumes_after_process_interruption(settings, external):
    original = external.respond

    def interrupted(request):
        response = original(request)
        if "/batches/" in request.url.path:
            raise KeyboardInterrupt()
        return response

    with pytest.raises(KeyboardInterrupt):
        run(
            ["refresh"],
            settings=settings,
            client=httpx.Client(transport=httpx.MockTransport(interrupted)),
            now=lambda: NOW,
        )
    assert len(external.submissions) == 1
    assert refresh(settings, external) == 0
    assert len(external.submissions) == 2  # existing description batch, new extraction batch
    assert "Łosoś świeży" in browser(settings).get("/").get_data(as_text=True)


def test_authentication_stops_without_retry_or_secret_in_ui(settings, external):
    add_page(external)
    external.failures["/api/v1/batches"] = 401
    assert refresh(settings, external) == 1
    assert len(external.submissions) == 1
    html = browser(settings).get("/").get_data(as_text=True)
    assert "uwierzytelnienia" in html
    assert "fixture-secret" not in html
    assert "Niekompletne" in html


def test_poll_failure_preserves_checkpoint_not_resubmitted(settings, external):
    external.failures["/api/v1/batches/batch-1"] = 503
    assert refresh(settings, external) == 1
    assert len(external.submissions) == 1
    assert len([r for r in external.requests if r.url.path.endswith("batch-1")]) == 4
    external.failures.clear()
    assert refresh(settings, external) == 0
    assert len(external.submissions) == 2


def test_discovery_failure_keeps_selection_and_reports_overdue(settings, external):
    assert refresh(settings, external) == 0
    external.failures["/informacje-dla-klienta/nasze-gazetki"] = 503
    assert refresh(settings, external) == 1
    html = browser(settings, NOW + timedelta(days=2)).get("/").get_data(as_text=True)
    assert "12–17.10.2026" in html
    assert "Łosoś świeży" in html
    assert "Przekroczono" in html


def test_new_current_flyer_is_selected_before_processing(settings, external):
    assert refresh(settings, external) == 0
    external.listing = external.listing.replace("gazetka-2026-41", "gazetka-new").replace(
        "12–17.10.2026", "Nowa gazetka"
    )
    external.failures["/v4/flyer"] = 503
    assert refresh(settings, external) == 1
    html = browser(settings).get("/").get_data(as_text=True)
    assert "Nowa gazetka" in html and "Łosoś świeży" in html
    assert "0 z 0 stron" in html


def test_overlap_prevents_paid_work(settings, external):
    with connect(settings) as conn:
        conn.execute("SELECT pg_advisory_lock(257002)")
        assert refresh(settings, external) == 2
        assert len(external.requests) == 0
    assert refresh(settings, external) == 0


def test_obsolete_conflict_context_does_not_return_from_audit(settings, external):
    add_page(external)
    original = external.extractions[1]["offers"][0]
    external.extractions[2] = {
        "offers": [
            {**original, "prices": [{"kind": "advertised", "amount": "29.99", "unit": "opak."}]}
        ]
    }
    assert refresh(settings, external) == 0
    assert "Rozbieżność źródeł" in browser(settings).get("/").get_data(as_text=True)
    external.images[2] += b"gone"
    external.extractions[2] = {"offers": []}
    assert refresh(settings, external) == 0
    html = browser(settings).get("/").get_data(as_text=True)
    assert "29,99" not in html and "Rozbieżność źródeł" not in html


def test_ambiguous_submit_requires_reconciliation_instead_of_duplicate(settings, external):
    original = external.respond

    def interrupted(request):
        response = original(request)
        if request.method == "POST":
            raise httpx.ReadTimeout("Response lost", request=request)
        return response

    assert (
        run(
            ["refresh"],
            settings=settings,
            client=httpx.Client(transport=httpx.MockTransport(interrupted)),
            now=lambda: NOW,
        )
        == 1
    )
    assert refresh(settings, external) == 1
    assert len(external.submissions) == 1
    # Operator identifies the accepted batch in OpenRouter and binds its custom task IDs.
    task_ids = [
        item["custom_id"].split("-")[-1]
        for item in json.loads(external.submissions[0].content)["requests"]
    ]
    assert run(["attach-batch", "batch-1", *task_ids], settings=settings) == 0
    assert refresh(settings, external) == 0
    assert len(external.submissions) == 2


def test_metadata_year_keeps_same_flyer_identity_across_new_year(settings, external):
    external.listing = external.listing.replace("12–17.10.2026", "28.12")
    external.metadata["flyer"].update(offerStartDate="2026-12-28", offerEndDate="2027-01-03")
    external.extractions[1]["offers"][0].update(valid_from="28.12", valid_to="03.01")
    assert refresh(settings, external, NOW.replace(month=12, day=29)) == 0
    assert refresh(settings, external, NOW.replace(year=2027, month=1, day=1)) == 0
    assert len(external.submissions) == 2
    html = browser(settings, NOW.replace(year=2027, month=1, day=1)).get("/").get_data(as_text=True)
    assert "2026-12-28" in html and "2027-01-03" in html
    assert len(BeautifulSoup(html, "html.parser").select("tr.offer")) == 1


def test_reprocess_reuses_retained_extraction_without_extending_observation(settings, external):
    external.metadata["flyer"].update(offerStartDate=None, offerEndDate=None)
    external.extractions[1]["offers"][0].update(valid_from=None, valid_to=None)
    assert refresh(settings, external) == 0
    after = NOW + timedelta(days=91)
    assert run(["reprocess"], settings=settings, now=lambda: after) == 0
    assert len(external.submissions) == 2
    assert "Łosoś świeży" not in browser(settings, after).get("/").get_data(as_text=True)


def test_omitted_metadata_page_preserves_support_and_reports_missing_coverage(settings, external):
    add_page(external)
    item = external.extractions[1]["offers"][0]
    external.extractions[2] = {"offers": [{**item, "name": "Oferta z pominiętej strony"}]}
    assert refresh(settings, external) == 0
    external.metadata["flyer"]["pages"] = external.metadata["flyer"]["pages"][:1]
    assert refresh(settings, external) == 1
    html = browser(settings).get("/").get_data(as_text=True)
    assert "Oferta z pominiętej strony" in html
    assert "1 z 2 stron przetworzono" in html and "Niekompletne" in html
    assert "poprzednie oferty zachowano" in html
    assert len(external.submissions) == 2


def test_successful_same_identity_reread_removes_superseded_descriptions_from_search(
    settings, external
):
    external.extractions[1]["offers"][0]["description"] = "Pochodzenie: Norwegia"
    assert refresh(settings, external) == 0
    external.images[1] += b"new-origin"
    external.extractions[1]["offers"][0]["description"] = "Pochodzenie: Szkocja"
    assert refresh(settings, external) == 0
    html = browser(settings).get("/").get_data(as_text=True)
    assert "Szkocja" in html and "Norwegia" not in html
    assert "Brak ofert dla" in browser(settings).get("/?q=Norwegia").get_data(as_text=True)
    assert "Łosoś świeży" in browser(settings).get("/?q=Szkocja").get_data(as_text=True)


def test_disagreeing_small_print_keeps_distinct_flagged_variants(settings, external):
    original = external.extractions[1]["offers"][0]
    external.extractions[1]["offers"] = [
        {**original, "small_print": "Oferta dotyczy wszystkich wariantów"},
        {**original, "small_print": "Oferta dotyczy tylko wariantu naturalnego"},
    ]
    assert refresh(settings, external) == 0
    rows = BeautifulSoup(browser(settings).get("/").data, "html.parser").select("tr.offer")
    assert len(rows) == 2
    assert all("Rozbieżność źródeł" in row.get_text() for row in rows)
    assert any("wszystkich wariantów" in row.get_text() for row in rows)
    assert any("wariantu naturalnego" in row.get_text() for row in rows)


def test_batch_authentication_error_stops_without_new_paid_batch(settings, external):
    original = external.respond

    def denied(request):
        response = original(request)
        if "/batches/" in request.url.path:
            return httpx.Response(
                200, json={"status": "failed", "error": {"code": 401}, "results": None}
            )
        return response

    assert (
        run(
            ["refresh"],
            settings=settings,
            client=httpx.Client(transport=httpx.MockTransport(denied)),
            now=lambda: NOW,
        )
        == 1
    )
    assert len(external.submissions) == 1
    assert "uwierzytelnienia" in browser(settings).get("/").get_data(as_text=True)
    assert refresh(settings, external) == 0
    assert len(external.submissions) == 3
    assert "Łosoś świeży" in browser(settings).get("/").get_data(as_text=True)


def test_mixed_batch_auth_failure_preserves_successful_paid_work(settings, external):
    add_page(external)
    original = external.respond

    def mixed(request):
        response = original(request)
        if request.url.path.endswith("/batch-1"):
            batch = response.json()
            batch["results"][0] = {
                "custom_id": batch["results"][0]["custom_id"],
                "response": {"status_code": 401},
            }
            return httpx.Response(200, json=batch)
        return response

    assert (
        run(
            ["refresh"],
            settings=settings,
            client=httpx.Client(transport=httpx.MockTransport(mixed)),
            now=lambda: NOW,
        )
        == 1
    )
    assert len(external.submissions) == 1
    assert refresh(settings, external) == 0
    # Only the authentication-failed description is submitted again.
    retried = json.loads(external.submissions[1].content)["requests"]
    assert len(retried) == 1 and retried[0]["custom_id"].startswith("page-1-")
    assert len(external.submissions) == 3
    assert "2 z 2 stron przetworzono" in browser(settings).get("/").get_data(as_text=True)
