# Component Diagram

High-level view of the containers and the modules inside the API. Query-Prism
is a **modular monolith**: one `api` process and one Celery `worker`, both built
from `backend/`. Modules call each other in-process through their `api.py`;
the only cross-process hop inside the system is API → `redis-broker` → worker.

```mermaid
C4Component
    title Query-Prism Component Diagram

    Person(user, "End User", "Company employee querying documents")
    Person(admin, "Company Admin", "Manages teams, users, billing")

    Container_Boundary(frontend, "React Frontend") {
        Component(spa, "SPA", "React 19 + TypeScript", "Single-page app served by Nginx")
    }

    Container_Boundary(gateway, "Nginx Gateway :8000") {
        Component(proxy, "Reverse Proxy", "Nginx", "Routes every API path to api:8000")
    }

    Container_Boundary(api, "api :8000 (FastAPI modular monolith)") {
        Component(retrieval, "retrieval", "/chat, /topics/{id}/questions", "Hybrid search, re-rank, LLM answers, answer cache, question history")
        Component(knowledge, "knowledge", "/ingest, /topics/{id}/documents", "Upload, document status, delete; queues ingestion")
        Component(workspace, "workspace", "/topics", "Topic CRUD and topic access checks")
        Component(identity, "identity", "/auth, /auth/oauth", "Register, login, Google OAuth, teams, invites, JWT")
        Component(metering, "metering", "/usage", "Plans, atomic query reservation, storage/team/user limits")
        Component(notification, "notification", "/contact", "Transactional email")
        Component(audit, "audit", "/audit", "Append-only audit trail")
        Component(shared, "shared", "kernel", "Config, DB pools, security, rate limit, events, embedder, NER")
    }

    Container_Boundary(worker, "worker (Celery, same codebase)") {
        Component(ingest_task, "ingest_document", "knowledge.tasks", "Load → chunk → embed → write chunks → mark complete")
        Component(graph_task, "build_knowledge_graph", "knowledge.graph_tasks", "GPT-4o-mini NER + relations → Neo4j")
    }

    ContainerDb(postgres, "PostgreSQL 18 + pgvector", "schema per module", "identity, workspace, knowledge, retrieval, metering, audit")
    ContainerDb(neo4j, "Neo4j 5.26", "Graph", "Document, Chunk, Entity nodes")
    ContainerDb(redis, "redis", "Redis 7, LRU", "Answer cache, rate limits")
    ContainerDb(broker, "redis-broker", "Redis 7, noeviction + AOF", "Celery queue 'ingestion'")
    ContainerDb(postfix, "Postfix", "SMTP relay", "Email delivery")

    Rel(user, spa, "Uses", "HTTPS")
    Rel(admin, spa, "Uses", "HTTPS")
    Rel(spa, proxy, "API requests", "HTTP/JSON, SSE")
    Rel(proxy, retrieval, "All API paths", "HTTP to api:8000")

    Rel(retrieval, knowledge, "Reads documents/chunks", "SQL (allowlisted cross-read)")
    Rel(retrieval, workspace, "require_topic_access", "in-process")
    Rel(retrieval, metering, "reserve_query / release_query", "in-process")
    Rel(knowledge, metering, "check_storage_limit", "in-process")
    Rel(identity, metering, "open_subscription, limits", "in-process")
    Rel(identity, notification, "Invite / reset emails", "in-process")

    Rel(knowledge, broker, "send_task ingest_document", "Redis")
    Rel(broker, ingest_task, "Dispatch", "Redis")
    Rel(ingest_task, graph_task, "send_task build_knowledge_graph", "Redis")

    Rel(ingest_task, postgres, "Write chunks + vectors", "asyncpg")
    Rel(graph_task, neo4j, "MERGE graph", "Bolt")
    Rel(retrieval, postgres, "Vector search (HNSW)", "asyncpg")
    Rel(retrieval, neo4j, "Entity traversal", "Bolt")
    Rel(retrieval, redis, "Answer cache", "Redis")
    Rel(notification, postfix, "Send via SMTP", "SMTP :25")
```

---

## Simplified Interaction Map

```
                 ┌──────────────┐
                 │ React (SPA)  │
                 └──────┬───────┘
                        │ HTTPS
                 ┌──────▼───────┐
                 │ Nginx :8000  │   every API path → api:8000
                 └──────┬───────┘
                        │
   ┌────────────────────▼──────────────── api ───────────────────────────┐
   │  retrieval ──► knowledge ──► workspace ──► identity                 │
   │      │             │              │            │                    │
   │      └─────────────┴──────────────┴────────────┴──► metering        │
   │                                                     notification    │
   │                                                     audit           │
   │  shared (config, db, security, events, AI clients)                  │
   └───────────────┬─────────────────────────────────────────────────────┘
                   │ send_task
           ┌───────▼────────┐        ┌──────────────────────────┐
           │  redis-broker  │──────► │  worker (Celery)         │
           └────────────────┘        │  ingest_document         │
                                     │  build_knowledge_graph   │
                                     └──────────────────────────┘
                   │                               │
   ┌───────────────▼───────────────────────────────▼──────────────┐
   │  PostgreSQL (schema per module)   Neo4j   redis (cache)       │
   └───────────────────────────────────────────────────────────────┘
```
