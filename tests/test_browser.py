import pytest
from bs4 import BeautifulSoup
from conftest import NOW

from lidl_engine.cli import run
from lidl_engine.web import create_app


def offers(browser, url="/"):
    response = browser.get(url)
    assert response.status_code == 200
    return BeautifulSoup(response.data, "html.parser").select("tr.offer")


def collect(settings, external):
    assert run(["refresh"], settings=settings, client=external.client(), now=lambda: NOW) == 0
    return create_app(settings, now=lambda: NOW).test_client()


@pytest.mark.parametrize("query", ["losos", "ŁOSOŚ", "ocean", "skora", "filet"])
def test_polish_name_brand_description_search(settings, external, query):
    browser = collect(settings, external)
    assert len(offers(browser, "/?q=" + query)) == 1


def test_categories_scope_and_unknowns(settings, external):
    original = external.extractions[1]["offers"][0]
    external.extractions[1]["offers"] = [
        {
            **original,
            "name": "Kawa ziarnista do parzenia",
            "categories": ["non-alcoholic beverages"],
        },
        {**original, "name": "Kawa gotowa do picia", "categories": ["pantry items"]},
        {
            **original,
            "name": "Owoce i warzywa",
            "scope": "category",
            "categories": ["fruits", "vegetables"],
        },
        {**original, "name": "Produkt nieznany", "categories": []},
        {**original, "name": "Wiertarka", "grocery": False},
        {**original, "name": "Reklama", "prices": [], "promotion": None},
    ]
    browser = collect(settings, external)
    assert len(offers(browser)) == 4
    assert "Kawa ziarnista" in offers(browser, "/?category=pantry+items")[0].get_text()
    assert "Kawa gotowa" in offers(browser, "/?category=non-alcoholic+beverages")[0].get_text()
    for category in ["fruits", "vegetables"]:
        assert len(offers(browser, "/?category=" + category)) == 1
    assert "Kategoria nieznana" in browser.get("/?q=Produkt").get_data(as_text=True)


def test_full_price_and_purchase_semantics(settings, external):
    item = external.extractions[1]["offers"][0]
    item.update(
        prices=[
            {"kind": "advertised", "amount": "3.99", "unit": "szt.", "currency": "PLN"},
            {"kind": "regular", "amount": "5.99", "unit": "szt.", "currency": "PLN"},
            {"kind": "unit", "amount": "7.98", "unit": "kg", "currency": "PLN"},
        ],
        coupon=True,
        lidl_plus=True,
        required_quantity="3 szt.",
        paid_quantity="2 szt.",
        received_quantity="3 szt.",
        purchase_limit="6 szt. na klienta",
        deposit="0,50 zł za butelkę",
        discount_percent="50",
        discount_scope="drugi tańszy produkt",
        small_print="Aktywuj kupon.",
    )
    browser = collect(settings, external)
    html = browser.get("/").get_data(as_text=True)
    for text in [
        "3,99",
        "Cena regularna",
        "Cena jednostkowa",
        "wymagany",
        "3 szt.",
        "2 szt.",
        "6 szt. na klienta",
        "0,50 zł za butelkę",
        "drugi tańszy produkt",
    ]:
        assert text in html
    assert "7,98" in html and "11,97" not in html


@pytest.mark.parametrize("sort", ["name", "category", "end"])
def test_conflicts_expand_context_and_remain_adjacent(settings, external, sort):
    original = external.extractions[1]["offers"][0]
    external.extractions[1]["offers"] = [
        original,
        {
            **original,
            "prices": [{"kind": "advertised", "amount": "24.99", "unit": "opak."}],
            "valid_to": "2026-10-13",
            "categories": ["dairy"],
        },
        {**original, "name": "Inny produkt", "categories": ["seafood"]},
        {
            **original,
            "deal_kind": "coupon",
            "coupon": True,
            "prices": [{"kind": "advertised", "amount": "15.99", "unit": "opak."}],
        },
    ]
    collect(settings, external)
    # Select another flyer to exercise an older out-of-day conflict context.
    external.listing = external.listing.replace("gazetka-2026-41", "gazetka-next")
    external.extractions[1] = {"offers": []}
    collect(settings, external)
    browser = create_app(settings, now=lambda: NOW).test_client()
    rows = offers(browser, f"/?date=2026-10-16&category=seafood&sort={sort}&q=losos")
    assert len(rows) == 3
    keys = [row["data-conflict-key"] for row in rows]
    positions = [i for i, key in enumerate(keys) if key == rows[0]["data-conflict-key"]]
    assert positions == list(range(min(positions), max(positions) + 1))
    contexts = [r for r in rows if "context" in r["class"]]
    assert len(contexts) == 1
    assert "24,99" in contexts[0].get_text()
    assert "2026-10-13" in contexts[0].get_text()
    assert "Kontekst rozbieżności" in contexts[0].get_text()
    coupon = [r for r in rows if "15,99" in r.get_text()][0]
    assert "Rozbieżność źródeł" not in coupon.get_text()


def test_all_rows_sorted_and_html_fragment_contract(settings, external):
    original = external.extractions[1]["offers"][0]
    external.extractions[1]["offers"] = [
        {**original, "name": f"Produkt {i:04d}"} for i in range(1000, 0, -1)
    ]
    browser = collect(settings, external)
    rows = offers(browser)
    assert len(rows) == 1000
    assert "Produkt 0001" in rows[0].get_text()
    assert "Produkt 1000" in rows[-1].get_text()
    fragment = browser.get("/?q=Produkt+001&sort=end", headers={"HX-Request": "true"})
    assert b"<html" not in fragment.data and b'id="results"' in fragment.data
    assert fragment.headers["Vary"] == "HX-Request"
    html = browser.get("/?q=Produkt+001&sort=end&category=seafood&date=2026-10-14").get_data(
        as_text=True
    )
    assert 'value="Produkt 001"' in html
    assert 'value="2026-10-14"' in html


@pytest.mark.parametrize(
    "query", ["?date=bad", "?sort=;DROP+TABLE+offers", "?category=unknown", "?date=20261012"]
)
def test_invalid_filters_return_polish_error(settings, query):
    response = create_app(settings).test_client().get("/" + query)
    assert response.status_code == 400
    assert "Nieprawidłowe" in response.get_data(as_text=True)
