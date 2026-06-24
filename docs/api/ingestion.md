# Ingestion Service API

**Base URL:** `/ingest`  
**Port:** `8002`  
**Auth:** Bearer JWT (all endpoints)  
**Rate Limit:** 20 requests / minute per user

---

## Upload Document

Uploads a file for processing. The file is saved to disk and a Celery background job is queued for chunking, embedding, and graph extraction.

```
POST /ingest
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

**Query Parameters**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `team_id` | UUID | No | Assign to a specific team (defaults to user's default team) |
| `topic_id` | UUID | No | Place document in a topic/folder |
| `visibility` | string | No | `team` (default) or `company` |

**Form Fields**

| Field | Type | Description |
|-------|------|-------------|
| `file` | File | The document to upload |

**Supported File Types**

| Category | Extensions |
|----------|-----------|
| Documents | `.pdf`, `.docx`, `.txt`, `.md` |
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp` |
| Video | `.mp4`, `.mov`, `.avi` |
| Audio | `.mp3`, `.wav`, `.m4a` |
| Data | `.csv` |

**Response `202`**
```json
{
  "document_id": "uuid",
  "job_id": "celery-task-uuid",
  "filename": "report-2024-acme.pdf",
  "status": "pending",
  "team_id": "uuid",
  "topic_id": "uuid"
}
```

**Errors**
- `400` — Unsupported file type
- `403` — No access to the specified team
- `413` — Storage quota exceeded for company plan

**Processing States**

| Status | Description |
|--------|-------------|
| `pending` | Queued, worker not yet started |
| `processing` | Worker is actively chunking/embedding |
| `completed` | Chunks and graph nodes written successfully |
| `failed` | Worker encountered an error (see `error_message`) |

---

## List Documents

Returns documents visible to the current user. Regular members see their teams' docs plus company-wide docs. Admins/owners see all company documents.

```
GET /ingest
Authorization: Bearer <token>
```

**Query Parameters**

| Param | Type | Description |
|-------|------|-------------|
| `team_id` | UUID | Filter by team (optional) |
| `topic_id` | UUID | Filter by topic (optional) |

**Response `200`**
```json
[
  {
    "document_id": "uuid",
    "original_name": "Q4 Report.pdf",
    "source_type": "pdf",
    "file_size": 204800,
    "status": "completed",
    "team_id": "uuid",
    "team_name": "Finance",
    "topic_id": "uuid",
    "topic_name": "Annual Reports",
    "uploaded_by_username": "jane",
    "visibility": "company",
    "error_message": null,
    "created_at": "2024-02-15T09:00:00Z"
  }
]
```

---

## Get Document Status

Polls the ingestion status of a single document. Useful for progress indication after upload.

```
GET /ingest/{document_id}
Authorization: Bearer <token>
```

**Response `200`**
```json
{
  "document_id": "uuid",
  "status": "completed",
  "team_id": "uuid",
  "topic_id": "uuid",
  "error_message": null
}
```

**Errors**
- `404` — Document not found or not accessible

---

## Delete Document

Deletes a document along with all its chunks from PostgreSQL and its nodes/relations from Neo4j. Also decrements the company's storage usage.

```
DELETE /ingest/{document_id}
Authorization: Bearer <token>
```

**Permissions:** The uploader, any team admin, or a company admin/owner may delete.

**Response `204`** — No content

**Errors**
- `403` — Insufficient permissions
- `404` — Document not found

---

## Background Processing Detail

When a document is uploaded, the following pipeline executes asynchronously via Celery:

```
Celery Task: ingest_document(document_id, file_path, source_type)
│
├── 1. Load file
│     ├── PDF       → pdfplumber (text + page metadata)
│     ├── DOCX      → python-docx
│     ├── TXT/MD    → raw read
│     ├── Image     → pytesseract OCR
│     ├── Video/Audio → faster-whisper transcription
│     └── CSV       → pandas → text representation
│
├── 2. Chunk text
│     └── LlamaIndex SentenceSplitter
│           chunk_size=512 tokens, chunk_overlap=64 tokens
│
├── 3. Embed chunks (batch)
│     └── OpenAI text-embedding-3-large → 3072-dim float32 vectors
│
├── 4. Write to PostgreSQL
│     └── INSERT into chunks (content, embedding, embedding_hv, metadata)
│
├── 5. Named Entity Recognition
│     └── spaCy en_core_web_sm → entities per chunk
│
├── 6. Relationship Extraction
│     └── Co-occurrence + LLM-based extraction
│
├── 7. Write to Neo4j
│     └── MERGE Entity nodes + RELATED_TO / MENTIONED_IN edges
│
└── 8. UPDATE documents SET status='completed'
```
