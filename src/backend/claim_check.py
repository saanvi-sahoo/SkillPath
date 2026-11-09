"""
Claim-level citation verification (E37, review 2 §5).

Word overlap is not factual support ("The Data Engineer role does NOT require Python [S1]" shares most words with a
record that requires Python). Each cited claim is checked in three steps:
  1. syntax + ID validity            deterministic: the label exists in the retrieved sources
  2. meaning                         NLI cross-encoder (premise = cited source, hypothesis = the claim):
                                     supported (entailment) / contradicted / insufficient evidence
  3. action                          contradicted -> must be removed or corrected; insufficient -> qualify or re-cite

Model: cross-encoder/nli-deberta-v3-xsmall (~70M parameters, CPU, ~20 ms per claim after loading). It is
evaluated separately (tests/test_claims.py and docs/evaluation.md §12) and falls back to the lexical check if it
can't load (e.g. no internet on first use), so answering never breaks.
"""
from __future__ import annotations

import os
import re
import threading
from typing import Dict, List, Optional

from src.backend.answer_check import _CIT, cited_ids, sentences, support

NLI_MODEL = os.getenv("NLI_MODEL", "cross-encoder/nli-deberta-v3-xsmall")
NLI_ENABLED = os.getenv("NLI_CHECK", "true").lower() == "true"
ENTAIL_MIN, CONTRA_MIN, VERBATIM_MIN = 0.5, 0.85, 0.6  # contradiction needs high confidence: the xsmall model is noisy on off-topic premises
_VERB = re.compile(r"\b(is|are|was|were|be|been|requires?|required|needs?|needed|includes?|lists?|listed|has|have|had|uses?|used|"
                   r"can|could|will|would|should|must|may|offers?|provides?|helps?|covers?|takes?|means|involves?|asks?|"
                   r"emphasi[sz]es?|focus(es)?|builds?|works?|pays?|earns?|grows?|matches|match|shows?|gives?|teaches|explains?)\b", re.I)
_model, _lock, _failed = None, threading.Lock(), False


def _nli():
    global _model, _failed
    if _model is None and not _failed and NLI_ENABLED:
        with _lock:
            if _model is None and not _failed:
                try:
                    from sentence_transformers import CrossEncoder
                    _model = CrossEncoder(NLI_MODEL, max_length=384)
                except Exception as e:  # noqa: BLE001
                    print(f"[claim_check] NLI model unavailable, lexical fallback: {e}")
                    _failed = True
    return _model


_ABSENCE = re.compile(r"\b(not|no|none|never|missing|lack\w*|without|only|\d+ (of|out of) \d+)\b", re.I)
_ADVICE = re.compile(r"^(?:[\w ]{0,40}:\s*)?(list|mirror|identify|add|use|include|focus|build|learn|practi[cs]e|start|create|tailor|"
                     r"highlight|apply|consider|try|take|join|update|write|prepare|aim|keep|avoid|make|spend|read|watch|complete|review)\b", re.I)


def _clean(sentence: str) -> str:
    s = _CIT.sub("", sentence)
    s = re.sub(r"[*_`#>|]+", " ", s)
    s = re.sub(r"^\s*(\d+[.)]|[-•])\s*", "", s)
    s = re.sub(r"^\s*[\w ,&/'-]{2,60}\([^)]{2,80}\)\s*:\s*", "", s)  # keyless labels: "Guidance (Topic) : ..."
    return re.sub(r"\s+", " ", s).strip(" :-")


def claims(text: str) -> List[Dict]:
    """Cited factual claims: every sentence (or bullet) that carries at least one [S#] label."""
    out = []
    for sent in sentences(text):
        ids = cited_ids(sent)
        c = _clean(sent)
        if ids and len(c.split()) >= 6 and _VERB.search(c):  # a statement that can be true or false, not a title/fragment
            out.append({"claim": c, "ids": ids, "advice": bool(_ADVICE.match(c))})
    return out


def verify(text: str, hits: List[Dict]) -> Dict:
    """Classify each (claim, cited source) pair: supported / contradicted / insufficient / invalid_id."""
    cl = claims(text)
    n = len(hits or [])
    pairs, rows = [], []
    for c in [x for x in cl if not x["advice"]]:  # cited advice is a suggestion, not a checkable fact
        for i in c["ids"]:
            if i < 1 or i > n:
                rows.append({"claim": c["claim"], "id": i, "label": "invalid_id"})
            else:
                rows.append({"claim": c["claim"], "id": i, "label": None})
                pairs.append((hits[i - 1].get("text", "")[:1500], c["claim"]))
    model = _nli() if pairs else None
    if pairs:
        if model is not None:
            probs = model.predict(pairs, apply_softmax=True, batch_size=16)
            j = 0
            for r in rows:
                if r["label"] is None:
                    p = probs[j]
                    j += 1
                    r["p"] = {"contradiction": round(float(p[0]), 3), "entailment": round(float(p[1]), 3), "neutral": round(float(p[2]), 3)}
                    lex = support(r["claim"], hits[r["id"] - 1].get("text", ""))
                    r["lexical"] = round(lex, 3)
                    src = hits[r["id"] - 1].get("source")
                    absence_or_count = bool(_ABSENCE.search(r["claim"]))
                    contra_min = 0.97 if src == "profile" else CONTRA_MIN  # profile facts are checked deterministically (fact_issues)
                    if p[0] >= contra_min and not (src == "profile" and absence_or_count):
                        r["label"] = "contradicted"
                    elif p[1] >= ENTAIL_MIN or (lex >= VERBATIM_MIN and p[0] < 0.5):  # entailed, or a near-verbatim restatement
                        r["label"] = "supported"
                    else:
                        r["label"] = "insufficient"
        else:  # lexical fallback
            j = 0
            for r in rows:
                if r["label"] is None:
                    s = support(pairs[j][1], pairs[j][0])
                    j += 1
                    r["label"], r["lexical"] = ("supported" if s >= 0.15 else "insufficient"), round(s, 3)
    counts = {k: sum(r["label"] == k for r in rows) for k in ("supported", "contradicted", "insufficient", "invalid_id")}
    total = len(rows)
    return {"claims": rows, "counts": counts, "n": total, "method": "nli" if model is not None else "lexical",
            "cited_advice": sum(x["advice"] for x in cl),
            "support_rate": round(counts["supported"] / total, 3) if total else None,
            "contradiction_rate": round(counts["contradicted"] / total, 3) if total else None}


def claim_issues(text: str, hits: List[Dict], max_items: int = 3) -> List[str]:
    """Revision instructions for prompt v8's self-check (contradictions first)."""
    rep = verify(text, hits)
    out = []
    for r in [x for x in rep["claims"] if x["label"] == "contradicted"][:max_items]:
        out.append(f"\"{r['claim'][:150]}\" CONTRADICTS [S{r['id']}]. Correct the claim to match the source, or remove it.")
    for r in [x for x in rep["claims"] if x["label"] == "invalid_id"][:max_items]:
        out.append(f"[S{r['id']}] does not exist. Use only the listed source labels.")
    weak = [x for x in rep["claims"] if x["label"] == "insufficient" and x.get("p", {}).get("neutral", 0) > 0.9]
    for r in weak[: max(0, max_items - len(out))]:
        if support(r["claim"], (hits[r["id"] - 1].get("text", "") if 0 < r["id"] <= len(hits) else "")) < 0.15:
            out.append(f"[S{r['id']}] does not support \"{r['claim'][:150]}\". Cite the source that does, or present it as general advice without a citation.")
    return out
