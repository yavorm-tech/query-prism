# Query-Prism Documentation

**AskYourBase** (internal codename: Query-Prism) is a multi-tenant RAG (Retrieval-Augmented Generation) platform that enables companies to upload documents and query them using AI.

---

## Table of Contents

| Document | Description |
|----------|-------------|
| [Architecture Overview](./architecture.md) | System design, tech stack, service breakdown |
| [Data Models](./data-models.md) | Database schema, field definitions, relationships |
| [Security & Permissions](./security.md) | Auth, RBAC, rate limiting, audit trail |
| **API Reference** | |
| [Auth API](./api/auth.md) | Registration, login, OAuth, teams, invites |
| [Ingestion API](./api/ingestion.md) | File upload, document management |
| [Chat API](./api/chat.md) | Query, streaming, topics |
| [Billing API](./api/billing.md) | Usage quotas, plan limits |
| [Notification API](./api/notification.md) | Email sending |
| **Diagrams** | |
| [Component Diagram](./diagrams/component-diagram.md) | High-level service interaction |
| [Class Diagram](./diagrams/class-diagram.md) | Service classes and their relationships |
| [ER Diagram](./diagrams/er-diagram.md) | Database entity-relationship diagram |
| [Sequence Diagrams](./diagrams/sequence-diagrams.md) | Key user-flow step-by-step sequences |
| [Deployment Diagram](./diagrams/deployment-diagram.md) | Infrastructure and container layout |

---

## Quick-Start

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys and secrets

# Start all services
docker compose up -d

# Access
# Frontend:      http://localhost:3000
# API Gateway:   http://localhost:8000
# Flower (queue):http://localhost:5556
```

---

## Service Ports

| Service | Port | Description |
|---------|------|-------------|
| Nginx Gateway | 8000 | External entry point, routes all traffic |
| Auth Service | 8001 | Authentication & user management |
| Ingestion Service | 8002 | File upload & processing |
| Chat Service | 8003 | RAG query & topics |
| Billing Service | 8004 | Usage quotas (internal only) |
| Notification Service | 8005 | Email delivery |
| PostgreSQL | 5434 | Primary relational store |
| Neo4j | 7474 / 7687 | Knowledge graph |
| Redis | 6380 | Cache & task broker |
| Flower | 5556 | Celery task monitor |

---

## Plan Tiers

| Plan | Queries/mo | Storage | Teams | Users | LLM |
|------|-----------|---------|-------|-------|-----|
| Starter (Free) | 50 | 50 MB | 1 | 3 | GPT-4o Mini |
| Team | 1,000 | 5 GB | 5 | 25 | Claude Haiku |
| Business | 5,000 | 20 GB | Unlimited | Unlimited | Claude Sonnet |
| Enterprise | Unlimited | Unlimited | Unlimited | Unlimited | Claude Sonnet |
