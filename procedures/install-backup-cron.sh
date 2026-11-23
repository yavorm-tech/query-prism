#!/usr/bin/env bash
# Install (or update) the nightly backup in the current user's crontab.
# Run once on the production host, as a user that can run `docker`:
#
#   procedures/install-backup-cron.sh            # 02:30 daily
#   BACKUP_SCHEDULE="15 3 * * *" procedures/install-backup-cron.sh
#   procedures/install-backup-cron.sh --remove
#
# Idempotent: the entry is tagged and replaced on every run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCHEDULE="${BACKUP_SCHEDULE:-30 2 * * *}"
TAG="# query-prism-backup"
LOG="${ROOT}/backups/backup.log"

current="$(crontab -l 2>/dev/null | grep -vF "${TAG}" || true)"

if [[ "${1:-}" == "--remove" ]]; then
  printf '%s\n' "${current}" | sed '/^$/d' | crontab -
  echo "Removed the query-prism backup from the crontab."
  exit 0
fi

command -v docker >/dev/null || { echo "docker is not on PATH for this user" >&2; exit 1; }
[[ -f "${ROOT}/.env" ]] || { echo "${ROOT}/.env not found" >&2; exit 1; }
if ! grep -qE '^BACKUP_S3_URI=.+' "${ROOT}/.env"; then
  echo "WARNING: BACKUP_S3_URI is not set in .env — backups will stay on this host only." >&2
fi

mkdir -p "${ROOT}/backups"
entry="${SCHEDULE} ${ROOT}/procedures/backup.sh >> ${LOG} 2>&1 ${TAG}"
{ printf '%s\n' "${current}" | sed '/^$/d'; echo "${entry}"; } | crontab -

echo "Installed: ${entry}"
echo "Run it once now to check: ${ROOT}/procedures/backup.sh"
echo "Alert if ${ROOT}/backups/LAST_SUCCESS is older than 26 hours."
