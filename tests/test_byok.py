"""Bring-your-own-key + deployment-safety tests (offline, no real API calls). Run: python -m pytest -q tests"""
import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_session_key_is_isolated_per_thread():
    """Streamlit runs each visitor's script in its own thread: a key set in one must be invisible in another."""
    from src.utilities import llm_provider as lp
    seen = {}

    def visitor_a():
        lp.set_session_llm({"provider": "groq", "api_key": "gsk_A", "model": "m"})
        seen["a"] = lp.llm_provider()

    def visitor_b():
        seen["b_cfg"] = lp.session_llm()

    t = threading.Thread(target=visitor_a); t.start(); t.join()
    t = threading.Thread(target=visitor_b); t.start(); t.join()
    assert seen["a"] == "byok" and seen["b_cfg"] is None
    assert lp.session_llm() is None  # main thread untouched


def test_byok_label_secret_and_redaction():
    from src.utilities import llm_provider as lp
    cfg = {"provider": "openrouter", "api_key": "sk-or-secret", "model": "x/y", "tavily_key": "tvly-mine"}
    lp.set_session_llm(cfg)
    try:
        assert lp.llm_provider() == "byok" and "OpenRouter" in lp.provider_label() and "x/y" in lp.provider_label()
        assert lp.get_secret("TAVILY_API_KEY") == "tvly-mine"
        assert "sk-or-secret" not in lp.redact("401 invalid key sk-or-secret", "sk-or-secret")
        assert "sk-or-secret" not in os.environ.values()
    finally:
        lp.set_session_llm(None)
    lp.set_session_llm({"provider": "unknown", "api_key": "x"})  # invalid provider is ignored
    assert lp.session_llm() is None


def test_build_user_llm_types():
    from src.utilities.llm_provider import build_user_llm
    assert type(build_user_llm({"provider": "groq", "api_key": "gsk_x", "model": "m"})).__name__ == "ChatGroq"
    o = build_user_llm({"provider": "openrouter", "api_key": "sk-or-x", "model": "a/b"})
    assert type(o).__name__ == "ChatOpenAI" and "openrouter" in str(o.openai_api_base)


def test_pipeline_imports_with_no_keys_and_no_dotenv(tmp_path):
    """Deployed (Streamlit Cloud) conditions: no .env, no keys -> importing the pipeline must not raise (E29),
    and third-party load_dotenv() (webdriver_manager) must not pull in keys when SKILLPATH_NO_DOTENV=1."""
    code = ("import os,sys; sys.path.insert(0, sys.argv[1]); import src.utilities.env, src.backend.main_runner;"
            "from src.utilities.llm_provider import llm_provider;"
            "print('KEYS', bool(os.getenv('GROQ_API_KEY') or os.getenv('GEMINI_API_KEY')), 'PROVIDER', llm_provider())")
    env = {"HOME": os.environ.get("HOME", ""), "PATH": os.environ.get("PATH", ""), "SKILLPATH_NO_DOTENV": "1",
           "OLLAMA_BASE_URL": "http://127.0.0.1:9"}
    r = subprocess.run([sys.executable, "-c", code, str(ROOT)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-1500:]
    assert "KEYS False PROVIDER none" in r.stdout
