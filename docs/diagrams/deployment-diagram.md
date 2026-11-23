# Deployment Diagram

## Docker Compose Services

```mermaid
graph TB
    subgraph Internet
        Browser["Browser / API Client"]
        Google["Google OAuth"]
        OpenAI_API["OpenAI API"]
        Anthropic_API["Anthropic API"]
        Cohere_API["Cohere API"]
    end

    subgraph Host["Docker Host (Linux)"]
        Traefik["Traefik\n:80, :443\nLet's Encrypt, auto-renew"]

        subgraph Net["rag_net"]
            Nginx["Nginx Gateway\n:8000"]
            ReactApp["React App\n(served by Nginx)"]
            Migrate["migrate\nalembic upgrade head\n(runs once per deploy)"]
            API["api :8000\nFastAPI modular monolith\nidentity · metering · notification · audit\nworkspace · knowledge · retrieval"]
            Worker["worker\nCelery ingestion\nmetrics :9101"]
            Postgres["PostgreSQL 18 + pgvector\nschema per context"]
            Neo4j["Neo4j 5.26"]
            Redis["redis\nanswer cache + rate limits\n(LRU)"]
            Broker["redis-broker\nCelery queue\n(noeviction, AOF)"]
            Postfix["Postfix SMTP"]
        end

        subgraph Mon["monitoring profile"]
            Prom["Prometheus\n127.0.0.1:9090"]
            AM["Alertmanager\n127.0.0.1:9093"]
            NodeExp["node-exporter\nbackup metrics"]
        end
    end

    Browser -->|HTTPS :443| Traefik
    Traefik -->|API paths, HTTP :8000| Nginx
    Traefik -->|everything else| ReactApp
    Nginx -->|all API paths| API

    Migrate -->|DDL| Postgres
    API -->|asyncpg| Postgres
    API -->|Bolt| Neo4j
    API -->|cache, rate limits| Redis
    API -->|send_task| Broker
    API -->|SMTP| Postfix
    API -->|HTTPS| OpenAI_API
    API -->|HTTPS| Anthropic_API
    API -->|HTTPS| Cohere_API
    API -->|OAuth| Google

    Broker --> Worker
    Worker -->|asyncpg| Postgres
    Worker -->|Bolt| Neo4j
    Worker -->|cache invalidation| Redis
    Worker -->|HTTPS| OpenAI_API

    Prom -->|scrape /metrics| API
    Prom -->|scrape :9101| Worker
    Prom -->|scrape| NodeExp
    Prom -->|alerts| AM
    AM -->|email| Postfix
    Postfix -->|SMTP relay| Relay["Email provider"]
```

Ports, memory limits and volumes for each container: [services.md](../services.md).

---

## Network Topology

All services share the `rag_net` Docker bridge network. There is no service-to-service
HTTP any more: contexts call each other in-process through their `api.py` modules, and
the API hands ingestion work to the worker through `redis-broker`.

```
api    → postgresql://postgres:5432   (search_path: identity, workspace, knowledge, retrieval, metering, audit, public)
api    → bolt://neo4j:7687
api    → redis://redis:6379/0          answer cache, rate limits
api    → redis://redis-broker:6379/0   enqueue ingestion
worker → same datastores; consumes redis-broker queue "ingestion"
```

---

## Deploying

The step-by-step procedure (first install, update, rollback, health check) is
`.claude/skills/deploy/SKILL.md`; `procedures/deploy-check.sh preflight|verify`
checks the host, `.env`, DNS, firewall, containers, HTTPS and backups.
