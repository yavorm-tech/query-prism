# Security & Permissions

## Authentication

### JWT Tokens
- Issued on successful login or registration
- Algorithm: HS256 (HMAC-SHA256)
- Expiry: 7 days (configurable via `SECRET_KEY`)
- Payload claims: `sub` (user_id), `username`, `email`, `company_id`, `team_ids`, `role`, `default_team_id`

### Password Handling
- Hashing: bcrypt (via `passlib`)
- Passwords are never stored in plain text
- OAuth users have `password = null`

### Google OAuth
1. Client redirected to `/auth/oauth/google`
2. Google redirects to `/auth/oauth/google/callback` with authorization code
3. Backend exchanges code for ID token, verifies claims
4. Existing users: issue JWT and log in
5. New users: issue short-lived `pending_token` → frontend completes signup at `/auth/oauth/complete`

### Password Reset
- 1-hour single-use tokens
- Tokens stored hashed; raw token sent to email
- `consumed_at` timestamp set on use (prevents replay)

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

Quotas are enforced by the Billing Service before each metered action.

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

## Service-to-Service Security

Internal services (Billing, Notification) are **not exposed through the Nginx gateway**. They are only accessible within the Docker network (`query-prism-network`). Other services communicate with them via their internal hostnames.
