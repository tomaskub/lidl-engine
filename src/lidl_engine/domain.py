"""Source-supported facts, date resolution, identity and browser matching."""

import hashlib
import json
import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CATEGORIES = {
    "bakery": "Pieczywo",
    "alcoholic beverages": "Napoje alkoholowe",
    "non-alcoholic beverages": "Napoje bezalkoholowe",
    "fruits": "Owoce",
    "vegetables": "Warzywa",
    "meats": "Mięso",
    "seafood": "Ryby i owoce morza",
    "dairy": "Nabiał",
    "pantry items": "Produkty do spiżarni",
    "ready made snacks": "Gotowe przekąski",
}


def fold(value: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", value.casefold().replace("ł", "l"))
        if not unicodedata.combining(c)
    )


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


class Price(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["advertised", "regular", "unit"]
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=4)
    currency: str = "PLN"
    unit: str | None = None


class Offer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=500)
    grocery: bool
    scope: Literal["product", "category"] = "product"
    brand: str | None = None
    size: str | None = None
    description: str | None = None
    categories: list[str] = Field(default_factory=list)
    deal_kind: Literal["ordinary", "coupon", "multibuy", "discount", "unknown"] = "unknown"
    promotion: str | None = None
    prices: list[Price] = Field(default_factory=list)
    discount_percent: Decimal | None = Field(default=None, ge=0, le=100)
    discount_scope: str | None = None
    required_quantity: str | None = None
    paid_quantity: str | None = None
    received_quantity: str | None = None
    lidl_plus: bool | None = None
    coupon: bool | None = None
    purchase_limit: str | None = None
    deposit: str | None = None
    small_print: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    validity_text: str | None = None


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offers: list[Offer]


def date_bound(value: str | None, year: int) -> tuple[date | None, bool]:
    if not value:
        return None, False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value), True
    if re.fullmatch(r"\d{2}\.\d{2}(?:\.\d{4})?", value):
        parts = value.split(".")
        return date(int(parts[2]) if len(parts) == 3 else year, int(parts[1]), int(parts[0])), len(
            parts
        ) == 3
    raise ValueError("Unsupported date bound")


def normalize(offer: Offer, flyer: dict[str, Any]) -> dict[str, Any] | None:
    if not offer.grocery or not (
        offer.prices or offer.promotion or offer.discount_percent is not None
    ):
        return None
    result = offer.model_dump(mode="json")
    result["prices"] = sorted(
        [
            {**price, "amount": format(Decimal(price["amount"]).normalize(), "f")}
            for price in result["prices"]
        ],
        key=lambda p: (p["kind"], p["amount"], p["unit"] or ""),
    )
    result["categories"] = sorted(set(offer.categories) & CATEGORIES.keys())
    # Only normalize the explicit brewing / ready-to-drink distinction, not arbitrary products.
    subject = fold(" ".join(filter(None, [offer.name, offer.description, offer.size])))
    if (
        re.search(r"\b(kawa|kawy|kawe|herbata|herbaty|herbate)\b", subject)
        and offer.scope == "product"
    ):
        if re.search(r"(gotow.*picia|ready.to.drink|mrozona|iced|napoj kawowy)", subject):
            result["categories"] = ["non-alcoholic beverages"]
        elif re.search(r"(parzenia|ziarnist|mielon|rozpuszczaln|torebk|lisciast)", subject):
            result["categories"] = ["pantry items"]
    start, start_year = date_bound(offer.valid_from, flyer["issue_year"])
    end, end_year = date_bound(offer.valid_to, flyer["issue_year"])
    if start and end and end < start and not end_year and start.month == 12 and end.month == 1:
        end = end.replace(year=start.year + 1)
    # A single yearless January bound in a December flyer belongs to the next year.
    flyer_start = flyer.get("valid_from")
    if flyer_start and flyer_start.month == 12:
        if start and not start_year and start.month == 1:
            start = start.replace(year=flyer_start.year + 1)
        if end and not end_year and end.month == 1:
            end = end.replace(year=flyer_start.year + 1)
    result["start_source"] = (
        "explicit" if start else "inferred" if flyer.get("valid_from") else "unknown"
    )
    result["end_source"] = "explicit" if end else "inferred" if flyer.get("valid_to") else "unknown"
    start = start or flyer.get("valid_from")
    end = end or flyer.get("valid_to")
    result["valid_from"] = start.isoformat() if start else None
    result["valid_to"] = end.isoformat() if end else None
    result["inconsistent_dates"] = bool(start and end and start > end)
    return result


def offer_identity(facts: dict[str, Any]) -> str:
    # Descriptive wording can vary between occurrences; commercial facts cannot.
    identity = {
        k: v
        for k, v in facts.items()
        if k
        not in {
            "description",
            "small_print",
            "validity_text",
            "start_source",
            "end_source",
            "categories",
        }
    }
    identity["name"] = fold(identity["name"]).strip()
    return fingerprint(identity)


def conflict_identity(facts: dict[str, Any]) -> str:
    # Suspect disagreement only for the same subject, pack, deal and start.
    return fingerprint(
        {
            k: fold(v) if isinstance(v, str) else v
            for k, v in facts.items()
            if k in {"name", "brand", "size", "scope", "deal_kind", "valid_from"}
        }
    )


def retention_until(facts: dict[str, Any], observed: date) -> date:
    end = date.fromisoformat(facts["valid_to"]) if facts.get("valid_to") else observed
    if facts.get("inconsistent_dates"):
        end = max(end, observed)
    return end + timedelta(days=90)
