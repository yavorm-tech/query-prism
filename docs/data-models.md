# Data Models

## PostgreSQL Schema

Tables live in one schema per module (`identity`, `workspace`, `knowledge`,
`retrieval`, `metering`, `audit`). The database `search_path` lists all of them,
so SQL uses unqualified table names. Each table is written only by its owning
module (see `docs/architecture.md`).

### `companies` (schema `identity`)

The top-level tenant table. Every other resource belongs to a company.

> The plan and usage columns below are **deprecated** since Alembic revision 0004:
> the plan and counters now live in `metering.subscriptions` and these columns are
> no longer maintained. They are kept for one release as a rollback path.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Unique identifier |
| `name` | TEXT NOT NULL | Display name |
| `slug` | TEXT UNIQUE | URL-safe identifier |
| `plan` | TEXT | *Deprecated* — see `subscriptions.plan` |
| `max_storage_mb`, `max_users`, `max_teams` | INT | *Deprecated* — limits come from `plan_limits` |
| `queries_used_this_month`, `queries_reset_at` | INT / TIMESTAMPTZ | *Deprecated* — see `subscriptions` |
| `storage_used_bytes` | BIGINT | *Deprecated* — see `subscriptions` |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

---

### `teams`

Organizational units within a company. Users are members of one or more teams; documents are owned by teams.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Unique identifier |
| `company_id` | UUID FK → companies | Owning tenant |
| `name` | TEXT NOT NULL | Team name |
| `description` | TEXT | Optional description |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

---

### `users`

Platform accounts. Each user belongs to exactly one company.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Unique identifier |
| `company_id` | UUID FK → companies | Owning tenant |
| `username` | TEXT NOT NULL | Display name |
| `email` | TEXT UNIQUE NOT NULL | Login email |
| `password` | TEXT | bcrypt hash (null for OAuth-only users) |
| `google_id` | TEXT UNIQUE | Google OAuth subject ID |
| `role` | TEXT | `member`, `admin`, `owner` |
| `default_team_id` | UUID FK → teams | Preferred team |
| `avatar` | TEXT | Base64-encoded image (max 1 MB) |
| `created_at` | TIMESTAMPTZ | Registration timestamp |

---

### `team_members`

Many-to-many junction: a user can belong to multiple teams with different roles.

| Column | Type | Description |
|--------|------|-------------|
| `team_id` | UUID FK → teams | Team reference |
| `user_id` | UUID FK → users | User reference |
| `role` | TEXT | `member` or `admin` (team-level) |
| `joined_at` | TIMESTAMPTZ | When membership was created |

**PK:** `(team_id, user_id)`

---

### `topics`

Logical folders for grouping documents within a team.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Unique identifier |
| `team_id` | UUID FK → teams | Owning team |
| `company_id` | UUID FK → companies | Owning tenant (denormalized for fast filtering) |
| `name` | TEXT NOT NULL | Topic name |
| `description` | TEXT | Optional description |
| `created_by` | UUID FK → users | Creator |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

---

### `documents`

Metadata for uploaded files. Actual content is stored as chunks.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Unique identifier |
| `company_id` | UUID FK → companies | Owning tenant |
| `team_id` | UUID FK → teams | Owning team |
| `topic_id` | UUID FK → topics | Optional folder |
| `uploaded_by` | UUID FK → users | Uploader |
| `filename` | TEXT | System filename on disk |
| `original_name` | TEXT | User-facing filename |
| `source_type` | TEXT | `pdf`, `docx`, `txt`, `image`, `video`, `csv`, `web` |
| `visibility` | TEXT | `team` or `company` |
| `status` | TEXT | `pending`, `processing`, `completed`, `failed` |
| `file_size` | BIGINT | File size in bytes |
| `error_message` | TEXT | Failure reason (nullable) |
| `created_at` | TIMESTAMPTZ | Upload timestamp |

---

### `chunks`

Embedded text segments. The core unit of retrieval.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Unique identifier |
| `document_id` | UUID FK → documents | Parent document |
| `chunk_index` | INT | Order within document |
| `content` | TEXT | Raw text content |
| `token_count` | INT | Token count (tiktoken) |
| `embedding_hv` | HALFVEC(3072) | Half-precision OpenAI embedding, HNSW-indexed (cosine) |
| `metadata` | JSONB | Page number, section, etc. |

---

### `query_history`

Persistent log of every question and answer.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Unique identifier |
| `company_id` | UUID FK → companies | Owning tenant |
| `team_id` | UUID FK → teams | Team context |
| `topic_id` | UUID FK → topics | Topic context (nullable) |
| `user_id` | UUID FK → users | Querying user |
| `question` | TEXT | User's question |
| `answer` | TEXT | LLM-generated answer |
| `asked_at` | TIMESTAMPTZ | Query timestamp |

---

### `invites`

Pending team invitations. Accepted invites create new user accounts.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Unique identifier |
| `company_id` | UUID FK → companies | Owning tenant |
| `team_id` | UUID FK → teams | Target team |
| `email` | TEXT NOT NULL | Invitee email |
| `role` | TEXT | Role to grant on acceptance |
| `token` | TEXT UNIQUE | One-time secret token in URL |
| `invited_by` | UUID FK → users | Who sent the invite |
| `expires_at` | TIMESTAMPTZ | Expiry (24 hours from creation) |
| `accepted_at` | TIMESTAMPTZ | When accepted (null = pending) |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

---

### `password_reset_tokens`

Short-lived single-use tokens for password recovery.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Unique identifier |
| `user_id` | UUID FK → users | Target user |
| `token` | TEXT UNIQUE | Secret token sent in email |
| `expires_at` | TIMESTAMPTZ | 1 hour from creation |
| `used_at` | TIMESTAMPTZ | When consumed (null = unused) |

---

### `audit_log`

Immutable event log for compliance.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Unique identifier |
| `company_id` | UUID FK → companies | Owning tenant |
| `team_id` | UUID FK → teams | Affected team (nullable) |
| `actor_id` | UUID | User who performed the action |
| `event_type` | TEXT | e.g., `user.registered`, `document.uploaded` |
| `resource_type` | TEXT | e.g., `document`, `team`, `user` |
| `resource_id` | UUID | ID of the affected resource |
| `resource_name` | TEXT | Human-readable name |
| `metadata` | JSONB | Extra context (IP, old values, etc.) |
| `created_at` | TIMESTAMPTZ | Event timestamp |

---

### `plan_limits`

Reference table (schema `metering`) mapping plan names to their limits and pricing.
`NULL` in a limit column means unlimited.

| Column | Type | Description |
|--------|------|-------------|
| `plan` | TEXT PK | Plan identifier |
| `max_queries` | INT | Monthly query quota |
| `max_storage_mb` | INT | Storage quota in MB |
| `max_teams` | INT | Team quota |
| `max_users` | INT | User quota |
| `llm_model` | TEXT | LLM model string for this plan |
| `price_monthly` | NUMERIC | Monthly price in USD |
| `price_yearly` | NUMERIC | Yearly price in USD (per month) |

---

### `subscriptions`

Schema `metering`. One row per company: its plan and usage counters. Created by
`metering.open_subscription` at sign-up; written only by metering.

| Column | Type | Description |
|--------|------|-------------|
| `company_id` | UUID PK, FK → companies | Tenant |
| `plan` | TEXT FK → plan_limits | Current plan (default `starter`) |
| `queries_used_this_month` | INT | Monthly counter; reset by `reserve_query` when the month rolls over |
| `queries_reset_at` | TIMESTAMPTZ | Start of the month the counter belongs to |
| `storage_used_bytes` | BIGINT | Bytes of completed documents |
| `created_at`, `updated_at` | TIMESTAMPTZ | Timestamps |

---

## Neo4j Graph Schema

Neo4j stores the knowledge graph built from ingested documents.

### Node Labels

| Label | Properties | Description |
|-------|-----------|-------------|
| `Document` | `id`, `filename`, `source_type` | Mirror of a PostgreSQL document |
| `Chunk` | `id`, `document_id`, `chunk_index`, `content_preview` | Mirror of a PostgreSQL chunk (first 200 chars) |
| `Entity` | `id`, `name`, `type`, `normalized`, `aliases` | Named entity extracted by GPT-4o-mini. `id` is a hash of type + normalized name, so the same entity merges across documents |

The graph holds **no tenant data**. Retrieval gets chunk ids from Neo4j and
applies company / team / visibility rules in PostgreSQL. Neo4j is derived from
PostgreSQL and can be rebuilt with the `build_knowledge_graph_bulk` task.

### Relationship Types

| Type | From → To | Description |
|------|----------|-------------|
| `HAS_CHUNK` | Document → Chunk | Chunk's parent document |
| `MENTIONS` | Chunk → Entity | Entity appears in this chunk |
| `RELATED_TO` | Entity → Entity | LLM-extracted relation; properties `predicate`, `weight`, `chunk_ids` |

---

## Entity Relationships Summary

```
companies ──< teams ──< team_members >── users
    │              │
    │              ├──< topics ──< documents ──< chunks
    │              └──< documents
    │
    ├──< users
    ├──< query_history
    ├──< audit_log
    └──< invites
```
