# Data Models

## PostgreSQL Schema

### `companies`

The top-level tenant table. Every other resource belongs to a company.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Unique identifier |
| `name` | TEXT NOT NULL | Display name |
| `slug` | TEXT UNIQUE | URL-safe identifier |
| `plan` | TEXT | `starter`, `team`, `business`, `enterprise` |
| `max_storage_mb` | INT | Storage quota from plan |
| `max_users` | INT | User quota from plan (`-1` = unlimited) |
| `max_teams` | INT | Team quota from plan (`-1` = unlimited) |
| `queries_used_this_month` | INT | Rolling monthly counter |
| `storage_used_bytes` | BIGINT | Running storage total |
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
| `embedding` | VECTOR(3072) | Full-precision OpenAI embedding |
| `embedding_hv` | HALFVEC(3072) | Half-precision embedding (index efficiency) |
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

Reference table mapping plan names to their limits and pricing.

| Column | Type | Description |
|--------|------|-------------|
| `plan` | TEXT PK | Plan identifier |
| `max_queries` | INT | Monthly query quota (`-1` = unlimited) |
| `max_storage_mb` | INT | Storage quota in MB (`-1` = unlimited) |
| `max_teams` | INT | Team quota (`-1` = unlimited) |
| `max_users` | INT | User quota (`-1` = unlimited) |
| `llm_model` | TEXT | LLM model string for this plan |
| `price_monthly` | NUMERIC | Monthly price in USD |
| `price_yearly` | NUMERIC | Yearly price in USD (per month) |

---

## Neo4j Graph Schema

Neo4j stores the knowledge graph built from ingested documents.

### Node Labels

| Label | Properties | Description |
|-------|-----------|-------------|
| `Entity` | `name`, `type`, `document_id`, `company_id` | Named entity extracted by spaCy (person, org, location, etc.) |
| `Chunk` | `chunk_id`, `document_id` | Reference to a PostgreSQL chunk |

### Relationship Types

| Type | From → To | Description |
|------|----------|-------------|
| `RELATED_TO` | Entity → Entity | Relationship extracted between two entities |
| `MENTIONED_IN` | Entity → Chunk | Entity appears in this chunk |
| `BELONGS_TO` | Chunk → Document | Chunk's parent document |

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
