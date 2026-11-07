"""
Career-retrieval benchmark on the source-of-truth dataset (project doc section 13: "20+ labeled
queries; Precision@5 and error analysis").

Each query in career_queries.jsonl has
  domains  : acceptable `domain` values (weak labels - the dataset's domain column is itself
             "classified from title and skills; review borderline roles")
  keywords : skill/title terms that make a result relevant
A top-5 hit counts as relevant if domain matches (Domain-P@5) / if any keyword appears in its
name or required_skills (Keyword-P@5). "Strict" requires both.

Grid: embedding-text variant (pilot | domain | full) x model.
  python -m src.eval.evaluate_career_retrieval
  python -m src.eval.evaluate_career_retrieval --models BAAI/bge-small-en-v1.5 --variants full
Outputs reports/embeddings/career_retrieval_<ts>.json + career_retrieval_latest.md
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from src.rag import config
from src.rag.documents import CAREER_TEXT_VARIANTS, load_career_frame

QUERIES = Path(__file__).with_name("career_queries.jsonl")
QUERY_PREFIX = {"BAAI/bge-small-en-v1.5": "Represent this sentence for searching relevant passages: "}


def _kw_hit(text: str, keywords) -> bool:
    t = text.lower()
    return any(re.search(r"\b" + re.escape(k), t) for k in keywords)


def run(models, variants, k=5):
    from sentence_transformers import SentenceTransformer

    df = load_career_frame()
    queries = [json.loads(l) for l in QUERIES.read_text().splitlines() if l.strip()]
    results = []
    for m in models:
        model = SentenceTransformer(m)
        prefix = QUERY_PREFIX.get(m, "")
        qv = model.encode([prefix + q["query"] for q in queries], normalize_embeddings=True)
        for v in variants:
            texts = [CAREER_TEXT_VARIANTS[v](r) for _, r in df.iterrows()]
            dv = model.encode(texts, batch_size=64, normalize_embeddings=True)
            sims = qv @ dv.T
            per_q, dom_p, kw_p, strict_p, top1 = [], [], [], [], []
            for q, row in zip(queries, sims):
                top = np.argsort(-row)[:k]
                hits = []
                for i in top:
                    r = df.iloc[i]
                    d_ok = r["domain"] in q["domains"]
                    k_ok = _kw_hit(f"{r['career_name']} {r['required_skills']}", q["keywords"])
                    hits.append({"career_id": int(r["career_id"]), "career": r["career_name"], "domain": r["domain"],
                                 "score": round(float(row[i]), 3), "domain_ok": d_ok, "keyword_ok": k_ok})
                dom_p.append(sum(h["domain_ok"] for h in hits) / k)
                kw_p.append(sum(h["keyword_ok"] for h in hits) / k)
                strict_p.append(sum(h["domain_ok"] and h["keyword_ok"] for h in hits) / k)
                top1.append(hits[0]["score"])
                per_q.append({"id": q["id"], "query": q["query"], "domain_p5": dom_p[-1], "keyword_p5": kw_p[-1], "hits": hits})
            results.append({"model": m, "variant": v, "n_queries": len(queries), "corpus": len(df),
                            "domain_p5": round(float(np.mean(dom_p)), 3), "keyword_p5": round(float(np.mean(kw_p)), 3),
                            "strict_p5": round(float(np.mean(strict_p)), 3), "top1_score_mean": round(float(np.mean(top1)), 3),
                            "worst_queries": sorted(per_q, key=lambda x: x["domain_p5"] + x["keyword_p5"])[:4], "per_query": per_q})
            print(f"{m:45s} {v:7s} domainP@5={results[-1]['domain_p5']} keywordP@5={results[-1]['keyword_p5']} strictP@5={results[-1]['strict_p5']}")
    return results


def to_md(results, ts):
    L = [f"# Career retrieval benchmark ({ts})", "", f"Corpus: {results[0]['corpus']} careers, {results[0]['n_queries']} labelled queries, k=5.", "",
         "| Model | Text variant | Domain-P@5 | Keyword-P@5 | Strict-P@5 | Top-1 score |", "|---|---|---|---|---|---|"]
    for r in results:
        L.append(f"| {r['model']} | {r['variant']} | {r['domain_p5']} | {r['keyword_p5']} | {r['strict_p5']} | {r['top1_score_mean']} |")
    best = max(results, key=lambda r: r["strict_p5"])
    L += ["", f"## Error analysis - best config ({best['model']}, {best['variant']})"]
    for q in best["worst_queries"]:
        L.append(f"- **{q['query']}** (domain {q['domain_p5']}, keyword {q['keyword_p5']}): "
                 + "; ".join(f"{h['career']} [{h['domain']}]" for h in q["hits"]))
    L += ["", "## Sample results - best config"]
    for q in best["per_query"][:6]:
        L.append(f"- **{q['query']}** -> " + "; ".join(f"{h['career']} ({h['score']})" for h in q["hits"]))
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--models", nargs="+", default=["sentence-transformers/all-MiniLM-L6-v2", "BAAI/bge-small-en-v1.5"])
    p.add_argument("--variants", nargs="+", default=list(CAREER_TEXT_VARIANTS))
    a = p.parse_args()
    res = run(a.models, a.variants)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.REPORTS_DIR / f"career_retrieval_{ts}.json").write_text(json.dumps(res, indent=2))
    md = to_md(res, ts)
    (config.REPORTS_DIR / "career_retrieval_latest.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
