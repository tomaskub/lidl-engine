#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
backup_source=${1:?Usage: scripts/restore.sh /absolute/path/to/backup}
backup_source=$(cd "$backup_source" && pwd)
# Stop the host timer and collector service before running this script.
docker compose stop web
docker compose --profile collection run --rm -T --no-deps --user root \
  -v "$backup_source:/backup:ro" collector lidl-engine restore /backup
docker compose run --rm migrate
docker compose up -d web
