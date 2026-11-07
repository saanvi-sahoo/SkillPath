# Experiment log

Add one entry for every change to models, prompts, thresholds, chunking or data. Newest first. Raw outputs live in `reports/`.

---

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
