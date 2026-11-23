# Module Diagram

The backend is one Python package, `backend/app`, split into modules (bounded
contexts). Each module exposes a public `api.py`; everything else in the
module is internal and may not be imported by other modules (enforced by
`lint-imports` and `tests/architecture/test_boundaries.py`).

Modules are mostly plain async functions rather than classes, so each box below
is a **module** and its members are the functions that matter.

---

## Public module APIs and how modules depend on each other

Arrows point from caller to callee. Modules may only call **downward**:
retrieval → knowledge → workspace → identity → metering / notification / audit → shared.
Upward reactions go through domain events (see the next section).

```mermaid
classDiagram
    direction TB

    class retrieval_router["retrieval.router  /chat"] {
        +POST /chat
        +GET /chat/stream
        +GET /topics/{id}/questions
    }

    class knowledge_router["knowledge.router  /ingest"] {
        +POST /ingest
        +GET /ingest
        +GET /ingest/{document_id}
        +DELETE /ingest/{document_id}
        +GET /topics/{id}/documents
    }

    class knowledge_api["knowledge.api"] {
        <<events>>
        DocumentUploaded
        DocumentIngested
        DocumentDeleted
    }

    class workspace_api["workspace.api"] {
        +get_topic(topic_id) dict
        +require_topic_access(topic_id, user) dict
        <<event>> TopicDeleted
    }

    class identity_api["identity.api"] {
        +get_team(team_id, company_id) dict
        +TenantDirectory.count_teams(company_id) int
        +TenantDirectory.count_users(company_id) int
        <<event>> CompanyRegistered
    }

    class metering_api["metering.api"] {
        +open_subscription(company_id, plan)
        +get_plan(company_id) str
        +reserve_query(company_id) str
        +release_query(company_id)
        +check_storage_limit(company_id, bytes)
        +check_team_limit(company_id, team_count)
        +check_user_limit(company_id, user_count)
        +increment_storage(company_id, bytes)
        +decrement_storage(company_id, bytes)
        +set_tenant_directory(TenantDirectory)
    }

    class notification_api["notification.api"] {
        +send_invite_email(email, company_name, team_name, token)
        +send_password_reset_email(email, token)
    }

    class audit_api["audit.api"] {
        +log_event(company_id, event_type, ...)
    }

    class shared["shared"] {
        config · db · neo4j · celery
        security: get_current_user, can_access_team, require_company_admin
        rate_limit · events · observability · loop_local
        ai.embedder: embed_texts
        ai.ner: extract_entities, extract_entities_batch
    }

    retrieval_router --> workspace_api : topic access
    retrieval_router --> identity_api : team in company
    retrieval_router --> metering_api : reserve / release query
    retrieval_router --> audit_api : question.asked
    knowledge_router --> workspace_api : topic access
    knowledge_router --> identity_api : team in company
    knowledge_router --> metering_api : storage limit / counters
    knowledge_router --> audit_api : document.*
    identity_api --> metering_api : open_subscription, limits
    identity_api --> notification_api : invite / reset email
    identity_api --> audit_api
    metering_api ..> identity_api : TenantDirectory port (wired in bootstrap)
    retrieval_router --> shared
    knowledge_router --> shared
```

---

## Domain events

Lower modules announce events; higher modules (or the publisher itself) react.
Handlers are subscribed in `app/bootstrap.py`, which both the API and the worker
call at startup. Events are stored in `shared.outbox` in the publisher's
transaction and delivered after commit; a failing handler does not fail the
publisher, and the API's outbox relay retries the event later.

```mermaid
classDiagram
    class DocumentUploaded {
        document_id
        storage_key
        source_type
        job_id
    }
    class CompanyRegistered {
        company_id
        team_id
        owner_id
    }
    class DocumentIngested {
        document_id
        company_id
        team_id
        visibility
    }
    class DocumentDeleted {
        document_id
        company_id
        team_id
        visibility
    }
    class TopicDeleted {
        topic_id
        team_id
        company_id
    }
    class workspace_handlers["workspace.handlers"] {
        +create_default_topic(CompanyRegistered)
    }
    class knowledge_handlers["knowledge.handlers"] {
        +queue_ingestion(DocumentUploaded)
        +queue_graph_build(DocumentIngested)
        +delete_graph(DocumentDeleted)
    }
    class retrieval_handlers["retrieval.handlers"] {
        +drop_answers_for_document(DocumentIngested | DocumentDeleted)
        +drop_answers_for_topic(TopicDeleted)
    }

    CompanyRegistered ..> workspace_handlers : identity publishes
    DocumentIngested ..> retrieval_handlers : knowledge (worker) publishes
    DocumentDeleted ..> retrieval_handlers : knowledge publishes
    TopicDeleted ..> retrieval_handlers : workspace publishes
    DocumentUploaded ..> knowledge_handlers : knowledge publishes
    DocumentIngested ..> knowledge_handlers
    DocumentDeleted ..> knowledge_handlers
```

---

## Knowledge: ingestion pipeline (worker)

```mermaid
classDiagram
    class ingest_document["tasks.ingest_document  (Celery, max_retries=3)"] {
        +ingest_document(document_id, file_path, source_type)
    }
    class build_knowledge_graph["graph_tasks  (Celery)"] {
        +build_knowledge_graph(document_id)
        +build_knowledge_graph_bulk()
    }
    class loaders {
        +load_document(file_path) (text, metadata)
        load_pdf · load_docx · load_txt
        load_image (tesseract) · load_video (faster-whisper) · load_csv
    }
    class chunker {
        +chunk_text(text, metadata) list~Chunk~
    }
    class Chunk {
        content: str
        chunk_index: int
        token_count: int
        metadata: dict
    }
    class embedder["shared.ai.embedder"] {
        +embed_texts(texts) list~vector3072~
    }
    class ner["shared.ai.ner (GPT-4o-mini)"] {
        +extract_entities_batch(pairs) list~ChunkEntities~
    }
    class relations["graph.relations"] {
        +extract_relations_batch(candidates) dict
    }
    class writer["graph.writer"] {
        +upsert_document_node()
        +upsert_chunk_node()
        +upsert_entities_and_mentions()
        +upsert_relations()
        +delete_document_graph(document_id)
    }

    ingest_document --> loaders : 1. extract text
    ingest_document --> chunker : 2. chunk
    chunker --> Chunk : produces
    ingest_document --> embedder : 3. embed
    ingest_document ..> build_knowledge_graph : 4. via DocumentIngested handler
    build_knowledge_graph --> ner : entities per chunk
    build_knowledge_graph --> relations : chunks with 2+ entities
    build_knowledge_graph --> writer : Neo4j MERGE
```

---

## Retrieval: answering a question

```mermaid
classDiagram
    class retriever {
        +retrieve(query, user, team_id, topic_id, source_type) (context, sources)
        -_vector_search() top 20, HNSW
        -_graph_search() top 20, tenant-filtered in Postgres
        +rerank(query, candidates, top_k=8)
        +assemble_context(chunks, max_tokens=6000)
    }
    class graph_query {
        +find_related_chunk_ids(query, max_hops=2, max_chunks)
        +get_entity_neighbourhood(entity_name, hops)
    }
    class llm {
        +generate_answer(query, context, sources, model) str
        +stream_answer(query, context, sources, model) AsyncGenerator
    }
    class cache["cache (Redis, TTL 1 h)"] {
        +get_cached(user, query, team_id)
        +set_cached(user, query, answer, sources, team_id)
        +invalidate_team_cache(team_id)
        +invalidate_company_cache(company_id)
    }
    class history {
        +save_question(user, query, team_id, topic_id, answer)
        +list_topic_questions(topic_id, ...)
    }

    retriever --> graph_query
    retriever ..> Cohere : rerank-v3.5 (falls back to similarity order)
    class adapter["shared.ai.llm (adapter)"] {
        +complete(tier, system, user) str
        +stream(tier, system, user) AsyncGenerator
        routes_for(tier) list~provider:model~
    }
    llm --> adapter : plan's answer tier
    adapter ..> Anthropic : messages.create / messages.stream
    adapter ..> OpenAI : chat.completions
```
