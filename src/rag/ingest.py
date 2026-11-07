"""
Ingestion CLI: build chunks -> embed -> upsert into the vector store.

Usage (from project root):
    python -m src.rag.ingest --sources all
    python -m src.rag.ingest --sources careers jobs --backend mongo
    python -m src.rag.ingest --sources profile          # after a new pipeline run
    python -m src.rag.ingest --sources careers --limit 200   # quick experiment

Every run appends one JSON line to reports/embeddings/ingestion_log.jsonl
(counts, timings, model, backend) so runs can be compared later.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.rag import config
from src.rag.documents import BUILDERS, build_career_chunks, build_profile_chunks
from src.rag.embedder import embed_texts
import numpy as np

from src.rag.vector_store import get_vector_store, resolve_backend


def _log_run(entry: Dict) -> None:
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.REPORTS_DIR / "ingestion_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def ingest(sources: List[str], backend: Optional[str] = None, limit: Optional[int] = None,
           replace: bool = True, show_progress: bool = True, user_id: Optional[str] = None) -> Dict:
    uid = user_id or config.DEFAULT_USER_ID
    summary = {"started_at": datetime.now(timezone.utc).isoformat(), "backend": resolve_backend(backend),
               "model": config.EMBEDDING_MODEL, "dim": config.EMBEDDING_DIM,
               "chunk_max_words": config.CHUNK_MAX_WORDS, "chunk_overlap": config.CHUNK_OVERLAP_WORDS,
               "sources": {}}
    touched = []
    for source in sources:
        store = get_vector_store(source, backend)
        store.ensure_index(wait=False)
        touched.append((source, store))
        t0 = time.perf_counter()
        if source == "careers" and limit:
            chunks = build_career_chunks(limit=limit)
        elif source == "profile":
            chunks = build_profile_chunks(config.memory_path(uid), user_id=uid)
        else:
            chunks = BUILDERS[source]()
        n_raw = len(chunks)
        chunks = list({c.id: c for c in chunks}.values())  # dedupe identical natural keys (keep last)
        t_build = time.perf_counter() - t0
        if not chunks:
            print(f"[ingest] {source}: no chunks (source file missing or empty)")
            summary["sources"][source] = {"chunks": 0}
            continue
        t1 = time.perf_counter()
        vecs = embed_texts([c.text for c in chunks], show_progress=show_progress)
        t_embed = time.perf_counter() - t1
        t2 = time.perf_counter()
        # profile data is per-run state: wipe the user's old chunks so stale gaps/jobs disappear
        deleted = store.delete(source, user_id=uid) if (replace and source == "profile") else 0
        written = store.upsert(chunks, vecs)
        # full-refresh semantics: records no longer produced by the builder are removed
        # (skipped for --limit runs, which are partial by design)
        pruned = 0 if limit else store.prune(source, [c.id for c in chunks],
                                             user_id=uid if source == "profile" else None)
        t_write = time.perf_counter() - t2
        words = [len(c.text.split()) for c in chunks]
        vec_ok = bool(np.isfinite(vecs).all()) and vecs.shape == (len(chunks), config.EMBEDDING_DIM)
        stats = {"collection": config.COLLECTIONS[source][0], "shape": list(vecs.shape), "finite_and_aligned": vec_ok,
                 "chunks": len(chunks), "duplicates_dropped": n_raw - len(chunks), "deleted_before": deleted, "written": written, "pruned_stale": pruned,
                 "avg_words": round(sum(words) / len(words), 1), "max_words": max(words),
                 "build_s": round(t_build, 2), "embed_s": round(t_embed, 2), "write_s": round(t_write, 2),
                 "chunks_per_s": round(len(chunks) / max(t_embed, 1e-6), 1)}
        summary["sources"][source] = stats
        print(f"[ingest] {source}: {stats}")
    for source, store in touched:
        if store.name == "mongo":
            store.ensure_index(wait=True)
    summary["totals_in_store"] = {src: get_vector_store(src, backend).count().get(src, 0) for src in BUILDERS}
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    _log_run(summary)
    return summary


def ingest_profile_safely(user_id: Optional[str] = None) -> Optional[Dict]:
    """Called after each pipeline run. Never raises (chat must not break the pipeline)."""
    uid = user_id or config.DEFAULT_USER_ID
    try:
        if not build_profile_chunks(config.memory_path(uid), user_id=uid):
            return None
        return ingest(["profile"], show_progress=False, user_id=uid)
    except Exception as e:  # noqa: BLE001
        print(f"[ingest] profile re-index failed: {e}")
        return None


def main():
    p = argparse.ArgumentParser(description="Embed SkillPath AI data into the vector store (MongoDB Atlas or local).")
    p.add_argument("--sources", nargs="+", default=["all"], help=f"any of {list(BUILDERS)} or 'all'")
    p.add_argument("--backend", choices=["auto", "mongo", "local"], default=None)
    p.add_argument("--limit", type=int, default=None, help="limit careers rows (experiments)")
    args = p.parse_args()
    sources = list(BUILDERS) if "all" in args.sources else args.sources
    print(json.dumps(ingest(sources, backend=args.backend, limit=args.limit), indent=2, default=str))


if __name__ == "__main__":
    main()
