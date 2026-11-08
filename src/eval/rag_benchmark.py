"""
RAG retrieval benchmark (E35, docs/rag.md §8). No LLM calls: measures what reaches the prompt.

Configs: vector | hybrid (BM25 + vector, RRF) | vector+rerank | hybrid+rerank (cross-encoder on the top 20)
Tasks:
  knowledge  30 labelled student questions -> expected guide section   (Hit@1, Hit@3, MRR@5)
  careers    24 labelled career queries    -> domain + keyword          (strict P@5, as in E11)
  profile    persona questions             -> expected profile doc types, with / without query expansion (Hit@3)

  python -m src.eval.rag_benchmark
Writes reports/embeddings/rag_benchmark_<ts>.json + rag_benchmark_latest.md
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import numpy as np

from src.rag import config
from src.rag.embedder import embed_query
from src.rag.hybrid import bm25_search, expand_query, rerank, rrf
from src.rag.vector_store import get_vector_store

HERE = Path(__file__).parent
CONFIGS = ["vector", "hybrid", "vector+rerank", "hybrid+rerank"]


def search(source: str, query: str, k: int, cfg: str, user_id=None, backend="local") -> List[Dict]:
    qv = embed_query(query)
    pool = 20 if cfg != "vector" else k
    vec = get_vector_store(source, backend).search(qv, k=pool, sources=[source], user_id=user_id)
    hits = vec
    if cfg.startswith("hybrid") and source != "profile":
        hits = rrf([vec, bm25_search(source, query, qv, k=pool)])[:pool]
    if cfg.endswith("rerank"):
        hits = rerank(query, hits, top=k)
    return hits[:k]


def knowledge_task(cfg: str) -> Dict:
    qs = [json.loads(l) for l in (HERE / "knowledge_queries.jsonl").read_text().splitlines() if l.strip()]
    ranks, lat, misses = [], [], []
    for q in qs:
        t = time.perf_counter()
        hits = search("knowledge", q["q"], 5, cfg)
        lat.append((time.perf_counter() - t) * 1000)
        r = next((i for i, h in enumerate(hits, 1) if (h.get("metadata") or {}).get("section") == q["expect"]), None)
        ranks.append(r)
        if r != 1:
            misses.append({"q": q["q"], "expect": q["expect"], "got": [(h.get("metadata") or {}).get("section") for h in hits[:3]]})
    n = len(ranks)
    return {"hit@1": round(sum(r == 1 for r in ranks) / n, 3), "hit@3": round(sum(bool(r and r <= 3) for r in ranks) / n, 3),
            "mrr@5": round(sum(1 / r for r in ranks if r) / n, 3), "ms_median": round(float(np.median(lat)), 1), "misses": misses}


def careers_task(cfg: str) -> Dict:
    from src.eval.evaluate_career_retrieval import _kw_hit
    qs = [json.loads(l) for l in (HERE / "career_queries.jsonl").read_text().splitlines() if l.strip()]
    strict, lat = [], []
    for q in qs:
        t = time.perf_counter()
        hits = search("careers", q["query"], 5, cfg)
        lat.append((time.perf_counter() - t) * 1000)
        ok = [((h.get("metadata") or {}).get("domain") in q["domains"]) and
              _kw_hit(f"{(h.get('metadata') or {}).get('career_name')} {(h.get('metadata') or {}).get('required_skills')}", q["keywords"]) for h in hits]
        strict.append(sum(ok) / 5)
    return {"strict_p@5": round(float(np.mean(strict)), 3), "ms_median": round(float(np.median(lat)), 1)}


PROFILE_QS = [  # question, question type, acceptable doc types in the top 3
    ("What am I missing for this job?", "fit_analysis", {"profile_overview", "job_description"}),
    ("Which requirements of this job do I already meet?", "fit_analysis", {"profile_overview", "job_description", "resume"}),
    ("Make a 4-week plan to close my gaps", "plan", {"learning_path", "learning_resource", "profile_overview"}),
    ("What does the job description require?", "jd_requirements", {"job_description", "profile_overview"}),
    ("What skills do I already have?", "profile_fact", {"resume", "profile_overview"}),
    ("Which gap should I learn first?", "profile_fact", {"profile_overview", "learning_path"}),
]


def profile_task(expand: bool) -> Dict:
    from src.backend.chatbot import load_memory
    hits_ok = []
    for uid in ("persona_da", "persona_be", "persona_ml"):
        mem = load_memory(uid)
        if not mem:
            continue
        for q, qtype, want in PROFILE_QS:
            query = expand_query(q, qtype, mem) if expand else q
            hits = search("profile", query, 3, "vector", user_id=uid, backend=None)
            hits_ok.append(any(h.get("doc_type") in want for h in hits))
    return {"hit@3": round(sum(hits_ok) / max(1, len(hits_ok)), 3), "n": len(hits_ok)}


def main():
    res = {"ts": datetime.now(timezone.utc).isoformat(), "model": config.EMBEDDING_MODEL, "knowledge": {}, "careers": {}, "profile": {}}
    for cfg in CONFIGS:
        res["knowledge"][cfg] = knowledge_task(cfg)
        res["careers"][cfg] = careers_task(cfg)
        print(cfg, "| knowledge", {k: v for k, v in res["knowledge"][cfg].items() if k != "misses"}, "| careers", res["careers"][cfg])
    for expand in (False, True):
        res["profile"]["expanded" if expand else "plain"] = profile_task(expand)
    print("profile", res["profile"])
    out = config.REPORTS_DIR / f"rag_benchmark_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    out.write_text(json.dumps(res, indent=2))
    L = ["# RAG retrieval benchmark", "", f"{res['ts']} · embeddings `{res['model']}`", "",
         "| Config | Knowledge Hit@1 | Hit@3 | MRR@5 | Careers strict-P@5 | Median ms (knowledge / careers) |", "|---|---|---|---|---|---|"]
    for cfg in CONFIGS:
        k, c = res["knowledge"][cfg], res["careers"][cfg]
        L.append(f"| {cfg} | {k['hit@1']} | {k['hit@3']} | {k['mrr@5']} | {c['strict_p@5']} | {k['ms_median']} / {c['ms_median']} |")
    L += ["", f"Profile retrieval Hit@3: plain {res['profile']['plain']['hit@3']} vs expanded {res['profile']['expanded']['hit@3']} (n={res['profile']['plain']['n']})"]
    (config.REPORTS_DIR / "rag_benchmark_latest.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
