# Progress ledger

Updated **2026-11-08**. This follows the evidence rule of the project doc (§2, §14.4): an item is **Verified** only if it was executed and its output is saved in `reports/`. Code that exists but hasn't been run end to end is marked as such.

| Area | What exists now | Status | Evidence |
|---|---|---|---|
| Environment | Python 3.12 `.venv`, `requirements.txt` (+pymongo, sentence-transformers, pandas, numpy) | ✅ Verified | Backend `/docs` 200, Streamlit 200 |
| Parsing (resume/JD) | `all_around_loader` (PDF/text/URL), Jina for URLs, Reducto optional | ✅ Verified (text input); 🟡 scanned PDFs need OCR | Pipeline run 2026-11-08 |
| LLM skill analysis | `brain.py` structured output (skills, gaps, ATS *estimate*, learning queries) | ✅ Verified | ATS 70, 4 gaps on the test profile |
| Full pipeline | LangGraph `/pipeline/run`: parse → analyse → LinkedIn + Naukri scraping, Tavily resources, summary | ✅ Verified end to end | 200 OK in 12.5 s, 30 jobs, 12 resources |
| LLM availability | Groq retired llama-3.3/3.1 and Google retired gemini-2.5-flash. Migrated to gpt-oss-120b/20b and gemini-3.5-flash; the answering model is logged | ✅ Fixed | experiment_log E7, E14 |
| **Career dataset (source of truth)** | `docs/emerging_tech_career_dataset_cleaned.csv`, 2,900 × 13, validated loader | ✅ Verified | `reports/data_quality/career_dataset_report.md` |
| Data quality | Audit script: duplicates, placeholders (2,848 salaries), 1 junk title excluded | ✅ Verified | same report |
| **Full-dataset embeddings** | MiniLM 384-d, "full" text variant, **2,899 × 384**, finite and ID-aligned | ✅ Verified (local store) | `reports/embeddings/ingestion_log.jsonl` |
| Embedding model selection | 3-model self-supervised test + 24-query labelled P@5 benchmark | ✅ Verified | `reports/embeddings/career_retrieval_latest.md` (strict-P@5 0.767) |
| **MongoDB Atlas** | `skillpath_ai` with 4 collections and 4 vector indexes, created by code; idempotent upsert/prune; model guard; `check_atlas` verifier | 🟡 **Code ready, not executed.** No cluster exists yet. Atlas CLI is installed; needs a one-time `atlas auth login`, then `atlas setup` creates everything | [mongodb_atlas_setup.md](mongodb_atlas_setup.md) |
| Career retrieval adapter | `retrieve_careers(query, top_k, domain)` + `CAREER_RAG_ENABLED` flag | ✅ Verified (local) | Smoke test: security query → career_2691 etc. (0.61–0.63) |
| **RAG** | Per-collection quotas, score floor, MATCH STRENGTH signal, `[S#]` citations + sources footer | ✅ Verified (local) | `/chat` debug responses |
| **Career Advisor chatbot** | Career/study-only scope guardrail (regex + kNN + LLM), RAG answers, `/chat` API, Streamlit tab | ✅ Verified | Router: hybrid 1.0 accuracy on 42 cases, 0 false refusals, 0 leaks |
| **Prompt script training** | Versioned prompts v1–v4, 42-case eval set (doc §9.4 classes), deterministic checks, offline rescoring, offline LLM judge | ✅ v1→v3 measured (v3 active; 42-case pass rate 0.929); 🟡 v4 A/B paused by the Groq daily token cap, re-run when quota resets | [prompt_scripting.md](prompt_scripting.md) |
| Skill normalisation + exact gap comparison | Aliases, categories, IMPLIES (MySQL ⇒ SQL), related ≠ equivalent | ✅ Verified (unit examples) | [skills_and_roadmap.md](skills_and_roadmap.md) |
| **30-day roadmap** | Prioritised (prerequisites + market share), validated, LLM-filled, template fallback; `/roadmap` + Streamlit | ✅ Verified (1 profile) | `reports/roadmaps/roadmap_*.json` (valid, 0 repairs) |
| Documentation | 15 docs: runbook (every process), scenarios (every case, real outputs), deployment, experiment log E0–E17 | ✅ | `docs/` |
| GitHub (`saanvi-sahoo/SkillPath`) | Local repo, personal data and secrets git-ignored, secret scan clean; SSH key created for SagarSwain05 | 🟡 Push waits for the SSH key to be added on GitHub | [deployment.md](deployment.md) |
| Hugging Face deployment | Dockerfile, start script, Space README, `push_space.py` (private Space, secrets via API); token valid (user `saanvisahoo26`) | 🟡 Prepared; deploy after the GitHub push and Atlas | [deployment.md](deployment.md) |

## Open items (in priority order)
1. Atlas connection string → `ingest --backend mongo` + `check_atlas --query ...` (doc §14.3 checkpoint).
2. Finish the v4 A/B, activate the winner, judge offline (Gemini quota permitting).
3. Push to GitHub, then optionally deploy to a Hugging Face Space.
4. Bigger held-out eval sets (100+ chat questions, 50+ career queries) from real usage.
5. Roadmap progress tracking and regeneration; LLM fallback for categorising unknown skills; OCR for scanned PDFs.
