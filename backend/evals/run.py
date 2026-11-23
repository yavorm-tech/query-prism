"""
Retrieval and answer-quality eval, run against a deployed stack through its API.

    python -m evals.run --base-url http://127.0.0.1:18000          # staging
    python -m evals.run --base-url ... --out evals/results/run.json --min-answer-pass 0.85

It signs up a throwaway company (or uses --email/--password), uploads the
documents in evals/corpus/ to its team, waits for ingestion, asks every question
in evals/questions.json through POST /chat (cache skipped), grades the replies
and prints a report. Exit status 1 if a --min-* threshold is missed, so it can
gate a release.

It spends real money: embeddings for the corpus and each question, graph
extraction, Cohere re-ranking and one LLM answer per question (~30 questions).
The answer model is the plan's tier (a new company is on "starter" → basic), so
to evaluate a model, point LLM_TIER_BASIC at it in that environment.

Grading is deterministic (no LLM judge):
  - documents: the expected source files appear among the answer's sources
    (doc recall; MRR = 1 / rank of the first expected file)
  - facts: each required fact (any of its alternatives, case-insensitive)
    appears in the answer; an answer passes when all its facts do
  - unanswerable: the answer says the documents don't cover it and names
    none of the forbidden (made-up) facts
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

HERE = Path(__file__).parent

REFUSAL = re.compile(
    r"(does not|doesn't|do not|don't|did not|didn't) (contain|include|mention|specify|provide|say|state|cover|have)"
    r"|no (information|mention|details?|data)|not (mentioned|specified|stated|provided|included|available|covered|found)"
    r"|(unable|not able) to (find|determine|answer)|(cannot|can't|could not|couldn't) (find|determine|answer)"
    r"|isn't (mentioned|specified|stated|covered)|there is no|not enough information",
    re.IGNORECASE,
)


# ── Grading (pure functions, unit-tested) ─────────────────────────────────────

def normalize(text: str) -> str:
    text = text.replace(" ", " ").replace(" ", " ").replace("’", "'")
    return re.sub(r"\s+", " ", text).strip().lower()


def fact_hits(answer: str, facts: list[list[str]]) -> list[bool]:
    a = normalize(answer)
    return [any(normalize(alt) in a for alt in alternatives) for alternatives in facts]


def doc_scores(expected: list[str], retrieved: list[str]) -> tuple[float, float]:
    """(recall of expected files among sources, reciprocal rank of the first expected file)."""
    if not expected:
        return 1.0, 1.0
    ordered = list(dict.fromkeys(retrieved))          # unique, in rank order
    recall = sum(1 for d in expected if d in ordered) / len(expected)
    rank = next((i for i, d in enumerate(ordered, 1) if d in expected), None)
    return recall, (1.0 / rank if rank else 0.0)


def is_refusal(answer: str, forbidden: list[str]) -> bool:
    a = normalize(answer)
    return bool(REFUSAL.search(answer)) and not any(normalize(f) in a for f in forbidden)


@dataclass
class Result:
    id: str
    kind: str
    question: str
    answer: str
    sources: list[str]
    seconds: float
    doc_recall: float
    mrr: float
    facts_found: int
    facts_total: int
    passed: bool
    error: str | None = None
    missing: list[list[str]] = field(default_factory=list)


def grade(q: dict, answer: str, sources: list[str], seconds: float) -> Result:
    recall, mrr = doc_scores(q["docs"], sources)
    if q["kind"] == "unanswerable":
        ok = is_refusal(answer, q.get("forbidden", []))
        hits, missing = [ok], ([] if ok else [["<a statement that the documents don't say>"]])
    else:
        hits = fact_hits(answer, q["facts"])
        missing = [f for f, h in zip(q["facts"], hits) if not h]
        ok = all(hits)
    return Result(
        id=q["id"], kind=q["kind"], question=q["question"], answer=answer, sources=sources,
        seconds=round(seconds, 2), doc_recall=recall, mrr=mrr,
        facts_found=sum(hits), facts_total=len(hits), passed=ok, missing=missing,
    )


def summarize(results: list[Result]) -> dict:
    def block(rs: list[Result]) -> dict:
        answerable = [r for r in rs if r.kind != "unanswerable"]
        return {
            "questions": len(rs),
            "answer_pass": round(sum(r.passed for r in rs) / len(rs), 3) if rs else None,
            "fact_recall": round(sum(r.facts_found for r in rs) / max(1, sum(r.facts_total for r in rs)), 3) if rs else None,
            "doc_recall": round(statistics.mean(r.doc_recall for r in answerable), 3) if answerable else None,
            "mrr": round(statistics.mean(r.mrr for r in answerable), 3) if answerable else None,
            "errors": sum(1 for r in rs if r.error),
        }
    out = {"overall": block(results)}
    for kind in ("single", "multi", "unanswerable"):
        rs = [r for r in results if r.kind == kind]
        if rs:
            out[kind] = block(rs)
    times = sorted(r.seconds for r in results if not r.error)
    if times:
        out["latency_seconds"] = {"p50": times[len(times) // 2], "p95": times[min(len(times) - 1, int(len(times) * 0.95))]}
    return out


# ── Talking to the API ────────────────────────────────────────────────────────

class Client:
    def __init__(self, base_url: str, email: str, password: str):
        self.http = httpx.Client(base_url=base_url.rstrip("/"), timeout=120)
        self.email, self.password = email, password
        self.token = ""

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def register(self) -> None:
        tag = uuid.uuid4().hex[:8]
        r = self.http.post("/auth/register", json={
            "company_name": f"Eval {time.strftime('%Y-%m-%d %H:%M')} {tag}",
            "username": f"eval{tag}", "email": self.email, "password": self.password,
        })
        r.raise_for_status()
        self.token = r.json()["access_token"]

    def login(self) -> None:
        r = self.http.post("/auth/login", json={"email": self.email, "password": self.password})
        r.raise_for_status()
        self.token = r.json()["access_token"]

    def request(self, method: str, url: str, **kw) -> httpx.Response:
        for attempt in range(6):
            r = self.http.request(method, url, headers=self._headers(), **kw)
            if r.status_code == 401 and attempt == 0:
                self.login()                       # access tokens live 15 minutes
                continue
            if r.status_code == 429:
                time.sleep(min(60, 5 * (attempt + 1)))
                continue
            return r
        return r

    def team_id(self) -> str:
        r = self.request("GET", "/auth/me")
        r.raise_for_status()
        me = r.json()
        return str(me.get("default_team_id") or me["team_ids"][0])


def upload_corpus(client: Client, team_id: str, corpus: Path, timeout: float) -> list[str]:
    ids = []
    for path in sorted(corpus.iterdir()):
        if path.is_file():
            r = client.request("POST", "/ingest", params={"team_id": team_id},
                               files={"file": (path.name, path.read_bytes(), "text/plain")})
            r.raise_for_status()
            ids.append(r.json()["document_id"])
            print(f"  uploaded {path.name}")
    deadline = time.monotonic() + timeout
    pending = set(ids)
    while pending:
        if time.monotonic() > deadline:
            raise SystemExit(f"Ingestion did not finish in {timeout:.0f}s ({len(pending)} documents pending)")
        for doc in list(pending):
            body = client.request("GET", f"/ingest/{doc}").json()
            if body["status"] == "completed":
                pending.discard(doc)
            elif body["status"] == "failed":
                raise SystemExit(f"Ingestion failed for {doc}: {body.get('error_message')}")
        if pending:
            time.sleep(3)
    return ids


def ask(client: Client, team_id: str, q: dict) -> Result:
    start = time.monotonic()
    try:
        r = client.request("POST", "/chat", json={"query": q["question"], "team_id": team_id, "skip_cache": True})
        r.raise_for_status()
        body = r.json()
    except Exception as e:
        res = grade(q, "", [], time.monotonic() - start)
        res.passed, res.error = False, f"{type(e).__name__}: {e}"
        return res
    sources = [s.get("original_name") or s.get("filename", "") for s in body.get("sources", [])]
    return grade(q, body.get("answer", ""), sources, time.monotonic() - start)


# ── Report ────────────────────────────────────────────────────────────────────

def _pct(v: float | None) -> str:
    return "-" if v is None else f"{v:.1%}"


def print_report(summary: dict, results: list[Result]) -> None:
    print(f"\n  {'':13} {'questions':>9}  {'answer pass':>11}  {'fact recall':>11}  {'doc recall':>10}  {'MRR':>5}")
    for name, s in summary.items():
        if name == "latency_seconds":
            continue
        mrr = "-" if s["mrr"] is None else f"{s['mrr']:.2f}"
        print(f"  {name:13} {s['questions']:>9}  {_pct(s['answer_pass']):>11}  {_pct(s['fact_recall']):>11}"
              f"  {_pct(s['doc_recall']):>10}  {mrr:>5}")
    if "latency_seconds" in summary:
        lat = summary["latency_seconds"]
        print(f"\n  latency  p50 {lat['p50']:.1f}s  p95 {lat['p95']:.1f}s")
    failed = [r for r in results if not r.passed]
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for r in failed:
            why = r.error or "missing " + "; ".join(" | ".join(m) for m in r.missing)
            print(f"  {r.id}: {why}")
            print(f"      sources: {', '.join(dict.fromkeys(r.sources)) or '-'}")
            print(f"      answer:  {normalize(r.answer)[:240]}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--base-url", default="http://127.0.0.1:18000", help="the API (gateway), e.g. staging")
    p.add_argument("--email", help="use this existing account instead of signing up a new company")
    p.add_argument("--password")
    p.add_argument("--questions", type=Path, default=HERE / "questions.json")
    p.add_argument("--corpus", type=Path, default=HERE / "corpus")
    p.add_argument("--only", help="comma-separated question ids")
    p.add_argument("--settle", type=float, default=60, help="seconds to wait after ingestion for graph extraction")
    p.add_argument("--ingest-timeout", type=float, default=900)
    p.add_argument("--keep", action="store_true", help="keep the uploaded documents afterwards")
    p.add_argument("--out", type=Path, help="write the full results as JSON")
    p.add_argument("--min-answer-pass", type=float, default=0.0)
    p.add_argument("--min-doc-recall", type=float, default=0.0)
    p.add_argument("--min-refusal", type=float, default=0.0, help="pass rate on unanswerable questions")
    args = p.parse_args(argv)

    questions = json.loads(args.questions.read_text())
    if args.only:
        wanted = set(args.only.split(","))
        questions = [q for q in questions if q["id"] in wanted]

    if args.email:
        client = Client(args.base_url, args.email, args.password or "")
        client.login()
    else:
        client = Client(args.base_url, f"eval-{uuid.uuid4().hex[:10]}@eval.invalid", uuid.uuid4().hex)
        client.register()
    team_id = client.team_id()

    print(f"Uploading {args.corpus} to team {team_id}")
    doc_ids = upload_corpus(client, team_id, args.corpus, args.ingest_timeout)
    if args.settle:
        print(f"Ingested; waiting {args.settle:.0f}s for graph extraction")
        time.sleep(args.settle)

    results = []
    for q in questions:
        res = ask(client, team_id, q)
        print(f"  {'PASS' if res.passed else 'FAIL'}  {res.id:12} {res.seconds:5.1f}s")
        results.append(res)

    if not args.keep:
        for doc in doc_ids:
            client.request("DELETE", f"/ingest/{doc}")

    summary = summarize(results)
    print_report(summary, results)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({
            "base_url": args.base_url, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "summary": summary, "results": [asdict(r) for r in results],
        }, indent=2, ensure_ascii=False))
        print(f"\nWrote {args.out}")

    o = summary["overall"]
    misses = []
    if (o["answer_pass"] or 0) < args.min_answer_pass:
        misses.append(f"answer pass {o['answer_pass']:.1%} < {args.min_answer_pass:.0%}")
    if o["doc_recall"] is not None and o["doc_recall"] < args.min_doc_recall:
        misses.append(f"doc recall {o['doc_recall']:.1%} < {args.min_doc_recall:.0%}")
    refusal = summary.get("unanswerable", {}).get("answer_pass")
    if refusal is not None and refusal < args.min_refusal:
        misses.append(f"refusal {refusal:.1%} < {args.min_refusal:.0%}")
    for m in misses:
        print(f"THRESHOLD MISSED: {m}")
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
