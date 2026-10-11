import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx

from .backup import backup, restore
from .collector import refresh
from .config import Settings
from .db import connect, migrate, required_row
from .repository import cleanup, reprocess


def run(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
    now: Callable[[], datetime] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Lidl Engine administration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="Apply versioned SQL migrations")
    commands.add_parser("refresh", help="Discover current flyer and collect or resume its pages")
    commands.add_parser(
        "reprocess", help="Reinterpret retained published extractions without inference"
    )
    commands.add_parser("cleanup", help="Remove evidence outside retention")
    for action in ["backup", "restore"]:
        command = commands.add_parser(action)
        command.add_argument("directory", type=Path)
    attach = commands.add_parser(
        "attach-batch", help="Reconcile an ambiguous OpenRouter submission"
    )
    attach.add_argument("batch_id")
    attach.add_argument("task_ids", type=int, nargs="+")
    args = parser.parse_args(argv)
    settings = settings or Settings.from_env()
    now = now or (lambda: datetime.now(UTC))
    if args.command in {"backup", "restore"}:
        if args.command == "backup":
            backup(settings, args.directory)
        else:
            restore(settings, args.directory)
        return 0
    if args.command == "migrate":
        migrate(settings)
        return 0
    if args.command in {"cleanup", "reprocess"}:
        with connect(settings) as conn:
            if not required_row(
                conn.execute("SELECT pg_try_advisory_lock(257002) AS acquired").fetchone()
            )["acquired"]:
                return 2
            if args.command == "cleanup":
                cleanup(conn, settings.evidence_dir, now())
            else:
                reprocess(conn)
        return 0
    if args.command == "attach-batch":
        with connect(settings) as conn:
            if not required_row(
                conn.execute("SELECT pg_try_advisory_lock(257002) AS acquired").fetchone()
            )["acquired"]:
                return 2
            conn.execute(
                "UPDATE tasks SET batch_id=%s WHERE id=ANY(%s) AND batch_id='submission-unknown'",
                (args.batch_id, args.task_ids),
            )
        return 0
    if client is not None:
        return refresh(settings, client, now, sleep=lambda _: None)
    with httpx.Client(timeout=180, headers={"User-Agent": "LidlEngine/0.1"}) as real_client:
        return refresh(settings, real_client, now)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        code = run()
    except Exception:
        logging.exception("Command failed")
        code = 1
    sys.exit(code)
