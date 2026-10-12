"""Lidl Poland listing and original flyer metadata boundary."""

import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from .domain import date_bound

LISTING_URL = "https://www.lidl.pl/informacje-dla-klienta/nasze-gazetki"
METADATA_URL = "https://endpoints.leaflets.schwarz/v4/flyer"


def discover(client: httpx.Client, now: datetime) -> dict[str, Any]:
    response = client.get(LISTING_URL, follow_redirects=True)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for anchor in soup.select("a[href]"):
        parsed = urlsplit(urljoin(LISTING_URL, str(anchor["href"])))
        match = re.match(r"/l/pl/gazetki/([A-Za-z0-9_-]+)(?:/|$)", parsed.path)
        if parsed.hostname != "www.lidl.pl" or not match:
            continue
        title_element = anchor.select_one(".flyer__title")
        title = title_element.get_text(" ", strip=True) if title_element else ""
        if str(anchor.get("data-track-name", "")).strip().casefold() != "gazetka":
            continue
        # Listing year is stronger evidence than discovery year around New Year.
        years = re.findall(r"\b(20\d{2})\b", title)
        year = int(years[0]) if years else now.year
        return {
            "slug": match[1],
            "title": title,
            "url": f"https://www.lidl.pl/l/pl/gazetki/{match[1]}",
            "issue_year": year,
            "year_explicit": bool(years),
        }
    raise ValueError("No regular Gazetka found")


def metadata(client: httpx.Client, flyer: dict[str, Any]) -> dict[str, Any]:
    response = client.get(METADATA_URL, params={"flyer_identifier": flyer["slug"]})
    response.raise_for_status()
    data = response.json()
    if not data.get("success") or not data.get("flyer", {}).get("pages"):
        raise ValueError("Missing flyer page manifest")
    item = data["flyer"]
    pages = []
    numbers = set()
    for page in sorted(item["pages"], key=lambda p: int(p["number"])):
        number = int(page["number"])
        if number <= 0 or number in numbers:
            raise ValueError("Invalid or duplicate source page")
        numbers.add(number)
        image = page["image"]
        parsed = urlsplit(image)
        if parsed.scheme != "https" or parsed.hostname != "imgproxy.leaflets.schwarz":
            raise ValueError("Unexpected source image host")
        pages.append(
            {
                "number": number,
                "image_url": image,
                "url": f"{flyer['url'].rstrip('/')}/view/flyer/page/{number}?_ab=1",
            }
        )
    start, _ = date_bound(item.get("offerStartDate"), flyer["issue_year"])
    end, _ = date_bound(item.get("offerEndDate"), flyer["issue_year"])
    return {
        "pages": pages,
        "valid_from": start,
        "valid_to": end,
        "issue_year": start.year if start else flyer["issue_year"],
    }
