# Services

Every container in `docker-compose.yml`: what it does, how it is reached, what it
stores and how much memory it may use. Memory limits are sized for one 8 GiB host
serving a handful of users (ADR-012 in [decisions.md](./decisions.md)); actual use is
well below them (about 1.7 GiB in total when idle).

```bash
docker compose --profile ssl --profile monitoring ps     # status of everything
docker logs --tail 100 <container>                        # logs (JSON lines for api/worker)
docker stats --no-stream                                  # memory use vs. limit
```

## Overview

| Service | Container | Profile | Host port | Memory limit | Data volume |
|---|---|---|---|---|---|
| traefik | `rag_traefik` | `ssl` | **80, 443** (public) | 256 MiB | `traefik_letsencrypt` |
| frontend | `rag_frontend` | `ssl` | — | 512 MiB | — |
| gateway | `svc_gateway` | — | 127.0.0.1:8000 | 128 MiB | — |
| api | `svc_api` | — | — | 1 GiB | `uploads` |
| worker | `svc_worker` | — | — | 1.5 GiB | `uploads` |
| migrate | `svc_migrate` | — | — | — | — (runs once, then exits 0) |
| postgres | `rag_postgres` | — | — | 1 GiB | `postgres_data` |
| neo4j | `rag_neo4j` | — | — | 1.5 GiB | `neo4j_data`, `neo4j_logs`, `neo4j_plugins` |
| redis | `rag_redis` | — | — | 512 MiB | `redis_data` |
| redis-broker | `rag_redis_broker` | — | — | 320 MiB | `redis_broker_data` |
| postfix | `rag_postfix` | — | — | 128 MiB | — |
| prometheus | `mon_prometheus` | `monitoring` | 127.0.0.1:9090 | 512 MiB | `prometheus_data` |
| alertmanager | `mon_alertmanager` | `monitoring` | 127.0.0.1:9093 | 128 MiB | `alertmanager_data` |
| node-exporter | `mon_node_exporter` | `monitoring` | — | 64 MiB | reads `./backups/metrics` |

Only Traefik is reachable from the internet. Ports bound to 127.0.0.1 are for this
host only; open them from your machine with an SSH tunnel
(`ssh -L 9090:127.0.0.1:9090 -L 9093:127.0.0.1:9093 <server>`). Datastores publish
no ports unless the dev overlay (`docker-compose.dev.yml`) is used.

Volumes are named `query-prism_<volume>` after the checkout directory, so the
directory must stay named `query-prism`. Deleting a volume deletes that data.

```
Internet ─► traefik :443 ─┬─ API paths ─► gateway :8000 ─► api :8000 ─┬─► postgres, neo4j, redis
                          └─ the rest ──► frontend :80                ├─► redis-broker ─► worker
                                                                      └─► postfix ─► SMTP relay
```

---

## Edge

### traefik — TLS and routing
- **Image** `traefik:v3.7.19`. Static settings are the command flags in
  `docker-compose.yml`; routes are in `traefik/dynamic.yml` (reloaded on change).
- Gets a Let's Encrypt certificate for `DOMAIN` on first start (HTTP challenge on
  port 80) and renews it about 30 days before expiry; no restart needed.
  Port 80 only redirects to HTTPS and answers the challenge.
- Routes only `Host(DOMAIN)`; other host names (e.g. `www.`) get a 404.
  `/auth/`, `/ingest`, `/chat`, `/usage`, `/contact/`, `/audit`, `/health`, and
  `/topics` requests carrying an `Authorization` header go to the gateway;
  everything else goes to the frontend. Adds HSTS; TLS 1.2 minimum.
- `.env`: `DOMAIN` (required; exits at start without it), `ACME_EMAIL` (optional),
  `ACME_CA_SERVER` (set only to test against the staging CA).
- Health: `traefik healthcheck --ping`. Certificate problems: `docker logs rag_traefik 2>&1 | grep -i acme`.

### frontend — the React app
- Built from `frontend-react/` (Vite bundle, served by nginx with
  `gateway/frontend-react.conf`). See [frontend-react/README.md](../frontend-react/README.md).
- `VITE_API_URL` is baked in at build time; empty (the default) means "same origin",
  which is what production uses.

### gateway — API reverse proxy
- **Image** `nginx:1.30.7-alpine`, config `gateway/nginx.conf`.
- Forwards every API path to `api:8000`, with SSE-friendly settings for `/chat/stream`.
  `/metrics` is not routed.
- Host port 127.0.0.1:8000 is for local frontend development and smoke tests;
  it never listens on a public interface.

---

## Application

The api, worker and migrate services are built from `backend/` (one codebase, see
[architecture.md](./architecture.md)). They read `.env`; compose overrides the
connection URLs so they always point at the containers below.

### api — HTTP API (FastAPI)
- **Image** `query-prism-api`. All endpoints ([API reference](./README.md#table-of-contents)),
  plus `/health` (used by the healthcheck) and `/metrics` (internal, scraped by Prometheus).
- Connects to Postgres as the least-privilege `APP_DB_USER` (`qp_app`), so
  row-level security applies; never as the owner.
- Runs the outbox relay (redelivers domain events every 5 s).
- Starts only after `migrate` has finished successfully and the datastores are healthy.
- Needs: `SECRET_KEY` (32+ characters), `APP_DB_PASSWORD`, `NEO4J_PASSWORD`,
  `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`; optional `COHERE_API_KEY` (re-ranking),
  Google OAuth keys, `LLM_TIER_*` model routes.

### worker — ingestion (Celery)
- **Image** `query-prism-worker` (api image plus document loaders, OCR and
  transcription). Queue `ingestion`, concurrency 2.
- Tasks: `app.worker.ingest_document` (load → chunk → embed → write chunks) and
  `app.graph_worker.build_knowledge_graph[_bulk]` (entities and relations → Neo4j).
- Metrics on `:9101` (internal).
- Reads uploaded files from the `uploads` volume (`STORAGE_BACKEND=local`) or
  from S3 (`STORAGE_BACKEND=s3`); files are deleted once ingestion ends.
- Rebuild the whole graph (costs LLM calls):
  `docker exec svc_worker celery -A app.worker call app.graph_worker.build_knowledge_graph_bulk`.

### migrate — schema migrations
- Same image as api; runs `alembic upgrade head` as the database owner
  (`POSTGRES_USER`) and exits. On an update, run it on its own first
  (`docker compose run --rm migrate`) so a failed migration doesn't stop the running API.
- Current revision:
  `docker exec rag_postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT version_num FROM alembic_version"'`.

---

## Datastores

### postgres — relational data and vectors
- **Image** `pgvector/pgvector:pg18-trixie`; tuning in `postgres/postgresql.conf`
  (256 MB shared buffers, 30 connections, sized for the 1 GiB limit).
- One schema per bounded context (identity, workspace, knowledge, retrieval,
  metering, audit, shared); chunk embeddings are `halfvec(3072)` with an HNSW index.
  See [data-models.md](./data-models.md).
- `POSTGRES_PASSWORD` is fixed into the volume at first start: don't change it afterwards.
- Backed up nightly by `procedures/backup.sh` (see [README](./README.md#backups)).

### neo4j — knowledge graph
- **Image** `neo4j:5.26-community` with APOC. Heap 512–768 MB, page cache 384 MB.
- Holds Document, Chunk and Entity nodes; it can be rebuilt from Postgres with the
  bulk graph task above, so it is not in the backup.
- `NEO4J_PASSWORD` is fixed into the volume at first start.

### redis — answer cache and rate limits
- **Image** `redis:7-alpine`, `maxmemory 512mb`, `allkeys-lru`: it evicts under
  pressure, so it may only hold data that can be lost.

### redis-broker — Celery queue
- **Image** `redis:7-alpine`, `maxmemory 256mb`, `noeviction`, AOF persistence.
  Kept separate from `redis` so queued jobs are never evicted.

---

## Mail

### postfix — outgoing mail relay
- **Image** `boky/postfix:5.2.1`. The api and Alertmanager send mail to it on the
  Docker network; it relays through `SMTP_RELAY_HOST_URL` with
  `SMTP_USERNAME`/`SMTP_PASSWORD` (a transactional email provider; mail sent
  straight from a VPS lands in spam).
- `SMTP_FROM_EMAIL` must be a sender the provider has verified.
- Undelivered mail: `docker logs rag_postfix`.

---

## Monitoring (profile `monitoring`)

Started together with the stack when `ALERT_EMAIL` is set.

### prometheus
- **Image** `prom/prometheus:v2.55.1`, config `monitoring/prometheus.yml`, alert
  rules `monitoring/alerts.yml`, 30 days of data.
- Scrapes `api:8000/metrics`, `worker:9101/metrics` and node-exporter. Down
  targets: `curl -s 127.0.0.1:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health}'`.

### alertmanager
- **Image** `prom/alertmanager:v0.27.0`; `monitoring/alertmanager.yml.tmpl` is
  filled in at start with `ALERT_EMAIL` (recipient) and `SMTP_FROM_EMAIL` (sender),
  and mail goes out through postfix. Exits at start if `ALERT_EMAIL` is empty.

### node-exporter
- **Image** `prom/node-exporter:v1.8.2` with every collector off except the
  textfile one: it only exposes `backups/metrics/*.prom` (backup age and whether it
  was copied off-host), written by `procedures/backup.sh`.

The alerts themselves are listed in [architecture.md](./architecture.md#observability).

---

## Changing memory limits

Limits are `mem_limit` in `docker-compose.yml`; Neo4j's heap and page cache are
its `NEO4J_server_memory_*` variables (keep heap + page cache about 400 MB below the
limit), and Postgres's buffers are in `postgres/postgresql.conf`. A container that
hits its limit is killed and restarted:
`docker inspect -f '{{.State.OOMKilled}}' <container>` shows whether that happened.
After a change: `docker compose --profile ssl --profile monitoring up -d`
recreates only the changed containers.
