-- ===================================================G=========
-- RAG Chatbot — Multi-tenant schema
-- Company -> Teams -> Users -> Documents
-- ============================================================
-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── Tier 1: Companies (top-level tenants) ────────────────────
CREATE TABLE IF NOT EXISTS companies (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name         TEXT NOT NULL,
    slug         TEXT UNIQUE NOT NULL,
    plan         TEXT NOT NULL DEFAULT 'starter'
                     CHECK (plan IN ('starter', 'free', 'team', 'business', 'enterprise')),
    max_storage_mb            INT NOT NULL DEFAULT 50,
    max_users                 INT NOT NULL DEFAULT 3,
    max_teams                 INT NOT NULL DEFAULT 1,
    queries_used_this_month   INT DEFAULT 0,
    queries_reset_at          TIMESTAMPTZ DEFAULT date_trunc('month', now()),
    storage_used_bytes        BIGINT DEFAULT 0,
    max_queries_per_month     INT DEFAULT 50,
    max_storage_bytes         BIGINT DEFAULT 52428800,
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

-- ── Tier 2: Teams within a company ───────────────────────────
CREATE TABLE IF NOT EXISTS teams (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id   UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    description  TEXT,
    created_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE(company_id, name)
);

-- ── Tier 3: Users ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id     UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    username       TEXT NOT NULL,
    email          TEXT UNIQUE NOT NULL,
    password       TEXT,
    google_id      TEXT UNIQUE,
    role           TEXT NOT NULL DEFAULT 'member'
                       CHECK (role IN ('member', 'admin', 'owner')),
    default_team_id UUID,                   -- preferred team for uploads
    avatar         TEXT,
    is_active      BOOLEAN DEFAULT TRUE,
    created_at     TIMESTAMPTZ DEFAULT now(),
    UNIQUE(company_id, username),
    CHECK (password IS NOT NULL OR google_id IS NOT NULL)
);

-- ── Many-to-many: users belong to teams ──────────────────────
CREATE TABLE IF NOT EXISTS team_members (
    team_id    UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role       TEXT NOT NULL DEFAULT 'member'
                   CHECK (role IN ('member', 'admin')),
    joined_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (team_id, user_id)
);

-- ── Password reset tokens ────────────────────────────────────
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ── Invite tokens ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invites (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id   UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    team_id      UUID REFERENCES teams(id) ON DELETE CASCADE,
    email        TEXT NOT NULL,
    role         TEXT NOT NULL DEFAULT 'member',
    token        TEXT UNIQUE NOT NULL,      -- signed invite token
    invited_by   UUID NOT NULL REFERENCES users(id),
    accepted_at  TIMESTAMPTZ,
    expires_at   TIMESTAMPTZ NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- ── Chunks table (pgvector) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS chunks (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id   UUID NOT NULL,            -- FK added after documents table
    chunk_index   INT  NOT NULL,
    content       TEXT NOT NULL,
    token_count   INT,
    embedding     vector(3072),
    embedding_hv  halfvec(3072),
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- ── Documents ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id    UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    team_id       UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    uploaded_by   UUID NOT NULL REFERENCES users(id),
    filename      TEXT NOT NULL,
    original_name TEXT NOT NULL,
    source_type   TEXT NOT NULL CHECK (source_type IN ('pdf','docx','txt','image','video','web','csv')),
    file_size     BIGINT,
    mime_type     TEXT,
    visibility    TEXT NOT NULL DEFAULT 'team'
                      CHECK (visibility IN ('team', 'company')),
    status        TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','processing','completed','failed')),
    error_message TEXT,
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);

-- Add FK from chunks to documents
ALTER TABLE chunks
    ADD CONSTRAINT fk_chunks_document
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE;

-- ── Topics ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS topics (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id      UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    company_id   UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    description  TEXT,
    created_by   UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS topic_id UUID REFERENCES topics(id) ON DELETE SET NULL;

-- ── Plan limits reference table ───────────────────────────────
CREATE TABLE IF NOT EXISTS plan_limits (
    plan            TEXT PRIMARY KEY,
    max_queries     INT,
    max_storage_mb  INT,
    max_teams       INT,
    max_users       INT,
    llm_model       TEXT NOT NULL,
    price_monthly   NUMERIC(10,2),
    price_yearly    NUMERIC(10,2)
);

INSERT INTO plan_limits VALUES
    ('starter',    50,    50,    1,    3,    'gpt-4o-mini',               0.00,  0.00),
    ('free',       50,    50,    1,    3,    'gpt-4o-mini',               0.00,  0.00),
    ('team',       1000,  5120,  5,    25,   'claude-haiku-4-5-20251001', 29.00, 24.00),
    ('business',   5000,  20480, NULL, NULL, 'claude-sonnet-4-6',         149.00, 124.00),
    ('enterprise', NULL,  NULL,  NULL, NULL, 'claude-sonnet-4-6',         NULL,  NULL)
ON CONFLICT (plan) DO UPDATE SET
    max_queries    = EXCLUDED.max_queries,
    max_storage_mb = EXCLUDED.max_storage_mb,
    max_teams      = EXCLUDED.max_teams,
    max_users      = EXCLUDED.max_users,
    llm_model      = EXCLUDED.llm_model,
    price_monthly  = EXCLUDED.price_monthly,
    price_yearly   = EXCLUDED.price_yearly;

-- ── Query / conversation history ─────────────────────────────
CREATE TABLE IF NOT EXISTS query_history (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    team_id    UUID REFERENCES teams(id) ON DELETE SET NULL,
    topic_id   UUID REFERENCES topics(id) ON DELETE SET NULL,
    user_id    UUID REFERENCES users(id) ON DELETE SET NULL,
    question   TEXT NOT NULL,
    answer     TEXT,
    asked_at   TIMESTAMPTZ DEFAULT now()
);

-- ── Audit log ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id     UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    team_id        UUID REFERENCES teams(id) ON DELETE SET NULL,
    actor_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_username TEXT,
    actor_email    TEXT,
    event_type     TEXT NOT NULL,
    resource_type  TEXT,
    resource_id    TEXT,
    resource_name  TEXT,
    metadata       JSONB,
    ip_address     TEXT,
    created_at     TIMESTAMPTZ DEFAULT now()
);

-- ── Indexes ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_teams_company          ON teams(company_id);
CREATE INDEX IF NOT EXISTS idx_users_company          ON users(company_id);
CREATE INDEX IF NOT EXISTS idx_users_email            ON users(email);
CREATE INDEX IF NOT EXISTS idx_team_members_user      ON team_members(user_id);
CREATE INDEX IF NOT EXISTS idx_team_members_team      ON team_members(team_id);
CREATE INDEX IF NOT EXISTS idx_documents_team         ON documents(team_id);
CREATE INDEX IF NOT EXISTS idx_documents_company      ON documents(company_id);
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by  ON documents(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_documents_status       ON documents(status);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id     ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm    ON chunks USING gin(content gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_invites_token          ON invites(token);
CREATE INDEX IF NOT EXISTS idx_invites_email          ON invites(email);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_token     ON password_reset_tokens(token);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_user      ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_query_history_company  ON query_history(company_id);
CREATE INDEX IF NOT EXISTS idx_query_history_topic    ON query_history(topic_id);
CREATE INDEX IF NOT EXISTS idx_query_history_team     ON query_history(team_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_company      ON audit_log(company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_team         ON audit_log(team_id, created_at DESC);

-- HNSW index — build manually after bulk ingestion:
-- CREATE INDEX chunks_embedding_hnsw_idx
-- ON chunks USING hnsw (embedding_hv halfvec_cosine_ops)
-- WITH (m = 16, ef_construction = 64);

-- ── Updated_at triggers ───────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
