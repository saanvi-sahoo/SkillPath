# Bring your own API key (BYOK)

The **deployed** app (Streamlit Community Cloud) has no API keys of its own, so by default it runs keyless (retrieval-only answers, rule-based analysis; see [keyless_mode.md](keyless_mode.md)). Any visitor can switch on full AI answers **with their own key**, for their session only. **Local runs** keep using Mistral via Ollama (`LLM_PROVIDER=local` in your local `.env`), and any local visitor can also enter their own key.

## 1. What the visitor sees
Sidebar → **AI engine & your own API key**:
1. **Current engine**, e.g. *Retrieval-only (no LLM)* on the deployed app or *Local LLM (mistral via Ollama)* locally.
2. **Provider** (multiple choice):

   | Provider | Default model | Get a key |
   |---|---|---|
   | Groq (free tier available, fast) | `openai/gpt-oss-120b` | https://console.groq.com/keys |
   | Google Gemini (free tier available) | `gemini-3.5-flash` | https://aistudio.google.com/apikey |
   | OpenAI | choose after "Load models" | https://platform.openai.com/api-keys |
   | OpenRouter (one key, many models) | `openai/gpt-oss-120b` | https://openrouter.ai/keys |
3. **API key** (a password field).
4. **Load models** lists the chat models *that key* can actually use, live from the provider, so nobody has to guess current model names. Otherwise the visitor types a model.
5. **Tavily key** (optional) turns on live web learning resources during Analyze Profile.
6. **Test & use** makes one tiny call ("Reply with exactly: OK"). If it succeeds, the key is activated. If not, the provider's error is shown, with the key redacted.
7. **Stop using my key** forgets it.

Once active, the status chip shows *Prompt v4 · Your key: Google Gemini · gemini-3.1-flash-lite*, and these all use the visitor's key:
- the Career Advisor answers
- the scope router's LLM step
- the resume/JD skill analysis
- the career summary
- the 30-day roadmap's daily tasks
- the web resources (if a Tavily key was given)

## 2. How the key is protected
| Rule | Implementation |
|---|---|
| Never shared between visitors | The key lives in `st.session_state` of that browser tab. Each script run passes it to the backend through a **ContextVar** (`llm_provider.set_session_llm`). Streamlit runs each visitor's script in its own thread, and ContextVars are per thread or task, so other visitors can't see it (`tests/test_byok.py::test_session_key_is_isolated_per_thread`) |
| Never in the server environment | No `os.environ` writes (a deployed app's environment is shared by every visitor). Verified: the key is absent from `os.environ` after use |
| Never stored or logged | Not written to disk, `memory.json`, the chat log or the feedback log. Verified: the key is absent from `reports/chat_logs/chat_log.jsonl` after a BYOK conversation |
| Errors don't echo it | `llm_provider.redact()` is applied to every provider error shown in the UI |
| Visitor's quota, not ours | With a session key there is **no fallback to server keys** (`build_user_llm` only). If the visitor's model fails, the turn degrades to retrieval-only |
| Runs where the key is | With a session key, Analyze Profile runs **in-process**: a separate API server can't see the session's key |

The key is forgotten when the tab closes, the session expires, or the visitor clicks *Stop using my key*.

## 3. Engine resolution order (`llm_provider()`)
```
visitor's own key (this session)  →  byok
else LLM_PROVIDER = api | local | none   (explicit setting)
else auto: server API keys → api;  Ollama reachable → local;  otherwise → none
```
| Where | Typical setting | Result |
|---|---|---|
| Your laptop | `.env`: `LLM_PROVIDER=local`, `OLLAMA_MODEL=mistral` | Mistral via Ollama; visitors may still enter their own key |
| Streamlit Cloud (no secrets) | nothing | retrieval-only; visitors may enter their own key |
| Streamlit Cloud with team secrets | `GROQ_API_KEY` / `GEMINI_API_KEY` in Secrets | hosted LLM for everyone (team quota) |

**Environment precedence (E29):** real environment variables (the shell, Streamlit secrets) now take precedence over `.env` (`load_dotenv(override=False)`). Before, `.env` silently won.

## 4. Verified behaviour (2026-11-08)
- **Model list + test:** a Gemini key listed 31 chat models; "Test & use" returned `OK`.
- **Visitor A with key:** chip *Your key: Google Gemini · gemini-3.1-flash-lite*. The advisor answer came from `gemini-3.1-flash-lite`, Analyze Profile used the key (LLM analysis in 19 s), and the roadmap was LLM-generated (valid, 30 days).
- **Visitor B without key, same server:** retrieval-only; unaffected.
- **Leak checks:** the key was not in `os.environ` and not in the chat log.

## 5. Deployment fixes found while building this (E29)
1. **The error in the screenshot:** `net_surf.py` raised `GEMINI_API_KEY is missing from your .env file!` **at import time**, so the deployed keyless app couldn't run Analyze Profile at all. It's now optional, and the node is skipped without keys.
2. `main_runner.py` loaded the Naukri scraper by a **working-directory-relative path** (`src/backend/scraper/...`), which broke when the app ran from another folder. It now resolves relative to the file.
3. The third-party `webdriver_manager` calls `load_dotenv()` on import and found the repo's `.env`. With `SKILLPATH_NO_DOTENV=1` we now also set python-dotenv's global `PYTHON_DOTENV_DISABLED=1`, so a keyless instance really has no keys (`tests/test_byok.py::test_pipeline_imports_with_no_keys_and_no_dotenv`).
4. `.env` precedence (above).
5. **Local Mistral hallucinated a requirement:** for a data-analyst JD that never mentions Kubernetes, it reported "Tools: Kubernetes" as a gap (ATS 68). Skill gaps must be exact, so with `local` the resume/JD analysis uses the deterministic extractor (correct gaps: Tableau, Statistics, Data Visualization, Communication). Mistral still writes chat answers and the summary.
6. **Deployed path verified** (no keys, no `.env`, in-process, run from another folder, Streamlit AppTest): Analyze Profile completes in 15.2 s, with no errors, those exact 4 gaps and 20 jobs.
7. With `local` Mistral, the scope router uses kNN only: a 7B router call adds 10–40 s, and kNN allow/refuse accuracy is 1.0 on the 42 cases.
