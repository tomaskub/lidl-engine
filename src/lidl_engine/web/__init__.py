from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from flask import Flask, Response, abort, render_template, request, send_file

from ..config import Settings
from ..db import connect
from ..domain import CATEGORIES
from ..repository import browse, diagnostics

WARSAW = ZoneInfo("Europe/Warsaw")


def create_app(
    settings: Settings | None = None, *, now: Callable[[], datetime] | None = None
) -> Flask:
    config = settings or Settings.from_env()
    clock = now or (lambda: datetime.now(UTC))
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

    @app.template_filter("price")
    def price(value: str) -> str:
        return format(Decimal(value), ".2f").replace(".", ",")

    @app.template_filter("localtime")
    def localtime(value: datetime) -> str:
        return value.astimezone(WARSAW).strftime("%d.%m.%Y %H:%M")

    @app.after_request
    def headers(response: Response) -> Response:
        response.headers["Vary"] = "HX-Request"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index() -> Any:
        query = request.args.get("q", "").strip()
        category = request.args.get("category", "")
        sort = request.args.get("sort", "name")
        day = request.args.get("date", clock().astimezone(WARSAW).date().isoformat())
        try:
            parsed = date.fromisoformat(day)
            if (
                day != parsed.isoformat()
                or len(query) > 500
                or sort not in {"name", "category", "end"}
                or (category and category not in CATEGORIES)
            ):
                raise ValueError("Invalid browser parameters")
        except ValueError:
            return render_template("error.html", message="Nieprawidłowe filtry lub data."), 400
        try:
            with connect(config) as conn:
                offers = browse(
                    conn,
                    today=clock().astimezone(WARSAW).date(),
                    day=day,
                    query=query,
                    category=category,
                    sort=sort,
                )
                status = diagnostics(conn)
        except psycopg.Error:
            app.logger.exception("Catalog unavailable")
            return render_template(
                "error.html", message="Dane chwilowo niedostępne. Spróbuj ponownie później."
            ), 503
        latest = status["run"]
        overdue = bool(latest and latest["status"] != "complete" and clock() > latest["deadline"])
        template = "results.html" if request.headers.get("HX-Request") == "true" else "index.html"
        return render_template(
            template,
            offers=offers,
            status=status,
            overdue=overdue,
            query=query,
            category=category,
            sort=sort,
            day=day,
            categories=CATEGORIES,
        )

    @app.get("/evidence/<int:revision_id>")
    def evidence(revision_id: int) -> Any:
        with connect(config) as conn:
            row = conn.execute(
                """SELECT r.* FROM revisions r WHERE r.id=%s AND EXISTS
                (SELECT 1 FROM occurrences c WHERE c.revision_id=r.id AND c.retain_until >= %s)""",
                (revision_id, clock().astimezone(WARSAW).date()),
            ).fetchone()
        if not row:
            abort(404)
        path = (config.evidence_dir / row["image_path"]).resolve()
        if not path.is_relative_to(config.evidence_dir.resolve()) or not path.is_file():
            abort(404)
        return send_file(path, mimetype=row["mime_type"])

    @app.get("/health")
    def health() -> Any:
        try:
            with connect(config) as conn:
                conn.execute("SELECT 1 FROM schema_migrations LIMIT 1")
            return {"status": "ok"}
        except psycopg.Error:
            return {"status": "unavailable"}, 503

    return app
