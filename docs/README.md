# Query-Prism Documentation

**AskYourBase** (internal codename: Query-Prism) is a multi-tenant RAG (Retrieval-Augmented Generation) platform that enables companies to upload documents and query them using AI.

---

## Table of Contents

| Document | Description |
|----------|-------------|
| [Architecture Overview](./architecture.md) | System design, tech stack, modules and their rules |
| [Architecture Review](./architecture-document.html) | Oct 2026 review, roadmap (Phases 0–3) and ADRs |
| [Data Models](./data-models.md) | Database schema, field definitions, relationships |
| [Security & Permissions](./security.md) | Auth, RBAC, rate limiting, audit trail |
| **API Reference** | |
| [Auth API](./api/auth.md) | Registration, login, OAuth, teams, invites (identity) |
| [Ingestion API](./api/ingestion.md) | File upload, document management (knowledge) |
| [Chat API](./api/chat.md) | Query, streaming, topics (retrieval, workspace) |
| [Metering API](./api/billing.md) | Usage quotas, plan limits (metering) |
| [Notification API](./api/notification.md) | Contact form, transactional email (notification) |
| **Diagrams** | |
| [Component Diagram](./diagrams/component-diagram.md) | Containers and the modules inside `api` |
| [Module Diagram](./diagrams/class-diagram.md) | Module APIs, dependencies and domain events |
| [ER Diagram](./diagrams/er-diagram.md) | Database entity-relationship diagram |
| [Sequence Diagrams](./diagrams/sequence-diagrams.md) | Key user-flow step-by-step sequences |
| [Deployment Diagram](./diagrams/deployment-diagram.md) | Infrastructure and container layout |

---

## Quick-Start

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys and secrets

# Start all services (production: no datastore ports published)
docker compose up -d

# Local development: also publishes datastore ports on 127.0.0.1 and starts Flower
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Access
# Frontend:      http://localhost:3000
# API Gateway:   http://localhost:8000   (bound to 127.0.0.1 only)
# Flower (queue):http://localhost:5556   (dev overlay only)
```

`SECRET_KEY` is required and must be at least 32 random characters
(`openssl rand -hex 32`); the API and worker refuse to start otherwise.
`POSTGRES_PASSWORD` and `NEO4J_PASSWORD` have no defaults.

---

## Containers and Ports

| Container | Port | Description |
|---------|------|-------------|
| Nginx Gateway | 127.0.0.1:8000 | API entry point behind the TLS proxy, routes everything to `api`; loopback-only on the host |
| api | 8000 (internal) | All HTTP endpoints; `/metrics` internal only |
| worker | 9101 (internal) | Celery ingestion worker; Prometheus metrics |
| migrate | — | Runs `alembic upgrade head` once per deploy |
| PostgreSQL | 5434 (dev overlay) | Primary relational store, one schema per context |
| Neo4j | 7474 / 7687 (dev overlay) | Knowledge graph |
| Redis (cache) | 6380 (dev overlay) | Answer cache & rate-limit counters, LRU eviction |
| Redis (broker) | 6381 (dev overlay) | Celery broker & results, noeviction + AOF |
| Flower | 5556 (dev overlay) | Celery task monitor |

## Backend development

```bash
cd backend
pip install -r requirements-dev.txt
ruff check . && lint-imports              # lint + architecture contract
python -m pytest                          # unit + architecture tests
TEST_DATABASE_URL=postgresql://user:pass@localhost:5434/postgres \
REDIS_URL=redis://localhost:6380/15 python -m pytest   # + integration tests (builds qp_test with Alembic)
alembic revision -m "describe change"     # new migration (raw SQL in upgrade())
```

## Plan Tiers

| Plan | Queries/mo | Storage | Teams | Users | Answer tier (default routes) |
|------|-----------|---------|-------|-------|-----|
| Starter (Free) | 50 | 50 MB | 1 | 3 | `basic`: GPT-4o Mini → Claude Haiku 4.5 |
| Team | 1,000 | 5 GB | 5 | 25 | `standard`: Claude Haiku 4.5 → GPT-4o Mini |
| Business | 5,000 | 20 GB | Unlimited | Unlimited | `premium`: Claude Sonnet 4.6 → GPT-4o |
| Enterprise | Unlimited | Unlimited | Unlimited | Unlimited | `premium` |

Routes are set with `LLM_TIER_BASIC`, `LLM_TIER_STANDARD` and `LLM_TIER_PREMIUM`
(see `.env.example`); changing a model is a config change and a restart.

## Backups

```bash
procedures/install-backup-cron.sh     # once, on the production host: nightly 02:30
procedures/backup.sh                  # run now (dump → verify → copy to BACKUP_S3_URI)
```

Set `BACKUP_S3_URI` (and `AWS_*`, or `BACKUP_S3_ENDPOINT_URL` for an S3-compatible
store) in `.env`; without it the dumps stay on the host. Each successful run
writes `backups/metrics/backup.prom`, which the monitoring profile alerts on.

## Staging

A second, isolated copy of the stack (`docker-compose.staging.yml`): its own
compose project, `stg_*` containers, volumes, `:staging` image tags and
`.env.staging` (production's `.env` is never read), listening only on
127.0.0.1:18080 (app) and :18000 (API).

```bash
cp .env.staging.example .env.staging          # own secrets, STAGING_PASSWORD
procedures/staging.sh up                      # build + start (empty database)
procedures/staging.sh refresh                 # load the newest backup, migrate, scrub
ssh -L 18080:127.0.0.1:18080 <host>           # open http://localhost:18080
```

`refresh` is the release rehearsal: it restores a production backup, applies
the pending migrations to real data, then runs `procedures/staging-scrub.sql`
(emails → `user-<id>@staging.invalid`, Google links, avatars, tokens, invites
and audit emails/IPs removed, every password set to `STAGING_PASSWORD`,
undelivered events dropped). Customer documents and questions stay, so keep
staging access as tight as production's. To test a release before deploying it,
run staging from a separate checkout of that release.

## Answer-quality eval

`backend/evals/` holds a fixed corpus (five documents about a fictional company)
and 28 questions: single-document lookups, questions that need two documents,
and questions the corpus can't answer. The runner signs up a throwaway company
on a running stack, uploads the corpus, asks every question through `POST /chat`
and grades the answers without an LLM judge: expected source files retrieved
(doc recall, MRR), required facts present, and a clear "the documents don't
say" for unanswerable questions.

```bash
cd backend
python -m evals.run --base-url http://127.0.0.1:18000 --out evals/results/$(date +%F).json
python -m evals.run ... --min-answer-pass 0.85 --min-refusal 1   # exit 1 below these
```

Run it against staging. It costs real API calls (embeddings, graph extraction,
re-ranking, ~28 answers). A new company is on the starter plan, so answers use
the `basic` tier; to compare models, change `LLM_TIER_BASIC` in staging and
run again. Add real (anonymised) questions over time; five documents make
retrieval easy, so the answer and refusal scores matter most at first.

## Monitoring and alerts

```bash
docker compose --profile monitoring up -d   # needs ALERT_EMAIL in .env
ssh -L 9090:127.0.0.1:9090 -L 9093:127.0.0.1:9093 <host>   # Prometheus / Alertmanager UIs
```

Prometheus scrapes `api` and `worker` and evaluates `monitoring/alerts.yml`;
Alertmanager emails `ALERT_EMAIL` through the `postfix` service. Alerts: a
service down, the backup older than 26 h, not copied off-host or never run, an
outbox event given up on or a 15-minute backlog, an LLM route failing over, over
5 % of answers failing on every route, documents pending for 15 minutes, and p95
time to first token over 4 s.
