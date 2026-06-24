# Chat Service API

**Base URL:** `/chat` and `/topics`  
**Port:** `8003`  
**Auth:** Bearer JWT (all endpoints)  
**Rate Limit:** 30 requests / minute per user

---

## Chat Endpoints

### Single-Turn Query

Sends a question and receives a complete answer with source citations.

```
POST /chat
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body**
```json
{
  "query": "What were the key findings in the Q4 report?",
  "team_id": "uuid",
  "topic_id": "uuid",
  "source_type": "pdf",
  "skip_cache": false
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | The user's question |
| `team_id` | UUID | No | Restrict search to a team's documents |
| `topic_id` | UUID | No | Restrict search to a topic's documents |
| `source_type` | string | No | Filter by file type (`pdf`, `docx`, `txt`, `image`, `video`, `csv`) |
| `skip_cache` | boolean | No | Bypass Redis cache, default `false` |

**Response `200`**
```json
{
  "answer": "The Q4 report highlights a 23% revenue increase...",
  "sources": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "filename": "q4-report-2024.pdf",
      "original_name": "Q4 Report 2024.pdf",
      "source_type": "pdf",
      "team_id": "uuid",
      "content_preview": "Revenue increased by 23% compared to Q3...",
      "similarity": 0.912,
      "rerank_score": 0.876
    }
  ],
  "query": "What were the key findings in the Q4 report?",
  "cached": false,
  "scope": "team"
}
```

**Response Fields**

| Field | Description |
|-------|-------------|
| `answer` | LLM-generated answer text |
| `sources` | Ranked list of source chunks used for context |
| `cached` | Whether the response was served from Redis cache |
| `scope` | Search scope used: `team`, `topic`, or `company` |

**Source Chunk Fields**

| Field | Description |
|-------|-------------|
| `chunk_id` | Chunk UUID in PostgreSQL |
| `document_id` | Parent document UUID |
| `similarity` | Cosine similarity score (0–1) from pgvector |
| `rerank_score` | Cohere re-ranking score (0–1) |
| `content_preview` | First ~200 characters of the chunk |

**Errors**
- `429` — Query quota exceeded for company plan
- `429` — Rate limit exceeded

---

### Streaming Chat (Server-Sent Events)

Streams the LLM response token-by-token using Server-Sent Events.

```
GET /chat/stream
Authorization: Bearer <token>
```

**Query Parameters**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | The user's question |
| `team_id` | UUID | No | Restrict to team |
| `topic_id` | UUID | No | Restrict to topic |
| `source_type` | string | No | Filter by file type |
| `skip_cache` | boolean | No | Default `false` |

**Response** — `text/event-stream`

Events are newline-delimited JSON objects prefixed with `data: `.

**Token Event** (one per token, repeated)
```
data: {"type": "token", "content": "The ", "cached": false}
data: {"type": "token", "content": "Q4 ", "cached": false}
data: {"type": "token", "content": "report...", "cached": false}
```

**Sources Event** (sent once, after all tokens)
```
data: {"type": "sources", "content": [ <same source objects as POST /chat> ]}
```

**Done Event**
```
data: {"type": "done", "content": null}
```

**Error Event**
```
data: {"type": "error", "content": "Quota exceeded"}
```

**Client Example (JavaScript)**
```javascript
const es = new EventSource(`/chat/stream?query=...&team_id=...`, {
  headers: { Authorization: `Bearer ${token}` }
});
es.onmessage = (e) => {
  const event = JSON.parse(e.data);
  if (event.type === 'token') appendToken(event.content);
  if (event.type === 'sources') showSources(event.content);
  if (event.type === 'done') es.close();
};
```

---

## Topics Endpoints

Topics are logical folders for organizing documents within a team.

### List Topics

```
GET /topics
Authorization: Bearer <token>
```

**Query Parameters**

| Param | Type | Description |
|-------|------|-------------|
| `team_id` | UUID | Filter to a specific team (optional) |

**Response `200`**
```json
[
  {
    "id": "uuid",
    "name": "Annual Reports",
    "description": "Year-end financial reports",
    "team_id": "uuid",
    "team_name": "Finance",
    "created_by_username": "jane",
    "document_count": 12,
    "completed_count": 11,
    "created_at": "2024-01-10T08:00:00Z"
  }
]
```

---

### Create Topic

```
POST /topics
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body**
```json
{
  "team_id": "uuid",
  "name": "Product Specs",
  "description": "Technical specifications for all products"
}
```

**Response `201`**
```json
{
  "id": "uuid",
  "name": "Product Specs",
  "description": "Technical specifications for all products",
  "team_id": "uuid",
  "created_by_username": "jane",
  "document_count": 0,
  "completed_count": 0,
  "created_at": "2024-02-15T10:00:00Z"
}
```

**Errors**
- `403` — User does not belong to the specified team

---

### Get Topic

```
GET /topics/{topic_id}
Authorization: Bearer <token>
```

**Response `200`** — Same shape as a single object from List Topics.

**Errors**
- `404` — Topic not found or not accessible

---

### Update Topic

```
PATCH /topics/{topic_id}
Authorization: Bearer <token>   (creator or team admin/company admin)
Content-Type: application/json
```

**Request Body** (all fields optional)
```json
{
  "name": "Product Specs v2",
  "description": "Updated description"
}
```

**Response `200`** — Updated topic object.

**Errors**
- `403` — Not the creator or admin

---

### Delete Topic

Deletes the topic and cascades to all contained documents (and their chunks/graph nodes).

```
DELETE /topics/{topic_id}
Authorization: Bearer <token>   (company admin/owner only)
```

**Response `204`** — No content

**Errors**
- `403` — Insufficient permissions

---

### List Questions in Topic

Returns the question/answer history for a topic, newest first.

```
GET /topics/{topic_id}/questions
Authorization: Bearer <token>
```

**Response `200`**
```json
[
  {
    "id": "uuid",
    "question": "What is the warranty period?",
    "answer": "The warranty period is 2 years...",
    "username": "jane",
    "asked_at": "2024-02-15T14:30:00Z"
  }
]
```

---

### List Documents in Topic

```
GET /topics/{topic_id}/documents
Authorization: Bearer <token>
```

**Response `200`**
```json
[
  {
    "document_id": "uuid",
    "original_name": "Warranty Policy.pdf",
    "source_type": "pdf",
    "file_size": 102400,
    "status": "completed",
    "uploaded_by_username": "jane",
    "created_at": "2024-02-15T09:00:00Z"
  }
]
```

---

## Retrieval Pipeline Detail

```
User Query
    │
    ▼
1. Encode query → 3072-dim vector (OpenAI)
    │
    ├── pgvector cosine search
    │     SELECT chunks WHERE company_id=X [AND team_id=Y] [AND topic_id=Z]
    │     ORDER BY embedding <=> query_vec LIMIT 20
    │
    └── Neo4j graph traversal
          Extract entities from query (spaCy)
          MATCH (e:Entity)-[:MENTIONED_IN]->(c:Chunk)
          WHERE e.name IN [entities] AND e.company_id = X
    │
    ▼
2. Merge & deduplicate results
    │
    ▼
3. Cohere re-ranking (top 20 → top 5)
    │
    ▼
4. Assemble context string (chunk contents)
    │
    ▼
5. LLM call (Claude or GPT based on plan)
    │
    ├── Streaming → SSE token stream
    └── Non-streaming → full answer
    │
    ▼
6. Store in query_history
7. Increment billing counter
8. Cache in Redis (TTL: configurable)
```
