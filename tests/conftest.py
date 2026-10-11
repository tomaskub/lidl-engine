import base64
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
import psycopg
import pytest
from psycopg import sql

from lidl_engine.config import Settings
from lidl_engine.db import migrate

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 12, 8, tzinfo=UTC)


@pytest.fixture
def settings(tmp_path):
    # A dedicated test database is required. Never default to production credentials.
    url = os.environ["TEST_DATABASE_URL"]
    schema = "test_" + tmp_path.name.replace("-", "_")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    config = Settings(
        database_url=url,
        evidence_dir=tmp_path / "evidence",
        schema=schema,
        description_model="fixture/vision",
        extraction_model="fixture/text",
        openrouter_key="fixture-secret",
        poll_seconds=0,
    )
    migrate(config)
    yield config
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


class ExternalResponses:
    def __init__(self):
        self.listing = (FIXTURES / "listing.html").read_text()
        self.metadata = json.loads((FIXTURES / "metadata.json").read_text())
        self.images = {
            1: base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1kAAAAASUVORK5CYII="
            )
        }
        self.extractions = {1: json.loads((FIXTURES / "extraction.json").read_text())}
        self.description = (FIXTURES / "description.txt").read_text()
        self.requests = []
        self.batches = {}
        self.failures = {}
        self.pending = False

    def respond(self, request):
        self.requests.append(request)
        path = request.url.path
        failure = self.failures.get(path)
        if failure:
            return httpx.Response(failure, request=request)
        if path.endswith("nasze-gazetki"):
            return httpx.Response(200, text=self.listing)
        if request.url.host == "endpoints.leaflets.schwarz":
            return httpx.Response(200, json=self.metadata)
        if request.url.host == "imgproxy.leaflets.schwarz":
            number = int(path.split("page-")[-1].split(".")[0])
            return httpx.Response(
                200, content=self.images[number], headers={"Content-Type": "image/png"}
            )
        if request.method == "POST" and path.endswith("batches"):
            payload = json.loads(request.content)
            batch_id = f"batch-{len(self.batches) + 1}"
            results = []
            for item in payload["requests"]:
                number = int(item["custom_id"].split("-")[1])
                content = (
                    self.description
                    if isinstance(item["body"]["messages"][0]["content"], list)
                    else json.dumps(self.extractions[number], ensure_ascii=False)
                )
                results.append(
                    {
                        "custom_id": item["custom_id"],
                        "response": {
                            "status_code": 200,
                            "body": {
                                "choices": [
                                    {"finish_reason": "stop", "message": {"content": content}}
                                ]
                            },
                        },
                    }
                )
            self.batches[batch_id] = {"id": batch_id, "status": "completed", "results": results}
            return httpx.Response(202, json={"id": batch_id, "status": "validating"})
        if "/batches/" in path:
            batch = self.batches[path.rsplit("/", 1)[-1]]
            return httpx.Response(
                200,
                json={**batch, "status": "in_progress", "results": None} if self.pending else batch,
            )
        raise AssertionError(f"Unexpected external request: {request.method} {request.url}")

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.respond))

    @property
    def submissions(self):
        return [r for r in self.requests if r.method == "POST"]


@pytest.fixture
def external():
    return ExternalResponses()
