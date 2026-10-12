from datetime import timedelta

from bs4 import BeautifulSoup
from conftest import NOW

from lidl_engine.cli import run
from lidl_engine.web import create_app


def test_known_expiry_retention_boundary_and_source_unavailability(settings, external):
    assert run(["refresh"], settings=settings, client=external.client(), now=lambda: NOW) == 0
    client = create_app(settings, now=lambda: NOW).test_client()
    preview = BeautifulSoup(client.get("/").data, "html.parser").select_one("a.preview-link")[
        "href"
    ]
    # Upstream requests are unavailable; retained preview remains local.
    external.failures["/page-1.jpg"] = 404
    end = NOW.replace(day=17) + timedelta(days=90)
    assert create_app(settings, now=lambda: end).test_client().get(preview).status_code == 200
    after = end + timedelta(days=1)
    assert run(["cleanup"], settings=settings, now=lambda: after) == 0
    assert create_app(settings, now=lambda: after).test_client().get(preview).status_code == 404
    assert list(settings.evidence_dir.iterdir()) == []


def test_unknown_expiry_uses_last_successful_observation(settings, external):
    external.metadata["flyer"].update(offerStartDate=None, offerEndDate=None)
    external.extractions[1]["offers"][0].update(valid_from=None, valid_to=None)
    assert run(["refresh"], settings=settings, client=external.client(), now=lambda: NOW) == 0
    observed = NOW + timedelta(days=20)
    assert run(["refresh"], settings=settings, client=external.client(), now=lambda: observed) == 0
    end = observed + timedelta(days=90)
    assert run(["cleanup"], settings=settings, now=lambda: end) == 0
    html = create_app(settings, now=lambda: end).test_client().get("/").get_data(as_text=True)
    assert "Łosoś świeży" in html and "Ważność nieznana" in html
    after = end + timedelta(days=1)
    assert run(["cleanup"], settings=settings, now=lambda: after) == 0
    assert "Łosoś świeży" not in create_app(settings, now=lambda: after).test_client().get(
        "/"
    ).get_data(as_text=True)


def test_shared_image_file_survives_until_last_dependent_offer_expires(settings, external):
    external.metadata["flyer"]["pages"].append(
        {"number": 2, "image": "https://imgproxy.leaflets.schwarz/page-2.jpg"}
    )
    external.images[2] = external.images[1]
    item = external.extractions[1]["offers"][0]
    external.extractions[2] = {
        "offers": [{**item, "name": "Inny produkt", "valid_to": "2026-10-25"}]
    }
    assert run(["refresh"], settings=settings, client=external.client(), now=lambda: NOW) == 0
    after = NOW.replace(day=18) + timedelta(days=90)
    assert run(["cleanup"], settings=settings, now=lambda: after) == 0
    assert len(list(settings.evidence_dir.iterdir())) == 1
    html = create_app(settings, now=lambda: after).test_client().get("/").get_data(as_text=True)
    assert "Inny produkt" in html and "Łosoś świeży" not in html


def test_unknown_retention_uses_household_day_at_utc_midnight_boundary(settings, external):
    external.metadata["flyer"].update(offerStartDate=None, offerEndDate=None)
    external.extractions[1]["offers"][0].update(valid_from=None, valid_to=None)
    observed = NOW.replace(hour=23)
    assert run(["refresh"], settings=settings, client=external.client(), now=lambda: observed) == 0
    end = observed + timedelta(days=90)
    assert run(["cleanup"], settings=settings, now=lambda: end) == 0
    assert "Łosoś świeży" in create_app(settings, now=lambda: end).test_client().get("/").get_data(
        as_text=True
    )
    after = end + timedelta(days=1)
    assert run(["cleanup"], settings=settings, now=lambda: after) == 0
    assert "Łosoś świeży" not in create_app(settings, now=lambda: after).test_client().get(
        "/"
    ).get_data(as_text=True)
