-- Run by procedures/staging.sh refresh after restoring a production backup into
-- STAGING. Removes what must not leave production and stops staging from acting
-- on production's behalf. Never run this against production.
--
-- :staging_password is set by the script (psql -v).

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- People: no real addresses (postfix rejects .invalid, so no mail reaches them),
-- no Google links, no avatars; one shared password for testers.
UPDATE identity.users SET
    email     = 'user-' || left(id::text, 8) || '@staging.invalid',
    google_id = NULL,
    avatar    = NULL,
    password  = crypt(:'staging_password', gen_salt('bf', 12));

-- Credentials and pending invitations.
TRUNCATE identity.refresh_tokens, identity.password_reset_tokens;
DELETE FROM identity.invites;

-- Who did what, from where.
UPDATE audit.audit_log SET actor_email = NULL, ip_address = NULL;

-- Undelivered production events would queue work for files staging doesn't have.
TRUNCATE shared.outbox;
UPDATE knowledge.documents
   SET status = 'failed', error_message = 'Restored into staging before ingestion finished'
 WHERE status IN ('pending', 'processing');

DROP EXTENSION pgcrypto;

COMMIT;
