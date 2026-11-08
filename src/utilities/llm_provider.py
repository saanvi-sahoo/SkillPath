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


# BYOK session context (see bottom of file)
# The key lives ONLY in this ContextVar for the duration of one script run / request. It is never put in
# os.environ (which is shared by every visitor of a deployed app), never written to disk and never logged.
from contextvars import ContextVar
from typing import Dict, List, Optional

_session_llm: ContextVar[Optional[Dict]] = ContextVar("session_llm", default=None)


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
    if _session_llm.get():  # a visitor supplied their own key for this session
        return "byok"
    mode = os.getenv("LLM_PROVIDER", "auto").lower()
    if mode in ("api", "local", "none"):
        return mode
    if has_api_keys():
        return "api"
    return "local" if ollama_available() else "none"


def provider_label() -> str:
    p = llm_provider()
    if p == "byok":
        cfg = _session_llm.get()
        return f"Your key: {BYOK_PROVIDERS[cfg['provider']]['label'].split(' (')[0]} · {cfg.get('model') or BYOK_PROVIDERS[cfg['provider']]['default_model']}"
    return {"api": "Hosted LLM (Groq/Gemini)", "local": f"Local LLM ({OLLAMA_MODEL} via Ollama)",
            "none": "Retrieval-only (no LLM)"}[p]


@lru_cache(maxsize=8)
def get_local_llm(temperature: float = 0.3):
    """Ollama through its OpenAI-compatible endpoint (langchain-openai is already a dependency)."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=OLLAMA_MODEL, base_url=f"{OLLAMA_BASE_URL}/v1", api_key="ollama",
                      temperature=temperature, timeout=300, max_retries=0)




BYOK_PROVIDERS: Dict[str, Dict] = {
    "groq": {"label": "Groq (free tier available, fast)", "default_model": "openai/gpt-oss-120b",
             "key_url": "https://console.groq.com/keys", "key_prefix": "gsk_"},
    "gemini": {"label": "Google Gemini (free tier available)", "default_model": "gemini-3.5-flash",
               "key_url": "https://aistudio.google.com/apikey", "key_prefix": "AI"},
    "openai": {"label": "OpenAI", "default_model": "", "key_url": "https://platform.openai.com/api-keys",
               "key_prefix": "sk-", "base_url": "https://api.openai.com/v1"},
    "openrouter": {"label": "OpenRouter (one key, many models)", "default_model": "openai/gpt-oss-120b",
                   "key_url": "https://openrouter.ai/keys", "key_prefix": "sk-or-", "base_url": "https://openrouter.ai/api/v1"},
}


def set_session_llm(cfg: Optional[Dict]) -> None:
    """cfg = {"provider": "groq|gemini|openai|openrouter", "api_key": "...", "model": "...", "tavily_key": "..."}."""
    _session_llm.set(cfg if (cfg and cfg.get("api_key") and cfg.get("provider") in BYOK_PROVIDERS) else None)


def session_llm() -> Optional[Dict]:
    return _session_llm.get()


def get_secret(name: str) -> Optional[str]:
    """Session-provided secret first (e.g. the visitor's own Tavily key), then the server environment."""
    cfg = session_llm() or {}
    if name == "TAVILY_API_KEY" and cfg.get("tavily_key"):
        return cfg["tavily_key"]
    return os.getenv(name)


def build_user_llm(cfg: Dict, temperature: float = 0.3):
    """Chat model for a visitor's own key. No server-side fallback: their key, their quota."""
    p, key, model = cfg["provider"], cfg["api_key"], cfg.get("model") or BYOK_PROVIDERS[cfg["provider"]]["default_model"]
    if p == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=model, api_key=key, temperature=temperature, max_retries=1)
    if p == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, google_api_key=key, temperature=temperature, max_retries=1)
    from langchain_openai import ChatOpenAI  # openai + openrouter (OpenAI-compatible)
    return ChatOpenAI(model=model, api_key=key, base_url=BYOK_PROVIDERS[p]["base_url"], temperature=temperature,
                      max_retries=1, timeout=120)


def list_models(provider: str, api_key: str) -> List[str]:
    """Chat-capable models this key can use (live from the provider), so users pick a valid, current model."""
    import requests
    try:
        if provider == "gemini":
            r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                             params={"key": api_key, "pageSize": 200}, timeout=15)
            r.raise_for_status()
            return sorted(m["name"].split("/", 1)[1] for m in r.json().get("models", [])
                          if "generateContent" in m.get("supportedGenerationMethods", [])
                          and not any(x in m["name"] for x in ("tts", "image", "embedding", "robotics", "lyria", "transcribe")))
        url = {"groq": "https://api.groq.com/openai/v1/models",
               "openai": "https://api.openai.com/v1/models",
               "openrouter": "https://openrouter.ai/api/v1/models"}[provider]
        r = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
        r.raise_for_status()
        ids = [m["id"] for m in r.json().get("data", [])]
        skip = ("whisper", "tts", "embedding", "guard", "orpheus", "dall-e", "moderation", "image", "audio", "realtime", "transcribe")
        return sorted(i for i in ids if not any(x in i for x in skip))
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Could not list models: {redact(str(e), api_key)[:200]}") from None


def test_user_llm(cfg: Dict) -> str:
    """One tiny call; returns the model's reply or raises ValueError with the key redacted."""
    try:
        return build_user_llm(cfg, temperature=0).invoke("Reply with exactly: OK").text.strip()[:40]
    except Exception as e:  # noqa: BLE001
        raise ValueError(redact(str(e), cfg.get("api_key", ""))[:300]) from None


def redact(text: str, key: str) -> str:
    return text.replace(key, "***") if key else text
