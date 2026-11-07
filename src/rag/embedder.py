"""
Embedding model wrapper.

One process-wide SentenceTransformer instance (loading costs ~2-4 s), exposed
through two functions so the rest of the code never touches the library
directly. Swapping the model = change EMBEDDING_MODEL / EMBEDDING_DIM in config
and re-run ingestion (vectors from different models are NOT comparable).
"""
from __future__ import annotations

import threading
from typing import List

import numpy as np

from src.rag import config

_model = None
_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(config.EMBEDDING_MODEL)
                dim = (getattr(_model, "get_embedding_dimension", None) or _model.get_sentence_embedding_dimension)()
                if dim != config.EMBEDDING_DIM:
                    raise ValueError(
                        f"{config.EMBEDDING_MODEL} outputs {dim}-dim vectors but "
                        f"EMBEDDING_DIM={config.EMBEDDING_DIM}. Update config and the Atlas index."
                    )
    return _model


def embed_texts(texts: List[str], show_progress: bool = False) -> np.ndarray:
    """Embed many texts -> float32 array of shape (n, EMBEDDING_DIM), L2-normalised."""
    if not texts:
        return np.zeros((0, config.EMBEDDING_DIM), dtype=np.float32)
    vecs = get_model().encode(
        texts,
        batch_size=config.EMBEDDING_BATCH_SIZE,
        normalize_embeddings=config.NORMALIZE_EMBEDDINGS,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
    )
    return vecs.astype(np.float32)


def embed_query(text: str) -> np.ndarray:
    """Embed a search query (adds the model's query instruction) -> shape (EMBEDDING_DIM,)."""
    return embed_texts([config.QUERY_INSTRUCTION + text])[0]


def embed_symmetric(text: str) -> np.ndarray:
    """Embed text compared against texts of the same kind (e.g. message vs anchor messages): no instruction."""
    return embed_texts([text])[0]
