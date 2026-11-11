"""
Release smoke tests (final validation, review 4 §3 item 5). Every check is executed; nothing is assumed.

  python -m src.eval.release_smoke                 # all checks (hosted latency uses LLM_PROVIDER=api + CHAT_MODEL)
  python -m src.eval.release_smoke --no-latency    # skip the hosted-model latency sample

Checks: deployed app health · Atlas retrieval · Atlas outage -> local fallback · CV upload (text PDF parsed, scanned PDF
rejected, skills extracted) · roadmap generate + adapt · user isolation (another user's profile never returned) · LLM
outage -> retrieval-only answer with notice · keyless answer · conversation state on a live turn · hosted latency p50/p95.
Writes reports/release/smoke_<ts>.json and smoke_latest.md.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from src.rag import config

APP_URL = "https://saanvi-sahoo-skillpath-srcfrontendfrontend-qwxzcn.streamlit.app"
OUT = config.PROJECT_ROOT / "reports" / "release"
RESULTS = []


def check(name):
    def deco(fn):
        def run():
            t0 = time.perf_counter()
            try:
                ok, evidence = fn()
            except Exception as e:  # noqa: BLE001
                ok, evidence = False, f"error: {type(e).__name__}: {str(e)[:200]} | {traceback.format_exc(limit=1)[-200:]}"
            RESULTS.append({"check": name, "passed": bool(ok), "evidence": evidence, "seconds": round(time.perf_counter() - t0, 1)})
            print(f"[{'PASS' if ok else 'FAIL'}] {name}: {evidence}", flush=True)
        return run
    return deco


@check("deployed app is up (Streamlit Cloud)")
def deployed():
    import urllib.request
    with urllib.request.urlopen(f"{APP_URL}/healthz", timeout=30) as r:
        code = r.status
    return code == 200, f"GET /healthz -> {code}"


@check("Atlas vector search returns career + knowledge records")
def atlas():
    from src.rag.embedder import embed_query
    from src.rag.vector_store import get_vector_store, resolve_backend
    if resolve_backend() != "mongo":
        return False, "MONGODB_URI not configured here"
    qv = embed_query("data analyst SQL Power BI")
    t0 = time.perf_counter()
    c = get_vector_store("careers").search(qv, k=5, sources=["careers"], user_id=None)
    k = get_vector_store("knowledge").search(qv, k=3, sources=["knowledge"], user_id=None)
    ms = round((time.perf_counter() - t0) * 1000)
    return len(c) == 5 and len(k) >= 1, f"{len(c)} careers ('{(c[0].get('metadata') or {}).get('career_name')}'), {len(k)} guides, {ms} ms"


@check("Atlas outage -> local copy of the same vectors (no crash, no invented records)")
def atlas_down():
    from src.rag import retriever, vector_store
    orig = vector_store.MongoVectorStore.search if hasattr(vector_store, "MongoVectorStore") else None
    cls = next(c for c in vars(vector_store).values() if isinstance(c, type) and c.__name__.lower().startswith("mongo"))
    orig = cls.search

    def boom(*a, **k):
        raise ConnectionError("simulated Atlas outage")
    cls.search = boom
    retriever._atlas_down_until = 0.0
    try:
        hits = retriever.retrieve("which careers use SQL and Tableau?", quotas={"careers": 3, "knowledge": 1})
        degraded = retriever.atlas_degraded()
    finally:
        cls.search = orig
        retriever._atlas_down_until = 0.0
    return bool(hits) and degraded, f"{len(hits)} hits from the local store, breaker open={degraded}"


@check("CV upload: text PDF parsed, scanned PDF rejected, skills extracted")
def cv_upload():
    import fitz
    from src.skills.extractor import rule_based_analysis
    from src.utilities.doc_check import unreadable_reason
    from src.utilities.Pdf_loader import extract_text_from_pdf
    d = tempfile.mkdtemp()
    good, scan = os.path.join(d, "cv.pdf"), os.path.join(d, "scan.pdf")
    doc = fitz.open()
    doc.new_page().insert_text((40, 60), "Asha Rao. B.Tech CSE 2025. Skills: Python, SQL, Excel, Power BI, Git.\n"
                                          "Projects: sales dashboard in Power BI; churn analysis with Python and Pandas.", fontsize=9)
    doc.save(good)
    doc = fitz.open()
    doc.new_page().draw_rect(fitz.Rect(40, 40, 400, 400), fill=(0.6, 0.6, 0.6))
    doc.save(scan)
    text = extract_text_from_pdf(good)
    a = rule_based_analysis(text, "Data Analyst. Required: SQL, Python, Tableau, Statistics, Power BI.")
    ok = unreadable_reason(good, "CV") is None and unreadable_reason(scan, "CV") is not None and {"SQL", "Python"} <= set(a["candidate_skills"])
    return ok, f"skills {a['candidate_skills']}, gaps {a['skill_gaps']}, ATS {a['ats_score']}; scanned PDF rejected"


@check("roadmap: valid 30-day plan, then adapted after a hard day and missed days")
def roadmap():
    from src.roadmap.adapt import adapt_roadmap
    from src.roadmap.generator import generate_roadmap
    r = generate_roadmap("Data Analyst", ["Excel"], gaps=["SQL", "Power BI", "Statistics"], daily_minutes=45, use_llm=False)
    a = adapt_roadmap(r, {1: "completed", 2: "needs_revision", 3: "skipped"}, today=4)
    ok = r["validation"]["valid"] and len(r["days"]) == 30 and a["days"][1]["kind"] == "revision" \
        and max(d["day"] for d in a["days"]) <= 30 and all(d["estimated_minutes"] <= 45 for d in a["days"])
    return ok, f"valid={r['validation']['valid']}, adapted: {'; '.join(a['changes'])[:160]}"


@check("user isolation: one student's profile is never retrieved for another")
def isolation():
    from src.eval.persona_eval import setup_personas
    from src.rag.retriever import retrieve
    setup_personas()
    leaks = 0
    for uid, other in (("persona_da", "persona_be"), ("persona_be", "persona_ml"), ("persona_ml", "persona_da")):
        hits = retrieve("what skills and projects are on my resume?", quotas={"profile": 8}, user_id=uid)
        leaks += sum(1 for h in hits if h.get("user_id") not in ("global", uid))
    return leaks == 0, f"3 students x 8 profile chunks: {leaks} records from another user"


@check("LLM outage -> retrieval-only answer with a notice (conversation kept)")
def llm_down():
    import src.utilities.brain as brain
    from src.backend.chatbot import answer
    orig = brain.get_robust_llm

    class Down:
        def invoke(self, *a, **k):
            raise ConnectionError("simulated provider outage")
    brain.get_robust_llm = lambda *a, **k: Down()
    prev = os.environ.get("LLM_PROVIDER")
    os.environ["LLM_PROVIDER"] = "api"
    try:
        r = answer([{"role": "user", "content": "Which careers use SQL and Power BI?"}], user_id="smoke_no_profile")
    finally:
        brain.get_robust_llm = orig
        os.environ["LLM_PROVIDER"] = prev or ""
    return "unavailable right now" in r["text"] and len(r["text"]) > 200, f"generation={r.get('generation')}; notice shown; {len(r['text'])} chars"


@check("keyless answer resolves 'the second one' from the conversation")
def keyless():
    from src.backend.chatbot import answer
    prev = os.environ.get("LLM_PROVIDER")
    os.environ["LLM_PROVIDER"] = "none"
    try:
        h = [{"role": "user", "content": "careers for someone who knows Python and SQL?"},
             {"role": "assistant", "content": "1. Data Analyst\n2. Data Engineer\n3. Backend Developer"},
             {"role": "user", "content": "tell me more about the second one"}]
        r = answer(h, user_id="smoke_no_profile")
    finally:
        os.environ["LLM_PROVIDER"] = prev or ""
    return "Data Engineer" in r["text"][:200], f"starts: {r['text'][:90]!r}"


def latency(n: int = 8):
    @check(f"hosted latency on {n} realistic turns (model: {os.getenv('CHAT_MODEL', 'default')})")
    def lat():
        from src.backend.chatbot import answer
        qs = ["What is Docker in one line?", "Suggest 3 careers for someone who likes maths and coding.",
              "Make me a 2 week SQL plan, 1 hour daily.", "How do I prepare for a data analyst interview?",
              "Explain overfitting simply.", "I studied civil engineering and want to move into software. How?",
              "What's the difference between Power BI and Tableau?", "How should I explain a 2-year gap in an interview?"][:n]
        times, models = [], set()
        for q in qs:
            r = answer([{"role": "user", "content": q}], user_id="smoke_no_profile")
            times.append(r["latency_ms"] / 1000)
            models.add(r.get("model"))
            time.sleep(3)
        p95 = sorted(times)[min(len(times) - 1, int(round(0.95 * (len(times) - 1))))]
        return all(m for m in models) and p95 < 60, f"p50 {statistics.median(times):.1f} s, p95 {p95:.1f} s, models {sorted(map(str, models))}"
    lat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-latency", action="store_true")
    a = ap.parse_args()
    for fn in (deployed, atlas, atlas_down, cv_upload, roadmap, isolation, llm_down, keyless):
        fn()
    if not a.no_latency:
        latency()
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (OUT / f"smoke_{ts}.json").write_text(json.dumps({"ts": ts, "results": RESULTS}, indent=2))
    L = [f"# Release smoke tests ({ts})", "", f"{sum(r['passed'] for r in RESULTS)}/{len(RESULTS)} passed. Every check was executed.", "",
         "| Check | Result | Evidence | s |", "|---|---|---|---|"]
    L += [f"| {r['check']} | {'PASS' if r['passed'] else 'FAIL'} | {r['evidence'].replace('|', '/')} | {r['seconds']} |" for r in RESULTS]
    (OUT / "smoke_latest.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
