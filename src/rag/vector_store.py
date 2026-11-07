"""
Vector store backends with one shared interface.

    MongoAtlasVectorStore  - production: MongoDB Atlas + Atlas Vector Search ($vectorSearch)
    LocalVectorStore       - offline fallback: numpy matrix + JSON metadata, exact cosine search

Both store the SAME document shape (see docs/embeddings.md#document-schema):

    {
      "_id": "<sha1 chunk id>",
      "text": "...", "source": "careers|jobs|profile|knowledge",
      "doc_type": "...", "user_id": "global|<user>",
      "metadata": {...},
      "embedding": [384 floats],
      "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
      "ingested_at": ISODate
    }
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import numpy as np

from src.rag import config
from src.rag.documents import Chunk


def _vector_index_definition() -> Dict:
    """Atlas Vector Search index. Filter fields must be declared to be usable in $vectorSearch.filter."""
    return {
        "fields": [
            {"type": "vector", "path": "embedding", "numDimensions": config.EMBEDDING_DIM, "similarity": "cosine"},
            {"type": "filter", "path": "source"},
            {"type": "filter", "path": "user_id"},
            {"type": "filter", "path": "doc_type"},
            {"type": "filter", "path": "domain"},
        ]
    }


def _build_filter(sources: Optional[Sequence[str]], user_id: Optional[str]) -> Dict:
    f: Dict = {}
    if sources:
        f["source"] = {"$in": list(sources)}
    # a user sees shared ("global") chunks plus their own private chunks
    f["user_id"] = {"$in": ["global", user_id]} if user_id else {"$in": ["global"]}
    return f


class BaseVectorStore:
    name = "base"

    def upsert(self, chunks: List[Chunk], vectors: np.ndarray) -> int: ...
    def delete(self, source: str, user_id: Optional[str] = None) -> int: ...
    def search(self, query_vec: np.ndarray, k: int, sources=None, user_id=None) -> List[Dict]: ...
    def count(self) -> Dict[str, int]: ...
    def prune(self, source: str, keep_ids, user_id: Optional[str] = None) -> int: ...


# ── MongoDB Atlas ────────────────────────────────────────────────────────────
class MongoAtlasVectorStore(BaseVectorStore):
    name = "mongo"

    def __init__(self, collection: str, index_name: str, db: str = None):
        self.client = _mongo_client()
        self.coll = self.client[db or config.MONGODB_DB][collection]
        self.index_name = index_name

    # index lifecycle
    def ensure_index(self, wait: bool = True, timeout_s: int = 180) -> None:
        from pymongo.operations import SearchIndexModel

        existing = {ix["name"]: ix for ix in self.coll.list_search_indexes()}
        if self.index_name not in existing:
            # collection must exist before a search index can be created on it
            if self.coll.name not in self.coll.database.list_collection_names():
                self.coll.database.create_collection(self.coll.name)
            self.coll.create_search_index(
                SearchIndexModel(definition=_vector_index_definition(), name=self.index_name, type="vectorSearch")
            )
            print(f"[mongo] created vector index '{self.index_name}'")
        if not wait:
            return
        start = time.time()
        while time.time() - start < timeout_s:
            ix = next((i for i in self.coll.list_search_indexes(self.index_name)), None)
            if ix and ix.get("queryable"):
                return
            time.sleep(3)
        print(f"[mongo] index '{self.index_name}' not queryable after {timeout_s}s; searches may return 0 hits until it is.")

    def upsert(self, chunks: List[Chunk], vectors: np.ndarray) -> int:
        from pymongo import ReplaceOne

        now = datetime.now(timezone.utc)
        ops = []
        for c, v in zip(chunks, vectors):
            doc = c.to_dict()
            doc["_id"] = doc.pop("id")
            doc["embedding"] = v.astype(float).tolist()
            doc["embedding_model"] = config.EMBEDDING_MODEL
            doc["embedding_text"] = doc["text"]
            if c.source == "careers":
                # project-doc schema (section 8.2): career fields at top level, queryable without $unwind
                doc.update({k: v for k, v in c.metadata.items() if k not in doc})
            doc["ingested_at"] = now
            ops.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert=True))
        written = 0
        for i in range(0, len(ops), 500):
            res = self.coll.bulk_write(ops[i : i + 500], ordered=False)
            written += res.upserted_count + res.modified_count + res.matched_count
        return written

    def delete(self, source: str, user_id: Optional[str] = None) -> int:
        q = {"source": source}
        if user_id:
            q["user_id"] = user_id
        return self.coll.delete_many(q).deleted_count

    def _check_model(self):
        """Refuse to query vectors written by a different model (e.g. a teammate's script)."""
        if getattr(self, "_model_ok", False):
            return
        sample = self.coll.find_one({}, {"embedding_model": 1})
        if sample and sample.get("embedding_model") != config.EMBEDDING_MODEL:
            raise RuntimeError(f"{self.coll.name} holds vectors from {sample.get('embedding_model')} but "
                               f"EMBEDDING_MODEL={config.EMBEDDING_MODEL}; re-ingest or change the model.")
        self._model_ok = True

    def prune(self, source: str, keep_ids, user_id: Optional[str] = None) -> int:
        q = {"source": source, "_id": {"$nin": list(keep_ids)}}
        if user_id:
            q["user_id"] = user_id
        return self.coll.delete_many(q).deleted_count

    def search(self, query_vec, k, sources=None, user_id=None) -> List[Dict]:
        self._check_model()
        pipeline = [
            {
                "$vectorSearch": {
                    "index": self.index_name,
                    "path": "embedding",
                    "queryVector": query_vec.astype(float).tolist(),
                    "numCandidates": k * config.NUM_CANDIDATES_MULTIPLIER,
                    "limit": k,
                    "filter": _build_filter(sources, user_id),
                }
            },
            {"$project": {"embedding": 0, "score": {"$meta": "vectorSearchScore"}}},
        ]
        hits = list(self.coll.aggregate(pipeline))
        for h in hits:
            h["id"] = h.pop("_id")
            # Atlas cosine score is (1 + cos) / 2 in [0, 1]; convert back to raw cosine for consistency
            h["score"] = 2 * h["score"] - 1
        return hits

    def count(self) -> Dict[str, int]:
        return {r["_id"]: r["n"] for r in self.coll.aggregate([{"$group": {"_id": "$source", "n": {"$sum": 1}}}])}


# ── Local numpy fallback ─────────────────────────────────────────────────────
class LocalVectorStore(BaseVectorStore):
    name = "local"

    def __init__(self, directory):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self.vec_path = self.dir / "embeddings.npy"
        self.meta_path = self.dir / "chunks.json"
        self._load()

    def _load(self):
        if self.vec_path.exists() and self.meta_path.exists():
            self.vectors = np.load(self.vec_path)
            self.docs: List[Dict] = json.loads(self.meta_path.read_text(encoding="utf-8"))
            models = {d.get("embedding_model") for d in self.docs}
            if self.docs and models != {config.EMBEDDING_MODEL}:
                raise RuntimeError(
                    f"Local store holds vectors from {models} but EMBEDDING_MODEL={config.EMBEDDING_MODEL}. "
                    f"Vectors from different models are not comparable: delete {self.dir} and re-run ingestion."
                )
        else:
            self.vectors = np.zeros((0, config.EMBEDDING_DIM), dtype=np.float32)
            self.docs = []

    def _save(self):
        np.save(self.vec_path, self.vectors)
        self.meta_path.write_text(json.dumps(self.docs, ensure_ascii=False), encoding="utf-8")

    def ensure_index(self, **_):
        return None

    def upsert(self, chunks, vectors) -> int:
        uniq = {c.id: (c, v) for c, v in zip(chunks, vectors)}
        chunks, vectors = [x[0] for x in uniq.values()], [x[1] for x in uniq.values()]
        pos = {d["id"]: i for i, d in enumerate(self.docs)}
        now = datetime.now(timezone.utc).isoformat()
        new_docs, new_vecs = [], []
        for c, v in zip(chunks, vectors):
            d = {**c.to_dict(), "embedding_model": config.EMBEDDING_MODEL, "ingested_at": now}
            if c.id in pos:
                self.docs[pos[c.id]] = d
                self.vectors[pos[c.id]] = v
            else:
                pos[c.id] = len(self.docs) + len(new_docs)
                new_docs.append(d)
                new_vecs.append(v)
        if new_docs:
            self.docs.extend(new_docs)
            self.vectors = np.vstack([self.vectors, np.asarray(new_vecs, dtype=np.float32)])
        self._save()
        return len(chunks)

    def delete(self, source, user_id=None) -> int:
        keep = [i for i, d in enumerate(self.docs) if not (d["source"] == source and (user_id is None or d["user_id"] == user_id))]
        removed = len(self.docs) - len(keep)
        self.docs = [self.docs[i] for i in keep]
        self.vectors = self.vectors[keep] if keep else np.zeros((0, config.EMBEDDING_DIM), dtype=np.float32)
        self._save()
        return removed

    def prune(self, source, keep_ids, user_id=None) -> int:
        keep_ids = set(keep_ids)
        idx = [i for i, d in enumerate(self.docs)
               if not (d["source"] == source and d["id"] not in keep_ids and (user_id is None or d["user_id"] == user_id))]
        removed = len(self.docs) - len(idx)
        if removed:
            self.docs = [self.docs[i] for i in idx]
            self.vectors = self.vectors[idx]
            self._save()
        return removed

    def search(self, query_vec, k, sources=None, user_id=None) -> List[Dict]:
        if not self.docs:
            return []
        allowed_users = {"global", user_id} if user_id else {"global"}
        mask = np.array([(not sources or d["source"] in sources) and d["user_id"] in allowed_users for d in self.docs])
        if not mask.any():
            return []
        idx = np.where(mask)[0]
        scores = self.vectors[idx] @ query_vec  # vectors are normalised -> cosine
        top = idx[np.argsort(-scores)[:k]]
        return [{**self.docs[i], "score": float(self.vectors[i] @ query_vec)} for i in top]

    def count(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for d in self.docs:
            out[d["source"]] = out.get(d["source"], 0) + 1
        return out


_client = None
_stores: Dict[tuple, BaseVectorStore] = {}


def _mongo_client():
    """One MongoClient per process (it is thread-safe and pools connections)."""
    global _client
    if _client is None:
        from pymongo import MongoClient

        if not config.MONGODB_URI:
            raise ValueError("MONGODB_URI is not set. Add it to .env (see docs/mongodb_atlas_setup.md).")
        _client = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=10000, appname="skillpath-ai-rag")
    return _client


def resolve_backend(backend: str = None) -> str:
    backend = (backend or config.VECTOR_BACKEND).lower()
    if backend == "auto":
        return "mongo" if config.MONGODB_URI else "local"
    return backend


def get_vector_store(source: str, backend: str = None) -> BaseVectorStore:
    """Store for one source (careers | knowledge | jobs | profile). Each maps to its own collection."""
    backend = resolve_backend(backend)
    collection, index = config.COLLECTIONS[source]
    key = (backend, collection)
    if key not in _stores:
        _stores[key] = (MongoAtlasVectorStore(collection, index) if backend == "mongo"
                        else LocalVectorStore(config.LOCAL_STORE_DIR / collection))
    return _stores[key]
