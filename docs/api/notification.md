# Notification Service API

**Base URL:** `/`  
**Port:** `8005`  
**Visibility:** Internal endpoints called service-to-service; `/contact` is accessible via Nginx gateway  
**Transport:** Postfix SMTP relay

---

## Public Endpoint

### Enterprise Contact Form

Accepts enterprise inquiry submissions from the Pricing/Contact page and emails them to the sales team.

```
POST /contact/enterprise
Content-Type: application/json
```

**Request Body**
```json
{
  "name": "John Smith",
  "email": "john@enterprise.com",
  "company_name": "BigCorp Inc.",
  "company_size": "500-1000",
  "message": "We need a custom deployment for 200 users..."
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Submitter's full name |
| `email` | string | Yes | Reply-to email address |
| `company_name` | string | Yes | Company name |
| `company_size` | string | Yes | Employee count range |
| `message` | string | Yes | Inquiry message body |

**Response `200`**
```json
{ "success": true }
```

**Errors**
- `422` — Missing or invalid fields
- `500` — SMTP relay failure

---

## Internal Endpoints

Called by other services within the Docker network. Not accessible externally.

### Send Invite Email

Called by Auth Service when a company admin creates an invite.

```
POST /notification/invite
Content-Type: application/json
```

**Request Body**
```json
{
  "email": "bob@example.com",
  "company_name": "Acme Corp",
  "team_name": "Engineering",
  "accept_url": "https://app.example.com/invite/accept/<token>"
}
```

**Response `200`**
```json
{ "ok": true }
```

**Email Template:** HTML email with the company name, team name, and a call-to-action button linking to `accept_url`. Expires notice included (24 hours).

---

### Send Password Reset Email

Called by Auth Service when a user requests password recovery.

```
POST /notification/reset-password
Content-Type: application/json
```

**Request Body**
```json
{
  "email": "jane@acme.com",
  "reset_url": "https://app.example.com/reset-password?token=<token>"
}
```

**Response `200`**
```json
{ "ok": true }
```

**Email Template:** HTML email with a reset password button linking to `reset_url`. Expiry warning included (1 hour).

---

## Email Delivery Stack

```
Notification Service
        │
        ▼ SMTP (localhost:25)
    Postfix Container
        │
        ▼ Relay (port 587/465)
  External MTA (SendGrid / AWS SES / direct MX)
```

**Configuration** (via environment variables):

| Variable | Description |
|----------|-------------|
| `SMTP_HOST` | SMTP relay host |
| `SMTP_PORT` | SMTP relay port (typically 587) |
| `SMTP_USER` | SMTP auth username |
| `SMTP_PASSWORD` | SMTP auth password |
| `SMTP_FROM` | From address (e.g., `noreply@yourdomain.com`) |
| `SMTP_FROM_NAME` | Display name (e.g., `AskYourBase`) |
