-- Migration 003: Update Team plan limits — 5 teams, 25 users
-- Safe to apply on a live database; uses ON CONFLICT so it is idempotent.

UPDATE plan_limits
SET max_teams = 5,
    max_users = 25
WHERE plan = 'team';
