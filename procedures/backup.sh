#!/usr/bin/env bash
# Nightly Postgres backup, verified and copied off-host.
#
# Postgres is the system of record. Neo4j is a derived index: rebuild it from
# Postgres with the build_knowledge_graph_bulk Celery task instead of backing it up.
# Uploads are deleted after ingestion, so there is nothing else to save.
#
# Schedule it with procedures/install-backup-cron.sh (02:30 daily by default).
#
# Settings are read from the repo's .env (cron runs with an empty environment);
# variables already set in the environment win:
#   BACKUP_DIR              local destination                (default: <repo>/backups)
#   RETENTION_DAYS          local copies to keep             (default: 14)
#   BACKUP_S3_URI           s3://bucket/prefix — off-host copy (strongly recommended)
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION
#   BACKUP_PG_CONTAINER     Postgres container               (default: rag_postgres)
#   BACKUP_DOCKER_NETWORK   network for the aws CLI container (default: host)
#   BACKUP_S3_ENDPOINT_URL  for S3-compatible stores (R2, B2, ...); empty for AWS
#
# The off-host copy runs the aws CLI in a container (amazon/aws-cli), so the
# host needs only Docker. On success the script writes <BACKUP_DIR>/LAST_SUCCESS;
# alert when that file is older than ~26 hours.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
AWS_CLI_IMAGE="amazon/aws-cli:2.18.10"

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }

# Value of KEY from .env unless already set in the environment.
setting() {
  local key="$1" default="${2:-}"
  if [[ -n "${!key:-}" ]]; then
    printf '%s' "${!key}"
  elif [[ -f "${ENV_FILE}" ]] && grep -qE "^${key}=" "${ENV_FILE}"; then
    grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 | cut -d= -f2- | sed -e 's/^["'"'"']//' -e 's/["'"'"']$//'
  else
    printf '%s' "${default}"
  fi
}

POSTGRES_USER="$(setting POSTGRES_USER)"
POSTGRES_DB="$(setting POSTGRES_DB)"
BACKUP_DIR="$(setting BACKUP_DIR "${ROOT}/backups")"
RETENTION_DAYS="$(setting RETENTION_DAYS 14)"
BACKUP_S3_URI="$(setting BACKUP_S3_URI)"
BACKUP_S3_ENDPOINT_URL="$(setting BACKUP_S3_ENDPOINT_URL)"
CONTAINER="$(setting BACKUP_PG_CONTAINER rag_postgres)"
DOCKER_NETWORK="$(setting BACKUP_DOCKER_NETWORK host)"

if [[ -z "${POSTGRES_USER}" || -z "${POSTGRES_DB}" ]]; then
  log "ERROR: POSTGRES_USER and POSTGRES_DB must be set (in ${ENV_FILE} or the environment)"
  exit 1
fi

mkdir -p "${BACKUP_DIR}"
STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
NAME="postgres-${POSTGRES_DB}-${STAMP}.dump"
OUT="${BACKUP_DIR}/${NAME}"

log "Dumping ${POSTGRES_DB} to ${OUT}"
docker exec "${CONTAINER}" pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc -Z 6 > "${OUT}.partial"
mv "${OUT}.partial" "${OUT}"

# A dump that pg_restore can't list is not a backup.
docker exec -i "${CONTAINER}" pg_restore --list < "${OUT}" > /dev/null
log "Verified $(du -h "${OUT}" | cut -f1) dump"

if [[ -n "${BACKUP_S3_URI}" ]]; then
  log "Copying to ${BACKUP_S3_URI%/}/${NAME}"
  endpoint=()
  [[ -n "${BACKUP_S3_ENDPOINT_URL}" ]] && endpoint=(--endpoint-url "${BACKUP_S3_ENDPOINT_URL}")
  AWS_ACCESS_KEY_ID="$(setting AWS_ACCESS_KEY_ID)" \
  AWS_SECRET_ACCESS_KEY="$(setting AWS_SECRET_ACCESS_KEY)" \
  AWS_DEFAULT_REGION="$(setting AWS_DEFAULT_REGION us-east-1)" \
  docker run --rm --network "${DOCKER_NETWORK}" \
    -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION \
    -v "${BACKUP_DIR}:/backups:ro" \
    "${AWS_CLI_IMAGE}" "${endpoint[@]}" s3 cp "/backups/${NAME}" "${BACKUP_S3_URI%/}/${NAME}" --only-show-errors
  log "Off-host copy done"
else
  log "WARNING: BACKUP_S3_URI is not set; this backup exists only on this host"
fi

find "${BACKUP_DIR}" -name 'postgres-*.dump' -mtime +"${RETENTION_DAYS}" -print -delete | sed 's/^/Removed old backup: /'
date -u '+%Y-%m-%dT%H:%M:%SZ' > "${BACKUP_DIR}/LAST_SUCCESS"
log "Backup complete"

# Restore:
#   docker exec -i rag_postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < backups/<file>.dump
# then rebuild the graph:
#   docker exec svc_worker celery -A app.worker call app.graph_worker.build_knowledge_graph_bulk
