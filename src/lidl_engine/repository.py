"""Atomic page publication, source support, browsing queries and retention."""

from datetime import date, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .db import required_row
from .domain import Extraction, conflict_identity, fold, normalize, offer_identity, retention_until

Connection = psycopg.Connection[dict[str, Any]]


def publish(conn: Connection, revision_id: int, facts: list[dict[str, Any]], now: datetime) -> None:
    with conn.transaction():
        conn.execute(
            """UPDATE occurrences SET active=false WHERE revision_id IN
                     (SELECT r.id FROM revisions r JOIN revisions target ON r.page_id=target.page_id
                      WHERE target.id=%s)""",
            (revision_id,),
        )
        for offer in facts:
            identity = offer_identity(offer)
            conn.execute(
                """INSERT INTO offers (id, conflict_key, facts) VALUES (%s,%s,%s)
                         ON CONFLICT (id) DO NOTHING""",
                (identity, conflict_identity(offer), Jsonb(offer)),
            )
            conn.execute(
                """INSERT INTO occurrences
                         (offer_id, revision_id, facts, observed_at, retain_until)
                         VALUES (%s,%s,%s,%s,%s) ON CONFLICT (offer_id,revision_id)
                         DO UPDATE SET active=true, facts=EXCLUDED.facts,
                         observed_at=EXCLUDED.observed_at, retain_until=EXCLUDED.retain_until""",
                (identity, revision_id, Jsonb(offer), now, retention_until(offer, now.date())),
            )
            for category in offer["categories"]:
                conn.execute(
                    "INSERT INTO offer_categories VALUES (%s,%s) ON CONFLICT DO NOTHING",
                    (identity, category),
                )


def browse(
    conn: Connection, *, today: date, day: str, query: str, category: str, sort: str
) -> list[dict[str, Any]]:
    # Retrieve source-supported records in one consistent query.
    rows = conn.execute(
        """
        SELECT o.id, o.conflict_key, o.facts,
               jsonb_agg(jsonb_build_object('revision_id',r.id,'url',p.url,'facts',c.facts,
                   'flyer_id',p.flyer_id,'number',p.number) ORDER BY p.id) AS sources,
               bool_or(p.flyer_id=s.flyer_id) AS current
        FROM offers o JOIN occurrences c ON c.offer_id=o.id AND c.active
        JOIN revisions r ON r.id=c.revision_id JOIN pages p ON p.id=r.page_id
        LEFT JOIN selection s ON true
        WHERE c.retain_until >= %s
        GROUP BY o.id
        """,
        (today,),
    ).fetchall()
    # Filtering/sorting happens on the server over stored records, never in the browser.
    # At the agreed 1,000-row scale this also keeps Polish normalization independent of extensions.
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        facts = dict(row["facts"])
        facts["categories"] = sorted(
            {category for source in row["sources"] for category in source["facts"]["categories"]}
        )
        row["facts"] = facts
        in_date = (not facts["valid_from"] or facts["valid_from"] <= day) and (
            not facts["valid_to"] or facts["valid_to"] >= day
        )
        if facts["inconsistent_dates"]:
            in_date = False
        texts = [facts["name"], facts["brand"], facts["description"]]
        texts.extend(source["facts"].get("description") for source in row["sources"])
        search_text = fold(" ".join(value for value in texts if value))
        row["matches"] = bool(
            (row["current"] or in_date)
            and fold(query) in search_text
            and (not category or category in facts["categories"])
        )
        row["in_date"] = in_date
        groups.setdefault(row["conflict_key"], []).append(row)
    result_groups = []
    for group in groups.values():
        matches = [r for r in group if r["matches"]]
        if not matches:
            continue
        for row in group:
            row["conflict"] = len(group) > 1
            row["context"] = not row["matches"]
        # The matching variant determines position; context never drags a group out of order.
        key = min(sort_key(row, sort) for row in matches)
        result_groups.append(
            (
                key,
                sorted(group, key=lambda r: (not r["matches"], fold(r["facts"]["name"]), r["id"])),
            )
        )
    return [row for _, group in sorted(result_groups, key=lambda item: item[0]) for row in group]


def sort_key(row: dict[str, Any], sort: str) -> tuple[str, ...]:
    facts = row["facts"]
    name = fold(facts["name"])
    if sort == "category":
        return ("|".join(facts["categories"]) or "~", name, row["id"])
    if sort == "end":
        return (facts["valid_to"] or "9999-12-31", name, row["id"])
    return (name, row["id"])


def diagnostics(conn: Connection) -> dict[str, Any]:
    return {
        "flyer": conn.execute(
            "SELECT f.* FROM flyers f JOIN selection s ON f.id=s.flyer_id"
        ).fetchone(),
        "run": conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone(),
        "successful": conn.execute(
            "SELECT finished_at FROM runs WHERE status='complete' ORDER BY id DESC LIMIT 1"
        ).fetchone(),
    }


def cleanup(conn: Connection, evidence_dir: Path, now: datetime) -> None:
    with conn.transaction():
        conn.execute("DELETE FROM occurrences WHERE retain_until < %s", (now.date(),))
        conn.execute(
            """DELETE FROM offers WHERE NOT EXISTS
                (SELECT 1 FROM occurrences c WHERE c.offer_id=offers.id)"""
        )
        # Keep incomplete task inputs for recovery for 90 days after observation.
        conn.execute(
            """DELETE FROM revisions r WHERE observed_at < %s - interval '90 days'
            AND NOT EXISTS (SELECT 1 FROM occurrences c WHERE c.revision_id=r.id)
            """,
            (now,),
        )
    referenced = {
        r["image_path"] for r in conn.execute("SELECT image_path FROM revisions").fetchall()
    }
    for path in evidence_dir.glob("*.image"):
        if path.name not in referenced:
            path.unlink(missing_ok=True)


def select_flyer(conn: Connection, flyer: dict[str, Any]) -> int:
    with conn.transaction():
        identifier = required_row(
            conn.execute(
                """INSERT INTO flyers (slug,issue_year,title,url,valid_from,valid_to)
               VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (slug,issue_year)
               DO UPDATE SET title=EXCLUDED.title,url=EXCLUDED.url,
               valid_from=COALESCE(EXCLUDED.valid_from,flyers.valid_from),
               valid_to=COALESCE(EXCLUDED.valid_to,flyers.valid_to) RETURNING id""",
                (
                    flyer["slug"],
                    flyer["issue_year"],
                    flyer["title"],
                    flyer["url"],
                    flyer.get("valid_from"),
                    flyer.get("valid_to"),
                ),
            ).fetchone()
        )["id"]
        conn.execute(
            """INSERT INTO selection VALUES (true,%s)
                     ON CONFLICT (id) DO UPDATE SET flyer_id=EXCLUDED.flyer_id""",
            (identifier,),
        )
        return int(identifier)


def reprocess(conn: Connection) -> None:
    # Reinterpret only browsable revisions; audit-only inputs cannot restore withdrawn offers.
    rows = conn.execute("""SELECT r.id, max(c.observed_at) AS observed_at, f.issue_year,
        f.valid_from, f.valid_to, t.result FROM revisions r
        JOIN occurrences c ON c.revision_id=r.id AND c.active
        JOIN pages p ON p.id=r.page_id JOIN flyers f ON f.id=p.flyer_id
        JOIN LATERAL (SELECT result FROM tasks WHERE revision_id=r.id
            AND stage='extraction' AND result IS NOT NULL ORDER BY id DESC LIMIT 1) t ON true
        GROUP BY r.id,f.id,t.result""").fetchall()
    for row in rows:
        extracted = Extraction.model_validate_json(row["result"])
        facts = [fact for offer in extracted.offers if (fact := normalize(offer, row)) is not None]
        publish(conn, row["id"], facts, row["observed_at"])
