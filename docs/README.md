# Query-Prism Documentation

**AskYourBase** (internal codename: Query-Prism) is a multi-tenant RAG (Retrieval-Augmented Generation) platform that enables companies to upload documents and query them using AI.

---

## Table of Contents

| Document | Description |
|----------|-------------|
| [Architecture Overview](./architecture.md) | System design, tech stack, service breakdown |
| [Data Models](./data-models.md) | Database schema, field definitions, relationships |
| [Security & Permissions](./security.md) | Auth, RBAC, rate limiting, audit trail |
| **API Reference** | |
| [Auth API](./api/auth.md) | Registration, login, OAuth, teams, invites |
| [Ingestion API](./api/ingestion.md) | File upload, document management |
| [Chat API](./api/chat.md) | Query, streaming, topics |
| [Billing API](./api/billing.md) | Usage quotas, plan limits |
| [Notification API](./api/notification.md) | Email sending |
| **Diagrams** | |
| [Component Diagram](./diagrams/component-diagram.md) | High-level service interaction |
| [Class Diagram](./diagrams/class-diagram.md) | Service classes and their relationships |
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
# API Gateway:   http://localhost:8000
# Flower (queue):http://localhost:5556   (dev overlay only)
```

`SECRET_KEY` is required and must be at least 32 random characters
(`openssl rand -hex 32`); the API and worker refuse to start otherwise.
`POSTGRES_PASSWORD` and `NEO4J_PASSWORD` have no defaults.

---

## Service Ports

| Service | Port | Description |
|---------|------|-------------|
| Nginx Gateway | 8000 | External API entry point, routes everything to `api` |
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
REDIS_URL=redis://localhost:6380/15 python -m pytest   # + integration tests
alembic revision -m "describe change"     # new migration (raw SQL in upgrade())
```

## Plan Tiers

| Plan | Queries/mo | Storage | Teams | Users | LLM |
|------|-----------|---------|-------|-------|-----|
| Starter (Free) | 50 | 50 MB | 1 | 3 | GPT-4o Mini |
| Team | 1,000 | 5 GB | 5 | 25 | Claude Haiku |
| Business | 5,000 | 20 GB | Unlimited | Unlimited | Claude Sonnet |
| Enterprise | Unlimited | Unlimited | Unlimited | Unlimited | Claude Sonnet |
