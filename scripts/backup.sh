#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
backup_root=${1:?Usage: scripts/backup.sh /absolute/path/to/backups}
mkdir -p "$backup_root"
backup_root=$(cd "$backup_root" && pwd)
backup_name=$(date -u +%Y%m%dT%H%M%SZ)
docker compose --profile collection run --rm -T --user root \
  -v "$backup_root:/backups" collector lidl-engine backup "/backups/$backup_name"
printf '%s\n' "$backup_root/$backup_name"
