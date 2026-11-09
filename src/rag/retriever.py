"""
Retriever: query -> relevant chunks -> formatted, citable context.

Strategy (see docs/rag.md#retrieval-strategy):
  1. Embed the query once.
  2. Search each source separately with its own quota. The careers corpus has
     ~2.9k chunks and would otherwise crowd out the user's own profile (~50).
  3. Drop hits under MIN_SCORE, merge, sort by score.
  4. Format as numbered [S1], [S2] ... blocks the LLM is told to cite.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

from src.rag import config
from src.rag.embedder import embed_query
from src.rag.vector_store import get_vector_store, resolve_backend

# per-source quotas for a single question; tuned in docs/experiment_log.md
DEFAULT_QUOTAS: Dict[str, int] = {"profile": 3, "knowledge": 2, "careers": 4, "jobs": 1}  # E13: careers 2->4 (source of truth)


_corpus_checked = False
_corpus_lock = threading.Lock()


# E32: circuit breaker. If Atlas is unreachable (e.g. this machine's IP is not in the Atlas access list ->
# "SSL handshake failed / TLSV1_ALERT_INTERNAL_ERROR"), use the local copy of the same vectors for 5 minutes
# instead of waiting for a timeout on every search.
_atlas_down_until = 0.0
BREAKER_S = 300


def atlas_degraded() -> bool:
    return time.time() < _atlas_down_until


def _search(source: str, qv, k: int, user_id) -> List[Dict]:
    global _atlas_down_until
    backend = resolve_backend()
    if backend == "mongo" and not atlas_degraded():
        try:
            return get_vector_store(source).search(qv, k=k, sources=[source], user_id=user_id)
        except Exception as e:  # noqa: BLE001
            _atlas_down_until = time.time() + BREAKER_S
            print(f"[retriever] Atlas unavailable ({str(e)[:120]}) -> local vector store for {BREAKER_S}s")
    try:
        if backend == "mongo":
            _ensure_local_fallback()
        return get_vector_store(source, backend="local").search(qv, k=k, sources=[source], user_id=user_id)
    except Exception as e:  # noqa: BLE001 - one bad source must not kill retrieval
        print(f"[retriever] search failed for {source}: {e}")
        return []


def _ensure_local_fallback() -> None:
    """Build the shared local corpora once if Atlas is down and no local copy exists yet."""
    if not get_vector_store("careers", backend="local").count().get("careers"):
        from src.rag.ingest import ingest
        ingest(["careers", "knowledge", "jobs"], backend="local", show_progress=False)


def ensure_local_corpus() -> None:
    """Local backend only: build the shared corpora once if the store is empty (fresh cloud container,
    e.g. Streamlit Community Cloud without MONGODB_URI). No-op on Atlas or when already built."""
    global _corpus_checked
    if _corpus_checked:
        return
    with _corpus_lock:
        if _corpus_checked:
            return
        _corpus_checked = True
        if resolve_backend() != "local":
            return
        missing = [s for s in ("careers", "knowledge", "jobs") if not get_vector_store(s).count().get(s)]
        if missing:
            from src.rag.ingest import ingest
            print(f"[retriever] local store empty for {missing} -> building it now (one-time, ~20 s)")
            ingest(missing, backend="local", show_progress=False)


def retrieve(query: str, quotas: Optional[Dict[str, int]] = None, user_id: str = config.DEFAULT_USER_ID,
             min_score: float = config.MIN_SCORE, user_skills: Optional[List[str]] = None) -> List[Dict]:
    ensure_local_corpus()
    quotas = quotas or DEFAULT_QUOTAS
    qv = embed_query(query)
    hits: List[Dict] = []
    for source, k in quotas.items():
        if k <= 0:
            continue
        if config.RAG_RERANK and source in config.RERANK_SOURCES:
            src_query, src_qv = query, qv
            if source == "careers" and config.RAG_SKILL_RERANK:
                from src.rag.skill_rerank import expand_career_query
                src_query = expand_career_query(query)  # E37: interests / career change -> career-area words
                if src_query != query:
                    src_qv = embed_query(src_query)
            pool = _search(source, src_qv, max(config.RERANK_POOL, k), user_id)
            try:
                from src.rag.hybrid import rerank
                if source == "careers" and config.RAG_SKILL_RERANK:
                    # E36: cross-encoder over the whole pool, then career-intent + exact/related skill evidence
                    from src.rag.skill_rerank import skill_rerank
                    ranked = skill_rerank(src_query, rerank(src_query, pool, top=len(pool)), top=k, user_skills=user_skills)
                else:
                    ranked = rerank(query, pool, top=k)
                hits.extend(h for h in ranked if h.get("rerank", 0) >= config.RERANK_MIN)
            except Exception as e:  # noqa: BLE001 - re-ranker unavailable -> plain vector order
                print(f"[retriever] rerank skipped: {e}")
                hits.extend(pool[:k])
        else:
            hits.extend(_search(source, qv, k, user_id))
    hits = [h for h in hits if h.get("score", 0) >= min_score]
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits


def format_context(hits: List[Dict]) -> str:
    if not hits:
        return "(no relevant documents found in the knowledge base)"
    blocks = []
    for i, h in enumerate(hits, 1):
        meta = h.get("metadata") or {}
        ref = meta.get("career_id") or meta.get("url") or meta.get("file") or h.get("doc_type")
        text = h["text"]
        if h["source"] == "careers":
            text += f" Education: {meta.get('education_required')}."
            if not meta.get("salary_is_placeholder", True):
                text += f" Dataset average salary: {meta.get('average_salary'):,.0f} (unverified; {meta.get('quality_note')})."
        blocks.append(f"[S{i}] (source={h['source']}/{h['doc_type']}, score={h['score']:.2f}, ref={ref})\n{text}")
    return "\n\n".join(blocks)


def retrieve_context(query: str, **kw) -> Dict:
    t0 = time.perf_counter()
    hits = retrieve(query, **kw)
    return {"hits": hits, "context": format_context(hits), "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


def retrieve_careers(query: str, top_k: int = 5, domain: Optional[str] = None, min_score: float = None) -> List[Dict]:
    """Stable career-retrieval adapter (project doc section 12, phase C).

    Returns [{career_id, career_name, domain, required_skills, education_required, score,
              salary (or None if placeholder), weak_match}] from the shared career knowledge base.
    `weak_match` flags results under the calibrated floor so callers can ask clarifying
    questions instead of presenting them as recommendations (doc section 9.2 step 26).
    """
    if not config.CAREER_RAG_ENABLED:
        return []
    ensure_local_corpus()
    floor = config.CAREER_MIN_SCORE if min_score is None else min_score
    hits = _search("careers", embed_query(query), top_k * (3 if domain else 1), None)
    out = []
    for h in hits:
        m = h.get("metadata") or {}
        if domain and m.get("domain") != domain:
            continue
        out.append({
            "career_id": m.get("career_id", h.get("id")), "career_name": m.get("career_name"),
            "domain": m.get("domain"), "required_skills": m.get("required_skills"),
            "education_required": m.get("education_required"), "score": round(float(h["score"]), 3),
            "salary": None if m.get("salary_is_placeholder", True) else m.get("average_salary"),
            "weak_match": float(h["score"]) < floor,
        })
    return out[:top_k]
