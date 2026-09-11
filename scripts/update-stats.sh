#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

VOLUME_NAME="${1:-${STATS_VOLUME_NAME:-stats_stats_data}}"
BACKUP_DIR="${2:-backups}"

./scripts/stats-backup.sh "$VOLUME_NAME" "$BACKUP_DIR"

docker compose pull
docker compose up -d --build

echo "Deploy complete."
echo "If your dashboard settings were reset, restore from latest backup:"
echo "  ./scripts/stats-restore.sh \"$VOLUME_NAME\" latest"
echo "  docker compose restart stats"
