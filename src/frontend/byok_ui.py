"""
Sidebar: "Use your own API key" (BYOK). docs/byok.md

The key is kept only in st.session_state of this browser tab and handed to the backend per script run
through a ContextVar (llm_provider.set_session_llm). It is never written to disk, logs or os.environ.
"""
from __future__ import annotations

import streamlit as st

from src.utilities.llm_provider import (BYOK_PROVIDERS, list_models, llm_provider, provider_label,
                                        redact, set_session_llm, test_user_llm)


def apply_session_llm() -> None:
    """Call at the top of every script run, BEFORE any LLM use (also resets when no key is set)."""
    set_session_llm(st.session_state.get("byok"))


def render_byok_sidebar() -> None:
    with st.sidebar:
        st.divider()
        active = st.session_state.get("byok")
        with st.expander(":material/key: AI engine & your own API key", expanded=False):
            if active:
                st.success(f"Using **your key**: {provider_label().replace('Your key: ', '')}")
                if st.button("Stop using my key", use_container_width=True, key="byok_forget"):
                    st.session_state.pop("byok", None)
                    st.session_state.pop("byok_models", None)
                    set_session_llm(None)
                    st.rerun()
            else:
                st.caption(f"Current engine: **{provider_label()}**")
                if llm_provider() == "none":
                    st.caption("Without a key, answers are composed directly from our career records (no AI writing). "
                               "Add your own key for fuller, conversational answers and AI resume analysis.")

            st.markdown("**Use your own API key** (optional)")
            prov = st.selectbox("Provider", list(BYOK_PROVIDERS), format_func=lambda k: BYOK_PROVIDERS[k]["label"],
                                key="byok_provider")
            meta = BYOK_PROVIDERS[prov]
            st.caption(f"Get a key: {meta['key_url']}")
            key = st.text_input("API key", type="password", key="byok_key",
                                placeholder=f"{meta['key_prefix']}…", help="Kept only in this browser tab's memory.")

            models = st.session_state.get("byok_models", {}).get(prov)
            c1, c2 = st.columns([1, 1])
            if c1.button("Load models", use_container_width=True, disabled=not key, key="byok_load"):
                try:
                    st.session_state.setdefault("byok_models", {})[prov] = list_models(prov, key)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            if models:
                default = meta["default_model"] if meta["default_model"] in models else models[0]
                model = st.selectbox(f"Model ({len(models)} available)", models, index=models.index(default), key="byok_model_sel")
            else:
                model = st.text_input("Model", value=meta["default_model"], key="byok_model_txt",
                                      help="Click 'Load models' to choose from the models your key can use.")
            tavily = st.text_input("Tavily key (optional, live web resources)", type="password", key="byok_tavily",
                                   help="https://app.tavily.com - leave empty to skip web search.")

            if c2.button("Test & use", type="primary", use_container_width=True, disabled=not (key and model), key="byok_use"):
                cfg = {"provider": prov, "api_key": key.strip(), "model": model.strip(), "tavily_key": (tavily or "").strip()}
                with st.spinner("Checking your key…"):
                    try:
                        reply = test_user_llm(cfg)
                        st.session_state["byok"] = cfg
                        set_session_llm(cfg)
                        st.success(f"Key works ({model} replied: {reply!r}). The advisor, resume analysis and roadmap now use it.")
                        st.rerun()
                    except ValueError as e:
                        st.error(f"That key/model didn't work: {redact(str(e), key)}")
            st.caption(":material/lock: Your key stays in this browser tab's memory only. It is never saved, logged or "
                       "shared with other visitors, and usage is billed to your own account. Closing the tab forgets it.")
