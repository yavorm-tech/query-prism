---
name: deploy
description: Install, update or health-check Query Prism on its production server (one Linux host, Docker Compose, Traefik with automatic Let's Encrypt certificates). Use when asked to deploy, install, set up production, update/upgrade the server, roll back, or check that production is healthy.
---

# Deploy Query Prism (single production host)

This runs **on the production server**, in the repository checkout (normally
`~/query-prism`). The stack is `docker-compose.yml` with the `ssl` profile
(Traefik on 80/443, issues and renews certificates itself) and optionally the
`monitoring` profile. Deterministic checks live in `procedures/deploy-check.sh`;
use them instead of ad-hoc commands, and treat a `FAIL` line as a stop sign.

Pick the mode first:

| Situation | Mode |
|---|---|
| `docker ps` shows no `svc_api` / `rag_traefik` | **A. First install** |
| The stack is running and the user wants new code | **B. Update** |
| The user asks whether production is OK | **C. Health check** (`procedures/deploy-check.sh verify`, then report) |

## Ground rules (always)

1. **Never reveal secrets.** Don't `cat`, `grep`, `Read` or otherwise print `.env`,
   and don't put secret values on a command line. `deploy-check.sh` reports only
   "set / empty / wrong". Ask the user to type API keys and passwords into `.env`
   themselves (`nano .env` in their own SSH session) rather than pasting them in chat.
2. **Never regenerate an existing secret** once the stack has started:
   `POSTGRES_PASSWORD` and `NEO4J_PASSWORD` are fixed into the data volumes at
   first start; changing `SECRET_KEY` signs everyone out. Changing
   `APP_DB_PASSWORD` needs the role updated too (see Troubleshooting).
3. **Ask before** installing packages, changing the firewall, the first
   `docker compose up` (it asks Let's Encrypt for a real certificate, and failures
   count against rate limits), and restarting a running production stack.
4. **Never without explicit approval:** `docker compose down -v`, `docker volume rm`,
   `docker system prune --volumes`, deleting `backups/`, `git reset --hard`,
   `git push`, `alembic downgrade`, restoring a backup, renaming the repository
   directory (compose names volumes after it).
5. If a step fails, **stop, show the relevant log lines, and explain**. Don't work
   around a failed check by editing compose files or disabling security settings.
6. `sudo` may need a password: ask the user to run that command with a `!` prefix.

---

## A. First install

### A1. Orient
```bash
hostname; ip -4 route get 1.1.1.1 | head -n 1      # this server's public IPv4 ("src")
cd ~/query-prism && git log --oneline -1 && git status --short
```
Confirm with the user that this is the production server and which domain it
will serve. The directory must stay named `query-prism`.

### A2. Prepare the host (only what preflight says is missing)
Run `procedures/deploy-check.sh preflight` and read the **Host** and **Firewall**
sections. If needed, with the user's OK:
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"                  # user must log out and back in
sudo sshd -T | grep -i '^port'                   # find the SSH port BEFORE touching the firewall
sudo ufw allow OpenSSH                           # or: sudo ufw allow <port>/tcp for a custom SSH port
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
sudo ufw enable
```
Docker-published ports bypass ufw; that is fine here because the compose file
publishes only 80/443 publicly (everything else is internal or 127.0.0.1).

### A3. Create `.env`
```bash
[ -f .env ] || cp .env.example .env
chmod 600 .env
# Random secrets for keys that are still empty; values are never printed.
for k in POSTGRES_PASSWORD NEO4J_PASSWORD APP_DB_PASSWORD SECRET_KEY; do
  if ! grep -qE "^$k=.+" .env; then
    v="$(openssl rand -hex 32)"
    if grep -qE "^$k=" .env; then sed -i "s|^$k=.*|$k=$v|" .env; else printf '%s=%s\n' "$k" "$v" >> .env; fi
  fi
done; unset v
```
Set the non-secret values from the domain the user gives (replace `example.com`):
```bash
d=example.com
sed -i -e "s|^DOMAIN=.*|DOMAIN=$d|" -e "s|^APP_URL=.*|APP_URL=https://$d|" \
       -e "s|^FRONTEND_URL=.*|FRONTEND_URL=https://$d|" \
       -e "s|^GOOGLE_REDIRECT_URL=.*|GOOGLE_REDIRECT_URL=https://$d/auth/oauth/google/callback|" \
       -e "s|^API_ENV=.*|API_ENV=production|" .env
```
Then ask the user to fill in, in their own editor: `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY` (required), `COHERE_API_KEY`, `SMTP_RELAY_HOST_URL` /
`SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_FROM_EMAIL` (a transactional email
provider; mail sent straight from a VPS lands in spam), `ACME_EMAIL`,
`ALERT_EMAIL`, `BACKUP_S3_URI` + `AWS_*` (+ `BACKUP_S3_ENDPOINT_URL` for
S3-compatible stores such as Contabo Object Storage), and the Google OAuth keys
if Google sign-in is used.

### A4. Preflight until clean
```bash
procedures/deploy-check.sh preflight
```
Repeat until it reports `0 failed`. Typical fixes:
- **DNS FAIL:** the domain's A record must point at this server's IPv4; wait for
  propagation (`getent ahostsv4 <domain>`). Remove or fix an AAAA record that points
  elsewhere: Let's Encrypt tries IPv6 first.
- **Port 80/443 in use:** find it with `sudo ss -ltnp 'sport = :80'` and stop it with the user's OK.

Go through the WARN lines with the user. Missing `BACKUP_S3_URI` means backups
stay on this server; missing `ALERT_EMAIL` means no alerts. Both are allowed, but
the user should decide knowingly.

### A5. Optional: certificate dry run
If the user is unsure about DNS or the firewall, test against Let's Encrypt's
staging CA first (no rate-limit risk, untrusted certificate):
```bash
echo 'ACME_CA_SERVER=https://acme-staging-v02.api.letsencrypt.org/directory' >> .env
```
After A6 shows a staging certificate was issued (`docker logs rag_traefik`), switch back:
```bash
sed -i '/^ACME_CA_SERVER=/d' .env
docker compose --profile ssl rm -sf traefik
docker volume rm query-prism_traefik_letsencrypt     # only the staging certificate lives here
docker compose --profile ssl up -d traefik
```

### A6. Build and start (ask first)
```bash
profiles="--profile ssl"; grep -qE '^ALERT_EMAIL=.+' .env && profiles="$profiles --profile monitoring"
docker compose $profiles up -d --build
```
The first build takes 10–20 minutes; run it in the background and wait for
completion. Then:
```bash
docker compose ps
docker compose logs --tail 50 migrate
docker logs rag_traefik 2>&1 | grep -iE 'acme|certificate|error' | tail -n 20
```

### A7. Verify
```bash
procedures/deploy-check.sh verify
```
Certificate issuance can take a minute or two after Traefik starts; if only the
HTTPS checks fail, wait 60 s and run `verify` again (at most ~5 tries), reading
Traefik's log in between. Fix every FAIL before going on (see Troubleshooting).

### A8. Backups
```bash
procedures/install-backup-cron.sh        # nightly at 02:30
procedures/backup.sh                     # once now; must end with "Backup complete"
procedures/deploy-check.sh verify        # backups section should now pass
```

### A9. Hand over
Ask the user to open `https://<domain>` and register the first company
themselves (that account becomes its owner; don't create accounts for them).
If Google sign-in is used, remind them to register
`https://<domain>/auth/oauth/google/callback` in Google Cloud Console.
Report: deployed commit, migration version, certificate expiry,
backup status (and whether it is off-host), monitoring status, and any warnings left.

---

## B. Update

### B1. What's new?
```bash
git fetch origin
git log --oneline HEAD..origin/master
```
If nothing is new, stop and say so.

### B2. Assess the impact and get a go-ahead
```bash
git diff --stat HEAD origin/master
git diff --name-only HEAD origin/master -- backend/migrations/versions
git diff HEAD origin/master -- .env.example docker-compose.yml traefik/ gateway/
```
Read every new migration. Flag to the user anything destructive (`DROP`,
`ALTER ... DROP COLUMN`, `TRUNCATE`, `DELETE`, type changes) and any new
`.env.example` key that needs a value. Summarise the changes, the expected
downtime (the API restarts; seconds to a minute) and get explicit approval. For
risky migrations, suggest rehearsing on staging first:
`procedures/staging.sh refresh` (needs `.env.staging`; see `docs/README.md`).

### B3. Back up first
```bash
procedures/backup.sh
```
It must end with "Backup complete". Note the dump file name for a possible restore.

### B4. Pull and check
```bash
git pull --ff-only origin master          # if this fails: local changes; stop and report
procedures/deploy-check.sh preflight      # ports 80/443 owned by rag_traefik is expected
```
Add any newly required `.env` keys (the user fills secret ones).

### B5. Apply (migrations first, while the old version keeps serving)
```bash
profiles="--profile ssl"; docker ps --format '{{.Names}}' | grep -q '^mon_prometheus$' && profiles="$profiles --profile monitoring"
docker compose $profiles build
docker compose $profiles run --rm migrate      # old api keeps serving; stop here if this fails
docker compose $profiles up -d                 # recreates the changed containers
procedures/deploy-check.sh verify
```
Always use this order. A plain `docker compose up -d --build` removes the running
API *before* it runs the migration, so a failed migration would mean an outage.

### B6. If it fails
- **`run --rm migrate` failed:** nothing was restarted, so the old version is still
  serving. Show its output and stop. Each migration commits on its own
  (`transaction_per_migration`): the failing one is rolled back, but earlier new
  migrations from the same update stay applied. Check where the database is:
  `docker exec rag_postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT version_num FROM alembic_version"'`.
  - Still at the previous revision: go back to the deployed code
    (`git checkout <previous commit>`, then `docker compose $profiles build` so the
    images match what is running).
  - Moved forward: the running old code now sees a newer schema. Tell the user;
    the options are fixing forward, `alembic downgrade` to the previous revision, or
    restoring the B3 backup. Don't choose for them.
  Don't edit migrations or downgrade without the user.
- **The new version misbehaves after a successful migration:** propose (don't do)
  one of these:
  1. Roll back code only, if the new migrations are backward compatible:
     `git checkout <previous commit>` then `docker compose $profiles up -d --build`.
  2. Restore the B3 backup (data written since the backup is lost):
     ```bash
     docker compose $profiles stop api worker
     docker exec -i rag_postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < backups/<file>.dump
     git checkout <previous commit> && docker compose $profiles up -d --build
     docker exec svc_worker celery -A app.worker call app.graph_worker.build_knowledge_graph_bulk   # rebuild graph (costs LLM calls)
     ```
- Report what was deployed, or what was rolled back and why.

---

## Troubleshooting

| Symptom | Look at | Usual cause and fix |
|---|---|---|
| `required variable X is missing a value` | the compose error | Set X in `.env` (the user, if it's a secret) |
| HTTPS check fails, Traefik log shows `acme` errors | `docker logs rag_traefik` | DNS not pointing here, port 80 blocked (ufw/provider firewall), or an AAAA record elsewhere. After 5 failures/hour Let's Encrypt blocks you for an hour: fix the cause, then wait, or use the staging CA (A5) |
| Traefik exits at start: `Set DOMAIN in .env` | `docker logs rag_traefik` | `DOMAIN` empty |
| Browser gets 404 from Traefik | `curl -sI https://<domain>/` | Requests use a host name other than `DOMAIN` (e.g. `www.`); only `DOMAIN` is routed |
| 502/504 from Traefik | `docker compose ps` | gateway, frontend or api is down: `docker logs svc_api` |
| `migrate` fails: `password authentication failed` | `docker compose logs migrate` | `POSTGRES_PASSWORD` was changed after the first start; put the original back |
| api unhealthy: `password authentication failed for user "qp_app"` | `docker logs svc_api` | `APP_DB_PASSWORD` changed after migration 0011 created the role; sync the role (below) |
| api exits: `SECRET_KEY` error | `docker logs svc_api` | Must be 32+ random characters |
| verify: `bypasses row-level security` | `docker logs svc_api` | api is connecting as the owner; `APP_DB_PASSWORD` must be set and compose must be current |
| A container keeps restarting | `docker inspect -f '{{.State.OOMKilled}}' <name>` | Out of memory; the host needs 16 GiB |
| Invite / reset emails don't arrive | `docker logs rag_postfix` | No `SMTP_RELAY_HOST_URL`, or the relay rejects the sender (`SMTP_FROM_EMAIL` domain must be verified with the provider) |

Sync the app role's password with `.env` without printing it:
```bash
(
  get() { grep -E "^$1=" .env | tail -n 1 | cut -d= -f2-; }
  ROLE="$(get APP_DB_USER)" PW="$(get APP_DB_PASSWORD)" docker exec -i -e ROLE -e PW rag_postgres \
    sh -c 'printf "%s\n" "ALTER ROLE :\"role\" PASSWORD :'\''pw'\'';" | psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v role="$ROLE" -v pw="$PW"'
)
docker compose --profile ssl restart api worker
```

## Reference

- Containers: `rag_traefik` (80/443), `svc_gateway` (127.0.0.1:8000), `svc_api`,
  `svc_worker`, `svc_migrate` (one-shot), `rag_frontend`, `rag_postgres`, `rag_neo4j`,
  `rag_redis`, `rag_redis_broker`, `rag_postfix`; monitoring: `mon_prometheus`
  (127.0.0.1:9090), `mon_alertmanager` (127.0.0.1:9093), `mon_node_exporter`.
- Volumes (data, never delete): `query-prism_postgres_data`, `query-prism_neo4j_data`,
  `query-prism_redis_broker_data`, `query-prism_uploads`, `query-prism_traefik_letsencrypt`.
- Routing: `traefik/dynamic.yml`. Backups: `procedures/backup.sh`, `backups/`.
  Alerts: `monitoring/alerts.yml`. Staging: `procedures/staging.sh`.
- Prometheus/Alertmanager UIs: `ssh -L 9090:127.0.0.1:9090 -L 9093:127.0.0.1:9093 <server>`.
