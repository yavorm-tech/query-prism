# Architecture Overview

## Tech Stack

### Backend
| Layer | Technology |
|-------|-----------|
| Language | Python 3.x |
| Framework | FastAPI 0.115.0 + Uvicorn |
| Async | asyncio, asyncpg |
| Task Queue | Celery 5.4.0 + dedicated Redis broker |
| Authentication | JWT (python-jose), OAuth2 (Google) |
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
| LLM | Anthropic Claude, OpenAI GPT |
| Embeddings | OpenAI text-embedding-3-large (3072 dims) |
| Re-ranking | Cohere API |
| Token Counting | tiktoken |
| Chunking | LlamaIndex SentenceSplitter |
| NER | spaCy |

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
| SSL | Certbot + Let's Encrypt |
| Mail | Postfix SMTP relay |

---

## Modular Monolith

Query-Prism runs as **one API process** organised into **bounded contexts**, plus a
separately deployed **Celery worker** built from the same code (`backend/`).
Until v2 it was five HTTP microservices sharing one database; see
`docs/architecture-document.html` for the review that led to the change.

```
        Browser ──► Nginx edge (TLS) ──► Nginx gateway :8000 ──► api :8000
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

When a lower context must trigger work in a higher one it publishes a **domain
event** (`app/shared/events.py`); handlers are wired in `app/bootstrap.py`:

| Event | Published by | Handled by |
|-------|--------------|-----------|
| `CompanyRegistered` | identity | workspace creates the default "Main" topic |
| `DocumentIngested` / `DocumentDeleted` | knowledge | retrieval drops affected cached answers |
| `TopicDeleted` | workspace | retrieval drops the team's cached answers |

Metering needs team/user counts for the usage page without reading identity's
tables: identity implements metering's `TenantDirectory` port (also wired in
`app/bootstrap.py`).

### Database schemas

| Schema | Tables | Owner |
|--------|--------|-------|
| `identity` | companies, teams, users, team_members, invites, password_reset_tokens | identity |
| `workspace` | topics | workspace |
| `knowledge` | documents, chunks (pgvector halfvec + HNSW) | knowledge |
| `retrieval` | query_history | retrieval |
| `metering` | plan_limits, subscriptions | metering |
| `audit` | audit_log | audit |

Migrations are Alembic revisions in `backend/migrations/versions/`, applied by the
`migrate` compose service before `api` and `worker` start.

### Observability

- **Logs**: one JSON object per line (structlog), with `request_id` on every API
  log line and `document_id` on worker lines. Send `X-Request-ID` to correlate.
  Tracebacks never include local variables.
- **Metrics**: `api:8000/metrics` and `worker:9101/metrics` (internal only, not
  routed by the gateway). Key series: `qp_answer_ttft_seconds`,
  `qp_answer_cache_total`, `qp_no_context_answers_total`,
  `qp_retrieval_fallback_total`, `qp_llm_errors_total`,
  `qp_ingest_duration_seconds`, `qp_documents_by_status`,
  `http_request_duration_seconds`.

Suggested alerts: `qp_documents_by_status{status="pending"}` > 0 for 15 min;
`rate(qp_llm_errors_total[5m])` > 5 % of answers; p95 of
`qp_answer_ttft_seconds` > 4 s for 15 min.

## Data Flow: Document Ingestion

```
User uploads file
       │
       ▼
Ingestion API ──► validates type/size
       │          ──► checks storage quota (metering)
       │          ──► stores metadata in PostgreSQL (status=pending)
       │          ──► saves file to disk
       ▼
Celery Queue (redis-broker)
       │
       ▼
Celery Worker
  1. Load file ──► extract raw text
  2. Chunk text (LlamaIndex SentenceSplitter)
  3. Embed chunks (OpenAI batch API)  ──► PostgreSQL chunks table (pgvector)
  4. NER + relation extraction (spaCy) ──► Neo4j knowledge graph
  5. Update document status → "completed"
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
Chat API ──► reserves one query atomically (metering)
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
LLM (Claude / GPT based on plan)
  ├── Streaming: SSE token stream to client
  └── Non-streaming: full answer returned
       │
       ▼
Store in query_history + increment billing counter
Cache result in Redis
```

---

## Multi-Tenancy Model

Every resource is scoped to a `company_id`. Strict row-level isolation is enforced at the application layer.

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
