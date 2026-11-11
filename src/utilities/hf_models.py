"""
Load Hugging Face models from the local cache first (final validation: a first career search in a fresh process once
waited ~15 minutes on the Hugging Face hub's online check while loading the cross-encoder). Falls back to downloading
when the model isn't cached yet (fresh Streamlit Cloud container).
"""
from __future__ import annotations


def load_cached(cls, name: str, **kw):
    try:
        return cls(name, local_files_only=True, **kw)
    except Exception:  # noqa: BLE001 - not cached (or old library without the flag): normal online load
        return cls(name, **kw)
