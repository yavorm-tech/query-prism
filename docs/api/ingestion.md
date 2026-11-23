# Ingestion API (knowledge module)

**Base URL:** `/ingest`  
**Served by:** `api` (port 8000, via the gateway)  
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
Celery task: app.worker.ingest_document(document_id, file_path, source_type)
(queue "ingestion" on redis-broker; max 3 retries, 30 s apart; file kept until the last attempt)
│
├── 1. UPDATE documents SET status='processing'
│
├── 2. Load file  (app/knowledge/loaders.py)
│     ├── PDF          → pdfplumber (text + page metadata)
│     ├── DOCX         → python-docx
│     ├── TXT/MD       → raw read
│     ├── Image        → pytesseract OCR
│     ├── Video/Audio  → faster-whisper transcription
│     └── CSV          → csv.DictReader, one sentence per row
│
├── 3. Chunk text
│     └── LlamaIndex SentenceSplitter (chunk_size=512, chunk_overlap=50 tokens)
│
├── 4. Embed chunks (batch)
│     └── OpenAI text-embedding-3-large → 3072-dim vectors
│
├── 5. Write to PostgreSQL (one transaction, safe to retry)
│     └── DELETE old chunks for the document, INSERT chunks (content, embedding_hv halfvec, metadata)
│
├── 6. metering.increment_storage(company_id, file_size)
├── 7. UPDATE documents SET status='completed'
├── 8. publish DocumentIngested → retrieval drops affected cached answers
│
└── 9. send_task app.graph_worker.build_knowledge_graph(document_id)
        ├── NER per chunk — GPT-4o-mini (app/shared/ai/ner.py)
        ├── Relation extraction — LLM, only chunks with 2+ entities
        └── Neo4j MERGE Document, Chunk, Entity nodes; HAS_CHUNK / MENTIONS / RELATED_TO edges

On final failure: status='failed', error_message set, file removed.
```
