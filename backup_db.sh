#!/bin/bash
# Quick backup of local PostgreSQL database
# Usage: bash backup_db.sh

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="d:/D/e_commerce_plateform/backups"
mkdir -p "$BACKUP_DIR"

pg_dump -U postgres ecommerce_multitenancy > "$BACKUP_DIR/backup_$TIMESTAMP.sql"

echo "Backup saved to: $BACKUP_DIR/backup_$TIMESTAMP.sql"
