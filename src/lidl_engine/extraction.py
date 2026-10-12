"""Two independently configured OpenRouter batch stages."""

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from .config import Settings
from .domain import Extraction, fingerprint

API_URL = "https://openrouter.ai/api/v1"
DESCRIPTION_PROMPT = """Opisz po polsku wszystkie oferty spożywcze i napoje na stronie gazetki,
w tym alkohol, zwykłe ceny oraz promocje obejmujące kategorie. Zachowaj dokładne nazwy,
marki, wielkości, warianty, kwoty i jednostki cen, zakres rabatu, wymagane ilości,
ilości płatne i otrzymywane, Lidl Plus, kupony, limity, kaucje, daty i drobny druk.
Nie obliczaj cen ani oszczędności. Nie dopisuj informacji nieobecnych na obrazie.
Brak informacji oznacza nieznane, nie oznacza braku warunku. Jeśli nie ma ofert,
napisz: Brak kwalifikujących się ofert spożywczych."""
EXTRACTION_PROMPT = """Wyodrębnij wyłącznie fakty podane w polskim opisie strony gazetki.
Zwróć obiekt JSON zgodny ze schematem poniżej. Nazwy i opisy pozostają po polsku.
Uwzględnij zwykłe ceny, napoje, alkohol i promocje kategorii. Odrzuć towary niespożywcze
oraz reklamy bez ceny lub korzyści. Każdy niezależny warunek ceny to oddzielna oferta.
Nie wyliczaj kwot. Nieznane wartości to null; nieznane kategorie to [].
Wymagania Lidl Plus i kuponu są null, chyba że źródło stwierdza ich obecność lub brak.
Daty jawne zapisz YYYY-MM-DD gdy podano rok, inaczej DD.MM. Nie wnioskuj dat z okresu
gazetki. Zachowaj oryginalne brzmienie dat. Ceny zawierają jednostkę lub ilość.
Kategorie: bakery, alcoholic beverages, non-alcoholic beverages, fruits, vegetables,
meats, seafood, dairy, pantry items, ready made snacks. Kawa/herbata do parzenia:
pantry items; gotowe do picia: non-alcoholic beverages. Oferta może mieć kilka kategorii.
Nie sugeruj, że dane zweryfikowano. Użyj offers: [] jeśli nie ma ofert.
Schemat: """ + json.dumps(Extraction.model_json_schema(), ensure_ascii=False)


@dataclass(frozen=True)
class StageConfiguration:
    name: str
    model: str
    prompt: str


def stage_configuration(settings: Settings, name: str) -> StageConfiguration:
    stages = {
        "description": StageConfiguration(
            "description", settings.description_model, DESCRIPTION_PROMPT
        ),
        "extraction": StageConfiguration(
            "extraction", settings.extraction_model, EXTRACTION_PROMPT
        ),
    }
    return stages[name]


def contract(settings: Settings, stage: StageConfiguration) -> str:
    return fingerprint(
        {
            "model": stage.model,
            "prompt": stage.prompt,
            "provider": settings.provider,
            "max_tokens": 16000,
        }
    )


def request_body(stage: StageConfiguration, input_value: str) -> dict[str, Any]:
    if stage.name == "description":
        content: Any = [
            {"type": "text", "text": stage.prompt},
            {"type": "image_url", "image_url": {"url": input_value}},
        ]
    else:
        content = stage.prompt + "\nOpis strony:\n" + input_value
    body: dict[str, Any] = {"max_tokens": 16000, "messages": [{"role": "user", "content": content}]}
    if stage.name == "extraction":
        body["response_format"] = {"type": "json_object"}
    return body


def submit(
    client: httpx.Client,
    settings: Settings,
    stage: StageConfiguration,
    requests: list[dict[str, Any]],
) -> dict[str, Any]:
    model = stage.model
    if not settings.openrouter_key or not model:
        raise ValueError("Configure OpenRouter key and both stage models")
    payload: dict[str, Any] = {
        "endpoint": "/v1/chat/completions",
        "model": model.removesuffix(":batch"),
        "completion_window": "24h",
    }
    if settings.provider:
        payload["provider"] = {"only": [settings.provider]}
    payload["requests"] = requests
    response = client.post(
        f"{API_URL}/batches",
        json=payload,
        headers={"Authorization": f"Bearer {settings.openrouter_key}"},
    )
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


def poll(client: httpx.Client, settings: Settings, batch_id: str) -> dict[str, Any]:
    response = client.get(
        f"{API_URL}/batches/{quote(batch_id, safe='')}",
        headers={"Authorization": f"Bearer {settings.openrouter_key}"},
    )
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


def result_text(item: dict[str, Any]) -> str:
    check_authentication(item.get("error"))
    response = item.get("response") or {}
    status = response.get("status_code")
    if status in (401, 403):
        raise AuthenticationFailure("Provider authentication failed")
    choices = (response.get("body") or {}).get("choices") or []
    if item.get("error") or status != 200 or not choices:
        raise ValueError("Failed or missing provider result")
    choice = choices[0]
    text = choice.get("message", {}).get("content")
    if choice.get("finish_reason") != "stop" or not isinstance(text, str) or not text.strip():
        raise ValueError("Empty or truncated provider result")
    return text.strip()


class AuthenticationFailure(RuntimeError):
    pass


def check_authentication(error: Any) -> None:
    if isinstance(error, dict) and str(error.get("code", "")).casefold() in {
        "401",
        "403",
        "authentication_error",
        "invalid_api_key",
        "authentication_failed",
    }:
        raise AuthenticationFailure("Provider authentication failed")
