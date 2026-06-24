# Billing Service API

**Base URL:** `/`  
**Port:** `8004`  
**Visibility:** Internal only — not exposed through the Nginx gateway  
**Auth:** Bearer JWT (for `/usage`); internal endpoints trust Docker network isolation

---

## Public Endpoint

### Get Usage Stats

Returns the current company's quota usage for the frontend dashboard.

```
GET /usage
Authorization: Bearer <token>
```

**Response `200`**
```json
{
  "plan": "team",
  "price_monthly": 29.00,
  "queries": {
    "used": 412,
    "limit": 1000,
    "resets_at": "2024-03-01T00:00:00Z",
    "percent": 41.2
  },
  "storage": {
    "used_bytes": 524288000,
    "used_mb": 500,
    "limit_mb": 5120,
    "percent": 9.8
  },
  "teams": {
    "used": 3,
    "limit": 5
  },
  "users": {
    "used": 12,
    "limit": 25
  }
}
```

**Notes:**
- `limit` values of `-1` indicate unlimited (Enterprise plan)
- `resets_at` is the first day of the next month (UTC)
- `percent` is rounded to one decimal place

---

## Internal Endpoints

These are called service-to-service within the Docker network. Not accessible externally.

### Check Query Limit

Called by Chat Service before executing any query.

```
POST /internal/check/queries
```

**Request Body**
```json
{ "company_id": "uuid" }
```

**Response `200`** — OK, quota available
```json
{ "ok": true }
```

**Response `429`** — Quota exceeded
```json
{ "detail": "Monthly query limit reached. Upgrade your plan." }
```

---

### Check Storage Limit

Called by Ingestion Service before accepting a file upload.

```
POST /internal/check/storage
```

**Request Body**
```json
{
  "company_id": "uuid",
  "file_size_bytes": 2097152
}
```

**Response `200`** — Storage available
```json
{ "ok": true }
```

**Response `413`** — Storage quota exceeded
```json
{ "detail": "Storage limit exceeded. Upgrade your plan or delete documents." }
```

---

### Check Team Limit

Called by Auth Service before creating a new team.

```
POST /internal/check/teams
```

**Request Body**
```json
{ "company_id": "uuid" }
```

**Response `200`** — OK
```json
{ "ok": true }
```

**Response `403`** — Team quota exceeded
```json
{ "detail": "Team limit reached for your plan." }
```

---

### Check User Limit

Called by Auth Service before accepting an invite.

```
POST /internal/check/users
```

**Request Body**
```json
{ "company_id": "uuid" }
```

**Response `200`** — OK
```json
{ "ok": true }
```

**Response `403`** — User quota exceeded
```json
{ "detail": "User limit reached for your plan." }
```

---

### Increment Query Counter

Called by Chat Service after a successful (non-cached) query.

```
POST /internal/queries/increment
```

**Request Body**
```json
{ "company_id": "uuid" }
```

**Response `200`**
```json
{ "ok": true }
```

---

### Decrement Storage

Called by Ingestion Service after a document is deleted.

```
POST /internal/storage/decrement
```

**Request Body**
```json
{
  "company_id": "uuid",
  "file_size_bytes": 2097152
}
```

**Response `200`**
```json
{ "ok": true }
```

---

### Get LLM Model

Called by Chat Service to determine which LLM to use for the company's plan.

```
GET /internal/model/{company_id}
```

**Response `200`**
```json
{ "model": "claude-haiku-4-5-20251001" }
```

**Model Mapping**

| Plan | Model |
|------|-------|
| Starter | `gpt-4o-mini` |
| Team | `claude-haiku-4-5-20251001` |
| Business | `claude-sonnet-4-6` |
| Enterprise | `claude-sonnet-4-6` |

---

## Plan Limits Reference

| Plan | Queries/mo | Storage | Teams | Users | Monthly | Yearly/mo |
|------|-----------|---------|-------|-------|---------|-----------|
| `starter` | 50 | 50 MB | 1 | 3 | $0 | $0 |
| `team` | 1,000 | 5,120 MB | 5 | 25 | $29 | $24 |
| `business` | 5,000 | 20,480 MB | Unlimited | Unlimited | $149 | $124 |
| `enterprise` | Unlimited | Unlimited | Unlimited | Unlimited | Custom | Custom |
