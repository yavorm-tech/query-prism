"""The eval runner's grading and flow, against a fake API (no money spent)."""
import json

import httpx
import pytest

from evals import run


def test_facts_match_any_alternative_case_and_spacing_insensitive():
    assert run.fact_hits("Up to 5 000 units; ask your VP.", [["5 000", "5000"], ["vice president", "vp"]]) == [True, True]
    assert run.fact_hits("The limit is €180.", [["240"]]) == [False]


def test_doc_scores_recall_and_reciprocal_rank():
    assert run.doc_scores(["a.md"], ["b.md", "a.md", "a.md"]) == (1.0, 0.5)
    assert run.doc_scores(["a.md", "c.md"], ["a.md", "b.md"]) == (0.5, 1.0)
    assert run.doc_scores(["a.md"], []) == (0.0, 0.0)


def test_refusal_needs_a_refusal_and_no_invented_fact():
    assert run.is_refusal("The documents don't mention a parental leave policy.", [])
    assert not run.is_refusal("Parents get 16 weeks of parental leave.", ["weeks of parental"])
    assert not run.is_refusal("The CEO is not mentioned, but Tomasz Erdély leads SRE.", ["Erdély"])


def test_grade_and_summary():
    q = {"id": "x", "kind": "single", "question": "?", "docs": ["a.md"], "facts": [["65"], ["euro", "€"]]}
    r = run.grade(q, "It is €65 per day.", ["a.md"], 1.0)
    assert r.passed and r.facts_found == 2 and r.mrr == 1.0
    r2 = run.grade(q, "It is 65.", ["b.md"], 3.0)
    assert not r2.passed and r2.missing == [["euro", "€"]] and r2.doc_recall == 0.0
    s = run.summarize([r, r2])
    assert s["overall"]["answer_pass"] == 0.5 and s["overall"]["fact_recall"] == 0.75
    assert s["single"]["doc_recall"] == 0.5


def _fake_api(answers: dict[str, str]):
    """A minimal stand-in for /auth, /ingest and /chat."""
    state = {"docs": {}, "deleted": [], "polls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        if path == "/auth/register":
            return httpx.Response(201, json={"access_token": "t"})
        if path == "/auth/me":
            return httpx.Response(200, json={"team_ids": ["team-1"], "default_team_id": "team-1"})
        if path == "/ingest" and method == "POST":
            name = request.content.split(b'filename="')[1].split(b'"')[0].decode()
            doc = f"doc-{len(state['docs'])}"
            state["docs"][doc] = name
            return httpx.Response(200, json={"document_id": doc, "status": "pending"})
        if path.startswith("/ingest/") and method == "GET":
            state["polls"] += 1
            done = state["polls"] > len(state["docs"])        # pending on the first pass
            return httpx.Response(200, json={"status": "completed" if done else "pending"})
        if path.startswith("/ingest/") and method == "DELETE":
            state["deleted"].append(path.rsplit("/", 1)[1])
            return httpx.Response(204)
        if path == "/chat":
            query = json.loads(request.content)["query"]
            answer, source = answers.get(query, ("I don't know.", None))
            sources = [{"original_name": source}] if source else []
            return httpx.Response(200, json={"answer": answer, "sources": sources})
        return httpx.Response(404)

    return handler, state


@pytest.fixture
def small_eval(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.md").write_text("Per diem is €65.")
    (corpus / "b.md").write_text("Hotel cap is €180.")
    questions = tmp_path / "q.json"
    questions.write_text(json.dumps([
        {"id": "q1", "kind": "single", "question": "per diem?", "docs": ["a.md"], "facts": [["65"]]},
        {"id": "q2", "kind": "single", "question": "hotel cap?", "docs": ["b.md"], "facts": [["180"]]},
        {"id": "q3", "kind": "unanswerable", "question": "ceo?", "docs": [], "facts": [], "forbidden": ["Alice"]},
    ]))
    monkeypatch.setattr(run.time, "sleep", lambda s: None)
    return corpus, questions


def _run(monkeypatch, handler, corpus, questions, tmp_path, *extra):
    real_client = httpx.Client
    monkeypatch.setattr(run.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    return run.main(["--corpus", str(corpus), "--questions", str(questions), "--settle", "0",
                     "--out", str(tmp_path / "out.json"), *extra])


def test_full_run_uploads_asks_grades_and_cleans_up(small_eval, monkeypatch, tmp_path):
    corpus, questions = small_eval
    handler, state = _fake_api({
        "per diem?": ("It is €65 per day.", "a.md"),
        "hotel cap?": ("The cap is €200.", "b.md"),                 # wrong fact
        "ceo?": ("The documents don't mention the CEO.", "a.md"),
    })
    code = _run(monkeypatch, handler, corpus, questions, tmp_path, "--min-answer-pass", "0.9")
    assert code == 1                                                # 2/3 < 90 %
    assert sorted(state["docs"].values()) == ["a.md", "b.md"]
    assert sorted(state["deleted"]) == sorted(state["docs"])
    out = json.loads((tmp_path / "out.json").read_text())
    assert out["summary"]["overall"]["answer_pass"] == pytest.approx(0.667, abs=1e-3)
    assert out["summary"]["unanswerable"]["answer_pass"] == 1.0
    assert [r["passed"] for r in out["results"]] == [True, False, True]


def test_thresholds_met_exit_zero(small_eval, monkeypatch, tmp_path):
    corpus, questions = small_eval
    handler, _ = _fake_api({
        "per diem?": ("€65.", "a.md"), "hotel cap?": ("€180.", "b.md"),
        "ceo?": ("That is not mentioned in the documents.", None),
    })
    assert _run(monkeypatch, handler, corpus, questions, tmp_path,
                "--min-answer-pass", "1", "--min-doc-recall", "1", "--min-refusal", "1") == 0
