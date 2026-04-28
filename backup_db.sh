#!/bin/bash
# Quick backup of PostgreSQL database (Docker)
# Usage: bash backup_db.sh

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$(dirname "$0")/backups"
mkdir -p "$BACKUP_DIR"

docker compose exec -T postgres pg_dumpall -U postgres > "$BACKUP_DIR/backup_$TIMESTAMP.sql"

echo "Backup saved to: $BACKUP_DIR/backup_$TIMESTAMP.sql"
