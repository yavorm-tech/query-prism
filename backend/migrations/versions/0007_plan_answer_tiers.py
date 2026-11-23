"""Plans name an answer tier instead of a vendor model ID (ADR-008).

plan_limits.llm_model held raw model IDs (e.g. claude-sonnet-4-6), so retiring
a model meant a data migration. Plans now carry a tier; the tier → provider:model
routes (with failover) live in configuration (LLM_TIER_BASIC/STANDARD/PREMIUM).

Revision ID: 0007
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE metering.plan_limits ADD COLUMN IF NOT EXISTS answer_tier TEXT")
    op.execute(
        """
        UPDATE metering.plan_limits SET answer_tier = CASE
            WHEN llm_model LIKE 'gpt-4o-mini%' THEN 'basic'
            WHEN llm_model LIKE 'claude-haiku%' THEN 'standard'
            ELSE 'premium'
        END
        WHERE answer_tier IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE metering.plan_limits
            ALTER COLUMN answer_tier SET NOT NULL,
            ADD CONSTRAINT plan_limits_answer_tier_check
                CHECK (answer_tier IN ('basic', 'standard', 'premium')),
            DROP COLUMN llm_model
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE metering.plan_limits ADD COLUMN IF NOT EXISTS llm_model TEXT")
    op.execute(
        """
        UPDATE metering.plan_limits SET llm_model = CASE answer_tier
            WHEN 'basic' THEN 'gpt-4o-mini'
            WHEN 'standard' THEN 'claude-haiku-4-5-20251001'
            ELSE 'claude-sonnet-4-6'
        END
        """
    )
    op.execute(
        """
        ALTER TABLE metering.plan_limits
            ALTER COLUMN llm_model SET NOT NULL,
            DROP CONSTRAINT IF EXISTS plan_limits_answer_tier_check,
            DROP COLUMN answer_tier
        """
    )
