# Notification API (notification module)

**Base URL:** `/`  
**Served by:** `api` (port 8000, via the gateway)  
**Visibility:** `/contact` through the gateway; invite and reset emails are sent in-process  
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

## In-process API (`app.notification.api`)

There are no internal HTTP endpoints. The identity module calls these functions
directly. Sending never raises: an SMTP failure is logged and the invite or
password-reset request still succeeds. User-supplied values are HTML-escaped.

| Function | Called by | Email |
|----------|-----------|-------|
| `send_invite_email(email, company_name, team_name, invite_token)` | `POST /auth/invite` | Invitation with an "Accept Invitation" button linking to `{APP_URL}/login?invite=<token>` |
| `send_password_reset_email(email, reset_token)` | `POST /auth/forgot-password` | Reset button linking to `{APP_URL}/reset-password?token=<token>`; link valid 1 hour |

---

## Email Delivery Stack

```
app.notification (api process)
        │
        ▼ SMTP (postfix:25)
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
