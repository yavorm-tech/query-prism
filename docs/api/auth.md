# Auth Service API

**Base URL:** `/auth`  
**Port:** `8001`  
**Auth:** Bearer JWT (all endpoints except register, login, OAuth, invite preview, and password reset)

---

## Authentication

### Register

Creates a new company, owner account, default team, and default topic in one step.

```
POST /auth/register
```

**Request Body**
```json
{
  "company_name": "Acme Corp",
  "username": "jane",
  "email": "jane@acme.com",
  "password": "s3cr3t!"
}
```

**Response `200`**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

**Errors**
- `409` — Email already registered

---

### Login

```
POST /auth/login
```

**Request Body**
```json
{
  "email": "jane@acme.com",
  "password": "s3cr3t!"
}
```

**Response `200`**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

**Errors**
- `401` — Invalid credentials

---

### Get Current User

```
GET /auth/me
Authorization: Bearer <token>
```

**Response `200`**
```json
{
  "id": "uuid",
  "username": "jane",
  "email": "jane@acme.com",
  "company_id": "uuid",
  "company_name": "Acme Corp",
  "plan": "team",
  "role": "owner",
  "team_ids": ["uuid1", "uuid2"],
  "default_team_id": "uuid1",
  "avatar": "data:image/png;base64,..."
}
```

---

## Google OAuth

### Initiate OAuth Flow

```
GET /auth/oauth/google
```

Redirects to Google consent screen.

---

### OAuth Callback

```
GET /auth/oauth/google/callback?code=<code>&state=<state>
```

- **Existing user:** Returns `{access_token, token_type}` directly.
- **New user:** Returns `{pending_token, email}` — frontend must call `/auth/oauth/complete`.

---

### Complete OAuth Signup

For new users arriving via Google OAuth who still need to set company/username.

```
POST /auth/oauth/complete
```

**Request Body**
```json
{
  "pending_token": "<short-lived token from callback>",
  "company_name": "Acme Corp",
  "username": "jane"
}
```

**Response `200`**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

**Errors**
- `400` — Invalid or expired pending token
- `409` — Company name already taken

---

## Avatar Management

### Update Avatar

```
PUT /auth/me/avatar
Authorization: Bearer <token>
```

**Request Body**
```json
{
  "avatar": "data:image/png;base64,<base64-encoded-image>"
}
```

**Constraints:** Max 1 MB encoded size.

**Response `200`**
```json
{ "ok": true }
```

---

### Delete Avatar

```
DELETE /auth/me/avatar
Authorization: Bearer <token>
```

**Response `204`** — No content

---

## Team Management

### List Teams

Returns all teams the current user belongs to (or all company teams for admins/owners).

```
GET /auth/teams
Authorization: Bearer <token>
```

**Response `200`**
```json
[
  {
    "id": "uuid",
    "name": "Engineering",
    "description": "Backend and infra",
    "company_id": "uuid",
    "member_count": 5
  }
]
```

---

### Create Team

```
POST /auth/teams
Authorization: Bearer <token>   (admin/owner only)
```

**Request Body**
```json
{
  "name": "Marketing",
  "description": "Growth and content"
}
```

**Response `201`**
```json
{
  "id": "uuid",
  "name": "Marketing",
  "description": "Growth and content",
  "company_id": "uuid"
}
```

**Errors**
- `403` — Caller is not admin or owner
- `402` — Team quota exceeded

---

### List Team Members

```
GET /auth/teams/{team_id}/members
Authorization: Bearer <token>
```

**Response `200`**
```json
[
  {
    "id": "uuid",
    "username": "jane",
    "email": "jane@acme.com",
    "company_role": "owner",
    "team_role": "admin",
    "joined_at": "2024-01-15T10:00:00Z"
  }
]
```

---

### Add Team Member

```
POST /auth/teams/{team_id}/members?user_id=<uuid>&role=member
Authorization: Bearer <token>   (admin/owner only)
```

**Response `204`** — No content

**Errors**
- `403` — Insufficient permissions
- `404` — User or team not found
- `409` — Already a member

---

### Remove Team Member

```
DELETE /auth/teams/{team_id}/members/{user_id}
Authorization: Bearer <token>   (admin/owner only)
```

**Response `204`** — No content

---

## Invitations

### Preview Invite

Public endpoint — no auth required. Shows minimal info before the invitee creates an account.

```
GET /auth/invite/{token}
```

**Response `200`**
```json
{
  "company_name": "Acme Corp",
  "team_name": "Engineering",
  "email": "bob@example.com"
}
```

**Errors**
- `404` — Token not found or expired

---

### Accept Invite

Creates a new user account and adds them to the invited team.

```
POST /auth/invite/{token}/accept
```

**Request Body**
```json
{
  "username": "bob",
  "password": "s3cur3!"
}
```

**Response `200`**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

**Errors**
- `404` — Invalid/expired token
- `409` — Email already registered
- `402` — User quota exceeded for company

---

### Create Invite

Sends an invitation email to a new user.

```
POST /auth/invite
Authorization: Bearer <token>   (admin/owner only)
```

**Request Body**
```json
{
  "email": "bob@example.com",
  "team_id": "uuid",
  "role": "member"
}
```

**Response `201`**
```json
{
  "id": "uuid",
  "token": "<invite-token>",
  "email": "bob@example.com",
  "expires_at": "2024-02-16T10:00:00Z"
}
```

---

### List Invites

```
GET /auth/invites
Authorization: Bearer <token>   (admin/owner only)
```

**Response `200`**
```json
[
  {
    "id": "uuid",
    "email": "bob@example.com",
    "role": "member",
    "team_name": "Engineering",
    "invited_by_username": "jane",
    "status": "pending",
    "created_at": "2024-02-15T10:00:00Z",
    "expires_at": "2024-02-16T10:00:00Z",
    "accepted_at": null
  }
]
```

**Invite Status Values:** `pending`, `accepted`, `expired`

---

## Password Reset

### Request Reset

```
POST /auth/forgot-password
```

**Request Body**
```json
{ "email": "jane@acme.com" }
```

**Response `204`** — Always returns 204 (prevents email enumeration)

Side-effect: Sends reset email if account exists.

---

### Complete Reset

```
POST /auth/reset-password
```

**Request Body**
```json
{
  "token": "<reset-token-from-email>",
  "new_password": "n3wP@ss!"
}
```

**Response `204`** — No content

**Errors**
- `400` — Invalid or expired token

---

## Audit Log

```
GET /audit
Authorization: Bearer <token>   (admin/owner only)
```

**Query Parameters**

| Param | Type | Description |
|-------|------|-------------|
| `team_id` | UUID | Filter by team (optional) |
| `event_type` | string | Filter by event type (optional) |
| `limit` | int | Max results, default `100` |
| `offset` | int | Pagination offset, default `0` |

**Response `200`**
```json
[
  {
    "id": "uuid",
    "event_type": "document.uploaded",
    "actor_username": "jane",
    "actor_email": "jane@acme.com",
    "team_id": "uuid",
    "team_name": "Engineering",
    "resource_type": "document",
    "resource_id": "uuid",
    "resource_name": "report.pdf",
    "metadata": { "file_size": 204800 },
    "created_at": "2024-02-15T12:30:00Z"
  }
]
```
