"""
Citation-checker audit (E38, review 3 §6: "manually review a representative sample of claims labelled supported,
unsupported, contradicted, and claims with no citations; distinguish genuine hallucinations from evaluator mistakes").

  python -m src.eval.claim_audit export reports/heldout/heldout_eval_heldout_v2_final_v7_v8.json   # -> claim_audit_<stem>.csv
  python -m src.eval.claim_audit score  reports/heldout/claim_audit_<stem>.csv                       # -> evaluator precision table

Sample (fixed seed): up to 20 'supported', 20 'insufficient', every 'contradicted' (max 15), 15 uncited factual sentences.
Each row shows the claim and the text of the source it cites. The reviewer fills `review`:
  supported      the cited source states it (or it is a faithful paraphrase)
  true_uncited   true / well-established, but the cited source doesn't say it (citation problem, not a hallucination)
  false          wrong or unsupported invention (hallucination)
  unclear        can't decide from the evidence, or not a checkable claim (heading / sentence fragment)
  evaluator_artifact  the checker's label is caused by the evaluation itself (e.g. sources cut off when saved)
"""
from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

LABELS = ("supported", "true_uncited", "false", "unclear", "evaluator_artifact")


def export(path: Path) -> Path:
    from src.backend.claim_check import claims, verify
    from src.eval.heldout_eval import _hits_from_context
    rep = json.loads(path.read_text())
    pools = defaultdict(list)
    for r in rep["rows"]:
        if r["category"] == "out_of_scope" or not r.get("context"):
            continue
        hits = _hits_from_context(r["context"])
        v = verify(r["answer"], hits)
        for c in v["claims"]:
            src = hits[c["id"] - 1]["text"] if 0 < c["id"] <= len(hits) else ""
            pools[c["label"]].append({"version": r["version"], "case": r["id"], "claim": c["claim"], "nli_label": c["label"],
                                      "cited": f"S{c['id']}", "p_entail": (c.get("p") or {}).get("entailment"),
                                      "p_contra": (c.get("p") or {}).get("contradiction"), "source_excerpt": src[:700]})
        from src.backend.answer_check import cited_ids, sentences
        from src.backend.claim_check import _ADVICE, _VERB, _clean
        for sent in sentences(r["answer"].split("\n\n---\n**Sources**")[0]):
            c = _clean(sent)
            if not cited_ids(sent) and len(c.split()) >= 6 and _VERB.search(c) and not _ADVICE.match(c) and "?" not in c:
                pools["uncited"].append({"version": r["version"], "case": r["id"], "claim": c, "nli_label": "uncited",
                                         "cited": "", "p_entail": None, "p_contra": None, "source_excerpt": ""})
    rnd = random.Random(38)
    sample = []
    for lab, k in (("supported", 20), ("insufficient", 20), ("contradicted", 15), ("invalid_id", 10), ("uncited", 15)):
        xs = pools.get(lab, [])
        sample += rnd.sample(xs, min(k, len(xs)))
    out = path.with_name("claim_audit_" + path.stem.replace("heldout_eval_", "") + ".csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["audit_id", "version", "case", "nli_label", "claim", "cited", "source_excerpt",
                                           "p_entail", "p_contra", "review", "review_note", "reviewer"])
        w.writeheader()
        for i, s in enumerate(sample, 1):
            w.writerow({"audit_id": f"c{i:03d}", **s, "review": "", "review_note": "", "reviewer": ""})
    totals = {k: len(v) for k, v in pools.items()}
    print(f"population {totals}; sampled {len(sample)} -> {out}")
    return out


def score(csv_path: Path) -> dict:
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    by = defaultdict(Counter)
    for r in rows:
        if r["review"] in LABELS:
            by[r["nli_label"]][r["review"]] += 1
    res = {lab: {"n": sum(c.values()), **{k: c[k] for k in LABELS}} for lab, c in by.items()}
    print("| Checker label | n reviewed | " + " | ".join(LABELS) + " |")
    print("|---|---|" + "---|" * len(LABELS))
    for lab, d in res.items():
        print(f"| {lab} | {d['n']} | " + " | ".join(str(d[k]) for k in LABELS) + " |")
    return res


if __name__ == "__main__":
    cmd, p = sys.argv[1], Path(sys.argv[2])
    export(p) if cmd == "export" else score(p)
