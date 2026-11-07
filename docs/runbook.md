# Runbook: every process, step by step

Commands run from the repository root with the virtualenv active (`source .venv/bin/activate`). Every process says what it **reads**, what it **writes**, and **how to check** it worked.

## 1. Set up a machine
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in GROQ_API_KEY, GEMINI_API_KEY, TAVILY_API_KEY (+ MONGODB_URI)
```
**Check:** `python -c "import src.backend.main_runner, src.backend.chatbot"` prints nothing (no error).

## 2. Run the application
```bash
uvicorn src.backend.fastapi_ends.api_endpoint:app --port 8000     # API: http://127.0.0.1:8000/docs
streamlit run src/frontend/frontend.py                            # UI:  http://localhost:8501
```
Restart the backend after any `.env` change, since environment variables are read at start-up.

| Endpoint | Purpose |
|---|---|
| `POST /pipeline/run` | Full analysis (resume + JD). Writes `memory.json` and re-embeds the profile |
| `POST /chat` | Career Advisor (`debug: true` returns the route and retrieved chunks) |
| `POST /roadmap` | 30-day roadmap (`from_profile: true` or explicit fields) |
| `POST /skills/compare` | Exact skill-gap comparison |
| `/jobs`, `/profiles`, … | Inherited scraping endpoints |

## 3. Audit the career dataset
```bash
python -m src.eval.career_data_quality
```
Reads `docs/emerging_tech_career_dataset_cleaned.csv`. Writes `reports/data_quality/career_dataset_report.md`.
**Check:** 2,900 rows, `career_id` unique, 0 missing values, exclusions listed.

## 4. Build the embeddings and vector store
```bash
python -m src.rag.ingest --sources all                 # backend: Atlas if MONGODB_URI is set, else local
python -m src.rag.ingest --sources careers --backend mongo
python -m src.rag.ingest --sources careers --limit 100 # experiment (no pruning)
```
Reads the CSV, the knowledge base, job JSONs and `memory.json`. Writes Atlas `skillpath_ai.*` collections (or `src/data/vector_store/<collection>/`), plus `reports/embeddings/ingestion_log.jsonl`.
**Check:** each source prints `shape [n, 384]` and `finite_and_aligned: True`. Careers = 2,899.

## 5. Connect MongoDB Atlas
Follow [mongodb_atlas_setup.md](mongodb_atlas_setup.md) (CLI path or click-by-click UI path). Then:
```bash
python -m src.rag.ingest --sources all --backend mongo
python -m src.rag.check_atlas --query "Python SQL data analyst"
```
**Check:** every index shows `queryable=True`; the counts match the ingestion output; the query prints 5 careers with scores.

## 6. Evaluate retrieval (embeddings)
```bash
python -m src.eval.evaluate_career_retrieval     # 24 labelled queries, P@5, models × text variants
python -m src.eval.evaluate_embeddings --models sentence-transformers/all-MiniLM-L6-v2 BAAI/bge-small-en-v1.5
```
Writes `reports/embeddings/career_retrieval_latest.md` and `embedding_eval_latest.md`.
**Check:** compare against [embeddings.md §2](embeddings.md#2-model-choice). Log the run in the experiment log.

## 7. Evaluate the chatbot (prompt script training)
```bash
python -m src.eval.run_prompt_eval --router-only --router-modes knn hybrid            # guardrail only, cheap
python -m src.eval.run_prompt_eval --versions v3 v4 --router off --sleep 3           # A/B prompts (~150k tokens)
python -m src.eval.run_prompt_eval --judge-file reports/prompt_eval/prompt_eval_<ts>.json --judge-model gemini-3.5-flash --sleep 7
python -m src.eval.run_prompt_eval --versions v4 --router hybrid                      # production config
python -m src.eval.run_prompt_eval --rescore reports/prompt_eval/prompt_eval_<ts>.json  # after changing a check
```
Writes `reports/prompt_eval/prompt_eval_<ts>.json/.md`. Every turn is also logged to `reports/chat_logs/chat_log.jsonl`.
**Check:** pass rate per category; `answering_models` mostly the intended model; `errors: 0`. Full procedure: [prompt_scripting.md §7](prompt_scripting.md#7-how-to-run-an-iteration-step-by-step).

## 8. Change a prompt / activate a version
1. Create `src/prompts/templates/advisor_system_vN.md` (and optionally `few_shots_vN.json`).
2. Run §7.
3. Set `ACTIVE["advisor_system"]` in `src/prompts/registry.py`, or `PROMPT_ADVISOR_SYSTEM=vN` in `.env`.
4. Restart the backend and Streamlit.
5. Log it in `docs/experiment_log.md`.

## 9. Teach the router a new message
1. Add the message to the right list in `src/prompts/scope_examples.json`.
2. Run `python -m src.eval.run_prompt_eval --router-only`.
3. Confirm there are 0 false refusals and 0 leaks.

## 10. Generate a 30-day roadmap
```bash
python -m src.roadmap.generator --from-profile --minutes 90
python -m src.roadmap.generator --role "data analyst" --have Python Excel --gaps SQL Tableau Statistics --minutes 60
python -m src.roadmap.generator --from-profile --no-llm          # deterministic template (no API)
```
Writes `reports/roadmaps/roadmap_<ts>.json`.
**Check:** `validation.valid: true`, `n_days: 30`, `all_gaps_covered: true`.

## 11. Run the full pipeline from the command line (no UI)
```bash
curl -X POST http://127.0.0.1:8000/pipeline/run -H 'Content-Type: application/json' \
  -d '{"resume_input":"<text or path>","jd_input":"<text, URL or path>","target_role":"data analyst","location":"Bangalore"}'
```

## 12. Publish code (GitHub) and deploy (Hugging Face)
See [deployment.md](deployment.md).

## 13. Daily-quota awareness (free tiers)
| Service | Limit seen | Impact |
|---|---|---|
| Groq gpt-oss-120b | 200k tokens/day | About one 2-version A/B per day. Chat falls back to gpt-oss-20b or qwen |
| Gemini 3.5 Flash (free) | per-minute/per-day limits | The judge is paced and resumable |
| Tavily (dev key) | monthly credits | net_surf resources per analysis |
| Atlas M0 | 512 MB storage | We use about 7 MB |
