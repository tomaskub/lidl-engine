from bs4 import BeautifulSoup
from conftest import NOW

from lidl_engine.cli import run
from lidl_engine.web import create_app


def test_refresh_persists_offer_and_evidence_without_duplicates(settings, external):
    assert run(["refresh"], settings=settings, client=external.client(), now=lambda: NOW) == 0
    browser = create_app(settings, now=lambda: NOW).test_client()
    response = browser.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Łosoś świeży" in html
    assert "19,99" in html and "opak." in html
    assert "Ocean Sea" in html
    assert "Kupon: nieznane" in html
    assert "Lidl Plus: nieznane" in html
    assert "fixture-secret" not in html
    soup = BeautifulSoup(html, "html.parser")
    assert not soup.select("img")
    source = soup.select_one("a.source-link")
    assert "gazetka-2026-41" in source["href"]
    preview = soup.select_one("a.preview-link")["href"]
    assert browser.get(preview).data == external.images[1]
    assert run(["refresh"], settings=settings, client=external.client(), now=lambda: NOW) == 0
    assert len(external.submissions) == 2
    # New web process observes the same persisted offer and retained preview.
    browser = create_app(settings, now=lambda: NOW).test_client()
    assert len(BeautifulSoup(browser.get("/").data, "html.parser").select("tr.offer")) == 1
    assert browser.get(preview).data == external.images[1]


def test_empty_catalog_and_empty_search_differ(settings, external):
    browser = create_app(settings, now=lambda: NOW).test_client()
    assert "Nie zebrano jeszcze" in browser.get("/").get_data(as_text=True)
    run(["refresh"], settings=settings, client=external.client(), now=lambda: NOW)
    assert "Brak ofert dla" in browser.get("/?q=nieistniejący").get_data(as_text=True)
