#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

VOLUME_NAME="${1:-${STATS_VOLUME_NAME:-stats_stats_data}}"
BACKUP_DIR="${2:-backups}"
mkdir -p "$BACKUP_DIR"

if ! docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1; then
  echo "Error: docker volume '$VOLUME_NAME' was not found." >&2
  echo "If your compose project name is different, pass the volume name as the first arg." >&2
  exit 1
fi

TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
BACKUP_PATH="${BACKUP_DIR}/usage-${TIMESTAMP}.db"

docker run --rm \
  -v "${VOLUME_NAME}:/data:ro" \
  -v "${PROJECT_ROOT}/${BACKUP_DIR}:/backup" \
  alpine:3.20 \
  sh -c "cp /data/usage.db /backup/usage-${TIMESTAMP}.db"

echo "Saved: ${BACKUP_PATH}"
