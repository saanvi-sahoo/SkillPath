# Release smoke tests (20261111T112906Z)

8/9 passed. Every check was executed.

| Check | Result | Evidence | s |
|---|---|---|---|
| deployed app is up (Streamlit Cloud) | PASS | GET /healthz -> 200 | 0.6 |
| Atlas vector search returns career + knowledge records | PASS | 5 careers ('Senior Data Analyst - People & Performance'), 3 guides, 827 ms | 4.9 |
| Atlas outage -> local copy of the same vectors (no crash, no invented records) | PASS | 4 hits from the local store, breaker open=True | 0.4 |
| CV upload: text PDF parsed, scanned PDF rejected, skills extracted | PASS | skills ['Python', 'SQL', 'Excel', 'Power BI', 'Git', 'Pandas'], gaps ['Tableau', 'Statistics'], ATS 60; scanned PDF rejected | 0.1 |
| roadmap: valid 30-day plan, then adapted after a hard day and missed days | PASS | valid=True, adapted: Added a revision day for 'Aggregations & GROUP BY' (day 2 was hard).; Moved 1 missed day(s) forward: days 3; Dropped 2 weekly review day(s) to make room. | 0.2 |
| user isolation: one student's profile is never retrieved for another | PASS | 3 students x 8 profile chunks: 0 records from another user | 20.5 |
| LLM outage -> retrieval-only answer with a notice (conversation kept) | PASS | generation=retrieval-only (all LLMs unavailable); notice shown; 1864 chars | 1.3 |
| keyless answer resolves 'the second one' from the conversation | PASS | starts: 'About **Data Engineer** (item 2 of my last list):\n\n**Guidance** (Entry-level tech and data' | 0.3 |
| hosted latency on 8 realistic turns (model: groq:openai/gpt-oss-120b) | FAIL | p50 3.8 s, p95 92.3 s, models ['openai/gpt-oss-120b', 'openai/gpt-oss-20b', 'qwen/qwen3.8-27b'] | 152.0 |
