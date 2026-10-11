import pytest
from bs4 import BeautifulSoup
from conftest import NOW

from lidl_engine.cli import run
from lidl_engine.web import create_app


def refresh(settings, external):
    assert run(["refresh"], settings=settings, client=external.client(), now=lambda: NOW) == 0


def text(settings, day):
    return (
        create_app(settings, now=lambda: NOW)
        .test_client()
        .get("/?date=" + day)
        .get_data(as_text=True)
    )


@pytest.mark.parametrize(
    "start,end,day,visible",
    [
        ("2026-10-12", "2026-10-20", "2026-10-19", True),
        (None, "2026-10-15", "2026-10-20", False),
        ("2026-10-15", None, "2026-10-12", False),
        (None, None, "2026-10-20", True),
        ("2026-10-20", "2026-10-12", "2026-10-16", False),
    ],
)
def test_old_flyer_respects_known_bounds_and_unknowns(settings, external, start, end, day, visible):
    external.metadata["flyer"].update(offerStartDate=None, offerEndDate=None)
    external.extractions[1]["offers"][0].update(valid_from=start, valid_to=end)
    refresh(settings, external)
    assert "Łosoś świeży" in text(settings, day)  # current-flyer exception
    external.listing = external.listing.replace("gazetka-2026-41", "gazetka-new")
    external.extractions[1] = {"offers": []}
    refresh(settings, external)
    assert ("Łosoś świeży" in text(settings, day)) == visible


def test_independent_inference_explicit_precedence(settings, external):
    original = external.extractions[1]["offers"][0]
    external.extractions[1]["offers"] = [{**original, "valid_from": None, "valid_to": "2026-10-20"}]
    refresh(settings, external)
    html = text(settings, "2026-10-19")
    assert "2026-10-12" in html and "2026-10-20" in html
    assert "Początek z okresu gazetki" in html
    assert "Koniec z okresu gazetki" not in html
    assert "Ważna 2026" not in html


def test_year_crossing_and_inconsistent_explicit_dates(settings, external):
    original = external.extractions[1]["offers"][0]
    external.metadata["flyer"].update(offerStartDate="2026-12-28", offerEndDate="2027-01-03")
    external.extractions[1]["offers"] = [
        {**original, "valid_from": "28.12", "valid_to": "03.01"},
        {**original, "name": "Inna oferta", "valid_from": "2026-12-28", "valid_to": "2026-01-03"},
        {**original, "name": "Styczniowa oferta", "valid_from": "02.01", "valid_to": None},
    ]
    refresh(settings, external)
    html = text(settings, "2027-01-02")
    rows = BeautifulSoup(html, "html.parser").select("tr.offer")
    salmon = next(r for r in rows if "Łosoś" in r.get_text())
    assert "2027-01-03" in salmon.get_text()
    inconsistent = next(r for r in rows if "Inna oferta" in r.get_text())
    assert "Niespójne daty" in inconsistent.get_text()
    assert "2026-01-03" in inconsistent.get_text()
    january = next(r for r in rows if "Styczniowa" in r.get_text())
    assert "2027-01-02" in january.get_text()
