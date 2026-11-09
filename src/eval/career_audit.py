"""
Career-retrieval audit (E37, review 2 §4). No LLM.

1. Query types: title / skill / transition / interest, so one P@5 can't hide a weak category.
2. Config sweep, SELECTED ON THE TUNING SET ONLY: vector, +cross-encoder, +skill re-ranker with domain bonus 6/3/0,
   BM25 hybrid (RRF) + cross-encoder + skill re-ranker.
3. Failure audit of the 30 E36 held-out queries: for each, the top-5 records with domain + skills, and a diagnosis:
     candidate_retrieval  no relevant record in the top-50 cosine pool
     ranking              relevant records were in the pool but not in the top 5
     source_data          a record matches the query's skills but carries another domain label
     strict_label         records are in the right domain but miss the keyword list (labels may be too strict)
   After this audit those 30 queries count as seen; the final number comes from heldout_careers_v2 (20, frozen).

  python -m src.eval.career_audit
Writes reports/heldout/career_audit_<ts>.json + career_audit_latest.md
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import numpy as np

from src.rag import config

HERE = Path(__file__).parent
OUT = config.PROJECT_ROOT / "reports" / "heldout"
SETS = {"tuning_24": HERE / "career_queries.jsonl", "heldout_30 (E36, audited)": HERE / "heldout" / "heldout_careers.jsonl",
        "heldout_v2_20 (frozen, final)": HERE / "heldout" / "heldout_careers_v2.jsonl"}
CONFIGS = ["vector", "vector+ce", "ce+skill(d6)", "ce+skill(d3)", "ce+skill(d0)", "hybrid+ce+skill(d3)"]


def qtype(q: Dict) -> str:
    if q.get("qtype"):
        return q["qtype"]
    t = q["query"].lower()
    if re.search(r"\b(switch|switching|moving|move into|transition|from \w+ to)\b", t):
        return "transition"
    if re.search(r"\b(i|i'm|me|my)\b", t):
        return "interest"
    from src.rag.skill_rerank import query_skills
    if len(query_skills(q["query"])) >= 2:
        return "skill"
    return "title" if len(t.split()) <= 5 else "interest"


def _ok(h: Dict, q: Dict) -> bool:
    from src.eval.evaluate_career_retrieval import _kw_hit
    m = h.get("metadata") or {}
    return (m.get("domain") in q["domains"]) and _kw_hit(f"{m.get('career_name')} {m.get('required_skills')}", q["keywords"])


def run_query(q: Dict, cache: Dict) -> Dict[str, List[Dict]]:
    from src.rag import skill_rerank as sr
    from src.rag.embedder import embed_query
    from src.rag.hybrid import bm25_search, rerank, rrf
    from src.rag.vector_store import get_vector_store
    if q["id"] not in cache:
        qv = embed_query(q["query"])
        pool50 = get_vector_store("careers", "local").search(qv, k=50, sources=["careers"])
        pool = pool50[:20]
        ce = rerank(q["query"], pool, top=20)
        hyb = rrf([pool, bm25_search("careers", q["query"], qv, k=20)])[:20]
        cache[q["id"]] = (pool50, pool, ce, rerank(q["query"], hyb, top=len(hyb)))
    pool50, pool, ce, hyb_ce = cache[q["id"]]
    out = {"vector": pool[:5], "vector+ce": ce[:5]}
    for name, d, src in (("ce+skill(d6)", 6.0, ce), ("ce+skill(d3)", 3.0, ce), ("ce+skill(d0)", 0.0, ce), ("hybrid+ce+skill(d3)", 3.0, hyb_ce)):
        old, sr.DELTA = sr.DELTA, d
        out[name] = sr.skill_rerank(q["query"], src, top=5)
        sr.DELTA = old
    out["_pool50"] = pool50
    return out


def diagnose(q: Dict, top: List[Dict], pool50: List[Dict]) -> str:
    from src.eval.evaluate_career_retrieval import _kw_hit
    if sum(_ok(h, q) for h in top) >= 4:
        return "ok"
    if not any(_ok(h, q) for h in pool50):
        kw_any = any(_kw_hit(f"{(h.get('metadata') or {}).get('career_name')} {(h.get('metadata') or {}).get('required_skills')}", q["keywords"]) for h in pool50)
        return "source_data (matching records carry other domain labels)" if kw_any else "candidate_retrieval (nothing relevant in top-50)"
    if any(_ok(h, q) for h in pool50[5:]) and sum(_ok(h, q) for h in top) < sum(_ok(h, q) for h in pool50[:20]) and sum(_ok(h, q) for h in pool50[:20]) >= 5:
        return "ranking (relevant records in the pool, not in the top 5)"
    dom = sum((h.get("metadata") or {}).get("domain") in q["domains"] for h in top)
    if dom >= 4:
        return "strict_label (right domain, keyword list missed)"
    return "source_data / mixed (few relevant records exist)"


def main():
    res = {"ts": datetime.now(timezone.utc).isoformat(), "sets": {}, "audit": []}
    for name, path in SETS.items():
        qs = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        cache: Dict = {}
        per_cfg = {c: [] for c in CONFIGS}
        by_type = defaultdict(lambda: {c: [] for c in CONFIGS})
        for q in qs:
            r = run_query(q, cache)
            t = qtype(q)
            for c in CONFIGS:
                p = sum(_ok(h, q) for h in r[c]) / 5
                per_cfg[c].append(p)
                by_type[t][c].append(p)
            if name.startswith("heldout_30"):
                top = r["ce+skill(d3)"]
                res["audit"].append({"id": q["id"], "query": q["query"], "type": t, "p@5": sum(_ok(h, q) for h in top) / 5,
                                     "diagnosis": diagnose(q, top, r["_pool50"]),
                                     "top5": [{"career": (h.get("metadata") or {}).get("career_name"), "domain": (h.get("metadata") or {}).get("domain"),
                                               "relevant": _ok(h, q), "skills": str((h.get("metadata") or {}).get("required_skills"))[:90]} for h in top]})
        res["sets"][name] = {"n": len(qs), "p@5": {c: round(float(np.mean(v)), 3) for c, v in per_cfg.items()},
                             "by_type": {t: {"n": len(v["vector"]), **{c: round(float(np.mean(x)), 3) for c, x in v.items()}} for t, v in by_type.items()}}
        print(name, res["sets"][name]["p@5"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"career_audit_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json").write_text(json.dumps(res, indent=2, default=str))
    L = ["# Career retrieval audit (E37)", "", res["ts"], "", "## Strict P@5 by configuration", "",
         "| Set | n | " + " | ".join(CONFIGS) + " |", "|---|---|" + "---|" * len(CONFIGS)]
    for name, d in res["sets"].items():
        L.append(f"| {name} | {d['n']} | " + " | ".join(str(d["p@5"][c]) for c in CONFIGS) + " |")
    L += ["", "## By query type", ""]
    for name, d in res["sets"].items():
        L += [f"**{name}**", "", "| Type | n | " + " | ".join(CONFIGS) + " |", "|---|---|" + "---|" * len(CONFIGS)]
        for t, v in sorted(d["by_type"].items()):
            L.append(f"| {t} | {v['n']} | " + " | ".join(str(v[c]) for c in CONFIGS) + " |")
        L.append("")
    counts: Dict[str, int] = defaultdict(int)
    for a in res["audit"]:
        counts[a["diagnosis"].split(" (")[0]] += 1
    L += ["## Audit of the 30 E36 held-out queries (config ce+skill(d3))", "", "Diagnoses: " + ", ".join(f"{k} × {v}" for k, v in counts.items()), "",
          "| Query | Type | P@5 | Diagnosis | Top-5 (✓ relevant) |", "|---|---|---|---|---|"]
    for a in sorted(res["audit"], key=lambda x: x["p@5"]):
        tops = "; ".join(f"{'✓' if h['relevant'] else '✗'} {h['career']} ({h['domain']})" for h in a["top5"])
        L.append(f"| {a['query']} | {a['type']} | {a['p@5']} | {a['diagnosis']} | {tops} |")
    (OUT / "career_audit_latest.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
