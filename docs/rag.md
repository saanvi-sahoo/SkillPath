# RAG design

## 1. Decision: embeddings only, or RAG?

| Option | What it is | Verdict |
|---|---|---|
| Embedding search only | Return the nearest careers, jobs or guides as a ranked list | Good for **recommendation widgets** (e.g. "careers similar to your skills"), but can't answer questions like "why is my ATS score 70?" |
| Full-context prompting (the old chatbot) | Paste the whole `memory.json` into an LLM call | Cost and latency grow with data. It hit the context limit with 30 jobs, can't use the 2.4k careers or the guides, and has no citations |
| **RAG (chosen)** | Retrieve the ~9 most relevant chunks, then have the LLM answer only from them, with citations | Small prompts, scales to any corpus size, grounded answers that can be traced |

We use **both**: the same embeddings power RAG for the chatbot, and they can be reused directly for similarity widgets (`retrieve(query, quotas={"careers": 10})`).

## 2. Pipeline

```
user message
  └─ scope_router.route()                 # only career/study goes further
       └─ _retrieval_query()              # short follow-up? prepend the previous user turn
            └─ embed_query()              # MiniLM (no instruction needed)
                 └─ search per collection # quotas: careers 4, profile 3, knowledge 2, jobs 1
                      └─ drop score < 0.30, sort, prepend MATCH STRENGTH (best career score vs 0.40)
                           └─ format_context()   # [S1] (source/doc_type, score, ref) text
                                └─ system prompt v4 = rules + style examples + PROFILE header + CONTEXT
                                     └─ LLM (Groq gpt-oss-120b, fallbacks) → answer with [S#]
                                          └─ sources footer (cited chunks only)
```

## 3. Retrieval strategy, step by step

1. **One query embedding, one search per collection.** One global top-k would be dominated by the 2,899 career records, so the user's 43 profile chunks would rarely appear. Searching each source with its own quota (`DEFAULT_QUOTAS` in `retriever.py`) guarantees a mix. Each search is a `$vectorSearch` with `filter: {source: X, user_id: {$in: ["global", user]}}`.
2. **Score floor.** `RAG_MIN_SCORE = 0.30` (MiniLM-calibrated, see [embeddings.md §6](embeddings.md#6-score-calibration)). If nothing passes, the context says so and the prompt tells the LLM not to invent facts.
3. **Always-on profile header.** A compact summary of `memory.json` (ATS score, skills, gaps, summary) is always injected, independent of retrieval. Core facts about the user can't be lost to a retrieval miss, and the header costs about 150 tokens.
4. **Follow-up expansion.** Messages of 6 words or fewer are concatenated with the previous user message before embedding, so "any free ones?" retrieves resources for Tableau.
5. **Atlas ANN settings.** `numCandidates = limit × 20` (Atlas recommends 10–20×) trades a little latency for recall on the HNSW index.

## 3b. Career retrieval adapter and weak evidence
`retrieve_careers(query, top_k=5, domain=None)` in `src/rag/retriever.py` is the stable interface from doc §12. It returns `career_id, career_name, domain, required_skills, education_required, score, salary (None if placeholder), weak_match`. It's gated by `CAREER_RAG_ENABLED` (default `true`; set it to `false` to fall back to profile and guide retrieval only).

Every career/study turn gets a first context line `MATCH STRENGTH: WEAK|OK (best career-record similarity x; floor 0.40)`. Prompt v4 rule 9 turns WEAK into 2–3 clarifying questions instead of guessed recommendations (doc §9.2 step 26).

## 4. Context format and citations

```
[S1] (source=knowledge/guide, score=0.78, ref=interview_preparation.md)
Interview Preparation - Technical preparation: For data analyst roles practise SQL joins …
```

The v2 system prompt requires inline `[S#]` citations for retrieved facts. `chatbot._sources_footer` then lists **only the cited** chunks, with job URLs, under the answer so users can verify. Uncited general advice is allowed but carries no citation (prompt rule 6).

## 5. Freshness

| Data | When re-embedded |
|---|---|
| profile | Automatically after each `/pipeline/run` (`ingest_profile_safely`, runs in a worker thread and never fails the request) |
| jobs | `python -m src.rag.ingest --sources jobs` after scraping |
| careers, knowledge | Manually, when the CSV or the guides change |

## 6. Measured behaviour (2026-11-08, E3-era bge store; MiniLM calibration is in embeddings.md §7)

| Query | Top hits (score) |
|---|---|
| "How do I prepare for a data analyst interview?" | knowledge: Interview prep – technical (0.782), careers: Data Analyst Intern (0.770), careers: Data Analyst, Intermediate (0.764), profile summary (0.729) |
| "What is my ATS score?" | knowledge: Raising an ATS score (0.676), knowledge: how ATS works (0.670), **profile overview with score** (0.650) |
| "Give me a recipe for paneer tikka" | best 0.543 → all filtered out (and the router refuses it first anyway) |

Retrieval latency, measured over 20 queries with 4 searches each: **median 9.0 ms, p95 11.9 ms** on the local store. Atlas M0 is expected to add network round-trips (one per source); measure it with `check_atlas --query` once connected.

## 7. Future improvements
- Hybrid search: Atlas `$search` (BM25) + `$vectorSearch` with reciprocal-rank fusion. This helps exact tool names like "PL-300" and "GST".
- Re-ranking with a cross-encoder (`BAAI/bge-reranker-base`) over the top 20.
- Query rewriting with the LLM for multi-turn conversations, replacing the current word-count heuristic.
- Per-user conversation memory as another `profile` doc type.

## 8. Retrieval precision upgrades (E35, measured, no LLM involved)

Benchmark: `python -m src.eval.rag_benchmark`, with 30 labelled student questions → expected guide section, plus the 24 labelled career queries (E11). Report: `reports/embeddings/rag_benchmark_latest.md`.

| Config | Guide Hit@1 | Guide Hit@3 | Guide MRR@5 | Career strict-P@5 | Median latency |
|---|---|---|---|---|---|
| vector (before) | 0.767 | 0.900 | 0.842 | 0.767 | 5–8 ms |
| hybrid BM25 + vector (RRF) | 0.667 | 0.800 | 0.740 | 0.800 | 4–5 ms |
| **vector + cross-encoder re-rank (adopted)** | **0.800** | **0.967** | **0.884** | **0.858** | 47–69 ms |
| hybrid + re-rank | 0.800 | 0.967 | 0.878 | 0.792 | 51–76 ms |

- **Adopted:** cosine search fetches a **20-candidate pool**, and the cross-encoder `cross-encoder/ms-marco-MiniLM-L-6-v2` reads (question, passage) pairs and keeps the best per source quota (careers, knowledge, jobs). The cosine `score` is kept, so MIN_SCORE and MATCH STRENGTH are unchanged. `RAG_RERANK=false` disables it.
- **Noise cut-off:** re-ranker score below **−6** → the chunk is dropped. Calibrated on both labelled sets: it keeps 91% of relevant chunks and drops 73% of non-relevant ones (−3 would keep only 80% of relevant ones).
- **Rejected: hybrid BM25.** It helps exact career titles slightly but lowers guide Hit@1 from 0.767 to 0.667, because student wording rarely shares words with the guides. The code stays in `src/rag/hybrid.py` for future experiments.
- **Rejected: profile-aware query expansion.** Profile retrieval is already Hit@3 = 1.0 (18/18 persona questions) without it.
- **Remaining guide misses** (6/30 at rank 1) are near-misses: in 4 of them the expected section is rank 2, after a closely related one (e.g. "Time management…" vs "Planning a study schedule"). The prompt receives 2–4 guide chunks, so they still reach the model.

## 9. Knowledge base coverage (E35)
The scope (study + career, including exams, SOPs, cover letters, first job and well-being) needed sources. 5 guides were added (now 9 guides, **37 sections**, one chunk each):
`higher_education_and_exams.md` (job vs MS/MBA, GATE/CAT/GRE prep, SOP, applying abroad + LORs), `applications_and_networking.md` (cover letters, LinkedIn, referrals and cold emails, rejections), `student_wellbeing_and_productivity.md` (exam stress, procrastination, time management, long-term exam study), `first_job_and_workplace.md` (first weeks, communicating with managers, raises, growth), `portfolio_and_projects.md` (why projects, ideas by role, READMEs, presenting projects).
Example: "How should I prepare for GATE in six months?" now retrieves *Preparing for GATE, CAT and GRE* (re-rank score 4.6). Before, no guide covered it.
