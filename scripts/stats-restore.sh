#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

if [ "${1-}" = "" ]; then
  VOLUME_NAME="${STATS_VOLUME_NAME:-stats_stats_data}"
  TARGET="latest"
elif [[ "$1" == *.db ]]; then
  VOLUME_NAME="${STATS_VOLUME_NAME:-stats_stats_data}"
  TARGET="$1"
else
  VOLUME_NAME="$1"
  TARGET="${2:-latest}"
fi

if [ "$TARGET" = "latest" ]; then
  BACKUP_DIR="backups"
  BACKUP_FILE="$(ls -1t "${BACKUP_DIR}"/usage-*.db 2>/dev/null | head -n 1 || true)"
  if [ -z "$BACKUP_FILE" ]; then
    echo "Error: no backups found in '${BACKUP_DIR}'."
    echo "Pass an explicit path: ./scripts/stats-restore.sh <volume-name> <backup-path>"
    exit 1
  fi
else
  BACKUP_FILE="$TARGET"
  if [ ! -f "$BACKUP_FILE" ] && [ -f "${PROJECT_ROOT}/${BACKUP_FILE}" ]; then
    BACKUP_FILE="${PROJECT_ROOT}/${BACKUP_FILE}"
  fi
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Error: backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

BACKUP_DIR_PATH="$(cd "$(dirname "$BACKUP_FILE")" && pwd)"
BACKUP_BASENAME="$(basename "$BACKUP_FILE")"

if ! docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1; then
  echo "Error: docker volume '$VOLUME_NAME' was not found." >&2
  echo "If your compose project name is different, pass the volume name as the first arg." >&2
  exit 1
fi

docker run --rm \
  -v "${VOLUME_NAME}:/data" \
  -v "${BACKUP_DIR_PATH}:/backup:ro" \
  alpine:3.20 \
  sh -c "cp /backup/${BACKUP_BASENAME} /data/usage.db"

echo "Restored: ${BACKUP_FILE} -> ${VOLUME_NAME}:/data/usage.db"
