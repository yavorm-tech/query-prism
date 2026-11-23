# Architecture Overview

## Tech Stack

### Backend
| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| Framework | FastAPI 0.115.0 + Uvicorn |
| Async | asyncio, asyncpg |
| Task Queue | Celery 5.4.0 + dedicated Redis broker |
| Authentication | JWT (PyJWT, HS256), OAuth2 (Google) |
| Rate Limiting | slowapi (per user, Redis-backed) |
| Logging / Metrics | structlog (JSON) / prometheus-client |
| Migrations | Alembic (raw SQL revisions) |

### Databases & Storage
| Store | Technology | Purpose |
|-------|-----------|---------|
| Primary DB | PostgreSQL 18 + pgvector 0.8 (halfvec + HNSW) | Relational data, vector embeddings |
| Graph DB | Neo4j 5 | Knowledge graph (entities & relations) |
| Cache | Redis 7 (`redis`) | Answer cache, rate-limit counters (LRU eviction) |
| Broker | Redis 7 (`redis-broker`) | Celery broker + results (noeviction, AOF) |

### AI / ML
| Component | Technology |
|-----------|-----------|
| LLM | Anthropic Claude, OpenAI GPT behind one adapter (`app/shared/ai/llm.py`): plans name a tier, tiers map to ordered provider:model routes with failover |
| Embeddings | OpenAI text-embedding-3-large (3072 dims) |
| Re-ranking | Cohere API |
| Token Counting | tiktoken |
| Chunking | LlamaIndex SentenceSplitter |
| NER | OpenAI GPT-4o-mini (shared by indexing and query) |

### Document Processing
| Format | Library |
|--------|---------|
| PDF | pdfplumber |
| Images | Pillow + pytesseract |
| Office | python-docx |
| Audio/Video | faster-whisper |
| CSV/TXT/MD | Built-in |

### Frontend
| Layer | Technology |
|-------|-----------|
| Framework | React 19 + TypeScript |
| Build | Vite |
| Styling | Tailwind CSS + Flowbite |
| State | TanStack React Query |
| Forms | TanStack React Form |
| Tables | TanStack React Table |
| HTTP | Axios |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Containers | Docker + Docker Compose |
| Gateway | Nginx (reverse proxy, SSL termination) |
| TLS | Traefik (Let's Encrypt, automatic issue and renewal) |
| Mail | Postfix SMTP relay |

---

## Modular Monolith

Query-Prism runs as **one API process** organised into **bounded contexts**, plus a
separately deployed **Celery worker** built from the same code (`backend/`).
Until v2 it was five HTTP microservices sharing one database; see
`docs/architecture-document.html` for the review that led to the change.

```
        Browser ──► Traefik (TLS) ──► Nginx gateway :8000 ──► api :8000
                                                                   │
   ┌───────────────────────────── backend/app ─────────────────────┴──────────┐
   │  retrieval   /chat, /topics/{id}/questions     answers, question history │
   │      ▼                                                                   │
   │  knowledge   /ingest, /topics/{id}/documents   documents, chunks, graph  │
   │      ▼                                                                   │
   │  workspace   /topics                           topics                    │
   │      ▼                                                                   │
   │  identity    /auth, /auth/oauth                companies, users, teams   │
   │      ▼                                                                   │
   │  metering /usage · notification /contact · audit /audit                  │
   │      ▼                                                                   │
   │  shared      config, db, neo4j, security, rate limit, events, AI clients │
   └──────────────────────────────────────────────────────────────────────────┘
          │ send_task("app.worker.ingest_document")
          ▼
   redis-broker ──► worker (Celery)  load → chunk → embed → Postgres → Neo4j
```

### Rules (enforced in CI)

| Rule | Enforced by |
|------|-------------|
| Contexts depend only downward in the order above | `lint-imports` (pyproject.toml) |
| A context imports another only through its `api.py` | `tests/architecture/test_boundaries.py` |
| Each table is written only by the context that owns its schema | `tests/architecture/test_boundaries.py` |
| Cross-context SQL reads may only shrink (allowlist) | `tests/architecture/test_boundaries.py` |
| Every table has an owning context | `tests/architecture/test_boundaries.py` |

When a lower context must trigger work in a higher one, or work must follow a
committed change, it publishes a **domain event** (`app/shared/events.py`);
handlers are wired in `app/bootstrap.py`:

| Event | Published by | Handled by |
|-------|--------------|-----------|
| `CompanyRegistered` | identity | workspace creates the default "Main" topic (skipped if it exists) |
| `DocumentUploaded` | knowledge (upload) | knowledge queues the ingestion task (Celery task id = `job_id`) |
| `DocumentIngested` | knowledge (worker) | retrieval drops affected cached answers; knowledge queues graph extraction |
| `DocumentDeleted` | knowledge | retrieval drops affected cached answers; knowledge deletes the document's graph |
| `TopicDeleted` | workspace | retrieval drops the team's cached answers |

Events go through a **transactional outbox** (ADR-010): `uow.publish()` writes
the event to `shared.outbox` in the same transaction as the change, so an event
exists exactly when its change committed. It is delivered right after commit in
the publishing process; if a handler fails or the process dies, the relay in
the API (`events.run_relay`, every 5 s) redelivers it with exponential backoff,
up to 10 attempts. Delivery is at-least-once, so handlers are idempotent.
`CompanyRegistered` is the one event not yet in the same transaction as its
change (registration spans several statements); it is still recorded before
delivery, so a failed handler is retried.

Metering needs team/user counts for the usage page without reading identity's
tables: identity implements metering's `TenantDirectory` port (also wired in
`app/bootstrap.py`).

### Database schemas

| Schema | Tables | Owner |
|--------|--------|-------|
| `identity` | companies, teams, users, team_members, invites, password_reset_tokens, refresh_tokens | identity |
| `workspace` | topics | workspace |
| `knowledge` | documents, chunks (pgvector halfvec + HNSW) | knowledge |
| `retrieval` | query_history | retrieval |
| `metering` | plan_limits, subscriptions | metering |
| `audit` | audit_log | audit |
| `shared` | outbox; functions `current_company()`, `apply_app_grants()` | shared kernel (`app/shared/events.py`, `app/shared/db.py`) |

Migrations are Alembic revisions in `backend/migrations/versions/`, applied by the
`migrate` compose service before `api` and `worker` start. Alembic alone builds a
fresh database: revision 0001 creates the baseline schema from
`backend/migrations/sql/0001_baseline.sql` when the database is empty.

The `migrate` service connects as the owner (`POSTGRES_USER`); `api` and `worker`
connect as `APP_DB_USER` (`qp_app`), which revision 0011 creates with only row
privileges, so row-level security (0012) applies to them.

### Upload storage

Files wait between upload and ingestion in `app/shared/storage.py`:
`STORAGE_BACKEND=local` (default) uses the `uploads` volume shared by `api` and
`worker`, so both must run on one host; `STORAGE_BACKEND=s3` uses any
S3-compatible bucket (`S3_BUCKET`, `S3_ENDPOINT_URL`, …), so they can run on
different hosts. Files are deleted once ingestion finishes or finally fails.

### Observability

- **Logs**: one JSON object per line (structlog), with `request_id` on every API
  log line and `document_id` on worker lines. Send `X-Request-ID` to correlate.
  Tracebacks never include local variables.
- **Metrics**: `api:8000/metrics` and `worker:9101/metrics` (internal only, not
  routed by the gateway). Key series: `qp_answer_ttft_seconds`,
  `qp_answer_cache_total`, `qp_no_context_answers_total`,
  `qp_retrieval_fallback_total`, `qp_llm_errors_total` (every route of a tier
  failed), `qp_llm_failovers_total` (a route was skipped), `qp_outbox_pending`,
  `qp_outbox_dead_total`, `qp_ingest_duration_seconds`, `qp_documents_by_status`,
  `http_request_duration_seconds`.

Alerts live in `monitoring/alerts.yml` and run in the opt-in `monitoring` compose
profile (Prometheus → Alertmanager → email via `postfix`): `ServiceDown`,
`BackupStale` (> 26 h), `BackupNeverRecorded`, `BackupNotOffHost`,
`OutboxEventDead`, `OutboxBacklog` (15 min), `LLMFailingOver`, `LLMErrors`
(> 5 % of answers), `IngestionStuck` (pending 15 min) and `SlowAnswers` (p95 time
to first token > 4 s). Backup age comes from `backups/metrics/backup.prom`, written
by `procedures/backup.sh` and exposed by node-exporter's textfile collector.

## Data Flow: Document Ingestion

```
User uploads file
       │
       ▼
knowledge (POST /ingest) ──► validates type/size, team/topic access
       │          ──► checks storage quota (metering)
       │          ──► streams the file to upload storage (local volume or S3)
       │          ──► one transaction: document row (status=pending) + DocumentUploaded
       ▼
DocumentUploaded handler: send_task → redis-broker (queue "ingestion")
       │
       ▼
Celery Worker
  0. Skip if the document is already completed (duplicate delivery)
  1. Load file (from upload storage) ──► extract raw text
  2. Chunk text (LlamaIndex SentenceSplitter)
  3. Embed chunks (OpenAI batch API)  ──► PostgreSQL chunks table (pgvector)
  4. One transaction: status → "completed" + DocumentIngested
  5. Count storage (metering), delete the uploaded file
  6. DocumentIngested handlers: drop cached answers; queue build_knowledge_graph
     (NER + relations with GPT-4o-mini ──► Neo4j)
       │
       ▼
PostgreSQL + Neo4j ready for queries
```

---

## Data Flow: Chat Query

```
User sends query
       │
       ▼
retrieval (/chat) ──► reserves one query atomically (metering)
       │    ──► checks Redis cache (hit → return cached)
       │
       ▼
Retriever
  ├── pgvector similarity search (top-K chunks)
  └── Neo4j graph traversal (entity-linked chunks)
       │
       ▼
Cohere Re-ranking (optional)
       │
       ▼
LLM adapter: plan's answer tier → first working provider:model route
  ├── Streaming: SSE token stream to client
  └── Non-streaming: full answer returned
       │
       ▼
Store in query_history (quota was already reserved; released on no-context or pre-LLM errors)
Cache result in Redis
```

---

## Multi-Tenancy Model

Every resource is scoped to a `company_id`. Isolation is enforced in the application layer and again by Postgres row-level security for authenticated requests (see `docs/security.md`), both covered by integration tests.

```
Company (tenant)
  ├── Teams (organizational units)
  │     ├── Members (users with team-level roles)
  │     ├── Topics (folder-like groupings)
  │     │     └── Documents
  │     └── Documents (team-scoped)
  └── Company-Wide Documents (visibility=company)
```

**Role Hierarchy:**

| Role | Scope | Permissions |
|------|-------|-------------|
| Owner | Company | All permissions including billing |
| Admin | Company | Team management, invite users, audit log |
| Member | Team(s) | Upload docs, chat within assigned teams |

**Document Visibility:**
- `team` — only visible to members of the owning team
- `company` — visible to all members of the company
