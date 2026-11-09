# Keyless mode: running without Groq or Gemini

**Short answer:** yes. Embeddings and RAG retrieval never needed an API key: MiniLM runs locally, and vector search runs on Atlas or locally. Only *text generation* used Groq/Gemini. Every generating step now has a deterministic or local replacement.

## 1. The three generation modes (`LLM_PROVIDER`)

| Mode | How answers are produced | Needs | Speed (measured on this Mac) | Use for |
|---|---|---|---|---|
| `api` | Groq gpt-oss-120b → fallbacks → Gemini → (Ollama if running) | API keys; free tiers cap at ~200k tokens/day per org | 1–3 s / answer | best fluency |
| `local` | **Mistral 7B via Ollama** on the same machine, prompt v4 | Ollama + a model (`ollama pull mistral`); no keys, no internet | **35–55 s / answer** (16 GB Mac, 3–4k-token prompts) | private / offline use |
| `none` | **Retrieval-only**: answers composed from the cited records + rules + templates | nothing | **0.24 s / answer** | public demos, free hosting, quota outages |
| `auto` (default) | `api` if a GROQ/GEMINI key is set → else `local` if Ollama answers → else `none` | | | |

Even in `api` mode, if every hosted model fails at runtime (quota, outage), the chatbot **degrades to retrieval-only** instead of showing an error, and the turn is logged as `generation: retrieval-only (all LLMs unavailable)`.

## 2. What replaces the LLM in each feature

| Feature | With an LLM | Keyless replacement | File |
|---|---|---|---|
| Embeddings + vector search | (never used an LLM) | same MiniLM + Atlas/local search | `src/rag/*` |
| Scope guardrail | regex + kNN + LLM for ambiguous messages | regex + kNN; short follow-ups are classified together with the previous user turn | `src/backend/scope_router.py` |
| Chat answers | prompt v4 + retrieved context | **composer**: profile facts, matching career records (skills you have / to learn), the best guide section (first for how-to questions), your learning resources, jobs, salary caveat, skill-equivalence rules (Docker ≠ Kubernetes, MySQL ⇒ SQL), clarifying questions for vague requests. Same `[S#]` citations | `src/backend/extractive_answer.py` |
| Resume/JD skill analysis | LLM structured JSON (hosted or visitor key) | **rule-based extractor** (also used in `local` mode, E29): 864-term vocabulary (alias table + skills appearing in ≥5 career records), whole-word matching, case-sensitive for ambiguous words ("Go", "Excel"); gaps via exact comparison; ATS = share of JD skills found (labelled an estimate) | `src/skills/extractor.py` |
| Web resources (Tavily) | Tavily search + LLM formatting | skipped; static Udemy/YouTube/Coursera links are still shown | `main_runner.net_surf_node` |
| Career summary | LLM paragraph | template from the analysis fields | `main_runner.template_summary` |
| 30-day roadmap | LLM fills the daily tasks | deterministic template (same prioritisation, skeleton and validation) | `src/roadmap/generator.py` |
| Job scraping parameters | LLM picks the experience level | defaults | `main_runner.scrape_jobs_node` |

## 3. Measured quality (42-case eval set, production router, 2026-11-08)

| Configuration | Pass rate | Weak evidence | Skill equivalence | Citation rate | Avg latency | Tokens |
|---|---|---|---|---|---|---|
| v4 on gemini-3.1-flash-lite (`api`) | 1.0 | 2/2 | 1/1 | 93% | 3.3 s | 93k |
| **Retrieval-only (`none`)** | **1.0** (first run 0.952 → rules added for doc07/doc09) | 2/2 | 1/1 | 93% | **0.24 s** | **0** |
| v4 on local Mistral 7B (`local`) | 0.881 (37/42) | 1/2 | 1/1 | **30%** | 38.6 s avg (LLM answers: median 46.5 s, max 148 s) | local (~4.4k/answer) |

**Honest caveats**
- The retrieval-only rules were refined *while looking at these 42 cases* (two fixes after the first run), so its 1.0 is optimistic. A held-out set is needed for a fair comparison.
- The checks are deterministic proxies (keywords, citations, refusals, questions). Retrieval-only answers are **structured and cited but not fluent**: they list records and guide excerpts rather than writing advice in natural language.
- The rule-based ATS estimate is stricter than the LLM's (43 vs 65–70 on the test profile), because it counts only exact canonical matches.

## 4. Per-visitor isolation (required for any public deployment)
Before E26, every visitor shared one `memory.json`, the private chunks of `user_id="default"`, and a process-wide cached result, so a second visitor saw the first visitor's analysis. Now:
- Every browser session gets an id kept in the URL (`?u=…`), so a refresh keeps your own data.
- Analysed profiles are stored as `src/backend/user_memory/<id>.json` (git-ignored). The local default user keeps using `memory.json`.
- Private profile chunks carry that `user_id`, and every search filters by `user_id ∈ {global, me}`.
- The cached UI state, the chat (`answer(user_id=…)`), the roadmap (`user_id=…`) and the API (`user_id` field on `/pipeline/run`, `/chat`, `/roadmap`) are all keyed by it.
- Tests: `tests/test_keyless.py::test_memory_path_is_per_user_and_sanitised` (also blocks path traversal like `../../etc/passwd`).

## 5. Local LLM results (Mistral 7B via Ollama)
Run: `LLM_PROVIDER=local`, prompt v4, production router, 42/42 cases completed (`reports/prompt_eval/keyless_local_mistral.json`).

| Metric | Value |
|---|---|
| Pass rate | **0.881** (37/42) |
| By category | 1.0: study, follow-up, greeting, all 12 refusals, edge, ambiguous, skill equivalence, salary. 0.8: profile, general career. 0.5: weak evidence. **0.0: career recommendation** |
| Failures | cs04, cs07, doc01, doc10: **no `[S#]` citations**; doc09 guessed careers instead of asking |
| Citation rate (in-scope) | **30%** (gemini-flash-lite with v4: 93%) |
| Latency | median 46.5 s per LLM answer, max 148 s (16 GB Mac); refusals are instant |

**Reading:** Mistral 7B follows the scope rules (every refusal correct) but largely ignores the citation contract and the weak-evidence rule. Recommendation by use case:
- public or free hosting → **retrieval-only**
- private offline use → **local** (fluent but slow, weak on citations)
- best quality → **api**

A stronger local model (e.g. `qwen2.5:7b-instruct` or `llama3.1:8b`) and a shorter context would be the next experiment.

## 6. How to run
```bash
# retrieval-only (no keys, no Ollama)
LLM_PROVIDER=none streamlit run src/frontend/frontend.py
# local LLM
ollama pull mistral && LLM_PROVIDER=local streamlit run src/frontend/frontend.py
# a keyless instance next to your normal one (ignores .env, so keys can't leak into it)
SKILLPATH_NO_DOTENV=1 LLM_PROVIDER=none VECTOR_BACKEND=local streamlit run src/frontend/frontend.py --server.port 8502
# evaluate any mode for free
LLM_PROVIDER=none python -m src.eval.run_prompt_eval --router-modes hybrid --versions v4 --router hybrid --paired --expect-model "" --sleep 0
```
`SKILLPATH_NO_DOTENV=1` makes every module skip `.env` (`src/utilities/env.py`).

## Intent routing in keyless mode (E37)
Keyless answers now use the same deterministic intent routing as prompt v8 (`src/backend/intent.py`): concept and
study questions retrieve guides only (no career records), profile questions only this student's analysis, and
"30-day plan" requests show the validated roadmap generator's plan directly. 65-case regression: 0.877 before and
after (same 8 failures: exact item counts and word limits, which a retrieval-only answer can't meet). Turn it off with
`KEYLESS_INTENT_ROUTING=false`.
