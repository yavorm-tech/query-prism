# Entity-Relationship Diagram

## Full PostgreSQL ER Diagram

```mermaid
erDiagram
    companies {
        uuid id PK
        text name
        text slug
        text plan
        int max_storage_mb
        int max_users
        int max_teams
        int queries_used_this_month
        bigint storage_used_bytes
        timestamptz created_at
    }

    teams {
        uuid id PK
        uuid company_id FK
        text name
        text description
        timestamptz created_at
    }

    users {
        uuid id PK
        uuid company_id FK
        text username
        text email
        text password
        text google_id
        text role
        uuid default_team_id FK
        text avatar
        timestamptz created_at
    }

    team_members {
        uuid team_id PK_FK
        uuid user_id PK_FK
        text role
        timestamptz joined_at
    }

    topics {
        uuid id PK
        uuid team_id FK
        uuid company_id FK
        text name
        text description
        uuid created_by FK
        timestamptz created_at
    }

    documents {
        uuid id PK
        uuid company_id FK
        uuid team_id FK
        uuid topic_id FK
        uuid uploaded_by FK
        text filename
        text original_name
        text source_type
        text visibility
        text status
        bigint file_size
        text error_message
        timestamptz created_at
    }

    chunks {
        uuid id PK
        uuid document_id FK
        int chunk_index
        text content
        int token_count
        vector embedding
        halfvec embedding_hv
        jsonb metadata
    }

    query_history {
        uuid id PK
        uuid company_id FK
        uuid team_id FK
        uuid topic_id FK
        uuid user_id FK
        text question
        text answer
        timestamptz asked_at
    }

    invites {
        uuid id PK
        uuid company_id FK
        uuid team_id FK
        text email
        text role
        text token
        uuid invited_by FK
        timestamptz expires_at
        timestamptz accepted_at
        timestamptz created_at
    }

    password_reset_tokens {
        uuid id PK
        uuid user_id FK
        text token
        timestamptz expires_at
        timestamptz used_at
    }

    audit_log {
        uuid id PK
        uuid company_id FK
        uuid team_id FK
        uuid actor_id FK
        text event_type
        text resource_type
        uuid resource_id
        text resource_name
        jsonb metadata
        timestamptz created_at
    }

    plan_limits {
        text plan PK
        int max_queries
        int max_storage_mb
        int max_teams
        int max_users
        text llm_model
        numeric price_monthly
        numeric price_yearly
    }

    companies ||--o{ teams : "has"
    companies ||--o{ users : "has"
    companies ||--o{ topics : "owns"
    companies ||--o{ documents : "owns"
    companies ||--o{ query_history : "records"
    companies ||--o{ audit_log : "records"
    companies ||--o{ invites : "sends"
    companies }o--|| plan_limits : "subscribes to"

    teams ||--o{ team_members : "has"
    teams ||--o{ topics : "contains"
    teams ||--o{ documents : "owns"
    teams ||--o{ query_history : "scopes"

    users ||--o{ team_members : "joins via"
    users ||--o{ documents : "uploads"
    users ||--o{ query_history : "creates"
    users ||--o{ invites : "sends"
    users ||--o{ password_reset_tokens : "requests"
    users ||--o{ audit_log : "triggers"
    users }o--o| teams : "default team"

    topics ||--o{ documents : "contains"
    topics ||--o{ query_history : "scopes"
    topics }o--|| users : "created by"

    documents ||--o{ chunks : "split into"
    documents }o--|| users : "uploaded by"
```

---

## Neo4j Graph Schema

```mermaid
graph LR
    subgraph Neo4j["Neo4j Knowledge Graph"]
        E1["Entity\n(name, type, company_id)"]
        E2["Entity\n(name, type, company_id)"]
        C["Chunk\n(chunk_id, document_id)"]
        D["Document\n(document_id)"]

        E1 -->|RELATED_TO| E2
        E1 -->|MENTIONED_IN| C
        E2 -->|MENTIONED_IN| C
        C -->|BELONGS_TO| D
    end
```

**Entity Types** (spaCy `en_core_web_sm` labels):

| Label | Description |
|-------|-------------|
| `PERSON` | People, including fictional |
| `ORG` | Companies, agencies, institutions |
| `GPE` | Countries, cities, states |
| `LOC` | Non-GPE locations |
| `PRODUCT` | Products, objects |
| `DATE` | Absolute or relative dates |
| `MONEY` | Monetary values |
| `LAW` | Named documents / laws |

---

## Relationship Cardinality Summary

| Relationship | Cardinality | Notes |
|-------------|-------------|-------|
| Company → Teams | 1:N | A company has many teams |
| Company → Users | 1:N | All users belong to one company |
| Team ↔ Users | M:N | Via `team_members` junction |
| Team → Topics | 1:N | Topics are folders within teams |
| Team → Documents | 1:N | Documents are owned by teams |
| Topic → Documents | 1:N | Optional grouping |
| Document → Chunks | 1:N | A document is split into many chunks |
| User → Documents | 1:N | User uploads documents |
| Company → plan_limits | N:1 | Many companies on the same plan |
