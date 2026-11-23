# Architecture decisions

The decisions that shape the system, newest last. A decision is changed by adding
a new one that supersedes it, not by editing the old one's rationale.

| ID | Decision | Status | Rationale |
|---|---|---|---|
| ADR-001 | Five independently deployed microservices | Superseded by ADR-002 | Chosen for separation of concerns, but the shared schema and synchronous calls between services removed the benefits. |
| ADR-002 | Modular monolith with a schema per bounded context; ingestion worker deployed separately | Accepted | Matches team size and load, keeps context boundaries enforceable by tooling, and removes three network hops from every chat request. Boundaries are enforced by import-linter and architecture tests (see [architecture.md](./architecture.md#rules-enforced-in-ci)). |
| ADR-003 | pgvector in Postgres as the vector store | Accepted | Tenant filters, document status and nearest-neighbour search in one query and one transaction. A dedicated vector database is not justified below roughly 50 M chunks. |
| ADR-004 | `halfvec(3072)` with an HNSW index; fp32 column dropped | Accepted | Halves storage with negligible recall loss; HNSW gives sub-linear search. The fp32 column was dropped in Alembic revision 0010. Open option: 1024-dimension embeddings to cut the index by 3×, to be judged with the eval set (`backend/evals/`). |
| ADR-005 | Neo4j knowledge graph as a second retrieval channel | Proposed | Value still unproven. Keep it while the eval set measures recall gained over vector search + re-ranking alone; if the gain is under 3 points, replace it with Postgres entity tables and drop a datastore. |
| ADR-006 | REST + Server-Sent Events for the client API | Accepted | Screens are resource-shaped and answer streaming is one-way. SSE passes through the proxies without upgrade handling; WebSockets add nothing here. |
| ADR-007 | Celery on Redis for ingestion, broker isolated with `noeviction` | Accepted | Retries, routing and Flower already work. The broker must never share an evicting keyspace with the cache. |
| ADR-008 | Plan-based model routing behind a provider-agnostic answer tier | Accepted | Keeps the commercial model (plans → tiers) separate from vendor model IDs, which are retired on vendor timelines, and gives one place for failover (`LLM_TIER_*`). |
| ADR-009 | Short-lived access JWT (15 min) + refresh token in an httpOnly cookie | Accepted | 7-day tokens carrying `team_ids` kept removed members in for up to a week; 15-minute tokens bound that window without a database lookup per request. |
| ADR-010 | Transactional outbox for domain events | Accepted | Cache invalidation, graph indexing and metering follow committed state only, avoiding dual-write bugs between Postgres, Neo4j and Redis. |
| ADR-011 | Traefik terminates TLS and manages Let's Encrypt certificates | Accepted | Replaces the nginx + certbot setup: certificates are issued on first start and renewed and reloaded automatically, with no cron job or restart. The nginx gateway stays as the internal API proxy. |
| ADR-012 | Size the stack for one 8 GiB host and a handful of users | Accepted | Production serves 2–3 users. Container limits total about 7.5 GiB (Postgres 1 GiB, Neo4j 1.5 GiB, worker 1.5 GiB, api 1 GiB) instead of about 20 GiB; raise them per service in `docker-compose.yml` when load grows (see [services.md](./services.md#changing-memory-limits)). |
