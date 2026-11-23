# Security & Permissions

## Authentication

### Access tokens and sessions (ADR-009)
- Access token: HS256 JWT signed with `SECRET_KEY`, valid `ACCESS_TOKEN_MINUTES` (default **15 minutes**)
- Claims: `type: "access"`, `sub` (user_id), `username`, `email`, `company_id`, `team_ids`, `role`, `default_team_id`. Only `type: "access"` tokens authenticate requests; the OAuth `oauth_pending` token and tokens issued before this change are rejected, so everyone signs in once after the upgrade.
- Session: opaque refresh token in an `HttpOnly`, `SameSite=Strict`, `Path=/auth` cookie (`Secure` on https), valid `REFRESH_TOKEN_DAYS` (default 30). Stored only as a SHA-256 hash in `identity.refresh_tokens`.
- Rotation: every refresh issues a new token. Reusing a spent token more than 30 s later revokes the whole session (multi-tab refreshes inside 30 s are allowed).
- Revocation: logout ends the session; a password reset or a deactivated account ends all of the user's sessions. Team and role changes reach the user at their next refresh (≤ 15 min).
- CORS allows only the configured origins (`FRONTEND_URL`, `APP_URL`, `CORS_ORIGINS`; plus local dev ports when `API_ENV=development`), never `*`, because requests carry credentials.

### Password Handling
- Hashing: bcrypt (via `passlib`)
- Passwords are never stored in plain text
- OAuth users have `password = null`

### Google OAuth
1. Client redirected to `/auth/oauth/google`
2. Google redirects to `/auth/oauth/google/callback` with authorization code
3. Backend exchanges code for ID token, verifies claims
4. Existing users: set the refresh cookie and redirect to `/login?oauth=success`; the page exchanges the cookie for an access token
5. New users: issue short-lived `pending_token` → frontend completes signup at `/auth/oauth/complete`

### Password Reset
- 1-hour single-use tokens (`used_at` set on use; requesting a new one invalidates older ones)
- Only the SHA-256 hash is stored (`password_reset_tokens.token_hash`); the raw token exists only in the email
- A successful reset revokes all of the user's sessions

### Invite Tokens
- 24-hour expiry
- UUID-based random tokens
- Preview endpoint reveals only company/team name (no PII)

---

## Authorization (RBAC)

### Company-Level Roles

| Role | Assigned To | Key Permissions |
|------|------------|----------------|
| `owner` | First user of company | All permissions, cannot be removed |
| `admin` | Promoted by owner | Team management, invite users, view audit log |
| `member` | Default for invited users | Access assigned teams only |

### Team-Level Roles

| Role | Permissions |
|------|-------------|
| `admin` | Manage team members, delete topics |
| `member` | Upload docs, chat, create topics |

### Permission Matrix

| Action | Member | Team Admin | Company Admin | Owner |
|--------|--------|-----------|---------------|-------|
| Chat / query | ✓ (own teams) | ✓ | ✓ | ✓ |
| Upload document | ✓ | ✓ | ✓ | ✓ |
| Delete own document | ✓ | ✓ | ✓ | ✓ |
| Delete any document | ✗ | ✓ | ✓ | ✓ |
| Create topic | ✓ | ✓ | ✓ | ✓ |
| Delete topic | ✗ | ✓ | ✓ | ✓ |
| Invite users | ✗ | ✗ | ✓ | ✓ |
| Create team | ✗ | ✗ | ✓ | ✓ |
| Add/remove team members | ✗ | ✗ | ✓ | ✓ |
| View audit log | ✗ | ✗ | ✓ | ✓ |
| View billing/usage | ✗ | ✗ | ✓ | ✓ |

---

## Data Isolation (Multi-Tenancy)

- Every table carries `company_id`
- All queries filter by `company_id` from the JWT token
- No cross-tenant data leakage is possible at the application layer
- Team members can only see:
  - Their own teams' documents
  - Documents with `visibility = company` (scoped to their company)
- Admins/owners see all company documents

---

## Rate Limiting

Implemented with `slowapi` (per-user IP by default).

| Endpoint Group | Limit |
|---------------|-------|
| Chat queries (`/chat`, `/chat/stream`) | 30 requests / minute |
| File upload (`/ingest`) | 20 requests / minute |

Exceeding limits returns `HTTP 429 Too Many Requests`.

---

## Quota Enforcement

Quotas are enforced in-process by the metering module (`app.metering.api`) before each metered action. Queries are *reserved* atomically before any work and released if no LLM call happens, so concurrent requests cannot overshoot the monthly limit.

| Quota | Trigger | HTTP Error |
|-------|---------|------------|
| Monthly query limit | Before any chat query | 429 |
| Storage limit | Before file upload | 413 |
| Team limit | Before team creation | 403 |
| User limit | Before invite acceptance | 403 |

---

## Audit Logging

All significant events are recorded in the `audit_log` table.

### Logged Event Types

| Category | Events |
|----------|--------|
| Auth | `user.registered`, `user.login`, `user.password_reset` |
| Documents | `document.uploaded`, `document.deleted` |
| Teams | `team.created`, `team.member_added`, `team.member_removed` |
| Invites | `invite.created`, `invite.accepted` |
| Topics | `topic.created`, `topic.updated`, `topic.deleted` |

Audit log entries are **immutable** — no update or delete endpoints exist.

Admins and owners can filter the audit log by `team_id` and `event_type`.

---

## Input Validation

- All request bodies validated by Pydantic models (FastAPI)
- File uploads restricted to allowed MIME types
- Avatar images limited to 1 MB (base64 validated)
- SQL injection prevented by asyncpg parameterized queries
- XSS mitigated by never rendering stored HTML; all content treated as text

---

## Internal Boundaries

There is no service-to-service HTTP. All modules run in the one `api` process
(plus the Celery `worker`) and call each other through their `api.py`.

- Only the Nginx gateway is published. PostgreSQL, Neo4j and both Redis
  instances have no host ports in production; `docker-compose.dev.yml` binds
  them to `127.0.0.1` for local development only.
- `/metrics` on `api` and `worker:9101` are reachable only inside the Docker
  network; the gateway does not route them.
- `SECRET_KEY`, `POSTGRES_PASSWORD` and `NEO4J_PASSWORD` have no defaults; the
  API and worker refuse to start without a 32+ character `SECRET_KEY`.
- Neo4j holds no tenant ids. Every graph result is re-filtered in PostgreSQL by
  company, team membership and visibility before it is used.
- Cross-tenant access is covered by integration tests
  (`backend/tests/integration`).
