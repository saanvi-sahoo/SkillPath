"""
Retrieval precision upgrades (E35, docs/rag.md §8): BM25 keyword search, reciprocal-rank fusion (RRF) with the
vector results, and an optional cross-encoder re-ranker.

Why: MiniLM vectors capture meaning but blur exact terms ("PL-300", "GATE", "SOP", "LinkedIn"). BM25 catches
exact terms; RRF merges both rankings without needing comparable scores; a cross-encoder reads question and
passage together and re-orders the top candidates. The cosine `score` field is kept on every hit, so the
existing safety thresholds (MIN_SCORE, MATCH STRENGTH) behave exactly as before.
"""
from __future__ import annotations

import math
import re
import threading
from collections import Counter, defaultdict
from typing import Dict, List, Optional

import numpy as np

_TOKEN = re.compile(r"[a-z0-9][a-z0-9+#.\-]*")
_STOP = set("""a an the and or of to in on for with at by from as is are was were be been it this that these those
i me my you your we our they their he she his her its what which who how why when where do does did can could should
would will shall may might about into over under than then so if not no yes any some all more most very just also
""".split())


def tokens(text: str) -> List[str]:
    return [t.strip(".-") for t in _TOKEN.findall((text or "").lower()) if t.strip(".-") not in _STOP and len(t) > 1]


class BM25:
    def __init__(self, docs: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b, self.n = k1, b, len(docs)
        self.len = np.array([len(d) for d in docs], dtype=np.float32)
        self.avg = float(self.len.mean()) if self.n else 0.0
        post: Dict[str, Dict[int, int]] = defaultdict(dict)
        for i, d in enumerate(docs):
            for t, c in Counter(d).items():
                post[t][i] = c
        self.post = {t: (np.fromiter(p.keys(), dtype=np.int32), np.fromiter(p.values(), dtype=np.float32)) for t, p in post.items()}
        self.idf = {t: math.log(1 + (self.n - len(p[0]) + 0.5) / (len(p[0]) + 0.5)) for t, p in self.post.items()}

    def scores(self, q: List[str]) -> np.ndarray:
        s = np.zeros(self.n, dtype=np.float32)
        for t in set(q):
            if t not in self.post:
                continue
            idx, tf = self.post[t]
            denom = tf + self.k1 * (1 - self.b + self.b * self.len[idx] / max(self.avg, 1e-6))
            s[idx] += self.idf[t] * tf * (self.k1 + 1) / denom
        return s


_lock = threading.Lock()
_indexes: Dict[tuple, tuple] = {}


def _index(source: str):
    """BM25 index over the shared (user_id='global') chunks of a source, built from the local vector copy."""
    from src.rag.vector_store import get_vector_store

    store = get_vector_store(source, backend="local")
    docs = [(i, d) for i, d in enumerate(store.docs) if d["source"] == source and d.get("user_id") == "global"]
    key = (source, len(docs))
    with _lock:
        if key not in _indexes:
            _indexes.clear() if len(_indexes) > 8 else None
            _indexes[key] = (BM25([tokens(d["text"]) for _, d in docs]), docs, store)
    return _indexes[key]


def bm25_search(source: str, query: str, qv: np.ndarray, k: int = 20) -> List[Dict]:
    bm, docs, store = _index(source)
    if not docs:
        return []
    sc = bm.scores(tokens(query))
    top = np.argsort(-sc)[:k]
    out = []
    for j in top:
        if sc[j] <= 0:
            break
        i, d = docs[j]
        out.append({**d, "score": float(store.vectors[i] @ qv), "bm25": float(sc[j])})  # keep cosine for thresholds
    return out


def rrf(rankings: List[List[Dict]], k: int = 60) -> List[Dict]:
    """Reciprocal-rank fusion: score(doc) = sum over rankings of 1 / (k + rank)."""
    fused: Dict[str, float] = defaultdict(float)
    first: Dict[str, Dict] = {}
    for ranking in rankings:
        for rank, h in enumerate(ranking, 1):
            hid = h.get("id")
            fused[hid] += 1.0 / (k + rank)
            first.setdefault(hid, h)
    return [{**first[i], "rrf": round(s, 5)} for i, s in sorted(fused.items(), key=lambda x: -x[1])]


_ce = None


def rerank(query: str, hits: List[Dict], top: int) -> List[Dict]:
    """Cross-encoder (query, passage) relevance; re-orders hits, keeps their cosine `score`."""
    global _ce
    if not hits:
        return hits
    if _ce is None:
        with _lock:
            if _ce is None:
                from sentence_transformers import CrossEncoder
                from src.utilities.hf_models import load_cached
                _ce = load_cached(CrossEncoder, "cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=320)
    ce = _ce.predict([(query, h["text"]) for h in hits], batch_size=32)
    order = np.argsort(-np.asarray(ce))[:top]
    return [{**hits[i], "rerank": round(float(ce[i]), 3)} for i in order]


def expand_query(question: str, qtype: str, memory: Optional[Dict]) -> str:
    """Profile-aware query expansion: add the user's target role / gaps / skills where the question depends on them."""
    if not memory:
        return question
    role = memory.get("target_role") or ""
    gaps = ", ".join(str(g).split(":")[-1].strip() for g in (memory.get("skill_gaps") or [])[:5])
    have = ", ".join(str(s).split(":")[-1].strip() for s in (memory.get("candidate_skills") or [])[:6])
    extra = {
        "fit_analysis": f"{role} requirements {gaps}",
        "plan": f"learning plan for {gaps} {role}",
        "profile_fact": f"{role} {gaps}",
        "recommendation": f"careers using {have}",
        "list": f"{role}",
    }.get(qtype, "")
    return f"{question} {extra}".strip()
