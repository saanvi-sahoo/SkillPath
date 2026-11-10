"""
Career retrieval through the PRODUCTION path (retriever.retrieve, careers quota 5), E37 vs E38 (review 3 §4). No LLM.

  E37 = E37 expansion + cross-encoder + skill re-ranker (the live configuration before this change)
  E38 = + structured query rewrite (background/target/role), 2x candidate pool for transitions & interests, exact-title bonus

Development sets (already seen, used to check the change): tuning_24, heldout_30, heldout_v2_20.
Fresh frozen set (measured once, after the change was fixed): heldout_careers_v3 (40 queries, 10 per type,
sha256 0730e3e0..., committed in 167fe13 before any E38 code).

  python -m src.eval.career_eval_v3 --sets dev        # development
  python -m src.eval.career_eval_v3 --sets v3         # final measurement
Writes reports/heldout/career_eval_v3_<sets>.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from src.eval.career_audit import HERE, OUT, _ok, qtype

DEV = {"tuning_24": HERE / "career_queries.jsonl", "heldout_30": HERE / "heldout" / "heldout_careers.jsonl",
       "heldout_v2_20": HERE / "heldout" / "heldout_careers_v2.jsonl"}
V3 = {"heldout_v3_40": HERE / "heldout" / "heldout_careers_v3.jsonl"}


def top5(query: str, e38: bool):
    from src.backend.features import set_e38
    from src.rag.retriever import retrieve
    tok = set_e38(e38)
    try:
        return retrieve(query, quotas={"careers": 5}, user_id=None, min_score=-1.0)
    finally:
        from src.backend.features import _E38
        _E38.reset(tok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", choices=["dev", "v3"], default="dev")
    a = ap.parse_args()
    sets = DEV if a.sets == "dev" else V3
    res = {}
    for name, path in sets.items():
        qs = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
        per = {"E37": [], "E38": []}
        by_t = defaultdict(lambda: {"E37": [], "E38": []})
        rows = []
        for q in qs:
            t = qtype(q)
            row = {"id": q["id"], "query": q["query"], "type": t}
            for arm in ("E37", "E38"):
                hits = top5(q["query"], arm == "E38")
                p = sum(_ok(h, q) for h in hits[:5]) / 5
                per[arm].append(p)
                by_t[t][arm].append(p)
                row[arm] = {"p@5": p, "top5": [f"{'✓' if _ok(h, q) else '✗'} {(h.get('metadata') or {}).get('career_name')} "
                                                f"({(h.get('metadata') or {}).get('domain')})" for h in hits[:5]]}
            rows.append(row)
            print(f"{name:14s} {t:10s} E37={row['E37']['p@5']:.1f} E38={row['E38']['p@5']:.1f}  {q['query'][:60]}")
        mean = lambda x: round(sum(x) / len(x), 3) if x else None  # noqa: E731
        res[name] = {"n": len(qs), "p@5": {k: mean(v) for k, v in per.items()},
                     "by_type": {t: {"n": len(v["E37"]), **{k: mean(x) for k, x in v.items()}} for t, v in sorted(by_t.items())}, "rows": rows}
        print(name, res[name]["p@5"], {t: (v["E37"], v["E38"]) for t, v in res[name]["by_type"].items()})
    out = OUT / f"career_eval_v3_{a.sets}.json"
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print("->", out)


if __name__ == "__main__":
    main()
