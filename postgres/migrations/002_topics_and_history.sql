-- Migration 002: Topics table, query_history table, and topic_id on documents
-- Safe to apply on a live database — all additive, no data touched.

-- 1. Topics
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

-- 2. topic_id on documents
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS topic_id UUID REFERENCES topics(id) ON DELETE SET NULL;

-- 3. Query / conversation history
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

-- 4. Indexes
CREATE INDEX IF NOT EXISTS idx_topics_team        ON topics(team_id);
CREATE INDEX IF NOT EXISTS idx_topics_company     ON topics(company_id);
CREATE INDEX IF NOT EXISTS idx_documents_topic    ON documents(topic_id);
CREATE INDEX IF NOT EXISTS idx_query_history_company ON query_history(company_id);
CREATE INDEX IF NOT EXISTS idx_query_history_topic   ON query_history(topic_id);
CREATE INDEX IF NOT EXISTS idx_query_history_team    ON query_history(team_id);
