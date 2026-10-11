# Lidl Engine

A private Polish desktop browser for Lidl Poland grocery offers. The collector selects the first regular Gazetka, retains original pages, generates Polish descriptions, and extracts structured offers through separately configured OpenRouter batch models. The web process reads PostgreSQL and stays available while collection runs or fails.

The behavior is defined in [the accepted PRD](docs/prd.md) and [PER-25](https://linear.app/tmk-personal-automation/issue/PER-25/implement-lidl-engine-first-release-offer-collection-and-desktop). See [the glossary](GLOSSARY.md) and [the extraction ADR](docs/adr/0001-two-stage-flyer-extraction.md).

## Run on Ubuntu

Install Docker Engine and Compose. Clone this repository to `/opt/lidl-engine`, then:

```sh
cp .env.example .env
# Set POSTGRES_PASSWORD and the matching URL-encoded DATABASE_URL password.
# Set OPENROUTER_API_KEY, DESCRIPTION_MODEL and EXTRACTION_MODEL for live collection.
# Set LIDL_BIND_ADDRESS to this server's household LAN IP.
chmod 600 .env
docker compose build
docker compose up -d web
```

Open `http://<household-server-ip>:8000/` on the household network. The app has no login. The default binding is localhost; set the household LAN address before opening it from another device. PostgreSQL has no published port. Database and evidence volumes persist through container recreation. `docker compose down` preserves them; `down -v` deletes them.

The migration service applies numbered SQL migrations before web startup. Each migration and its version record commit in one transaction under a database lock. Applied migrations are not rerun.

## Refresh and recover

```sh
docker compose --profile collection run --rm collector
```

The same public command is `lidl-engine refresh`. Exit codes are 0 for complete collection, 1 for incomplete collection, and 2 when another collector or maintenance operation holds the lock. Successful pages publish independently, including successful pages with no offers. Failed rereads preserve their previous published occurrences. The UI shows selected flyer, coverage, completeness, failures, last full success and overdue collection.

Every refresh downloads source images and checks their SHA-256 content revisions. Changed URL signatures alone do not invalidate cached work. Description and extraction contracts include their model, prompt, output contract and provider configuration. Extraction additionally depends on the exact saved description. Interpretation runs again from retained extraction on refresh. After changing normalization, use `lidl-engine reprocess` to reinterpret all retained published revisions without new inference. It preserves original observation times and cannot restore audit-only withdrawn occurrences.

Batch IDs, individual results and raw provider evidence live in PostgreSQL. After interruption, refresh polls an existing batch instead of submitting it again. A transient failed inference can make an initial attempt plus at most three retries. Polling does not consume inference retries. Authentication failure stops the run.

If submission returns no response, the app cannot determine whether OpenRouter accepted it. It leaves an explicit `submission-unknown` checkpoint instead of automatically duplicating paid work. Find the accepted batch in OpenRouter and read the task numbers from its custom IDs, for example `page-1-42`, then:

```sh
docker compose --profile collection run --rm collector lidl-engine attach-batch batch_id 42
```

If no batch was accepted, an operator can clear only the affected `submission-unknown` task rows' `batch_id` to SQL NULL after checking the provider. A subsequent refresh will retry. Missing configuration does not create ambiguous checkpoints.

The batch boundary follows the [OpenRouter Batch API contract](https://github.com/OpenRouterTeam/docs/blob/main/batch-quickstart.mdx). Choose models with batch endpoints and a provider that accepts public image URLs. The saved image is the original inspection evidence; the description stage cannot recover source facts it missed. No production credentials or paid requests are needed for fixture tests.

## Weekly schedule

Adjust the service's `WorkingDirectory` if installed elsewhere, then:

```sh
sudo cp deploy/lidl-engine.service deploy/lidl-engine.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lidl-engine.timer
systemctl list-timers lidl-engine.timer
```

The timer runs Wednesday at 06:00 in `Europe/Warsaw`, including daylight-saving transitions. `Persistent=true` catches a missed invocation after downtime. Completion targets the following day at 06:00 for scheduled runs. Manual runs target 24 hours after their start. A resumed incomplete flyer keeps its original deadline. A newly selected flyer gets a fresh target. Overdue collection remains visible and does not stop the browser. PostgreSQL advisory locking prevents manual and scheduled runs from overlapping.

## Backup and restore

```sh
scripts/backup.sh /absolute/path/to/backups
```

This creates a timestamped directory with a custom-format PostgreSQL dump, evidence archive and SHA-256 checksums. The backup holds the same database lock as collection throughout the dump and evidence copy. Keep `.env` separately in protected server configuration; these archives do not include credentials.

To restore, stop the timer and collection service, start the database, and replace the application database and evidence from the selected backup:

```sh
sudo systemctl stop lidl-engine.timer lidl-engine.service
docker compose up -d db
scripts/restore.sh /absolute/path/to/backups/<timestamp>
sudo systemctl start lidl-engine.timer
```

Restoration verifies archive checksums, restores PostgreSQL, validates content-addressed evidence, applies any newer migrations, and starts web again. It replaces database contents. Existing unreferenced image files remain until cleanup; they cannot create browser records. Use the same application version or a newer version with compatible migrations.

## Local verification

Install uv and Python 3.12. Use a dedicated test database, never the household database:

```sh
uv sync --frozen
docker run -d --name lidl-engine-test -e POSTGRES_PASSWORD=test-only \
  -e POSTGRES_DB=lidl_test -p 127.0.0.1:55432:5432 postgres:17-alpine
export TEST_DATABASE_URL=postgresql://postgres:test-only@127.0.0.1:55432/lidl_test
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run playwright install chromium
uv run pytest
# Each workflow test creates an isolated schema and applies the actual migrations.
DATABASE_URL="$TEST_DATABASE_URL" uv run lidl-engine migrate
DATABASE_URL="$TEST_DATABASE_URL" uv run lidl-engine migrate
LIDL_ENV_FILE=.env.example docker compose --env-file .env.example config --quiet
docker build -t lidl-engine:verify .
```

The collection-to-browser harness drives the public refresh command with saved HTTP responses, real PostgreSQL, isolated evidence storage and controlled time. It keeps interpretation, reconciliation, storage and Flask rendering real. `tests/test_workflow.py` is the smallest complete path. Other scenarios cover date rules, categories, conflict context, source replacement, retries, interruption, retention and 1,000 rows. A Chromium check exercises HTMX updates, URL navigation and source previews loaded on demand.

GitHub Actions runs the locked dependencies, Ruff, mypy, migrations, pytest with PostgreSQL and Chromium, Compose validation and the production image build on pushes and pull requests. Hosted execution requires pushing this branch.

## Launch verification

Fixture tests verify application behavior. Launch still requires the original-image quality evaluation and household-network performance measurements described in [the verification guide](docs/verification/launch.md). They are separate checks; this implementation does not report fabricated accuracy, cost or deployment measurements.
