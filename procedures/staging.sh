#!/usr/bin/env bash
# Staging: a second, isolated copy of the stack (docker-compose.staging.yml).
#
#   procedures/staging.sh up                 build and start staging (empty database)
#   procedures/staging.sh refresh [DUMP]     load a production backup, scrubbed (see below)
#   procedures/staging.sh migrate            run Alembic against staging
#   procedures/staging.sh ps | logs [svc]    status / follow logs
#   procedures/staging.sh down               stop (data kept)
#   procedures/staging.sh destroy            stop and delete staging's volumes
#
# Settings come from .env.staging (copy .env.staging.example). Staging never
# reads production's .env.
#
# refresh restores DUMP (default: the newest backups/postgres-*.dump), applies
# pending migrations to it — the realistic test of a release's migrations — and
# then runs procedures/staging-scrub.sql: emails rewritten to @staging.invalid,
# Google links, avatars, tokens, invites and audit emails/IPs removed, every
# password set to STAGING_PASSWORD. Customer documents and questions remain:
# keep staging access as restricted as production's.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/.env.staging"
PROJECT="query-prism-staging"
PG="stg_postgres"

log() { echo "[staging] $*"; }
die() { echo "[staging] ERROR: $*" >&2; exit 1; }

[[ -f "${ENV_FILE}" ]] || die "${ENV_FILE} not found; copy .env.staging.example and fill it in"

compose() {
  docker compose -p "${PROJECT}" --env-file "${ENV_FILE}" \
    -f "${ROOT}/docker-compose.yml" -f "${ROOT}/docker-compose.staging.yml" "$@"
}

# Value of KEY in .env.staging, or DEFAULT.
setting() {
  local v
  v="$(grep -E "^$1=" "${ENV_FILE}" | tail -n 1 | cut -d= -f2- | sed -e 's/^["'"'"']//' -e 's/["'"'"']$//' || true)"
  printf '%s' "${v:-${2:-}}"
}

# psql in the staging Postgres container against database $1.
psql_stg() {
  local db="$1"; shift
  docker exec -i "${PG}" psql -v ON_ERROR_STOP=1 -q -U "$(setting POSTGRES_USER)" -d "${db}" "$@"
}

wait_for_postgres() {
  for _ in $(seq 1 60); do
    docker exec "${PG}" pg_isready -q -U "$(setting POSTGRES_USER)" 2>/dev/null && return 0
    sleep 2
  done
  die "staging Postgres did not become ready"
}

cmd="${1:-}"; shift || true
case "${cmd}" in
  up)
    compose up -d --build "$@"
    log "App: http://127.0.0.1:$(setting STAGING_HTTP_PORT 18080) (API: $(setting STAGING_API_PORT 18000)); reach it with an SSH tunnel"
    ;;

  migrate)
    compose run --rm --build migrate
    ;;

  refresh)
    dump="${1:-$(ls -1t "${ROOT}"/backups/postgres-*.dump 2>/dev/null | head -n 1 || true)}"
    [[ -n "${dump}" && -f "${dump}" ]] || die "no dump given and none in backups/ (run procedures/backup.sh)"
    password="$(setting STAGING_PASSWORD)"
    [[ ${#password} -ge 12 ]] || die "set STAGING_PASSWORD (12+ characters) in .env.staging"

    log "Restoring $(basename "${dump}") into staging"
    compose stop frontend gateway api worker 2>/dev/null || true
    compose up -d postgres
    wait_for_postgres
    db="$(setting POSTGRES_DB)"
    psql_stg postgres -c "DROP DATABASE IF EXISTS \"${db}\" WITH (FORCE)" -c "CREATE DATABASE \"${db}\""
    # Grants are not restored (--no-privileges: role names differ between
    # environments); staging's app role is (re)created and granted below.
    app_role="$(setting APP_DB_USER qp_app)"
    app_password="$(setting APP_DB_PASSWORD)"
    [[ -n "${app_password}" ]] || die "set APP_DB_PASSWORD in .env.staging"
    docker exec -i "${PG}" pg_restore --no-owner --no-privileges --exit-on-error \
      -U "$(setting POSTGRES_USER)" -d "${db}" < "${dump}"

    log "Applying migrations to the restored data"
    compose run --rm --build migrate

    log "Granting ${app_role} access to the restored database"
    psql_stg "${db}" -v role="${app_role}" -v pw="${app_password}" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'role', :'pw')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role') \gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS', :'role', :'pw') \gexec
SELECT shared.apply_app_grants(:'role');
SQL

    log "Scrubbing personal data and credentials"
    psql_stg "${db}" -v staging_password="${password}" < "${ROOT}/procedures/staging-scrub.sql"

    # Neo4j is derived from Postgres: drop staging's old graph rather than keep a stale one.
    compose rm -sf neo4j >/dev/null 2>&1 || true
    docker volume rm "${PROJECT}_neo4j_data" >/dev/null 2>&1 || true

    log "Done. Start the app with: procedures/staging.sh up"
    log "Sign in as any user with STAGING_PASSWORD; emails are user-<first 8 of id>@staging.invalid."
    log "Graph search stays empty until rebuilt (costs LLM calls):"
    log "  docker exec stg_worker celery -A app.worker call app.graph_worker.build_knowledge_graph_bulk"
    ;;

  ps)      compose ps "$@" ;;
  logs)    compose logs -f --tail 100 "$@" ;;
  down)    compose down "$@" ;;

  destroy)
    read -r -p "Delete all staging data (volumes of project ${PROJECT})? [y/N] " ok
    [[ "${ok}" == "y" ]] || exit 1
    compose down -v
    ;;

  *)
    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
