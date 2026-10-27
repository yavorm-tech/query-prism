# Metering API (billing)

**Base URL:** `/`  
**Served by:** `api` (port 8000, via the gateway)  
**Visibility:** `/usage` through the gateway  
**Auth:** Bearer JWT

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

## In-process API (`app.metering.api`)

The former `/internal/*` HTTP endpoints are gone; other contexts call these
functions directly. Plan and counters live in `metering.subscriptions`.

| Function | Used by | Behaviour |
|----------|---------|-----------|
| `open_subscription(company_id)` | identity (sign-up) | Creates the `starter` subscription |
| `get_plan(company_id)` | identity (`/auth/me`) | Current plan name |
| `reserve_query(company_id)` | retrieval | Atomically consumes one query (rolls the month over); returns the plan's model; 429 when exhausted |
| `release_query(company_id)` | retrieval | Returns a reserved query when no LLM call happened |
| `check_storage_limit(company_id, bytes)` | knowledge | 413 when the upload would exceed the plan |
| `check_team_limit(company_id, team_count)` | identity | 403 `team_limit_reached` |
| `check_user_limit(company_id, user_count)` | identity | 403 `user_limit_reached` |
| `increment_storage` / `decrement_storage` | knowledge | Storage counter (never below 0) |

To change a company's plan: `UPDATE metering.subscriptions SET plan = 'business' WHERE company_id = '…';`

## Plan Limits Reference

| Plan | Queries/mo | Storage | Teams | Users | Monthly | Yearly/mo |
|------|-----------|---------|-------|-------|---------|-----------|
| `starter` | 50 | 50 MB | 1 | 3 | $0 | $0 |
| `team` | 1,000 | 5,120 MB | 5 | 25 | $29 | $24 |
| `business` | 5,000 | 20,480 MB | Unlimited | Unlimited | $149 | $124 |
| `enterprise` | Unlimited | Unlimited | Unlimited | Unlimited | Custom | Custom |
