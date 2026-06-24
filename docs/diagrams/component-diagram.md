# Component Diagram

High-level view of the services and how they interact.

```mermaid
C4Component
    title Query-Prism Component Diagram

    Person(user, "End User", "Company employee querying documents")
    Person(admin, "Company Admin", "Manages teams, users, billing")

    Container_Boundary(frontend, "React Frontend") {
        Component(spa, "SPA", "React 19 + TypeScript", "Single-page app served by Nginx")
    }

    Container_Boundary(gateway, "Nginx Gateway :8000") {
        Component(proxy, "Reverse Proxy", "Nginx", "Routes /auth, /ingest, /chat, /topics, /contact")
    }

    Container_Boundary(auth_svc, "Auth Service :8001") {
        Component(auth_api, "Auth API", "FastAPI", "Register, login, teams, invites, audit")
        Component(jwt, "JWT Handler", "python-jose", "Token issuance & verification")
        Component(oauth, "OAuth Handler", "Google OAuth2", "Google sign-in flow")
    }

    Container_Boundary(ingest_svc, "Ingestion Service :8002") {
        Component(ingest_api, "Ingest API", "FastAPI", "File upload, status, delete")
        Component(celery_q, "Task Queue", "Celery + Redis", "Background job dispatch")
    }

    Container_Boundary(worker, "Celery Worker") {
        Component(loader, "File Loader", "pdfplumber, python-docx, whisper", "Extract text from files")
        Component(chunker, "Chunker", "LlamaIndex SentenceSplitter", "Split text into chunks")
        Component(embedder, "Embedder", "OpenAI text-embedding-3-large", "Generate 3072-dim vectors")
        Component(ner, "NER + Relations", "spaCy", "Entity & relation extraction")
        Component(graph_writer, "Graph Writer", "neo4j-driver", "Write to Neo4j")
    }

    Container_Boundary(chat_svc, "Chat Service :8003") {
        Component(chat_api, "Chat API", "FastAPI", "Query, streaming SSE")
        Component(retriever, "Retriever", "asyncpg + neo4j", "Hybrid vector + graph search")
        Component(reranker, "Re-ranker", "Cohere API", "Re-rank retrieved chunks")
        Component(llm, "LLM Client", "Anthropic / OpenAI SDK", "Generate answers")
        Component(cache, "Query Cache", "Redis", "Cache query results")
        Component(topics_svc, "Topics Service", "FastAPI", "CRUD for topic folders")
    }

    Container_Boundary(billing_svc, "Billing Service :8004") {
        Component(billing_api, "Billing API", "FastAPI", "Quota enforcement, usage stats")
    }

    Container_Boundary(notif_svc, "Notification Service :8005") {
        Component(email_svc, "Email Service", "smtplib + Postfix", "Transactional emails")
    }

    ContainerDb(postgres, "PostgreSQL :5434", "PostgreSQL 16 + pgvector", "Users, documents, chunks, history")
    ContainerDb(neo4j, "Neo4j :7687", "Neo4j 5", "Knowledge graph")
    ContainerDb(redis, "Redis :6380", "Redis 7", "Cache + Celery broker")
    ContainerDb(postfix, "Postfix", "SMTP relay", "Email delivery")

    Rel(user, spa, "Uses", "HTTPS")
    Rel(admin, spa, "Uses", "HTTPS")
    Rel(spa, proxy, "API requests", "HTTP/JSON, SSE")

    Rel(proxy, auth_api, "Routes /auth", "HTTP")
    Rel(proxy, ingest_api, "Routes /ingest", "HTTP/multipart")
    Rel(proxy, chat_api, "Routes /chat", "HTTP/SSE")
    Rel(proxy, topics_svc, "Routes /topics", "HTTP")
    Rel(proxy, email_svc, "Routes /contact", "HTTP")

    Rel(auth_api, postgres, "R/W users, teams, invites", "asyncpg")
    Rel(auth_api, billing_api, "Check limits", "HTTP internal")
    Rel(auth_api, email_svc, "Send emails", "HTTP internal")

    Rel(ingest_api, postgres, "Insert document metadata", "asyncpg")
    Rel(ingest_api, billing_api, "Check storage limit", "HTTP internal")
    Rel(ingest_api, celery_q, "Queue ingestion job", "Redis")

    Rel(celery_q, worker, "Dispatch task", "Redis")
    Rel(loader, chunker, "Pass text")
    Rel(chunker, embedder, "Pass chunks")
    Rel(embedder, postgres, "Write chunks + vectors", "asyncpg")
    Rel(ner, graph_writer, "Pass entities")
    Rel(graph_writer, neo4j, "Write graph", "Bolt")

    Rel(chat_api, retriever, "Retrieve context")
    Rel(retriever, postgres, "Vector search", "asyncpg + pgvector")
    Rel(retriever, neo4j, "Graph search", "Bolt")
    Rel(retriever, reranker, "Re-rank chunks", "Cohere HTTP")
    Rel(chat_api, llm, "Generate answer", "Anthropic/OpenAI HTTP")
    Rel(chat_api, cache, "Cache R/W", "Redis")
    Rel(chat_api, billing_api, "Check & increment queries", "HTTP internal")

    Rel(email_svc, postfix, "Send via SMTP", "SMTP :25")
```

---

## Simplified Service Interaction Map

```
                    ┌──────────┐
                    │  React   │
                    │ Frontend │
                    └────┬─────┘
                         │ HTTPS
                    ┌────▼─────┐
                    │  Nginx   │
                    │ :8000    │
                    └──┬──┬──┬─┘
                       │  │  │
          ┌────────────┘  │  └──────────────┐
          │               │                 │
    ┌─────▼────┐    ┌──────▼──────┐   ┌─────▼──────┐
    │   Auth   │    │  Ingestion  │   │    Chat    │
    │  :8001   │    │   :8002     │   │   :8003    │
    └──┬───────┘    └──────┬──────┘   └──────┬─────┘
       │                   │                  │
       │           ┌───────▼──────┐           │
       │           │ Celery Worker│           │
       │           └───────┬──────┘           │
       │                   │                  │
       └─────────┬──────────┘──────────────────┘
                 │                  │
    ┌────────────▼──┐    ┌──────────▼────────┐
    │  Billing Svc  │    │  Notification Svc │
    │    :8004      │    │      :8005        │
    │  (internal)   │    │    (+ /contact)   │
    └───────────────┘    └───────────────────┘
                 │
    ┌────────────▼────────────────────────────────┐
    │         Data Layer                           │
    │  PostgreSQL :5434  Neo4j :7687  Redis :6380  │
    └─────────────────────────────────────────────┘
```
