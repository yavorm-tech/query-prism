import asyncio
import uuid

import pytest

from app.retrieval import retriever
from app.shared.db import get_pool

pytestmark = pytest.mark.integration


async def _seed_docs(co: dict, vec, n: int = 60, label: str | None = None, topic_id: str | None = None) -> str:
    label = label or co["company_id"][:8]
    pool = await get_pool()
    async with pool.acquire() as conn:
        doc_id = await conn.fetchval(
            """INSERT INTO documents (company_id, team_id, topic_id, uploaded_by, filename, original_name,
                                      source_type, file_size, visibility, status)
               VALUES ($1, $2, $3, $4, 'f.txt', 'f.txt', 'txt', 10, 'team', 'completed') RETURNING id""",
            co["company_id"], co["team_id"], topic_id, co["user_id"],
        )
        await conn.executemany(
            "INSERT INTO chunks (document_id, chunk_index, content, token_count, embedding_hv) VALUES ($1, $2, $3, 5, $4::halfvec)",
            [(doc_id, i, f"{label} chunk {i}", str(vec(f"{label}-{i}"))) for i in range(n)],
        )
    return label


async def _used(company_id: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT queries_used_this_month FROM subscriptions WHERE company_id = $1", company_id)


async def test_hnsw_index_serves_vector_search():
    pool = await get_pool()
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("SET LOCAL enable_seqscan = off")  # small table; prove the index fits the query shape
        plan = await conn.fetch("EXPLAIN SELECT id FROM chunks ORDER BY embedding_hv <=> $1::halfvec LIMIT 20", str([0.1] * 3072))
    assert any("chunks_embedding_hv_hnsw_idx" in r[0] for r in plan)


async def test_vector_and_graph_search_stay_inside_the_tenant(register, ai_stubs, monkeypatch):
    a, b = await register(), await register()
    la = await _seed_docs(a, ai_stubs["vec"])
    lb = await _seed_docs(b, ai_stubs["vec"])
    user_a = {**a["claims"], "role": "member"}

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await retriever._vector_search(conn, ai_stubs["vec"](f"{la}-7"), user_a, top_k=20)
        all_ids = [str(r["id"]) for r in await conn.fetch("SELECT id FROM chunks ORDER BY random()")]
    assert len(rows) == 20
    assert rows[0]["content"] == f"{la} chunk 7"
    assert not [r for r in rows if lb in r["content"]]

    # Neo4j has no tenant data: it may return any company's chunk ids.
    async def related(query_text, max_hops=2, max_chunks=20):
        return all_ids[:max_chunks]
    monkeypatch.setattr("app.retrieval.graph_query.find_related_chunk_ids", related)
    async with pool.acquire() as conn:
        graph_rows = await retriever._graph_search(conn, "q", user_a, top_k=20)
    assert graph_rows and not [r for r in graph_rows if lb in r["content"]]


async def test_concurrent_retrievals_and_graph_outage(register, ai_stubs):
    a = await register()
    await _seed_docs(a, ai_stubs["vec"])
    # Neo4j is unreachable in tests: every call exercises the vector-only fallback.
    results = await asyncio.wait_for(asyncio.gather(*[retriever.retrieve("what?", a["claims"]) for _ in range(8)]), 30)
    assert all(context and len(sources) == 8 for context, sources in results)


async def test_quota_is_released_when_no_llm_call_happens(client, register, ai_stubs):
    co = await register()
    h = co["headers"]

    r = await client.post("/chat", json={"query": "anything"}, headers=h)          # no documents yet
    assert r.status_code == 200 and r.json()["sources"] == []
    assert await _used(co["company_id"]) == 0

    await _seed_docs(co, ai_stubs["vec"])
    r = await client.post("/chat", json={"query": "anything"}, headers=h)          # answered
    assert r.json()["answer"] == "stub answer"
    assert await _used(co["company_id"]) == 1

    r = await client.post("/chat", json={"query": "anything"}, headers=h)          # cache hit
    assert r.json()["cached"] is True
    assert await _used(co["company_id"]) == 1

    ai_stubs["fail"] = True
    r = await client.post("/chat", json={"query": "new question"}, headers=h)      # provider error
    assert r.status_code == 500
    assert await _used(co["company_id"]) == 1


async def test_stream_answers_and_records_history(client, register, ai_stubs):
    co = await register()
    pool = await get_pool()
    async with pool.acquire() as conn:
        topic_id = str(await conn.fetchval("SELECT id FROM topics WHERE team_id = $1", co["team_id"]))
    await _seed_docs(co, ai_stubs["vec"], topic_id=topic_id)

    r = await client.get("/chat/stream", params={"query": "q1", "topic_id": topic_id}, headers=co["headers"])
    assert r.status_code == 200
    assert '"type": "done"' in r.text and "stub" in r.text
    assert await _used(co["company_id"]) == 1

    history = (await client.get(f"/topics/{topic_id}/questions", headers=co["headers"])).json()
    assert [h["question"] for h in history] == ["q1"]

    ai_stubs["fail"] = True
    r = await client.get("/chat/stream", params={"query": "q2"}, headers=co["headers"])
    assert '"type": "error"' in r.text and "provider down" not in r.text   # no internals leaked
    assert await _used(co["company_id"]) == 2   # the provider call started, so it stays counted


async def test_rate_limit_is_per_user(client, register, ai_stubs):
    a, b = await register(), await register()
    statuses = [(await client.post("/chat", json={"query": f"q{uuid.uuid4()}"}, headers=a["headers"])).status_code for _ in range(31)]
    assert statuses[-1] == 429 and statuses[:30].count(429) == 0
    assert (await client.post("/chat", json={"query": "q"}, headers=b["headers"])).status_code == 200
