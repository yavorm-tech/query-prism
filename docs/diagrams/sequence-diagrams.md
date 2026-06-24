# Sequence Diagrams

## 1. User Registration Flow

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Nginx
    participant AuthSvc as Auth Service
    participant BillingSvc as Billing Service
    participant Postgres

    User->>Frontend: Fill registration form
    Frontend->>Nginx: POST /auth/register
    Nginx->>AuthSvc: Forward request

    AuthSvc->>Postgres: Check email uniqueness
    Postgres-->>AuthSvc: Not found

    AuthSvc->>Postgres: INSERT company
    AuthSvc->>Postgres: INSERT user (owner role)
    AuthSvc->>Postgres: INSERT default team
    AuthSvc->>Postgres: INSERT default topic
    AuthSvc->>Postgres: INSERT team_member (owner → default team)

    AuthSvc->>AuthSvc: Build JWT payload
    AuthSvc-->>Nginx: {access_token, token_type}
    Nginx-->>Frontend: 200 OK
    Frontend->>Frontend: Store token, redirect to app
```

---

## 2. Google OAuth Flow

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Nginx
    participant AuthSvc as Auth Service
    participant Google

    User->>Frontend: Click "Sign in with Google"
    Frontend->>Nginx: GET /auth/oauth/google
    Nginx->>AuthSvc: Forward
    AuthSvc-->>Frontend: 302 Redirect to Google

    User->>Google: Consent + authenticate
    Google-->>AuthSvc: Callback with auth code

    AuthSvc->>Google: Exchange code for ID token
    Google-->>AuthSvc: ID token + user info

    alt Existing user
        AuthSvc->>AuthSvc: Generate JWT
        AuthSvc-->>Frontend: {access_token}
    else New user
        AuthSvc->>AuthSvc: Generate short-lived pending_token
        AuthSvc-->>Frontend: {pending_token, email}
        Frontend->>User: Show complete-signup form
        User->>Frontend: Enter company_name + username
        Frontend->>Nginx: POST /auth/oauth/complete
        Nginx->>AuthSvc: Forward
        AuthSvc->>AuthSvc: Validate pending_token
        AuthSvc->>AuthSvc: Create company + user
        AuthSvc-->>Frontend: {access_token}
    end
```

---

## 3. Document Upload & Ingestion

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Nginx
    participant IngestSvc as Ingestion Service
    participant BillingSvc as Billing Service
    participant Postgres
    participant Redis
    participant Worker as Celery Worker
    participant OpenAI
    participant Neo4j

    User->>Frontend: Select file
    Frontend->>Nginx: POST /ingest (multipart)
    Nginx->>IngestSvc: Forward

    IngestSvc->>BillingSvc: POST /internal/check/storage {company_id, file_size}
    BillingSvc->>Postgres: Check storage_used vs max_storage_mb
    Postgres-->>BillingSvc: Usage data
    BillingSvc-->>IngestSvc: 200 OK (quota available)

    IngestSvc->>Postgres: INSERT document (status=pending)
    IngestSvc->>IngestSvc: Save file to disk
    IngestSvc->>Redis: Queue Celery task (ingest_document)
    IngestSvc-->>Frontend: {document_id, job_id, status: "pending"}

    Note over Worker: Asynchronous processing starts

    Worker->>Postgres: UPDATE document status=processing
    Worker->>Worker: Load file & extract text
    Worker->>Worker: Split into chunks (LlamaIndex)
    Worker->>OpenAI: Embed chunks (batch API)
    OpenAI-->>Worker: Embedding vectors [3072-dim]
    Worker->>Postgres: INSERT chunks with embeddings
    Worker->>Worker: NER extraction (spaCy)
    Worker->>Worker: Relation extraction
    Worker->>Neo4j: MERGE Entity nodes + relationships
    Worker->>Postgres: UPDATE document status=completed
    Worker->>Postgres: UPDATE company storage_used_bytes

    Frontend->>Nginx: GET /ingest/{document_id} (polling)
    Nginx->>IngestSvc: Forward
    IngestSvc->>Postgres: SELECT document status
    Postgres-->>IngestSvc: status=completed
    IngestSvc-->>Frontend: {status: "completed"}
```

---

## 4. Chat Query (Non-Streaming)

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Nginx
    participant ChatSvc as Chat Service
    participant BillingSvc as Billing Service
    participant Redis
    participant Postgres
    participant Neo4j
    participant Cohere
    participant LLM as LLM (Claude/GPT)

    User->>Frontend: Type question + Send
    Frontend->>Nginx: POST /chat
    Nginx->>ChatSvc: Forward

    ChatSvc->>BillingSvc: POST /internal/check/queries
    BillingSvc-->>ChatSvc: 200 OK

    ChatSvc->>Redis: GET cache key
    alt Cache hit
        Redis-->>ChatSvc: Cached response
        ChatSvc-->>Frontend: {answer, sources, cached: true}
    else Cache miss
        ChatSvc->>ChatSvc: Embed query (OpenAI)

        par Hybrid retrieval
            ChatSvc->>Postgres: Vector search (pgvector cosine, top-20)
        and
            ChatSvc->>Neo4j: Graph search (entity traversal)
        end

        Postgres-->>ChatSvc: Vector results
        Neo4j-->>ChatSvc: Graph results

        ChatSvc->>ChatSvc: Merge & deduplicate results

        ChatSvc->>Cohere: Re-rank top-20 → top-5
        Cohere-->>ChatSvc: Re-ranked SourceChunks

        ChatSvc->>ChatSvc: Assemble context string

        ChatSvc->>BillingSvc: GET /internal/model/{company_id}
        BillingSvc-->>ChatSvc: {model: "claude-haiku-..."}

        ChatSvc->>LLM: Generate answer (query + context)
        LLM-->>ChatSvc: Answer text

        ChatSvc->>Postgres: INSERT query_history
        ChatSvc->>BillingSvc: POST /internal/queries/increment
        ChatSvc->>Redis: SET cache key (TTL)

        ChatSvc-->>Frontend: {answer, sources, cached: false}
    end

    Frontend->>User: Display answer + sources
```

---

## 5. Streaming Chat (SSE)

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Nginx
    participant ChatSvc as Chat Service
    participant LLM as LLM (Claude/GPT)

    User->>Frontend: Type question + Send
    Frontend->>Nginx: GET /chat/stream (SSE connection)
    Nginx->>ChatSvc: Forward (long-lived connection)

    Note over ChatSvc: Retrieval + re-ranking (same as POST /chat)

    ChatSvc->>LLM: stream_answer(query, context, model)

    loop For each token
        LLM-->>ChatSvc: token
        ChatSvc-->>Frontend: data: {"type":"token","content":"The "}
    end

    ChatSvc-->>Frontend: data: {"type":"sources","content":[...]}
    ChatSvc-->>Frontend: data: {"type":"done","content":null}

    Frontend->>Frontend: Assemble full answer from tokens
    Frontend->>User: Display streamed answer
```

---

## 6. Team Invitation Flow

```mermaid
sequenceDiagram
    actor Admin
    actor Invitee
    participant Frontend
    participant AuthSvc as Auth Service
    participant NotifSvc as Notification Service
    participant Email as Email (Postfix)
    participant Postgres

    Admin->>Frontend: Enter invitee email + team
    Frontend->>AuthSvc: POST /auth/invite

    AuthSvc->>AuthSvc: Check admin permissions
    AuthSvc->>BillingSvc: POST /internal/check/users
    BillingSvc-->>AuthSvc: 200 OK

    AuthSvc->>Postgres: INSERT invite (token, expires_at=+24h)
    AuthSvc->>NotifSvc: POST /notification/invite {email, accept_url}
    NotifSvc->>Email: Send HTML invite email via SMTP
    Email-->>Invitee: Invitation email

    AuthSvc-->>Frontend: {id, token, expires_at}
    Frontend->>Admin: "Invite sent"

    Invitee->>Frontend: Click link in email
    Frontend->>AuthSvc: GET /auth/invite/{token}
    AuthSvc->>Postgres: SELECT invite by token
    Postgres-->>AuthSvc: {company_name, team_name, email}
    AuthSvc-->>Frontend: Invite preview

    Invitee->>Frontend: Set username + password
    Frontend->>AuthSvc: POST /auth/invite/{token}/accept

    AuthSvc->>Postgres: Validate token (not expired, not used)
    AuthSvc->>Postgres: INSERT user
    AuthSvc->>Postgres: INSERT team_member
    AuthSvc->>Postgres: UPDATE invite accepted_at
    AuthSvc->>AuthSvc: Generate JWT
    AuthSvc-->>Frontend: {access_token}
    Frontend->>Invitee: Logged in to workspace
```

---

## 7. Password Reset Flow

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant AuthSvc as Auth Service
    participant NotifSvc as Notification Service
    participant Postgres

    User->>Frontend: Enter email on forgot-password page
    Frontend->>AuthSvc: POST /auth/forgot-password {email}

    AuthSvc->>Postgres: SELECT user by email
    alt User exists
        AuthSvc->>Postgres: INSERT password_reset_tokens (token, expires=+1h)
        AuthSvc->>NotifSvc: POST /notification/reset-password {email, reset_url}
        NotifSvc-->>User: Password reset email
    end

    Note over AuthSvc: Always returns 204 (prevents email enumeration)
    AuthSvc-->>Frontend: 204 No Content
    Frontend->>User: "If account exists, check your email"

    User->>Frontend: Click link in email
    Frontend->>User: Show new-password form
    User->>Frontend: Enter new password
    Frontend->>AuthSvc: POST /auth/reset-password {token, new_password}

    AuthSvc->>Postgres: SELECT token (valid, not expired, not used)
    AuthSvc->>AuthSvc: Hash new password
    AuthSvc->>Postgres: UPDATE user password
    AuthSvc->>Postgres: UPDATE token used_at
    AuthSvc-->>Frontend: 204 No Content
    Frontend->>User: "Password changed — please log in"
```
