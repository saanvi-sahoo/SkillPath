# SkillPath AI (formerly UpskillxAI) – Project Documentation

SkillPath AI (built on the previous batch's UpskillxAI) analyses a candidate's resume against a job description and produces:
- an ATS score
- skill gaps
- a learning path
- matching jobs (LinkedIn and Naukri)
- learning resources
- a **Career Advisor chatbot** that answers only career and study questions, grounded in the candidate's own data through RAG over MongoDB Atlas Vector Search.

| Doc | What it covers |
|---|---|
| [evaluation.md](evaluation.md) | **Prompt training v7 + held-out evaluation (E36)**: 170 frozen unseen tests, metrics vs targets, skill-aware career re-ranking, citation correctness, profile isolation, v6 vs v7 A/B, shared results table, team workflow |
| [feedback_learning.md](feedback_learning.md) | **Precise answers + learning from 👍/👎**: question profiler, answer contract (prompt v5), feedback memory, router learning, verified tests |
| [byok.md](byok.md) | **Bring your own API key** on the deployed app (Groq / Gemini / OpenAI / OpenRouter), per-session and never stored; engine resolution; deployment fixes |
| [keyless_mode.md](keyless_mode.md) | **Run without Groq/Gemini**: retrieval-only and local-LLM (Ollama) modes, what replaces the LLM, measured quality, per-visitor isolation |
| [runbook.md](runbook.md) | **Every process step by step**: setup, run, ingest, Atlas, evals, prompt changes, roadmap, deploy |
| [scenarios.md](scenarios.md) | **Every scenario**: student journeys, chat cases (with real outputs), embedding/data, RAG, prompt-training and failure cases |
| [architecture.md](architecture.md) | End-to-end system, components, data flow, folder map |
| [embeddings.md](embeddings.md) | **Everything about embeddings:** model choice and benchmark, chunking per source, document schema, ingestion stats, score calibration, reproduction |
| [rag.md](rag.md) | Embedding search vs. RAG decision, retrieval strategy, context format, citations |
| [skills_and_roadmap.md](skills_and_roadmap.md) | Skill normalisation, exact gap comparison, validated 30-day roadmap |
| [status.md](status.md) | **Progress ledger**: what is done, verified, pending (mirrors the project doc's ledger) |
| [mongodb_atlas_setup.md](mongodb_atlas_setup.md) | Creating the Atlas cluster, connection string, vector index, verification |
| [chatbot.md](chatbot.md) | Career Advisor chatbot: turn flow, scope guardrail, API, logging |
| [prompt_scripting.md](prompt_scripting.md) | Prompt engineering ("prompt script training"): versions, eval set, metrics, results, how to iterate |
| [deployment.md](deployment.md) | GitHub push and Hugging Face Space deployment; what is never published |
| [experiment_log.md](experiment_log.md) | Dated log of every experiment and parameter change |
| [roadmap.md](roadmap.md) | Status of every workstream and next steps |

## Quick start

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in GROQ, GEMINI, TAVILY (+ MONGODB_URI for Atlas)

# 1. Build the vector index (local fallback if MONGODB_URI is empty)
python -m src.rag.ingest --sources all
# 2. Backend + frontend
uvicorn src.backend.fastapi_ends.api_endpoint:app --port 8000
streamlit run src/frontend/frontend.py
```

## Evaluations (re-run after any change)

```bash
python -m src.eval.career_data_quality              # dataset audit
python -m src.eval.evaluate_career_retrieval        # labelled P@5 benchmark
python -m src.eval.evaluate_embeddings --models BAAI/bge-small-en-v1.5 sentence-transformers/all-MiniLM-L6-v2
python -m src.eval.run_prompt_eval --router-only            # fast, router only
python -m src.eval.run_prompt_eval --versions v3 v4 --router off --judge --judge-model gemini-3.5-flash
python -m src.eval.heldout_offline                  # held-out: career P@5, 20 roadmaps, profile isolation (no LLM)
LLM_PROVIDER=api CHAT_MODEL=gemini-3.5-flash python -m src.eval.heldout_eval --versions v6 v7 --expect-model gemini-3.6-flash --workers 3
# E38 real-world reliability (docs/evaluation.md Part 3)
python -m src.eval.career_eval_v3 --sets v3          # career search through the production path, E37 vs E38
python -m src.eval.career_label_review               # dataset label review (nothing changed)
LLM_PROVIDER=api CHAT_MODEL=gemini-3.1-flash-lite python -m src.eval.heldout_eval --set heldout_v3 --versions v7 v7+e38 v8+e38 \
    --expect-model gemini-3.1-flash-lite --sleep 8      # 120 realistic cases ('+e38' = with the E38 pipeline)
LLM_PROVIDER=api CHAT_MODEL=groq:openai/gpt-oss-120b python -m src.eval.journey_eval --versions v7 v7+e38 --expect-model openai/gpt-oss-120b
python -m src.eval.claim_audit export reports/heldout/heldout_eval_<run>.json   # citation-checker audit sample
python -m src.eval.progress                          # progress bars for running evaluations
```

Reports are written to `reports/embeddings/` and `reports/prompt_eval/`, and every ingestion run is appended to `reports/embeddings/ingestion_log.jsonl`.

## Glossary
| Term | Meaning here |
|---|---|
| Embedding | 384-number vector from all-MiniLM-L6-v2 representing a text's meaning |
| Cosine similarity | Similarity of two normalised vectors (−1…1). A ranking signal, not a measure of fit |
| Vector index | Atlas Vector Search index enabling fast nearest-neighbour search (`$vectorSearch`) |
| RAG | Retrieve relevant records first, then let the LLM answer only from them, with citations |
| Chunk | One embedded unit (a career record, a guide section, a job piece, a profile piece) |
| MATCH STRENGTH | WEAK/OK signal from the best career similarity; WEAK → ask clarifying questions |
| Scope router | Guardrail deciding career_study / greeting / out_of_scope / prompt_attack |
| Prompt version | `advisor_system_vN.md`; changed only via a new version and an A/B eval |
| P@5 | Share of the top 5 results labelled relevant |
| ATS estimate | LLM-estimated keyword-match score. Not a validated ATS result |
