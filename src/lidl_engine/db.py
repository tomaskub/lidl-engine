"""Versioned migrations and short-lived PostgreSQL connections."""

from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from .config import Settings


@contextmanager
def connect(settings: Settings) -> Iterator[psycopg.Connection[dict[str, Any]]]:
    with psycopg.connect(
        settings.database_url, row_factory=dict_row, autocommit=True, connect_timeout=5
    ) as conn:
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(settings.schema)))
        yield conn


def migrate(settings: Settings) -> None:
    with connect(settings) as conn, conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(257001)")
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY)")
        for path in sorted(
            files("lidl_engine").joinpath("migrations").iterdir(), key=lambda p: p.name
        ):
            if not path.name.endswith(".sql"):
                continue
            if not conn.execute(
                "SELECT 1 FROM schema_migrations WHERE name=%s", (path.name,)
            ).fetchone():
                conn.execute(path.read_text())
                conn.execute("INSERT INTO schema_migrations VALUES (%s)", (path.name,))


def required_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        raise RuntimeError("Expected database row was not returned")
    return row
