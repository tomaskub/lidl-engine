import threading

import pytest
from conftest import NOW
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from lidl_engine.cli import run
from lidl_engine.web import create_app


@pytest.mark.browser
def test_htmx_navigation_history_and_demand_loaded_preview(settings, external, tmp_path):
    assert run(["refresh"], settings=settings, client=external.client(), now=lambda: NOW) == 0
    server = make_server("127.0.0.1", 0, create_app(settings, now=lambda: NOW))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            chromium = pw.chromium.launch()
            page = chromium.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            requests = []
            page.on("request", lambda request: requests.append(request.url))
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            assert page.locator("tr.offer").count() == 1
            assert not any("/evidence/" in url for url in requests)
            page.screenshot(path=str(tmp_path / "desktop.png"), full_page=True)
            page.locator("input[name=q]").fill("nieistniejący")
            page.wait_for_function(
                "document.querySelector('#results').textContent.includes('Brak ofert dla')"
            )
            assert "q=" in page.url
            assert page.locator("#results").count() == 1
            page.locator("input[name=q]").fill("losos")
            page.wait_for_selector("tr.offer")
            assert page.locator("#results").count() == 1
            page.locator("a.preview-link").click()
            page.wait_for_function("document.querySelector('#preview img').naturalWidth > 0")
            assert any("/evidence/" in url for url in requests)
            page.locator("#close-preview").click()
            page.locator("select[name=sort]").select_option("end")
            page.wait_for_function("location.search.includes('sort=end')")
            page.go_back()
            page.wait_for_function(
                "location.search.includes('q=losos') && location.search.includes('sort=name')"
            )
            assert page.locator("input[name=q]").input_value() == "losos"
            assert page.locator("select[name=sort]").input_value() == "name"
            page.locator("select[name=sort]").select_option("end")
            page.wait_for_function("location.search.includes('sort=end')")
            bookmark = page.url
            page.goto(bookmark)
            assert page.locator("input[name=q]").input_value() == "losos"
            assert page.locator("select[name=sort]").input_value() == "end"
            assert page.locator("tr.offer").count() == 1
            assert not errors
            chromium.close()
    finally:
        server.shutdown()
        thread.join()
