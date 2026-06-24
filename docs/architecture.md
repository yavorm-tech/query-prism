# Architecture Overview

## Tech Stack

### Backend
| Layer | Technology |
|-------|-----------|
| Language | Python 3.x |
| Framework | FastAPI 0.115.0 + Uvicorn |
| Async | asyncio, asyncpg |
| Task Queue | Celery 5.4.0 + Redis broker |
| Authentication | JWT (python-jose), OAuth2 (Google) |
| Rate Limiting | slowapi |

### Databases & Storage
| Store | Technology | Purpose |
|-------|-----------|---------|
| Primary DB | PostgreSQL 16 + pgvector | Relational data, vector embeddings |
| Graph DB | Neo4j 5 | Knowledge graph (entities & relations) |
| Cache / Broker | Redis 7 | Query cache, Celery task broker |

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

## Microservices Architecture

Query-Prism is split into **5 independent backend services** plus supporting infrastructure.

```
                          ┌─────────────────────────────┐
  Browser / Client        │        Nginx Gateway         │  :8000
                          │  (reverse proxy + SSL)       │
                          └──────────────┬──────────────┘
                                         │
              ┌──────────────┬───────────┼───────────┬───────────┐
              │              │           │           │           │
         ┌────▼────┐  ┌──────▼──┐  ┌────▼────┐  ┌──▼──────┐  ┌─▼──────────┐
         │  Auth   │  │Ingestion│  │  Chat   │  │ Billing │  │Notification│
         │ :8001   │  │ :8002   │  │ :8003   │  │ :8004   │  │  :8005     │
         └────┬────┘  └────┬────┘  └────┬────┘  └──┬──────┘  └────────────┘
              │             │            │           │
              └─────────────┴────────────┴───────────┘
                                 │
              ┌──────────────────┼────────────────────┐
              │                  │                    │
         ┌────▼────┐        ┌────▼────┐          ┌───▼───┐
         │Postgres │        │  Neo4j  │          │ Redis │
         │ :5434   │        │  :7687  │          │ :6380 │
         └─────────┘        └─────────┘          └───────┘
                                                      │
                                               ┌──────▼──────┐
                                               │Celery Worker│
                                               │ (ingestion) │
                                               └─────────────┘
```

---

## Service Responsibilities

### Auth Service (`:8001`)
- Company & user registration
- Login, JWT issuance, token refresh
- Google OAuth flow
- Team creation and membership management
- Invitation lifecycle (create, preview, accept)
- Password reset via email token
- Audit event logging

### Ingestion Service (`:8002`)
- File upload validation (type, size)
- Queues Celery background ingestion job
- Document status tracking
- Document listing and deletion

**Celery Worker (background)**
1. Load & extract text from uploaded file
2. Chunk text with LlamaIndex SentenceSplitter
3. Embed chunks with OpenAI (3072-dim vectors)
4. Run NER with spaCy
5. Extract entity relationships
6. Write chunks + embeddings to PostgreSQL
7. Write entities + relations to Neo4j
8. Update document status → `completed`

### Chat Service (`:8003`)
- Hybrid retrieval: pgvector similarity search + Neo4j graph traversal
- Cohere re-ranking of retrieved chunks
- LLM answer generation (Claude or GPT based on plan)
- Redis caching of query results
- Server-Sent Events streaming
- Topic (folder) CRUD and question history

### Billing Service (`:8004`)
- Enforces per-plan quotas (queries, storage, teams, users)
- Tracks monthly query and storage usage
- Returns usage stats for the frontend dashboard
- Called internally by other services; **not exposed externally**

### Notification Service (`:8005`)
- Sends transactional emails via Postfix SMTP relay
- Invite emails, password reset emails, enterprise contact form

---

## Data Flow: Document Ingestion

```
User uploads file
       │
       ▼
Ingestion API ──► validates type/size
       │          ──► checks storage quota (billing svc)
       │          ──► stores metadata in PostgreSQL (status=pending)
       │          ──► saves file to disk
       ▼
Celery Queue (Redis)
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
Chat API ──► checks query quota (billing svc)
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
