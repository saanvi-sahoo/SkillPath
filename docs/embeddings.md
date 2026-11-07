# Embeddings: complete reference

This file records **every decision about embeddings** so it can be analysed, reproduced and changed later. When you change anything here, add a dated entry to [experiment_log.md](experiment_log.md). Section numbers like "doc §8" refer to `SkillPath_AI_End_to_End_Project_Documentation.pdf`.

## 1. What we embed

| Source | Collection (`skillpath_ai.*`) | File | Unit = 1 vector | Count | Shared? |
|---|---|---|---|---|---|
| **careers** (source of truth) | `careers_embeddings_v1` | `docs/emerging_tech_career_dataset_cleaned.csv` | one career record (`career_id`) | **2,899** (2,900 − 1 excluded, §3) | shared |
| knowledge | `knowledge_chunks_v1` | `src/data/knowledge_base/*.md` | one `##` section | 17 | shared |
| jobs | `job_listings_v1` | LinkedIn `master_jobs_detailed.json` + Naukri `scraper/jobs.json` | one listing piece | 153 | shared |
| profile | `user_profile_chunks_v1` | `src/backend/memory.json` (latest analysis) | overview, resume and JD parts, skill gap + resources, matched jobs, summary | ~39 per run | **private** (`user_id`) |

**Why separate collections?** The project doc (§12) says to *never place sensitive resume contents in the shared career collection*. It also asks for a dedicated career collection that doesn't overwrite inherited collections (§8.1, step 17). Each collection has its own vector index (`career_vector_index`, `knowledge_vector_index`, `jobs_vector_index`, `profile_vector_index`).

## 2. Model choice: `sentence-transformers/all-MiniLM-L6-v2` (384-d, cosine)

Two experiments were run:

**E2 (self-supervised, old 3-column CSV, 500 queries).** For "I want to become a <career>" against career documents, bge-small (MRR 0.889) beat MiniLM (0.768). But the query contains the target's own title, which flatters asymmetric models.

**E11 (labelled, new dataset, the doc §13 acceptance test).** 24 natural student questions in `src/eval/career_queries.jsonl`, each labelled with acceptable domains and relevant skill keywords. Measured P@5 over 2,900 records (`python -m src.eval.evaluate_career_retrieval`):

| Model | Text variant | Domain-P@5 | Keyword-P@5 | **Strict-P@5** (both) |
|---|---|---|---|---|
| MiniLM | pilot (name + skills) | 0.725 | 0.942 | 0.708 |
| MiniLM | + domain | 0.775 | 0.917 | 0.750 |
| **MiniLM** | **+ domain + description** | **0.800** | 0.908 | **0.767** |
| bge-small | pilot | 0.667 | 0.942 | 0.658 |
| bge-small | + domain | 0.742 | 0.950 | 0.725 |
| bge-small | + domain + description | 0.775 | 0.925 | 0.733 |

**Decision: MiniLM with the "full" text.**
1. It's best on the labelled benchmark, the one closest to real use.
2. **Team compatibility:** the team's embedding starter kit (doc §8.4) writes MiniLM vectors. If code queried a MiniLM collection with another model, the results would be silently meaningless. The stores now refuse to search a collection whose `embedding_model` differs from the configured one.
3. It's the doc's stated baseline (§7.3).

The gap to bge is about 4 hits out of 120, so this is a close call. Re-run the benchmark when the labelled set grows.

**Error analysis (best configuration):**
- *"recommendation systems for e-commerce"* (P@5 0.2): the dataset has few recommender roles.
- *"sports analyst"*: correct analytical roles appear, such as "Analyst, Baseball Operations" and "Basketball Data Analyst", but the dataset labels them *Project and Business Management*. This is a label problem, not a retrieval problem.
- *"Python, SQL and dashboards"*: returns Python data-engineering roles over BI analyst roles.

**Model details**
- Vectors are L2-normalised, so cosine equals the dot product (exact local search, and it matches Atlas `similarity: cosine`).
- MiniLM truncates at 256 tokens. The longest career text is 211 words (about 280 tokens), so a few long descriptions lose their tail. The skills come before the description, so they're never cut.
- MiniLM needs no query instruction. `config._QUERY_INSTRUCTIONS` covers models that do (e.g. bge).

## 3. Career records: validation, exclusions, embedding text

`load_career_frame()` + `build_career_chunks()` in `src/rag/documents.py`:

| Rule | Why |
|---|---|
| Required columns present, `career_id` unique (else fail) | Stable record ID ↔ vector alignment (doc §8.2) |
| **No deduplication by title** | 194 titles repeat, and 193 of them have *different* skill sets (e.g. 29 × "Data Engineer"). They're distinct profiles (doc §6.4) |
| Exclude titles with no letters → **career_id 12 "393360"** | Not a career. It came top for "Recommend me a career" (score 0.48) |
| Embedding text = `Career: {name}. Domain: {domain}. Required skills: {skills}. Description: {description}` | E11 variant "full" (+6 strict-P@5 points over the pilot text) |
| Metadata stored next to the vector: education, domain, salary, growth, `salary_is_placeholder`, `growth_is_placeholder`, basis/quality notes | Grounding and honest caveats |
| `_id = career_{id:04d}` (e.g. `career_0001`) | Doc §8.2 schema. Cited in answers |

**Salary and growth are placeholders for most rows:** 2,848 rows have 140,100 and 2,897 have growth 0.05 (see `reports/data_quality/career_dataset_report.md`). Only non-placeholder values reach the LLM, labelled "dataset value, unverified" (prompt v4 rule 11).

Full data-quality audit: `python -m src.eval.career_data_quality`.

## 4. Other sources: chunking

| Parameter | Value | Reason |
|---|---|---|
| `CHUNK_MAX_WORDS` / overlap | 150 / 30 | Within MiniLM's 256-token limit |
| Jobs | header (title, company, location, skills, experience, salary) repeated on each description piece | Pieces stay self-describing |
| Profile `learning_path` | one chunk per skill gap = plan + matched curated resource links (E6) | Separate chunks meant links never got retrieved |
| Knowledge | split on `##` headings | One topic per chunk |

## 5. Document schema

Career collection (top-level fields per doc §8.2, plus the generic fields):
```json
{
  "_id": "career_0001", "career_id": "career_0001",
  "career_name": "(Senior) Data Partnerships Manager", "domain": "Project and Business Management",
  "required_skills": "Data Management Platforms, Programmatic Advertising, Telecommunication",
  "education_required": "Bachelor's degree in a relevant field; …", "description": "…",
  "average_salary": 140100.0, "salary_is_placeholder": true, "job_growth_rate": 0.05, "growth_is_placeholder": true,
  "text": "Career: … Domain: … Required skills: … Description: …", "embedding_text": "(same)",
  "source": "careers", "doc_type": "career_profile", "user_id": "global", "metadata": {…},
  "embedding": [384 floats], "embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "ingested_at": "…"
}
```
Vector index (same definition on every collection; created by `ensure_index()`):
```json
{"fields": [
  {"type": "vector", "path": "embedding", "numDimensions": 384, "similarity": "cosine"},
  {"type": "filter", "path": "source"}, {"type": "filter", "path": "user_id"},
  {"type": "filter", "path": "doc_type"}, {"type": "filter", "path": "domain"}
]}
```

## 6. Ingestion

```bash
python -m src.rag.ingest --sources all                    # Atlas if MONGODB_URI is set, else local
python -m src.rag.ingest --sources careers --backend mongo
python -m src.rag.ingest --sources careers --limit 100    # partial run (no pruning)
```
- **Idempotent:** upserts by `_id`, then **prunes** records the builder no longer produces (e.g. career_0012). Profile chunks are deleted per user before re-inserting.
- Every run checks `shape == (n, 384)` and that all values are finite (`finite_and_aligned`). Everything goes to `reports/embeddings/ingestion_log.jsonl`: model, collection, shape, counts, duplicates, pruned, words, and timings.
- Latest local run (2026-11-08): careers **(2899, 384)** in 13.8 s (211 records/s), jobs (153, 384), profile (39, 384), knowledge (17, 384). All finite and aligned.

## 7. Score calibration (MiniLM)

| Threshold | Value | Evidence |
|---|---|---|
| `RAG_MIN_SCORE` | 0.30 | Off-topic best hits: recipe 0.243, cricket 0.220, poem 0.169. In-scope best hits 0.39–0.69 |
| `CAREER_MIN_SCORE` (weak match → ask clarifying questions) | 0.40 | "I like music and painting" 0.276, "I enjoy helping people" 0.324 → weak. "Python, SQL, dashboards" 0.722 → OK |
| Router `SCOPE_KNN_MIN_TOP_SIM` / `VOTE_SHARE` | 0.55 / 0.80 | In-scope messages as low as 0.375 go to the LLM router. Hybrid accuracy 1.0 on 42 cases |

A similarity score is **not** a measure of fit or employability (doc §1.2). "Recommend me a career" scores 0.48 while carrying no information, so missing evidence is also handled by prompt rule 9.

## 8. Limitations and next steps
- Domain labels are classifier-assigned ("review borderline roles"), so domain-P@5 is a weak-label metric.
- 1,379 descriptions were generated from title and skills. They help retrieval but are not independent evidence.
- The labelled set is small (24 queries). Grow it to 100+ from real chat logs (`reports/chat_logs/`).
- Possible upgrades: hybrid BM25 + vector search (Atlas `$search` + `$vectorSearch`), a cross-encoder re-ranker, and fine-tuning once labelled pairs exist.
