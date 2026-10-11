"""Public refresh workflow. All external responses and time enter at this boundary."""

import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from psycopg.types.json import Jsonb

from . import extraction, source
from .config import Settings
from .db import connect, lock_collection, required_row
from .domain import Extraction, fingerprint, normalize
from .extraction import AuthenticationFailure
from .repository import Connection, cleanup, publish, select_flyer

LOG = logging.getLogger(__name__)


def retry[T](operation: Callable[[], T], sleep: Callable[[float], None]) -> T:
    for attempt in range(4):
        try:
            return operation()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                raise AuthenticationFailure("Source or provider authentication failed") from None
            if exc.response.status_code not in (408, 429) and exc.response.status_code < 500:
                raise
            if attempt == 3:
                raise
        except httpx.TransportError:
            if attempt == 3:
                raise
        sleep(min(2**attempt, 30))
    raise RuntimeError("Unreachable retry state")


def safe_error(exc: Exception) -> str:
    # UI messages never copy URLs, response bodies, database DSNs or credentials.
    if isinstance(exc, AuthenticationFailure):
        return "Błąd uwierzytelnienia źródła lub dostawcy. Zbieranie zatrzymano."
    return "Nie udało się przetworzyć danych. Szczegóły w logach serwera."


def save_image(root: Path, content: bytes) -> str:
    import hashlib

    name = hashlib.sha256(content).hexdigest() + ".image"
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / (name + ".part")
    temporary.write_bytes(content)
    temporary.replace(root / name)
    return name


def refresh(
    settings: Settings,
    client: httpx.Client,
    now: Callable[[], datetime],
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    with connect(settings) as conn:
        if not lock_collection(conn):
            return 2
        started = now()
        # A resumed run keeps its original deadline rather than resetting an overdue target.
        previous = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        deadline = (
            previous["deadline"]
            if previous and previous["status"] in ("running", "incomplete")
            else started.astimezone(ZoneInfo("Europe/Warsaw")) + timedelta(days=1)
        )
        run_id = required_row(
            conn.execute(
                """INSERT INTO runs (started_at,deadline,status)
                   VALUES (%s,%s,'running') RETURNING id""",
                (started, deadline),
            ).fetchone()
        )["id"]
        errors: list[str] = []
        processed = 0
        try:
            flyer = retry(lambda: source.discover(client, now()), sleep)
            if not flyer["year_explicit"]:
                known = conn.execute(
                    "SELECT issue_year FROM flyers WHERE slug=%s ORDER BY id DESC LIMIT 1",
                    (flyer["slug"],),
                ).fetchone()
                if known:
                    flyer["issue_year"] = known["issue_year"]
            flyer["id"] = select_flyer(conn, flyer)
            conn.execute("UPDATE runs SET flyer_id=%s WHERE id=%s", (flyer["id"], run_id))
            manifest = retry(lambda: source.metadata(client, flyer), sleep)
            flyer.update(manifest)
            flyer["id"] = select_flyer(conn, flyer)
            conn.execute("UPDATE runs SET flyer_id=%s WHERE id=%s", (flyer["id"], run_id))
            if previous and previous.get("flyer_id") != flyer["id"]:
                conn.execute(
                    "UPDATE runs SET deadline=%s WHERE id=%s",
                    (started.astimezone(ZoneInfo("Europe/Warsaw")) + timedelta(days=1), run_id),
                )
            conn.execute(
                "UPDATE flyers SET valid_from=%s,valid_to=%s WHERE id=%s",
                (flyer["valid_from"], flyer["valid_to"], flyer["id"]),
            )
            known_numbers = {
                row["number"]
                for row in conn.execute(
                    "SELECT number FROM pages WHERE flyer_id=%s", (flyer["id"],)
                ).fetchall()
            }
            manifest_numbers = {page["number"] for page in flyer["pages"]}
            for missing in sorted(known_numbers - manifest_numbers):
                errors.append(f"Strona {missing}: brak w metadanych, poprzednie oferty zachowano.")
            conn.execute(
                "UPDATE runs SET expected=%s WHERE id=%s",
                (len(known_numbers | manifest_numbers), run_id),
            )
            pages = []
            for page in flyer["pages"]:
                try:
                    page_id = required_row(
                        conn.execute(
                            """INSERT INTO pages (flyer_id,number,url) VALUES (%s,%s,%s)
                        ON CONFLICT (flyer_id,number) DO UPDATE SET url=EXCLUDED.url
                        RETURNING id""",
                            (flyer["id"], page["number"], page["url"]),
                        ).fetchone()
                    )["id"]
                    response = retry(partial(fetch_image, client, page["image_url"]), sleep)
                    path = save_image(settings.evidence_dir, response.content)
                    revision = required_row(
                        conn.execute(
                            """INSERT INTO revisions
                        (page_id,content_hash,image_path,mime_type,observed_at)
                        VALUES (%s,%s,%s,%s,%s)
                        ON CONFLICT (page_id,content_hash)
                        DO UPDATE SET observed_at=EXCLUDED.observed_at
                        RETURNING id""",
                            (
                                page_id,
                                path.split(".")[0],
                                path,
                                response.headers.get("content-type", "image/jpeg").split(";")[0],
                                now(),
                            ),
                        ).fetchone()
                    )["id"]
                    pages.append({**page, "revision_id": revision})
                except AuthenticationFailure:
                    raise
                except Exception as exc:
                    LOG.exception("Source page retrieval failed")
                    errors.append(f"Strona {page['number']}: {safe_error(exc)}")
            descriptions = process_stage(
                conn, settings, client, pages, "description", now, sleep, errors
            )
            prepared = []
            for page in pages:
                if page["revision_id"] in descriptions:
                    prepared.append({**page, "description": descriptions[page["revision_id"]]})
            outputs = process_stage(
                conn, settings, client, prepared, "extraction", now, sleep, errors
            )
            for page in prepared:
                output = outputs.get(page["revision_id"])
                if output is None:
                    continue
                try:
                    parsed = Extraction.model_validate_json(output)
                    facts = [
                        fact
                        for offer in parsed.offers
                        if (fact := normalize(offer, flyer)) is not None
                    ]
                    publish(conn, page["revision_id"], facts, now())
                    processed += 1
                    conn.execute("UPDATE runs SET processed=%s WHERE id=%s", (processed, run_id))
                except Exception as exc:
                    LOG.exception("Offer interpretation/publication failed")
                    errors.append(f"Strona {page['number']}: {safe_error(exc)}")
            cleanup(conn, settings.evidence_dir, now())
        except Exception as exc:
            LOG.exception("Collection stopped")
            errors.append(safe_error(exc))
        status = "incomplete" if errors else "complete"
        conn.execute(
            "UPDATE runs SET status=%s,finished_at=%s,errors=%s WHERE id=%s",
            (status, now(), Jsonb(errors), run_id),
        )
        return 1 if errors else 0


def fetch_image(client: httpx.Client, url: str) -> httpx.Response:
    response = client.get(url)
    response.raise_for_status()
    if not response.content or not response.headers.get("content-type", "").startswith("image/"):
        raise ValueError("Missing original image")
    return response


def process_stage(
    conn: Connection,
    settings: Settings,
    client: httpx.Client,
    pages: list[dict[str, Any]],
    stage: str,
    now: Callable[[], datetime],
    sleep: Callable[[float], None],
    errors: list[str],
) -> dict[int, str]:
    configuration = extraction.stage_configuration(settings, stage)
    tasks = {}
    outputs = {}
    for page in pages:
        key = fingerprint(
            [
                extraction.contract(settings, configuration),
                page.get("description") if stage == "extraction" else None,
            ]
        )
        task = required_row(
            conn.execute(
                """INSERT INTO tasks (revision_id,stage,contract) VALUES (%s,%s,%s)
            ON CONFLICT (revision_id,stage,contract) DO UPDATE SET contract=EXCLUDED.contract
            RETURNING *""",
                (page["revision_id"], stage, key),
            ).fetchone()
        )
        if task["result"] is not None:
            outputs[page["revision_id"]] = task["result"]
        else:
            tasks[task["id"]] = {**task, "page": page}
    # Each initial failed inference is retried at most three times, separately from polling.
    for attempt in range(4):
        if not tasks:
            break
        new = [task for task in tasks.values() if not task["batch_id"]]
        if new:
            if not settings.openrouter_key or not configuration.model:
                errors.append("Brak konfiguracji dostawcy przetwarzania. Zbieranie niekompletne.")
                break
            ids = [task["id"] for task in new]
            # No automatic resubmission after an ambiguous POST or crash before checkpointing.
            conn.execute("UPDATE tasks SET batch_id='submission-unknown' WHERE id=ANY(%s)", (ids,))
            requests = [
                {
                    "custom_id": f"page-{task['page']['number']}-{task['id']}",
                    "body": extraction.request_body(
                        configuration,
                        task["page"]["image_url"]
                        if stage == "description"
                        else task["page"]["description"],
                    ),
                }
                for task in new
            ]
            try:
                batch = extraction.submit(client, settings, configuration, requests)
                batch_id = batch["id"]
                conn.execute("UPDATE tasks SET batch_id=%s WHERE id=ANY(%s)", (batch_id, ids))
                for task in new:
                    task["batch_id"] = batch_id
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403):
                    conn.execute("UPDATE tasks SET batch_id=NULL WHERE id=ANY(%s)", (ids,))
                    raise AuthenticationFailure("Provider authentication failed") from None
                # An HTTP rejection did not accept a batch. Retry only transient rejections.
                conn.execute("UPDATE tasks SET batch_id=NULL WHERE id=ANY(%s)", (ids,))
                if (
                    exc.response.status_code in (408, 429) or exc.response.status_code >= 500
                ) and attempt < 3:
                    sleep(2**attempt)
                    continue
                errors.append(safe_error(exc))
                break
            except Exception:
                LOG.exception("Batch submission requires reconciliation")
                errors.append(
                    "Nieznany wynik wysłania zadania. Sprawdź OpenRouter "
                    "i użyj attach-batch przed ponowieniem."
                )
                break
        batch_ids = {task["batch_id"] for task in tasks.values()}
        for batch_id in batch_ids:
            selected = {key: task for key, task in tasks.items() if task["batch_id"] == batch_id}
            if batch_id == "submission-unknown":
                errors.append("Zadanie bez potwierdzonego identyfikatora. Wymagane attach-batch.")
                for key in selected:
                    del tasks[key]
                continue
            try:
                while True:
                    batch = retry(partial(extraction.poll, client, settings, batch_id), sleep)
                    if batch["status"] in {"completed", "failed", "cancelled", "expired"}:
                        break
                    sleep(settings.poll_seconds)
                extraction.check_authentication(batch.get("error"))
                results = batch.get("results") or []
                by_id = {}
                for item in results:
                    custom_id = item.get("custom_id", "")
                    if custom_id in by_id:
                        raise ValueError("Duplicate batch custom_id")
                    by_id[custom_id] = item
                for key, task in selected.items():
                    custom_id = f"page-{task['page']['number']}-{key}"
                    try:
                        item = by_id.get(custom_id, {})
                        text = extraction.result_text(item)
                        if stage == "extraction":
                            Extraction.model_validate_json(text)
                        conn.execute(
                            "UPDATE tasks SET result=%s,evidence=%s WHERE id=%s",
                            (text, Jsonb(item), key),
                        )
                        outputs[task["revision_id"]] = text
                        del tasks[key]
                    except AuthenticationFailure:
                        raise
                    except ValueError:
                        conn.execute(
                            "UPDATE tasks SET batch_id=NULL,evidence=%s WHERE id=%s",
                            (Jsonb(by_id.get(custom_id, batch)), key),
                        )
                        task["batch_id"] = None
                        if attempt == 3:
                            errors.append(
                                f"Strona {task['page']['number']}: "
                                f"nieudany etap {stage} po 4 próbach."
                            )
            except AuthenticationFailure:
                raise
            except Exception as exc:
                LOG.exception("Batch polling failed; preserving batch checkpoint")
                errors.append(safe_error(exc))
                # Resume the existing batch next invocation after polling failure.
                for key in selected:
                    tasks.pop(key, None)
    return outputs
