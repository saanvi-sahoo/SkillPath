# Experiment log

Add one entry for every change to models, prompts, thresholds, chunking or data. Newest first. Raw outputs live in `reports/`.

---

## 2026-11-08: E35 Retrieval precision (re-ranking), knowledge coverage, specific roadmaps
- **RAG benchmark** (`src/eval/rag_benchmark.py`, no LLM): 30 labelled guide questions + 24 labelled career queries. **Vector + cross-encoder re-rank adopted**: guide Hit@1 0.767 → 0.800, Hit@3 0.900 → 0.967, MRR 0.842 → 0.884; **career strict-P@5 0.767 → 0.858**; +40–65 ms. Hybrid BM25 rejected (guide Hit@1 0.667). Query expansion rejected (profile Hit@3 already 1.0).
- **Re-rank noise cut-off −6**, calibrated: keeps 91% relevant, drops 73% non-relevant (e.g. "Recruiter" job records for a LinkedIn question, −7).
- **Knowledge base 17 → 37 sections** (5 new guides: higher education & exams, applications & networking, student well-being, first job, portfolio & projects). Ingested to the local store and Atlas. "How should I prepare for GATE…" now retrieves the GATE guide.
- **Roadmap:** curated free resources per skill on every learning day; role-specific capstone (analyst / backend / ML / cloud) naming the person's gaps; plan & build + polish & present days. `roadmap_eval`: **3/3 personas pass 7/7 checks**.
- **Deployment:** Atlas access list now has 0.0.0.0/0 in the *SkillPath AI* project (first added to the empty "Project 0" by mistake → "Inactive"); the deployed app uses the least-privilege `skillpath_cloud` user via Streamlit secrets.
- **Model quotas:** gemini-3.1-flash-lite exhausted its daily free quota during the evals (E34's v5/v6 run stopped cleanly at 30/65 pairs: both 1.0, v6 citation rate 1.0 vs 0.94). gpt-oss-120b and gemini-3.5-flash recovered.
- Tests: 35 → **40**.

## 2026-11-08: E34 Question queue, scope v2, self-revising answers (v6), Atlas for other devices
- **Chat:** while an answer was generating, a new question interrupted the run and was lost. Now there's a **question queue** (answered in order; a question leaves the queue only after its answer is stored). AppTest: 2 queued questions answered in order, then a typed one.
- **Scope:** one written definition for router v2 + advisor v6 (study-adjacent topics in, everything else out). +8 in-scope / +8 out-of-scope router anchors (worded differently from the tests). +14 scope eval cases (65 total). **Router v1 vs v2 on 65 cases: both hybrid 1.0 label and allow/refuse accuracy, 0 false refusals, 0 leaks** → v2 active (aligned definition).
- **Persona eval (profile / JD / both, 3 personas × 10 questions):** v4 0.90 vs **v5 1.00** (v4 failed only the "am I a fit" verdict). Recursive rounds: R1 learned 0.867 vs control 0.967 was **confounded** (fallback models answered the learned arm), R2 learned 0.933 vs control 0.90. Root cause of the paraphrase failures: question-type misclassification ("Should I apply…" → profile_fact; "first gap" → definition). Fixed in the profiler; the persona runner now has a strict-model guard.
- **v6 = v5 + generate → verify → revise** (`answer_check.py`, max 1 revision, only when the draft breaks the contract) + the explicit scope text.
- **Atlas for other devices:** least-privilege user `skillpath_cloud` (readWrite@skillpath_ai only; writes elsewhere verified denied). Opening `0.0.0.0/0` was refused by the automation safety policy, so it's left to the project owner (one command, mongodb_atlas_setup.md §0b).

## 2026-11-08: E33 Profile lifecycle, fast roadmap, cleaner skill extraction, JD-aware questions
- **Roadmap "not generating":** locally the 30-day plan was written by Mistral as one large JSON (**216 s**, looked broken). Now there's a curriculum-based template (ordered topics per skill in `src/roadmap/syllabus.py` + mini project + interview readiness): **0.7 s**. Hosted or visitor-key models still write the plan, with a 75 s hard timeout and template fallback. The deployed crash was the Python 3.14 magic issue (E32).
- **"Profile summary not changing":** re-analysis did update. But removing CV/JD left the old profile (and the chatbot's memory of it), changed uploads showed no hint, and the old roadmap survived. Added input fingerprints, a stale banner with **Re-analyse now**, auto-clear on removal (not on refresh), **Clear profile** (memory file + profile chunks), provenance, per-visitor upload names and roadmap reset. Verified end to end with AppTest (5 steps).
- **Rule-based extractor quality:** degree names ("Computer Science"), generic words ("Analysis", "Design") and JD *responsibilities* ("build dashboards") were counted as skills or requirements. Now the requirements section is parsed when present, plus a NOT_SKILLS list. Persona gaps went from 5–7 noisy entries to the exact ones (e.g. Microservices, Docker, Kubernetes, AWS).
- **JD-aware question types:** `fit_analysis` (resume vs JD) and `jd_requirements`, with their own retrieval mix and answer contracts. The profile header now includes JD and resume excerpts.
- **Atlas:** this Mac's IP rotated (49.37.117.224 → 49.37.113.161) and was added. A circuit breaker now serves the local copy while Atlas is unreachable.
- **v5 vs v4** (51 cases, paired, gemini-3.1-flash-lite): **pass 0.98 vs 0.922**, precision 0.889 vs 0.667, avg 156 vs 201 words, citation rate 0.78 vs 0.89. **v5 activated.**

## 2026-11-08: E31 Deployed app: ImportError after redeploy (stale modules)
- **Symptom (live, Streamlit Cloud):** `ImportError` at `byok_ui.py` line 11, `from src.utilities.llm_provider import (BYOK_PROVIDERS, …)`. The GitHub code was correct (all names present).
- **Cause:** Streamlit Cloud pulls new code on push but keeps the same Python process. `src.utilities.llm_provider` was cached from the pre-BYOK version, while `frontend.py`/`byok_ui.py` were new, so the new names were missing from the cached module.
- **Reproduced locally:** worktree at the pre-BYOK commit, Streamlit with `--server.fileWatcherType none`, files swapped in place without restarting → the same ImportError.
- **Fix:** `frontend.py` fingerprints `src/**/*.py` (path, mtime, size) on every run and drops cached `src.*` modules when it differs from the last run (including when no fingerprint exists yet). Verified in the same stale process: the next page load works, and later reloads work.
- **Regression test:** `tests/test_app_boot.py::test_frontend_survives_stale_modules_after_redeploy` plants an old module in `sys.modules`. It fails without the guard with the exact live error and passes with it. 26/26 tests.
- Deploying this commit repairs the running app on its next page load (no reboot needed). If Streamlit Cloud hasn't pulled yet: ⋮ → Reboot app.

## 2026-11-08: E30 One-command local start (`run_local.sh`)
- Starts Ollama (pulls mistral if missing), frees stale ports, starts the API (:8000) and the app (:8501), and opens the browser. `--keyless` gives the deployment-identical instance (:8502).
- Bug found while testing: macOS bash 3.2 treats an empty array as unbound under `set -u` (`ENVV[@]: unbound variable`). Fixed with the `${ENVV[@]+"${ENVV[@]}"}` form. Both modes verified: health 200, and pages render the Career Advisor in headless Chrome.

## 2026-11-08: E29 Bring-your-own-key + deployed-app fixes
- **Reported:** the deployed app showed `Pipeline failed: GEMINI_API_KEY is missing from your .env file!` → `net_surf.py` raised at import time. Fixed (now optional).
- **Also found and fixed:** a working-directory-relative Naukri scraper path; `webdriver_manager` calling `load_dotenv()` at import (keyless instances silently got the repo keys; now `PYTHON_DOTENV_DISABLED=1` under `SKILLPATH_NO_DOTENV=1`); `.env` overriding real env vars (now `override=False`).
- **BYOK:** sidebar provider choice (Groq / Gemini / OpenAI / OpenRouter), key, live "Load models", optional Tavily key, "Test & use". The key is per session via a ContextVar, never in os.environ, disk or logs, and errors are redacted. Used for chat, router, analysis, summary, roadmap and web resources, with no server-key fallback.
- **Local default:** `LLM_PROVIDER=local` (Mistral via Ollama) in the local `.env`. The router uses kNN only with local/none. **Skill analysis uses the rule-based extractor in local mode**, because Mistral 7B invented a "Kubernetes" gap for a JD without it.
- **Deployed path end to end** (no keys/.env, in-process, AppTest from another folder): Analyze Profile 15.2 s, no errors, exact gaps, 20 jobs.
- **Verified:** Gemini key → 31 models, test `OK`. Visitor A answers via `gemini-3.1-flash-lite`, Analyze Profile via the key (19 s), LLM roadmap valid. Visitor B (no key) is retrieval-only and unaffected. Key absent from os.environ and the chat log.
- **Tests:** 21 → **25** (thread isolation, label/secret/redaction, model builders, no-key/no-dotenv pipeline import).

## 2026-11-08: E28 Bug: app failed to start (`ModuleNotFoundError: No module named 'src'`)
- **Cause:** the E26 refactor that centralised `.env` loading placed `from src.utilities.env import load_env` *above* the line that adds the project root to `sys.path` in `frontend.py`. `streamlit run` (and Streamlit Cloud) only put the script's own folder on `sys.path`, so every page load failed. The headless tests missed it because they ran from the repo root.
- **Fix:** `sys.path.insert(0, <root>)` is now the first thing in `frontend.py`.
- **Regression test:** `tests/test_app_boot.py` boots the real script with AppTest from a temporary directory (like Streamlit Cloud). Verified it **fails without the fix** and passes with it. 21/21 tests pass.
- **Verified in a real browser** (headless Chrome via Selenium) on both instances: page renders, the starter question returns cited career answers with a Sources panel, and the off-topic question is refused. No tracebacks in either server log.

## 2026-11-08: E27 Local LLM (Mistral 7B via Ollama), keyless
- `LLM_PROVIDER=local`, prompt v4, production router (kNN + Mistral for ambiguous messages), 42 cases. Measured latency **35–55 s per answer** (16 GB Mac, 3–4k-token prompts), too slow for a public demo, fine offline.
- **Result (42/42 cases): pass 0.881**. All 12 refusals and the equivalence/salary cases are correct, but there are **no citations in 4 answers (citation rate 30%)**, career_reco 0/2 and weak evidence 1/2. Median 46.5 s per LLM answer. Conclusion: local mode is usable offline but weaker than v4 on a hosted model (1.0) and retrieval-only (1.0, with the tuning caveat). Details in [keyless_mode.md §5](keyless_mode.md#5-local-llm-results-mistral-7b-via-ollama).

## 2026-11-08: E26 Keyless mode + per-visitor isolation
- **Question asked:** can the system run without Gemini/Groq? Embeddings and retrieval never needed keys. Generation now has three modes: `api | local | none` (`src/utilities/llm_provider.py`, `LLM_PROVIDER=auto`).
- **Retrieval-only replacements:** chat composer (`extractive_answer.py`), rule-based skill extractor (864-term vocabulary from aliases + dataset; case-sensitive for "Go"/"Excel"), template summary, Tavily skipped, template roadmap, no-LLM router (follow-ups classified together with the previous turn). Runtime fallback: `api` → … → Ollama → retrieval-only, so the chatbot never dead-ends.
- **Keyless pipeline:** 15.2 s, the same 4 gaps as the LLM version (Tableau, Statistics, Data Visualization, Communication), ATS estimate 43 (the LLM said 65–70), 30 jobs, 12 course links.
- **Keyless eval (42 cases):** first run 0.952 (doc07 Docker/Kubernetes, doc09 vague no-profile). Added an equivalence rule (IMPLIES/RELATED) and follow-up questions when no profile → **1.0, 0 tokens, 0.24 s/answer**, router allow/refuse 1.0. Optimistic: rules were tuned on this set.
- **Privacy bug found and fixed:** all visitors shared `memory.json`, the `default` profile chunks and a process-wide cached result. Now there's a per-session id (URL `?u=`), `user_memory/<id>.json`, `user_id`-filtered retrieval, and `user_id` in the API. Verified: a new visitor's "What are my skill gaps?" → "I don't see an analysed profile yet".
- `.env` loading is centralised (`src/utilities/env.py`); `SKILLPATH_NO_DOTENV=1` runs a keyless instance from the same checkout without picking up any keys.
- Zero-secret Streamlit Cloud deploy verified by simulation (`auto` → none/local/in-process). A public cloudflared tunnel was blocked by the local safety policy and left to the team.
- Tests: 12 → **20** (provider resolution, LLMUnavailable, extractor, ambiguous words, composer clarification/citations/equivalence, per-user memory path + traversal).

## 2026-11-08: E25 v4 re-check on gpt-oss-120b: attempted, quota-bound
- Strict paired run (`--versions v4 --expect-model openai/gpt-oss-120b --sleep 30`): case 1 (cs01) passed on 120b, then case 2 was answered by the gpt-oss-20b fallback (120b at the org's daily/per-minute cap), so the run stopped with 1/42 cases. **Not conclusive. Still pending.**
- Bug fixed: when a paired run stopped, the saved `_meta.stopped` stayed `None`. The stop reason is now written to the report.
- Re-run when the Groq org quota is fresh (about 100k tokens for the 30 LLM-answered cases):
  `python -m src.eval.run_prompt_eval --router-modes knn --versions v4 --router hybrid --paired --expect-model openai/gpt-oss-120b --sleep 30`

## 2026-11-08: E24 Career Advisor UI redesign
- **Problem:** the chatbot tab was rendered only inside `if pipeline_data`, so a student without a CV (journey B) never saw it.
- **Change:** Career Advisor is now the always-visible first tab (`src/frontend/advisor_ui.py`): status chips, starter questions for both journeys, a sources expander, an "Explain" panel (route, retrieved records + scores, model, latency), thumbs feedback logged to `reports/chat_logs/feedback.jsonl`, and new-chat/save. The analysis tabs show guidance until a profile exists.
- **Verified** with Streamlit `AppTest` (headless): 5 tabs, no exceptions. Starter "Which career fits Python, SQL and dashboards?" → career_study (kNN), 10 hits (career_2059, 2061, 2482, 2060…), answered by gpt-oss-120b. Recipe question → out_of_scope refusal.
- **Linux build simulation (E23) passed:** uv install 238 s, torch 2.15.0+cpu (no CUDA), 12/12 tests, Streamlit health ok.

## 2026-11-08: E23 Streamlit Community Cloud readiness
- `requirements.txt`: CPU torch is pinned by **direct wheel URL** (cp312, x86_64) instead of `--extra-index-url`, because uv (Streamlit Cloud's installer) prefers an extra index for *every* package. A root `.streamlit/config.toml` was added (Cloud reads config from the repo root).
- **Atlas + Streamlit Cloud:** Streamlit's fixed outbound-IP allowlist is retired, so Atlas would need `0.0.0.0/0`. Opening it was blocked by the local safety policy and is left to the team's decision (deployment.md §3a, variant B).
- **Self-building local index:** `ensure_local_corpus()` builds the careers/knowledge/jobs vectors on first use when the local store is empty. Measured: first retrieval 14.2 s (2,899 + 170 vectors), next 0.01 s. The app is deployable today without any Atlas change (variant A).
- Linux build simulated in Docker (`linux/amd64`, python:3.12-slim, uv). Result in `reports/streamlit_cloud_sim.log`.

## 2026-11-08: E22 v3 vs v4: paired A/B complete → **v4 activated**
- Production config (hybrid router, Atlas), paired + strict model `gemini-3.1-flash-lite` (all Groq models capped, E21), 42/42 pairs, 0 errors. Router (hybrid, flash-lite as router LLM) 1.0 accuracy on 42 cases.
- **Harness fix after reading answers:** `no_profile` cases still retrieved the stored profile from Atlas ("Based on your profile, you have Python, SQL…"), and `asks_question` accepted a single "?". Now no-profile also sets the profile quota to 0, and clarification needs at least 2 questions. doc06/doc09 were re-run.
- **Result:** v3 0.952 (fails both weak-evidence cases), **v4 1.0**. All other categories 1.0 for both. v4 asks 3 clarifying questions; v3 guesses or only says "upload your resume". Salary: v3 refuses, v4 explains there's no data and gives verification sources. Cost: v4 +21% tokens/answer (3,116 vs 2,571).
- Files: `reports/prompt_eval/ab_v3_v4_paired_gemini_lite.json`, `weak_evidence_fixed_harness.json`, logs in `reports/prompt_eval/logs/`.
- Pending (quota-bound): LLM-judge pass with gpt-oss-120b; v4 re-check on gpt-oss-120b.

## 2026-11-08: E21 Quotas are per Groq organisation; deployment constraints
- **Finding:** both Groq keys belong to the same organisation (`org_01m5j33q…`). Groq daily limits are per org, so the second key added **no** capacity. By the evening every Groq model was at its 200k tokens/day: gpt-oss-120b 198,577, qwen3.8-27b 199,597, gpt-oss-20b 199,697. gemini-3.5-flash was also exhausted (RESOURCE_EXHAUSTED).
- **Gemini Flash-Lite has a separate quota.** `gemini-3.1-flash-lite` was added as the last fallback in `brain._FREE_TIER_MODELS`, so the live chatbot keeps answering when Groq is exhausted.
- **Hugging Face:** `402 Payment Required`, Docker/Gradio Spaces on free CPU now need HF PRO. Free route: Streamlit Community Cloud. The UI now runs the pipeline in-process when no API server is reachable (`src/backend/pipeline_service.py`, `PIPELINE_MODE`).
- **Bug fixed:** `asyncio.gather` in `scrape_jobs_node` had no exception handling, so a Naukri/Selenium failure (e.g. no Chrome) crashed the whole pipeline. Each scraper now fails independently.
- `requirements.txt`: CPU-only torch on Linux (`torch==2.15.0+cpu`); unused `torchvision` removed.

## 2026-11-08: E20 MongoDB Atlas live
- Created with the Atlas CLI: project **SkillPath AI**, cluster **skillpath-cluster** (M0, AWS Mumbai), DB user `skillpath_app` (random password, only in `.env`), current-IP access.
- Ingested: careers (2899, 384), knowledge (17, 384), jobs (153, 384), profile (39, 384). All finite and aligned.
- `check_atlas`: 3 indexes READY/queryable. "Python SQL data analyst" → career_0682 Data Analyst 0.520, career_0689 0.518, career_0662 0.515, career_0093 0.507, career_0306 0.505.
- **Parity:** Atlas ANN top 5 = exact local top 5 (5/5) for "Which career fits Python, SQL and dashboards?".
- **Latency:** full retrieval (4 searches) median **359 ms**, p95 419 ms (local: 9 ms).

## 2026-11-08: E19 Atlas M0 allows at most 3 search indexes
- The 4th index (`knowledge_vector_index`) failed: `The maximum number of FTS indexes has been reached for this instance size`.
- **Change:** jobs moved into `knowledge_chunks_v1` (filtered by `source=jobs`); `job_listings_v1` dropped. Index deletion is asynchronous, so the retry needed about 30 s.

## 2026-11-08: E18 Second Groq key + quota-aware evaluation
- New `GROQ_API_KEY` (fresh 200k tokens/day); the exhausted key becomes `GROQ_API_KEY_2`. `get_robust_llm` now tries **the same model on key 2** before weaker models.
- Measured cost: one in-scope answer ≈ **3.3k tokens** (2.4–2.9k input, 0.4–0.9k output). A full 84-call router-off A/B ≈ 280k tokens, more than one key's daily cap. gpt-oss-120b also has a per-minute token cap (~8k), so back-to-back calls fall back to gpt-oss-20b.
- **New eval design:** `--paired --expect-model openai/gpt-oss-120b --sleep 30`. Versions alternate on each case; the run stops the moment another model answers, so every completed pair is a same-model comparison. It runs in production mode (hybrid router), so the 12 refusals cost no LLM calls (~60 LLM calls in total). Token usage is recorded per row.
- Spot check doc09 ("I like music and painting…", no profile): v3 guessed careers; v4 asked 3 clarifying questions (answered by the 20b fallback, which is why the strict design was needed).

## 2026-11-08: E17 v3 on the 42-case set; v4 A/B paused by the daily token cap
- **v3 (router off, gpt-oss-120b 35/42, qwen 7/42): pass rate 0.929**, citation rate 43%. Failures: cs04 (no citation), cs08 (flagged as a refusal, to inspect), doc09 (weak evidence: guessed careers instead of asking). weak_evidence 0.5.
- v4 started, then Groq returned `429 tokens per day (TPD): Limit 200000, Used 199166`. Comparing v4 on fallback models against v3 on 120b would be confounded, so **the run was stopped**. v3 stays active.
- Eval hardening: results are now saved after every version (previously only at the end, so the v3 rows of this run exist only in `reports/prompt_eval/logs/run_v3_v4_router_off.log`). The judge runs offline with `--judge-file`, paced, resumable, with no fallback chain.

## 2026-11-08: E16 30-day roadmap generator, first run
- Data-analyst profile, 90 min/day: gaps ordered by market share in the role's career records (Data Visualization 0.32, Tableau 0.24, Statistics 0.24, Communication 0.00) → 7/6/6/5 learning days.
- `valid: true` with 0 repairs. LLM-filled in 42 s. [skills_and_roadmap.md](skills_and_roadmap.md).

## 2026-11-08: E15 Prompt v4 (project-doc rules) + 10 new eval cases
- **Change:** v4 = v3 + untrusted-context rule, career-recommendation rules (cite `career_XXXX`, give reasons), a weak-evidence → clarifying-questions rule driven by a `MATCH STRENGTH` context line, related ≠ equivalent skills, the salary-placeholder rule, and the ATS-estimate disclaimer. `few_shots_v4.json` adds weak-evidence and career-recommendation examples.
- **Eval set:** 32 → 42 cases (the doc §9.4 test classes: career, ambiguous "What about AI?", IPL 2026, sports analyst, adversarial cricket, weak evidence ×2, Docker vs Kubernetes, salary, security careers). Weak-evidence cases run with `no_profile`.
- Retrieval quotas: careers 2 → 4, jobs 2 → 1 (the career KB is now the source of truth).
- **Results:** [prompt_scripting.md §5](prompt_scripting.md#5-results).

## 2026-11-08: E14 Gemini 2.5 Flash retired
- `gemini-2.5-flash` → 404 "no longer available". It was the primary model for brain/net_surf/summarise and the eval judge. **The E9 judge scores were produced by Groq fallbacks** (same family as the answer model, so self-preference bias is possible).
- **Change:** `GEMINI_MODEL=gemini-3.5-flash`, and `.text` is used instead of `.content` everywhere (Gemini 3.x returns a list of parts; the judge parser was failing on it). The judge model used is now recorded per row.

## 2026-11-08: E13 New source-of-truth dataset + dedicated Atlas collections
- `docs/emerging_tech_career_dataset_cleaned.csv` (2,900 × 13) replaces the 3-column CSV. **No title dedupe**: 193 of 194 repeated titles have different skill sets. career_id 12 ("393360") is excluded. Result: **2,899 × 384 vectors, finite and aligned**.
- Storage split per doc §8/§12: `skillpath_ai.careers_embeddings_v1`, `knowledge_chunks_v1`, `job_listings_v1`, `user_profile_chunks_v1` (private). Idempotent upsert + prune. Model guard on Atlas reads.
- Data-quality report: 2,848 placeholder salaries and 2,897 placeholder growth values. They're flagged and hidden from answers.

## 2026-11-08: E12 MiniLM recalibration
- `RAG_MIN_SCORE` 0.60 → 0.30 (off-topic ≤ 0.243, in-scope ≥ 0.39). `CAREER_MIN_SCORE` = 0.40. Router top-sim 0.70 → 0.55.
- Router on 42 cases: kNN 0.952 label accuracy (allow/refuse 1.0), **hybrid 1.0** (21 LLM calls).

## 2026-11-08: E11 Labelled career-retrieval benchmark → back to MiniLM
- 24 labelled queries, Precision@5, models × text variants (table in [embeddings.md §2](embeddings.md#2-model-choice)). **MiniLM + full text: strict-P@5 0.767** vs bge 0.733. Adding domain + description gave +6 points over the pilot text.
- Switched `EMBEDDING_MODEL` back to MiniLM, which also keeps compatibility with the team starter kit.

## 2026-11-08: E10 Refusal detector fix #2 (curly apostrophes) + offline rescoring
- The model writes "can’t" (U+2019), which the regex missed. Fixed, and `--rescore` re-checks stored answers without LLM calls. The E9 numbers below are rescored.
- **E9 result (router off, 32 cases):** pass rate v1 0.75 → v2 0.969 → v3 0.969. Judge (Groq fallback) relevance 4.38 / 3.88 / **5.0**, groundedness 3.72 / 3.62 / **4.72**, scope 4.16 / 4.91 / **5.0**. v2's only failure was cs02, copying its fake few-shot turn. **v3 activated.**

## 2026-11-08: E9 Clean prompt A/B v1 vs v2 vs v3 (+ production config)
- **Runs:** (a) `--router off --versions v1 v2 v3 --judge` (b) `--router hybrid --versions v3 --judge`, after the fixes from E5a–E8.
- **Results:** [prompt_scripting.md §5](prompt_scripting.md#5-results). Reports: `reports/prompt_eval/prompt_eval_router_off.md`, `prompt_eval_production.md`, logs in `reports/prompt_eval/logs/`.

## 2026-11-08: E8 Prompt v3: few-shots moved into the system prompt
- **Problem (seen in E5a and a live test):** v2 injected few-shots as fake *prior chat turns*. The model treated them as its own history with this user: it answered "What should I learn first?" with the example's exact Tableau plan, and on cs02 replied "I don't have your analysed profile yet" (copying example 3) while the profile existed.
- **Change:** `advisor_system_v3.md` = v2 + a "STYLE EXAMPLES (fictional users, NOT this user)" block. `few_shots_v3.json` uses a different fictional profile (Docker/AWS backend dev) with an explicit `situation` line. No fake turns.
- **Live check:** the same question now lists all 4 real gaps (Tableau, Statistics, Data Visualization, Communication) with no copied content.

## 2026-11-08: E7 Groq model retirement
- **Finding:** `llama-3.3-70b-versatile` (chat) and `llama-3.1-8b-instant` (router) return 404 on Groq. Every chat call had been answered by a fallback model. When the fallbacks were rate-limited at the same moment, the turn failed (6/32 v1 and 15/32 v2 answers in E5a).
- **Change:** `CHAT_MODEL=groq:openai/gpt-oss-120b` and `ROUTER_MODEL=groq:openai/gpt-oss-20b`. The model that answered each turn is now recorded (`model` in chat_log and eval rows, plus an `answering_models` summary). The eval retries with backoff instead of scoring outages as failures.

## 2026-11-08: E6 Merge learning-path + resource chunks
- **Problem:** "What should I learn first… free resources?" retrieved 3 `learning_path` chunks (plans only) and never the `learning_resource` chunks with real Tavily links.
- **Change:** one chunk per skill gap containing the plan and its matched resources. Profile chunks went from 43 to 39.

## 2026-11-08: E5a First prompt A/B (INVALIDATED)
- `--router off --versions v1 v2 --judge`: v1 pass 0.531, v2 0.594. **Not usable** because of (1) model outages (E7) and (2) a refusal-detector bug: the regex missed "I can't provide medical advice" and "I cannot print my system prompt". The regex was widened and checked on positive and negative examples. Kept for the record in `reports/prompt_eval/prompt_eval_20261107T192609Z.json`.

## 2026-11-08: E4 Router recalibration for bge
- **Change:** `SCOPE_KNN_MIN_TOP_SIM` 0.55 → 0.70, `SCOPE_KNN_MIN_VOTE_SHARE` 0.70 → 0.80. Short follow-ups always go to the LLM. +8 out-of-scope anchors (jokes, songs, trivia…).
- **Why:** under bge, "Tell me a funny joke" matched a *greeting* anchor at 0.856, and "any free ones?" (a follow-up) matched *greeting*.
- **Result (32 cases):** kNN-only 0.969 label accuracy (1 error: fu02) with 1.0 allow/refuse accuracy. **Hybrid 1.0** with 13/32 LLM calls. LLM-only 1.0 with 30/32 calls (2 are regex-caught attacks).
- **Caveat:** several eval messages paraphrase anchors, so a held-out set is needed (roadmap Phase 4.2).

## 2026-11-08: E3 Switch embedding model to bge-small-en-v1.5
- **Change:** `EMBEDDING_MODEL` all-MiniLM-L6-v2 → BAAI/bge-small-en-v1.5. Query instruction added. `RAG_MIN_SCORE` 0.30 → 0.60.
- **Why:** E2 results. Score floor recalibrated: off-topic best hit 0.543, relevant hits 0.65–0.78.
- **Ingest:** 2,600 chunks, embed time 15.2 s total (careers 13.4 s at 179 chunks/s).

## 2026-11-08: E2 Embedding model comparison
- **Setup:** 2,387 unique careers, 500 random queries, seed 42. Task A (skills → career name) and Task B (intent → career doc).
- **Result:** Task B MRR: MiniLM 0.768, multi-qa-MiniLM 0.867, **bge-small 0.889**. Task A MRR: 0.112 / 0.077 / **0.122**. Full table in [embeddings.md §2](embeddings.md#2-model-choice).

## 2026-11-08: E1 First full ingestion (MiniLM, local store)
- careers 2,387 (12 case-duplicates dropped), jobs 153, profile 43, knowledge 17. Embed ~265 chunks/s.
- Bug found: duplicate chunk ids inside one batch crashed the local upsert. Fixed by deduping before embedding.

## 2026-10-28: E0 Team baseline (`embedding_experiment/test_embeddings.py`)
- MiniLM on the first 100 careers. Shape (100, 384). Query "Python, machine learning and data analysis" → top "Analyst, Data" (0.393).
