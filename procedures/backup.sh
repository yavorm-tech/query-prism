#!/usr/bin/env bash
# Nightly Postgres backup.
#
# Postgres is the system of record. Neo4j is a derived index: rebuild it from
# Postgres with the build_knowledge_graph_bulk Celery task instead of backing it up.
# Uploaded files are deleted after ingestion, so there is nothing else to save.
#
# Usage (cron, 02:30 daily):
#   30 2 * * * /path/to/query-prism/procedures/backup.sh >> /var/log/queryprism-backup.log 2>&1
#
# Optional environment:
#   BACKUP_DIR       local destination            (default: <repo>/backups)
#   RETENTION_DAYS   local copies to keep         (default: 14)
#   BACKUP_S3_URI    e.g. s3://my-bucket/queryprism — copied off-host with the aws CLI
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${ROOT}/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
CONTAINER="rag_postgres"

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }

# Read only the DB name and user from .env; the password is not needed inside the container.
POSTGRES_USER="$(grep -E '^POSTGRES_USER=' "${ROOT}/.env" | cut -d= -f2- | tr -d '"'"'"'')"
POSTGRES_DB="$(grep -E '^POSTGRES_DB=' "${ROOT}/.env" | cut -d= -f2- | tr -d '"'"'"'')"

mkdir -p "${BACKUP_DIR}"
STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
OUT="${BACKUP_DIR}/postgres-${POSTGRES_DB}-${STAMP}.dump"

log "Dumping ${POSTGRES_DB} to ${OUT}"
docker exec "${CONTAINER}" pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc -Z 6 > "${OUT}.partial"
mv "${OUT}.partial" "${OUT}"

# A dump that pg_restore can't list is not a backup.
docker exec -i "${CONTAINER}" pg_restore --list < "${OUT}" > /dev/null
log "Verified $(du -h "${OUT}" | cut -f1) dump"

if [[ -n "${BACKUP_S3_URI:-}" ]]; then
  log "Copying to ${BACKUP_S3_URI}"
  aws s3 cp "${OUT}" "${BACKUP_S3_URI%/}/$(basename "${OUT}")" --only-show-errors
fi

find "${BACKUP_DIR}" -name 'postgres-*.dump' -mtime +"${RETENTION_DAYS}" -print -delete | sed 's/^/Removed old backup: /'
log "Backup complete"

# Restore:
#   docker exec -i rag_postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < backups/<file>.dump
# then rebuild the graph:
#   docker exec svc_worker celery -A app.worker call app.graph_worker.build_knowledge_graph_bulk
