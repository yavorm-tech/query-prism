#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="$(cd "$(dirname "$0")/.." && pwd)/docker-compose.services.yml"
DOMAIN="queryprism.online"
EMAIL="yavor.p.mihaylov@gmail.com"

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }

log "Attempting certificate renewal for ${DOMAIN}"

# Run certbot renew inside the existing certbot container.
# --force-renewal can be appended for testing; omit for normal runs.
docker compose -f "${COMPOSE_FILE}" exec -T certbot \
  certbot renew \
    --webroot -w /var/www/certbot \
    --cert-name "${DOMAIN}" \
    --non-interactive \
    --agree-tos \
    -m "${EMAIL}" \
    --quiet

EXIT_CODE=$?

if [ "${EXIT_CODE}" -ne 0 ]; then
  log "ERROR: certbot renew exited with code ${EXIT_CODE}"
  exit "${EXIT_CODE}"
fi

# Reload nginx so it picks up the new certificate without downtime.
log "Reloading nginx in ssl-proxy container"
docker compose -f "${COMPOSE_FILE}" exec -T ssl-proxy nginx -s reload

log "Done — certificate for ${DOMAIN} is up to date"
