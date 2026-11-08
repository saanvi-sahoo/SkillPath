# Progress ledger

Updated **2026-11-08 (evening)**. This follows the evidence rule of the project doc (§2, §14.4): an item is **Verified** only if it was executed and its output is saved in `reports/`. Code that exists but hasn't been run end to end is marked as such.

| Area | What exists now | Status | Evidence |
|---|---|---|---|
| Environment | Python 3.12 `.venv`, `requirements.txt` (+pymongo, sentence-transformers, pandas, numpy) | ✅ Verified | Backend `/docs` 200, Streamlit 200 |
| Parsing (resume/JD) | `all_around_loader` (PDF/text/URL), Jina for URLs, Reducto optional | ✅ Verified (text input); 🟡 scanned PDFs need OCR | Pipeline run 2026-11-08 |
| LLM skill analysis | `brain.py` structured output (skills, gaps, ATS *estimate*, learning queries) | ✅ Verified | ATS 70, 4 gaps on the test profile |
| Full pipeline | LangGraph `/pipeline/run`: parse → analyse → LinkedIn + Naukri scraping, Tavily resources, summary | ✅ Verified end to end | 200 OK in 12.5 s, 30 jobs, 12 resources |
| LLM availability | Groq retired llama-3.3/3.1 and Google retired gemini-2.5-flash. Migrated to gpt-oss-120b/20b and gemini-3.5-flash; the answering model is logged | ✅ Fixed | experiment_log E7, E14 |
| **Career dataset (source of truth)** | `docs/emerging_tech_career_dataset_cleaned.csv`, 2,900 × 13, validated loader | ✅ Verified | `reports/data_quality/career_dataset_report.md` |
| Data quality | Audit script: duplicates, placeholders (2,848 salaries), 1 junk title excluded | ✅ Verified | same report |
| **Full-dataset embeddings** | MiniLM 384-d, "full" text variant, **2,899 × 384**, finite and ID-aligned | ✅ Verified (local + Atlas) | `reports/embeddings/ingestion_log.jsonl` |
| Embedding model selection | 3-model self-supervised test + 24-query labelled P@5 benchmark | ✅ Verified | `reports/embeddings/career_retrieval_latest.md` (strict-P@5 0.767) |
| **MongoDB Atlas** | Cluster `skillpath-cluster` (M0, Mumbai), project SkillPath AI; `skillpath_ai` with 3 collections + 3 vector indexes (M0 maximum); idempotent upsert/prune; model guard | ✅ **Verified live**: 2,899 careers + 170 knowledge/jobs + 39 profile chunks; indexes READY; real query OK; Atlas = exact top-5 (5/5); 359 ms median | `reports/embeddings/atlas_check_latest.txt`, [mongodb_atlas_setup.md](mongodb_atlas_setup.md) §0 |
| Career retrieval adapter | `retrieve_careers(query, top_k, domain)` + `CAREER_RAG_ENABLED` flag | ✅ Verified (local) | Smoke test: security query → career_2691 etc. (0.61–0.63) |
| **RAG** | Per-collection quotas, score floor, MATCH STRENGTH signal, `[S#]` citations + sources footer | ✅ Verified (local) | `/chat` debug responses |
| **Career Advisor chatbot** | Career/study-only scope guardrail (regex + kNN + LLM), RAG answers, `/chat` API; **always-visible first tab** with starters, sources, Explain panel, feedback | ✅ Verified | Router: hybrid 1.0 accuracy on 42 cases, 0 false refusals, 0 leaks |
| **Prompt script training** | Versioned prompts v1–v4, 42-case eval set (doc §9.4 classes), paired same-model A/B, deterministic checks, offline rescoring, offline LLM judge | ✅ **v4 active**: paired A/B v4 1.0 vs v3 0.952 (weak evidence 2/2 vs 0/2). 🟡 Judge pass + 120b re-check wait for Groq quota | [prompt_scripting.md](prompt_scripting.md) §5 |
| Skill normalisation + exact gap comparison | Aliases, categories, IMPLIES (MySQL ⇒ SQL), related ≠ equivalent | ✅ Verified (unit examples) | [skills_and_roadmap.md](skills_and_roadmap.md) |
| **30-day roadmap** | Prioritised (prerequisites + market share), validated, LLM-filled, template fallback; `/roadmap` + Streamlit | ✅ Verified (1 profile) | `reports/roadmaps/roadmap_*.json` (valid, 0 repairs) |
| Automated tests | `tests/test_core.py` + `tests/test_keyless.py`: 20 offline unit tests | ✅ 20/20 pass | `python -m pytest -q tests` |
| **Keyless mode** | `LLM_PROVIDER=api/local/none/auto`; retrieval-only composer, rule-based analysis, template summary/roadmap; graceful runtime fallback | ✅ Retrieval-only 42/42 (0 tokens, 0.24 s); local Mistral 0.881 (30% citations, ~46 s/answer) | [keyless_mode.md](keyless_mode.md) |
| **Per-visitor isolation** | Session id in URL, per-user memory files, `user_id`-filtered retrieval, API `user_id` | ✅ Verified (new visitor sees no one else's profile) | keyless_mode.md §4 |
| Documentation | 15 docs: runbook (every process), scenarios (every case, real outputs), deployment, experiment log E0–E17 | ✅ | `docs/` |
| GitHub (`saanvi-sahoo/SkillPath`) | Pushed (SSH key on saanvi-sahoo); personal data and secrets git-ignored; secret scan clean | ✅ | [deployment.md](deployment.md) |
| Hosting | **Hugging Face blocked**: Docker Spaces now need HF PRO (402). **Streamlit Community Cloud ready** (in-process pipeline mode, CPU torch, scraper-failure tolerance); needs one GitHub login at share.streamlit.io | 🟡 One browser step left | [deployment.md](deployment.md) §3 |

## Open items (in priority order)
1. LLM-judge pass on the v3/v4 answers + v4 re-check on gpt-oss-120b, when Groq quota resets.
2. Deploy on Streamlit Community Cloud with the prefilled form (deployment.md §3a). **Variant 0 needs no secrets at all** (keyless); variant B (Atlas) needs the team to allow `0.0.0.0/0`. Build pre-tested in Linux (E23).
3. Rotate the credentials that were shared in chat (Groq ×2, HF token, Atlas/HF account password).
4. Bigger held-out eval sets (100+ chat questions, 50+ career queries) from real usage.
5. Roadmap progress tracking and regeneration; LLM fallback for categorising unknown skills; OCR for scanned PDFs.
