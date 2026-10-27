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
        NginxSSL["Nginx SSL\n:80, :443\nCertbot auto-renew"]

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
    end

    Browser -->|HTTPS :443| NginxSSL
    NginxSSL -->|HTTP :8000| Nginx
    NginxSSL -->|/*| ReactApp
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
```

---

## Port Reference

| Container | Internal Port | Host Port | Accessible From |
|-----------|--------------|-----------|----------------|
| nginx-gateway | 80 | 8000 | Public (via SSL proxy) |
| api | 8000 | — | Internal + Gateway |
| worker | 9101 (metrics) | — | Internal |
| nginx-ssl | 80/443 | 80/443 | Public |

---

## Volume Mounts

| Volume | Mount Path | Purpose |
|--------|-----------|---------|
| `postgres_data` | `/var/lib/postgresql/data` | PostgreSQL persistent data |
| `neo4j_data` | `/data` | Neo4j persistent data |
| `redis_data` | `/data` | Answer cache snapshot (RDB) |
| `redis_broker_data` | `/data` | Celery broker persistence (AOF) |
| `uploads` | `/app/uploads` | Uploaded files awaiting ingestion (shared between api and worker; deleted after ingestion) |
| `certbot_conf` | `/etc/letsencrypt` | SSL certificate store |
| `certbot_www` | `/var/www/certbot` | ACME challenge files |

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

## Production Deployment Checklist

- [ ] Set `SECRET_KEY` to a cryptographically random 32+ byte value (enforced at startup)
- [ ] Set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `COHERE_API_KEY`
- [ ] Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URL`
- [ ] Configure `SMTP_*` environment variables for email delivery
- [ ] Configure Certbot with your domain for HTTPS
- [ ] Set `DATABASE_URL` with production credentials
- [ ] Set `NEO4J_PASSWORD` to a strong password
- [ ] Mount persistent volumes for PostgreSQL, Neo4j, Redis, and uploads
- [x] Enable Redis AOF persistence for durability (`redis-broker`)
- [ ] Schedule `procedures/backup.sh` nightly (cron) and set `BACKUP_S3_URI` for off-host copies
- [ ] Set up log rotation for all service containers
- [x] Flower runs only in the dev overlay, bound to 127.0.0.1
- [ ] Scrape `api:8000/metrics` and `worker:9101/metrics` with Prometheus
