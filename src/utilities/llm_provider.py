"""
Which text generator is available? (docs/keyless_mode.md)

LLM_PROVIDER = auto | api | local | none
    api   : hosted models (Groq / Gemini) via brain.get_robust_llm, needs API keys
    local : a model served by Ollama on this machine (default `mistral`), no keys, no internet
    none  : no generator; every feature falls back to retrieval-only / rule-based / template output
    auto  : api if a GROQ or GEMINI key is set, else local if Ollama answers, else none

Embeddings (MiniLM) and vector search never need a key in any mode.
"""
from __future__ import annotations

import os
import time
from functools import lru_cache

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")


class LLMUnavailable(RuntimeError):
    """Raised when LLM_PROVIDER resolves to `none` (callers switch to their no-LLM path)."""


_ollama_cache = {"t": 0.0, "ok": False}


def ollama_available(ttl_s: float = 60.0) -> bool:
    now = time.time()
    if now - _ollama_cache["t"] < ttl_s:
        return _ollama_cache["ok"]
    ok = False
    try:
        import requests

        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=1.5)
        ok = r.ok and any(m.get("name", "").split(":")[0] == OLLAMA_MODEL.split(":")[0] for m in r.json().get("models", []))
    except Exception:  # noqa: BLE001
        ok = False
    _ollama_cache.update(t=now, ok=ok)
    return ok


def has_api_keys() -> bool:
    return bool(os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY"))


def llm_provider() -> str:
    mode = os.getenv("LLM_PROVIDER", "auto").lower()
    if mode in ("api", "local", "none"):
        return mode
    if has_api_keys():
        return "api"
    return "local" if ollama_available() else "none"


def provider_label() -> str:
    return {"api": "Hosted LLM (Groq/Gemini)", "local": f"Local LLM ({OLLAMA_MODEL} via Ollama)",
            "none": "Retrieval-only (no LLM)"}[llm_provider()]


@lru_cache(maxsize=8)
def get_local_llm(temperature: float = 0.3):
    """Ollama through its OpenAI-compatible endpoint (langchain-openai is already a dependency)."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=OLLAMA_MODEL, base_url=f"{OLLAMA_BASE_URL}/v1", api_key="ollama",
                      temperature=temperature, timeout=300, max_retries=0)
