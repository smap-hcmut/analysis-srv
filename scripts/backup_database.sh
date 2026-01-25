#!/bin/bash
# Database backup script for Analytics Service migration
# Usage: ./scripts/backup_database.sh [backup_dir]

set -e

# Configuration
BACKUP_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/analytics_backup_${TIMESTAMP}.sql"

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Parse database URL
DB_URL="${DATABASE_URL_SYNC:-postgresql://dev:dev123@localhost:5432/analytics_dev}"

# Extract components from URL
DB_HOST=$(echo $DB_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=$(echo $DB_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_NAME=$(echo $DB_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
DB_USER=$(echo $DB_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
DB_PASS=$(echo $DB_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')

echo "=============================================="
echo "Analytics Database Backup"
echo "=============================================="
echo "Timestamp: ${TIMESTAMP}"
echo "Database: ${DB_NAME}"
echo "Host: ${DB_HOST}:${DB_PORT}"
echo "Backup file: ${BACKUP_FILE}"
echo "=============================================="

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Perform backup
echo "Starting backup..."
PGPASSWORD="${DB_PASS}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --format=plain \
    --no-owner \
    --no-privileges \
    > "${BACKUP_FILE}"

# Compress backup
echo "Compressing backup..."
gzip "${BACKUP_FILE}"
BACKUP_FILE="${BACKUP_FILE}.gz"

# Calculate size
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)

echo "=============================================="
echo "Backup completed successfully!"
echo "File: ${BACKUP_FILE}"
echo "Size: ${BACKUP_SIZE}"
echo "=============================================="

# Keep only last 7 backups
echo "Cleaning old backups (keeping last 7)..."
ls -t "${BACKUP_DIR}"/analytics_backup_*.sql.gz 2>/dev/null | tail -n +8 | xargs -r rm -f

echo "Done."
