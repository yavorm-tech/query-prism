"""
Hybrid retriever — multi-tenant, team-scoped.

Access rules:
  - Regular members: see docs from their teams + company-wide docs
  - Admins/owners: see all docs in the company

All queries enforce these rules at the SQL level.
"""
import logging
import asyncio
import asyncpg
from app.config import get_settings
from app.services.embedder import embed_texts

settings = get_settings()
logger = logging.getLogger(__name__)


def _build_access_filter(user: dict) -> tuple[str, list]:
    """
    Build the SQL WHERE clause and params for document access.
    Returns (where_clause, params) — params start at $1.
    """
    role = user.get("role", "member")
    company_id = user["company_id"]

    if role in ("admin", "owner"):
        # Admins see everything in the company
        where = "d.company_id = $1 AND d.status = 'completed'"
        params = [company_id]
    else:
        # Members see their team docs + company-wide docs
        team_ids = user.get("team_ids") or []
        where = """
            (
                d.team_id = ANY($1::uuid[])
                OR (d.company_id = $2 AND d.visibility = 'company')
            )
            AND d.status = 'completed'
        """
        params = [team_ids, company_id]

    return where, params


async def _vector_search(
    conn: asyncpg.Connection,
    query_embedding: list[float],
    user: dict,
    top_k: int = 20,
    source_type: str | None = None,
    team_id: str | None = None,
    topic_id: str | None = None,
) -> list[dict]:
    """ANN similarity search using halfvec HNSW index."""

    role = user.get("role", "member")
    company_id = user["company_id"]

    # Build params list — embedding goes FIRST as $1 to avoid position conflicts
    params = [str(query_embedding)]   # $1 = embedding

    if role in ("admin", "owner"):
        access_where = "d.company_id = $2 AND d.status = 'completed'"
        params.append(company_id)     # $2
        next_param = 3
    else:
        team_ids = user.get("team_ids") or []
        access_where = """
            (
                d.team_id = ANY($2::uuid[])
                OR (d.company_id = $3 AND d.visibility = 'company')
            )
            AND d.status = 'completed'
        """
        params.append(team_ids)       # $2
        params.append(company_id)     # $3
        next_param = 4

    extra = ""
    if team_id:
        extra += f" AND d.team_id = ${next_param}::uuid"
        params.append(team_id)
        next_param += 1

    if topic_id:
        extra += f" AND d.topic_id = ${next_param}::uuid"
        params.append(topic_id)
        next_param += 1

    if source_type:
        extra += f" AND d.source_type = ${next_param}"
        params.append(source_type)
        next_param += 1

    top_k_param = f"${next_param}"
    params.append(top_k)

    sql = f"""
        SELECT
            c.id,
            c.content,
            c.chunk_index,
            c.token_count,
            c.metadata,
            d.id           AS document_id,
            d.filename,
            d.original_name,
            d.source_type,
            d.team_id,
            d.visibility,
            1 - (c.embedding_hv <=> $1::halfvec) AS similarity
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE {access_where}
          AND c.embedding_hv IS NOT NULL
          {extra}
        ORDER BY c.embedding_hv <=> $1::halfvec
        LIMIT {top_k_param}
    """

    rows = await conn.fetch(sql, *params)
    return [dict(r) for r in rows]

async def _graph_search(
    conn: asyncpg.Connection,
    query_text: str,
    user: dict,
    top_k: int = 20,
    team_id: str | None = None,
    topic_id: str | None = None,
) -> list[dict]:
    from app.services.graph.query import find_related_chunk_ids

    chunk_ids = await find_related_chunk_ids(query_text, max_hops=2, max_chunks=top_k)
    if not chunk_ids:
        return []

    role = user.get("role", "member")
    company_id = user["company_id"]

    # chunk_ids goes FIRST as $1
    params = [chunk_ids]              # $1

    if role in ("admin", "owner"):
        access_where = "d.company_id = $2 AND d.status = 'completed'"
        params.append(company_id)     # $2
        next_param = 3
    else:
        team_ids = user.get("team_ids") or []
        access_where = """
            (
                d.team_id = ANY($2::uuid[])
                OR (d.company_id = $3 AND d.visibility = 'company')
            )
            AND d.status = 'completed'
        """
        params.append(team_ids)       # $2
        params.append(company_id)     # $3
        next_param = 4

    extra = ""
    if team_id:
        extra += f" AND d.team_id = ${next_param}::uuid"
        params.append(team_id)
        next_param += 1

    if topic_id:
        extra += f" AND d.topic_id = ${next_param}::uuid"
        params.append(topic_id)
        next_param += 1

    sql = f"""
        SELECT
            c.id,
            c.content,
            c.chunk_index,
            c.token_count,
            c.metadata,
            d.id           AS document_id,
            d.filename,
            d.original_name,
            d.source_type,
            d.team_id,
            d.visibility,
            NULL::float    AS similarity
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE {access_where}
          AND c.id = ANY($1::uuid[])
          {extra}
    """

    rows = await conn.fetch(sql, *params)
    return [dict(r) for r in rows]

async def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 8,
) -> list[dict]:
    if not candidates:
        return []

    if settings.cohere_api_key and settings.cohere_api_key.strip():
        try:
            import cohere
            co = cohere.AsyncClientV2(api_key=settings.cohere_api_key)
            documents = [c["content"] for c in candidates]
            response = await co.rerank(
                model="rerank-v3.5",
                query=query,
                documents=documents,
                top_n=top_k,
            )
            reranked = []
            for result in response.results:
                chunk = dict(candidates[result.index])
                chunk["rerank_score"] = result.relevance_score
                reranked.append(chunk)
            return reranked
        except Exception as e:
            logger.warning(f"Cohere rerank failed, falling back: {e}")

    return sorted(
        candidates,
        key=lambda c: c.get("similarity") or 0.0,
        reverse=True,
    )[:top_k]


def assemble_context(
    chunks: list[dict],
    max_tokens: int = 6000,
) -> tuple[str, list[dict]]:
    seen_ids = set()
    unique_chunks = []
    for chunk in chunks:
        cid = str(chunk["id"])
        if cid not in seen_ids:
            seen_ids.add(cid)
            unique_chunks.append(chunk)

    context_parts = []
    sources = []
    total_tokens = 0

    for chunk in unique_chunks:
        token_count = chunk.get("token_count") or len(chunk["content"].split()) * 1.3
        if total_tokens + token_count > max_tokens:
            break
        context_parts.append(chunk["content"])
        sources.append(chunk)
        total_tokens += token_count

    context = "\n\n---\n\n".join(context_parts)
    logger.debug(f"Context: {len(sources)} chunks, ~{int(total_tokens)} tokens")
    return context, sources


async def retrieve(
    query: str,
    user: dict,                        # full JWT payload — contains role, team_ids, company_id
    team_id: str | None = None,        # optional: scope to one specific team
    topic_id: str | None = None,       # optional: scope to one specific topic
    top_k_vector: int = 20,
    top_k_graph: int = 20,
    top_k_rerank: int = 8,
    source_type: str | None = None,
    max_context_tokens: int = 6000,
) -> tuple[str, list[dict]]:
    """
    Full hybrid retrieval — multi-tenant access controlled.

    Pass user=current_user (the decoded JWT dict) and optionally
    team_id or topic_id to scope the search.
    """
    embeddings = await embed_texts([query])
    query_embedding = embeddings[0]

    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn=dsn)

    try:
        await conn.set_type_codec(
            "vector",
            encoder=lambda v: str(v),
            decoder=lambda v: v,
            schema="public",
            format="text",
        )

        vector_results, graph_results = await asyncio.gather(
            _vector_search(conn, query_embedding, user, top_k_vector, source_type, team_id, topic_id),
            _graph_search(conn, query, user, top_k_graph, team_id, topic_id),
        )
    finally:
        await conn.close()

    role = user.get("role", "member")
    team_ids = user.get("team_ids", [])
    logger.debug(
        f"[{user.get('username')}|{role}] "
        f"Vector: {len(vector_results)}, Graph: {len(graph_results)}"
    )

    all_candidates = vector_results + graph_results
    reranked = await rerank(query, all_candidates, top_k_rerank)
    context, sources = assemble_context(reranked, max_context_tokens)

    return context, sources
