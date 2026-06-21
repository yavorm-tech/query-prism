-- Migration 001: Billing Plans & Usage Tracking
-- Apply to existing databases. init.sql already includes these for fresh setups.

-- 1. Widen the plan CHECK constraint to include 'starter', set default
ALTER TABLE companies DROP CONSTRAINT IF EXISTS companies_plan_check;
ALTER TABLE companies ADD CONSTRAINT companies_plan_check
    CHECK (plan IN ('starter', 'free', 'team', 'business', 'enterprise'));
ALTER TABLE companies ALTER COLUMN plan SET DEFAULT 'starter';

-- 2. Add usage tracking columns
ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS queries_used_this_month  INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS queries_reset_at         TIMESTAMPTZ DEFAULT date_trunc('month', now()),
    ADD COLUMN IF NOT EXISTS storage_used_bytes       BIGINT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_queries_per_month    INT DEFAULT 50,
    ADD COLUMN IF NOT EXISTS max_storage_bytes        BIGINT DEFAULT 52428800;

-- 3. Plan limits reference table
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

-- 4. Migrate 'free' plan companies to 'starter'
UPDATE companies SET plan = 'starter' WHERE plan = 'free';

-- 5. Set limit columns from plan_limits
UPDATE companies c SET
    max_queries_per_month = pl.max_queries,
    max_storage_bytes     = pl.max_storage_mb * 1024 * 1024
FROM plan_limits pl
WHERE pl.plan = c.plan;
