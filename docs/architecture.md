# Architecture

## 1. System overview

```mermaid
flowchart LR
    subgraph UI[Streamlit frontend :8501]
        D[Dashboard tabs] --- C[Career Advisor chat]
    end
    subgraph API[FastAPI backend :8000]
        P[/pipeline/run/] --> G[LangGraph pipeline]
        CH[/chat/]
    end
    D -->|resume + JD| P
    C -->|chat_with_agent| BOT[chatbot.py]
    CH --> BOT
    G -->|final state| M[(memory.json)]
    M -->|ingest_profile_safely| ING[src/rag/ingest.py]
    ING --> EMB[all-MiniLM-L6-v2 embedder]
    CSV[(emerging_tech_career_dataset_cleaned.csv<br/>source of truth)] --> ING
    RM[/roadmap/] --> RG[roadmap generator] --> RET
    EMB --> VS[(MongoDB Atlas skillpath_ai<br/>careers_embeddings_v1 · knowledge_chunks_v1 (+jobs)<br/>user_profile_chunks_v1)]
    BOT --> R[scope_router] --> RET[retriever] --> VS
    RET --> LLM[Groq gpt-oss-120b<br/>+ fallbacks]
```

## 2. Analysis pipeline (LangGraph, `src/backend/main_runner.py`)

```
START ─┬─ load_resume ─┐
       └─ load_jd ─────┴─ analyse ─┬─ scrape_jobs ──────┐
                                   ├─ net_surf (Tavily) ├─ summarise ─ END
                                   └─ resource_finder ──┘
```

| Node | Does | Key deps |
|---|---|---|
| load_resume / load_jd | Parse PDF, URL or text (`all_around_loader`, Jina reader for URLs) | pypdf, Jina |
| analyse | Extracts skills, ATS score, gaps and learning path as structured JSON (`brain.py`) | Groq / Gemini with fallbacks |
| scrape_jobs | LinkedIn (requests + BS4) and Naukri (Selenium) | webdriver-manager |
| net_surf | Finds a curated resource for each gap | Tavily + Gemini |
| resource_finder | Udemy, YouTube and Coursera search links | none |
| summarise | Career summary paragraph | LLM |

After a run, `/pipeline/run` writes the final state to `src/backend/memory.json` **and re-embeds it** (`ingest_profile_safely`), so the chatbot answers from the newest analysis. A run takes about 12 s end to end (measured 2026-11-08, data-analyst test profile).

## 3. RAG and chatbot layer (new)

| Module | Responsibility |
|---|---|
| `src/rag/config.py` | All tunables (model, dimensions, thresholds, Mongo names), overridable from env |
| `src/rag/embedder.py` | Singleton SentenceTransformer, `embed_texts` / `embed_query` / `embed_symmetric` |
| `src/rag/documents.py` | Source → `Chunk` builders (careers, jobs, profile, knowledge) |
| `src/rag/vector_store.py` | `MongoAtlasVectorStore` (`$vectorSearch`) and `LocalVectorStore` (numpy), same interface |
| `src/rag/ingest.py` | CLI: build, embed, upsert, log |
| `src/rag/retriever.py` | Per-source quota search, score filter, `[S#]` context formatting |
| `src/rag/check_atlas.py` | Atlas ping, index creation and status |
| `src/backend/scope_router.py` | Career/study guardrail (regex + embedding kNN + LLM) |
| `src/backend/chatbot.py` | Turn orchestration; `chat_with_agent()` used by Streamlit |
| `src/prompts/` | Versioned prompt templates, few-shots, router anchors |
| `src/eval/` | Embedding benchmark and prompt evaluation harness |
| `src/data/knowledge_base/` | Curated career and study guides (RAG corpus) |
| `src/skills/normalizer.py` | Skill aliases → canonical names, categories, exact gap comparison (related ≠ equivalent) |
| `src/roadmap/generator.py` | Prioritised, validated 30-day roadmap (`/roadmap`, Streamlit Learning Paths tab) |
| `src/eval/evaluate_career_retrieval.py` | Labelled P@5 benchmark (24 queries) on the career dataset |
| `src/eval/career_data_quality.py` | Reproducible dataset quality report |

## 4. Folder map (relevant parts)

```
src/
  backend/        pipeline, API, chatbot, scope_router, scrapers, loaders
  frontend/       Streamlit app
  rag/            embeddings + vector store + retrieval
  prompts/        templates/*.md, few_shots.json, scope_examples.json, registry.py
  eval/           evaluate_embeddings.py, run_prompt_eval.py, prompt_eval_set.jsonl
  data/knowledge_base/   *.md guides
  data/vector_store/     local fallback index (git-ignored, rebuildable)
reports/
  embeddings/     embedding_eval_*.json/md, ingestion_log.jsonl
  prompt_eval/    prompt_eval_*.json/md
  chat_logs/      chat_log.jsonl (git-ignored, has user text)
docs/             this documentation
```

## 5. Known gaps in the existing codebase

- These are empty stubs: `src/main.py`, `src/models/*`, `src/feature_engineering/*`, `src/visualization/*`, `FactChecker/`.
- `extract_imports.py` hardcodes a Windows path. `tempCodeRunnerFile.py` and `$null` are editor junk.
- **Google retired `gemini-2.5-flash`** (404, 2026-11-08). The pipeline's analyse, net_surf and summarise nodes had silently been running on Groq fallbacks. They now use `GEMINI_MODEL=gemini-3.5-flash` (in `brain.py`) and read `.text`, because Gemini 3.x returns content as a list.
- **Groq retired `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`** (checked against the Groq `/models` API on 2026-11-08). The old chatbot's primary model therefore always failed over silently. The chatbot now uses `gpt-oss-120b` and the router `gpt-oss-20b`. Models served at the time: gpt-oss-120b, gpt-oss-20b, gpt-oss-safeguard-20b, qwen3.8-27b, llama-prompt-guard-2 (22m/86m), allam-2-7b and whisper. 
- `embedding_experiment/.venv` is a broken Python 3.13 venv from another machine (1.1 GB) and is safe to delete.
