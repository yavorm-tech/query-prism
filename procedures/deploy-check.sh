#!/usr/bin/env bash
# Deployment checks for a single-host production install (see .claude/skills/deploy).
#
#   procedures/deploy-check.sh preflight   before (re)deploying: host, .env, DNS, firewall, git
#   procedures/deploy-check.sh verify      after `docker compose --profile ssl up -d`
#
# Prints one line per check: PASS / WARN / FAIL. Exit status 1 if anything FAILs.
# Never prints a value from .env — only whether it is set and well-formed.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
FAILS=0
WARNS=0

pass() { printf 'PASS  %s\n' "$*"; }
warn() { printf 'WARN  %s\n' "$*"; WARNS=$((WARNS + 1)); }
fail() { printf 'FAIL  %s\n' "$*"; FAILS=$((FAILS + 1)); }
section() { printf '\n== %s\n' "$*"; }

# Value of KEY in .env (last assignment, surrounding quotes removed). Never echoed by this script.
env_get() {
  [[ -f "${ENV_FILE}" ]] || return 0
  grep -E "^$1=" "${ENV_FILE}" | tail -n 1 | cut -d= -f2- | sed -e 's/^["'"'"']//' -e 's/["'"'"']$//'
}

# ── preflight ────────────────────────────────────────────────────────────────

check_host() {
  section "Host"
  [[ "$(id -u)" -eq 0 ]] && warn "running as root; use a normal user in the docker group" || pass "running as $(id -un)"
  if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
    pass "docker $(docker version --format '{{.Server.Version}}' 2>/dev/null) reachable"
  else
    fail "docker missing or not usable by $(id -un) (install it; add the user to the docker group, then log in again)"
    return
  fi
  local cv; cv="$(docker compose version --short 2>/dev/null || true)"
  if [[ -z "${cv}" ]]; then
    fail "docker compose v2 plugin missing"
  elif printf '%s\n2.24.0\n' "${cv#v}" | sort -V -C; then
    warn "docker compose ${cv} is older than 2.24 (needed by the staging overlay)"
  else
    pass "docker compose ${cv}"
  fi
  local mem_gb; mem_gb=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)
  # Container limits (docker-compose.yml) are sized for a small deployment and total ~7.5 GiB.
  if (( mem_gb >= 7 )); then pass "${mem_gb} GiB RAM"
  elif (( mem_gb >= 5 )); then warn "${mem_gb} GiB RAM; 8 GiB recommended (container limits total ~7.5 GiB)"
  else fail "${mem_gb} GiB RAM; at least 5 GiB needed, 8 GiB recommended"; fi
  local root_dir free_gb; root_dir="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo /var/lib/docker)"
  free_gb=$(df -BG --output=avail "${root_dir}" 2>/dev/null | tail -n 1 | tr -dc '0-9')
  if (( ${free_gb:-0} >= 20 )); then pass "${free_gb} GB free for Docker (${root_dir})"
  else fail "only ${free_gb:-?} GB free for Docker (${root_dir}); need 20+ for images and data"; fi
}

check_env() {
  section ".env"
  if [[ ! -f "${ENV_FILE}" ]]; then fail ".env missing (cp .env.example .env)"; return; fi
  local mode; mode="$(stat -c %a "${ENV_FILE}")"
  [[ "${mode}" == "600" ]] && pass ".env mode 600" || warn ".env mode ${mode}; run: chmod 600 .env"

  local k
  for k in POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB NEO4J_PASSWORD APP_DB_PASSWORD SECRET_KEY DOMAIN OPENAI_API_KEY ANTHROPIC_API_KEY; do
    [[ -n "$(env_get "$k")" ]] && pass "$k is set" || fail "$k is empty (required)"
  done
  local sk; sk="$(env_get SECRET_KEY)"
  [[ -z "${sk}" || ${#sk} -ge 32 ]] || fail "SECRET_KEY is shorter than 32 characters"

  local pg neo app; pg="$(env_get POSTGRES_PASSWORD)"; neo="$(env_get NEO4J_PASSWORD)"; app="$(env_get APP_DB_PASSWORD)"
  if [[ -n "${pg}" && ( "${pg}" == "${neo}" || "${pg}" == "${app}" ) ]] || [[ -n "${neo}" && "${neo}" == "${app}" ]]; then
    fail "POSTGRES_PASSWORD, NEO4J_PASSWORD and APP_DB_PASSWORD must all differ"
  fi

  local domain; domain="$(env_get DOMAIN)"
  if [[ -n "${domain}" ]]; then
    [[ "${domain}" =~ ^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] || fail "DOMAIN must be a bare host name (no https://, no path)"
    for k in APP_URL FRONTEND_URL; do
      [[ "$(env_get "$k")" == "https://${domain}" ]] && pass "$k is https://DOMAIN" || fail "$k must be exactly https://${domain}"
    done
    if [[ -n "$(env_get GOOGLE_CLIENT_ID)" ]]; then
      [[ "$(env_get GOOGLE_REDIRECT_URL)" == "https://${domain}/auth/oauth/google/callback" ]] \
        && pass "GOOGLE_REDIRECT_URL matches DOMAIN" \
        || fail "GOOGLE_REDIRECT_URL must be https://${domain}/auth/oauth/google/callback (and registered in Google Cloud)"
    fi
  fi
  [[ "$(env_get API_ENV)" == "production" ]] && pass "API_ENV=production" || fail "API_ENV must be production"
  [[ -z "$(env_get ACME_CA_SERVER)" ]] || warn "ACME_CA_SERVER is set: certificates will come from that CA (staging CA certificates are not trusted by browsers)"

  for k in COHERE_API_KEY SMTP_RELAY_HOST_URL BACKUP_S3_URI ALERT_EMAIL ACME_EMAIL; do
    [[ -n "$(env_get "$k")" ]] && pass "$k is set" || warn "$k is empty (recommended)"
  done

  # Settings added to .env.example by newer releases but absent from .env.
  local missing
  missing="$(comm -23 <(grep -oE '^[A-Z_][A-Z0-9_]*=' "${ROOT}/.env.example" | sort -u) \
                      <(grep -oE '^[A-Z_][A-Z0-9_]*=' "${ENV_FILE}" | sort -u) | tr -d '=' | tr '\n' ' ')"
  [[ -z "${missing// /}" ]] && pass "every key in .env.example is present in .env" \
    || warn "keys in .env.example but not in .env (check whether they are needed): ${missing}"
}

public_ipv4() {
  ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") print $(i + 1)}'
}

check_dns() {
  section "DNS"
  local domain; domain="$(env_get DOMAIN)"
  [[ -n "${domain}" ]] || { fail "DOMAIN not set; skipping DNS"; return; }
  local ip4 a aaaa; ip4="$(public_ipv4)"
  a="$(getent ahostsv4 "${domain}" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ')"
  aaaa="$(getent ahostsv6 "${domain}" 2>/dev/null | awk '$1 !~ /^::ffff:/ {print $1}' | sort -u | tr '\n' ' ')"
  if [[ -z "${a// /}" ]]; then
    fail "${domain} has no A record yet (point it at ${ip4:-this server})"
  elif [[ " ${a} " == *" ${ip4} "* ]]; then
    pass "${domain} → ${a% } (this server)"
  else
    fail "${domain} → ${a% }, but this server's IPv4 is ${ip4:-unknown}; Let's Encrypt would fail (and rate-limits failures)"
  fi
  if [[ -n "${aaaa// /}" ]]; then
    local ip6; ip6="$(ip -6 addr show scope global 2>/dev/null | awk '/inet6/ {sub("/.*", "", $2); print $2}' | tr '\n' ' ')"
    [[ -n "${ip6}" && " ${ip6} " == *" ${aaaa%% *} "* ]] && pass "AAAA ${aaaa% } is this server" \
      || warn "${domain} has an AAAA record (${aaaa% }) that isn't this server; Let's Encrypt prefers IPv6 — remove it or point it here"
  fi
}

check_network() {
  section "Firewall and ports"
  local p owner
  for p in 80 443; do
    if ss -ltnH "( sport = :${p} )" 2>/dev/null | grep -q .; then
      owner="$(docker ps --filter publish=${p} --format '{{.Names}}' 2>/dev/null | tr '\n' ' ')"
      [[ "${owner}" == *rag_traefik* ]] && pass "port ${p} is served by rag_traefik" \
        || fail "port ${p} is already in use by something else (${owner:-a host process}); stop it first"
    else
      pass "port ${p} is free"
    fi
  done
  if command -v ufw >/dev/null 2>&1; then
    local st; st="$(sudo -n ufw status 2>/dev/null || true)"
    if [[ -z "${st}" ]]; then
      warn "can't read ufw status without sudo; check it allows OpenSSH, 80 and 443"
    elif grep -q "Status: active" <<<"${st}"; then
      for p in 80 443; do grep -qE "^${p}(/tcp)?[[:space:]]+ALLOW" <<<"${st}" && pass "ufw allows ${p}" || fail "ufw is active but does not allow ${p}"; done
      grep -qiE "^(22|OpenSSH)" <<<"${st}" && pass "ufw allows SSH" || warn "ufw is active without an SSH rule (custom SSH port?)"
    else
      warn "ufw is inactive: enable it with SSH, 80 and 443 allowed"
    fi
  else
    warn "ufw not installed; make sure only SSH, 80 and 443 are reachable"
  fi
}

check_git() {
  section "Code"
  cd "${ROOT}" || return
  local branch; branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  pass "on ${branch:-?} at $(git rev-parse --short HEAD 2>/dev/null)"
  if [[ -n "$(git status --porcelain --untracked-files=no 2>/dev/null)" ]]; then
    warn "tracked files have local changes (git status); a deploy should run committed code"
  fi
  [[ "$(basename "${ROOT}")" == "query-prism" ]] && pass "directory name query-prism (compose project / volume names)" \
    || warn "directory is $(basename "${ROOT}"): compose names volumes after it; never rename it after the first start"
}

# ── verify ───────────────────────────────────────────────────────────────────

check_containers() {
  section "Containers"
  local c st
  local mc; mc="$(docker inspect -f '{{.State.Status}} {{.State.ExitCode}}' svc_migrate 2>/dev/null)"
  [[ "${mc}" == "exited 0" ]] && pass "migrate finished successfully" || fail "migrate: ${mc:-not found} (docker compose logs migrate)"
  for c in rag_postgres rag_neo4j rag_redis rag_redis_broker rag_postfix svc_api svc_worker svc_gateway rag_frontend rag_traefik; do
    st="$(docker inspect -f '{{.State.Status}}{{if .State.Health}}/{{.State.Health.Status}}{{end}}' "${c}" 2>/dev/null)"
    case "${st}" in
      running/healthy|running) pass "${c} ${st}" ;;
      running/starting) warn "${c} still starting" ;;
      "") fail "${c} not found" ;;
      *) fail "${c} ${st} (docker logs ${c})" ;;
    esac
  done
  local head current
  head="$(grep -h '^revision = ' "${ROOT}"/backend/migrations/versions/*.py | tr -dc '0-9\n' | sort | tail -n 1)"
  current="$(docker exec rag_postgres psql -U "$(env_get POSTGRES_USER)" -d "$(env_get POSTGRES_DB)" -Atc 'SELECT version_num FROM alembic_version' 2>/dev/null)"
  [[ -n "${head}" && "${current}" == "${head}" ]] && pass "database at migration ${current} (head)" \
    || fail "database at migration ${current:-?}, code expects ${head:-?}"
  local role
  role="$(docker exec rag_postgres psql -U "$(env_get POSTGRES_USER)" -d "$(env_get POSTGRES_DB)" -Atc \
    "SELECT DISTINCT a.usename || ' ' || (r.rolsuper OR r.rolbypassrls) FROM pg_stat_activity a JOIN pg_roles r ON r.rolname = a.usename
      WHERE a.datname = current_database() AND a.application_name = '' AND a.pid <> pg_backend_pid() AND a.usename <> '$(env_get POSTGRES_USER)'" 2>/dev/null)"
  if docker logs --since 30m svc_api 2>&1 | grep -q "bypasses row-level security"; then
    fail "api connects as a role that bypasses row-level security (check APP_DB_PASSWORD / DATABASE_URL)"
  elif [[ "${role}" == *" false"* && "${role}" != *" true"* ]]; then
    pass "app connections use the least-privilege role (${role%% *})"
  else
    fail "no app connections as the least-privilege role found (${role:-none}); is svc_api running?"
  fi
}

check_https() {
  section "HTTPS"
  local domain; domain="$(env_get DOMAIN)"
  [[ -n "${domain}" ]] || { fail "DOMAIN not set"; return; }
  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "https://${domain}/health" 2>/dev/null)"
  [[ "${code}" == "200" ]] && pass "https://${domain}/health → 200 with a trusted certificate" \
    || fail "https://${domain}/health → ${code:-no answer} (certificate not issued yet? docker logs rag_traefik)"
  local cert; cert="$(echo | openssl s_client -connect "${domain}:443" -servername "${domain}" 2>/dev/null | openssl x509 -noout -issuer -enddate 2>/dev/null)"
  if [[ -n "${cert}" ]]; then
    local issuer end days
    issuer="$(sed -n 's/^issuer=//p' <<<"${cert}")"; end="$(sed -n 's/^notAfter=//p' <<<"${cert}")"
    days=$(( ( $(date -d "${end}" +%s) - $(date +%s) ) / 86400 ))
    [[ "${issuer}" == *"Let's Encrypt"* ]] && pass "certificate from Let's Encrypt, ${days} days left" \
      || warn "certificate issuer: ${issuer} (${days} days left) — expected Let's Encrypt"
  fi
  code="$(curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 10 "http://${domain}/" 2>/dev/null)"
  [[ "${code}" == 30[178]" https://"* ]] && pass "http:// redirects to https://" || fail "http://${domain}/ → ${code}"
  code="$(curl -sS -o /dev/null -w '%{http_code} %{content_type}' --max-time 10 "https://${domain}/" 2>/dev/null)"
  [[ "${code}" == "200 text/html"* ]] && pass "frontend served at https://${domain}/" || fail "https://${domain}/ → ${code}"
  local body
  if body="$(curl -sS --fail-with-body --max-time 10 "https://${domain}/metrics" 2>/dev/null)" || [[ -n "${body}" ]]; then
    [[ "${body}" != *"http_requests_total"* ]] && pass "/metrics is not exposed publicly" || fail "/metrics is publicly reachable"
  fi
}

check_exposure() {
  section "Exposure"
  local public
  public="$(docker ps --format '{{.Names}} {{.Ports}}' | tr ',' '\n' | grep -E '0\.0\.0\.0:|\[::\]:' | grep -vE ':(80|443)->' | sort -u)"
  [[ -z "${public}" ]] && pass "only 80 and 443 are published on public interfaces" \
    || fail "published on all interfaces: ${public//$'\n'/; }"
}

check_ops() {
  section "Backups and monitoring"
  if crontab -l 2>/dev/null | grep -q "# query-prism-backup"; then pass "backup cron installed"
  else warn "backup cron not installed (procedures/install-backup-cron.sh)"; fi
  local dir; dir="$(env_get BACKUP_DIR)"; dir="${dir:-${ROOT}/backups}"
  if [[ -f "${dir}/LAST_SUCCESS" ]]; then
    local age=$(( ( $(date +%s) - $(date -d "$(cat "${dir}/LAST_SUCCESS")" +%s) ) / 3600 ))
    (( age <= 26 )) && pass "last backup ${age} h ago" || fail "last backup ${age} h ago"
  else
    warn "no successful backup yet (run procedures/backup.sh)"
  fi
  [[ -n "$(env_get BACKUP_S3_URI)" ]] || warn "BACKUP_S3_URI unset: backups stay on this server"
  if docker inspect mon_prometheus >/dev/null 2>&1; then
    local down
    down="$(docker exec mon_prometheus wget -qO- 'http://localhost:9090/api/v1/query?query=up==0' 2>/dev/null | grep -o '"job":"[^"]*"' | sort -u | tr '\n' ' ')"
    [[ -z "${down}" ]] && pass "Prometheus: all scrape targets up" || fail "Prometheus targets down: ${down}"
  else
    warn "monitoring profile not running (needs ALERT_EMAIL)"
  fi
}

summary() {
  printf '\n%s: %d failed, %d warnings\n' "$1" "${FAILS}" "${WARNS}"
  (( FAILS == 0 ))
}

case "${1:-}" in
  preflight) check_host; check_env; check_dns; check_network; check_git; summary preflight ;;
  verify)    check_containers; check_https; check_exposure; check_ops; summary verify ;;
  *) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
