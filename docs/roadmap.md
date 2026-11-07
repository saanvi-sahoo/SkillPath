# Roadmap

The current item-by-item status, with evidence, is in **[status.md](status.md)**. This page is the forward plan, aligned with the integration phases of the project doc (§12).

| Phase (doc §12) | Scope | State | Rollback / flag |
|---|---|---|---|
| A | Standalone full-data embedding + local search | ✅ Done (2,899 × 384, P@5 benchmark) | Local store under `src/data/vector_store/` |
| B | Atlas upload into dedicated collections + vector indexes | ✅ Live on `skillpath-cluster`, verified (E20) | `VECTOR_BACKEND=local` |
| C | Career retrieval adapter + tests | ✅ `retrieve_careers()` + labelled benchmark | `CAREER_RAG_ENABLED=false` |
| D | Career-only classification + RAG context in the chatbot | ✅ Router + prompt **v4** live (paired A/B, E22) | `PROMPT_ADVISOR_SYSTEM`, `SCOPE_ROUTER_MODE` |
| E | Structured 30-day roadmap generator | ✅ First version, validated | Original learning-resource cards are still shown |
| F | Frontend/API integration | ✅ `/chat`, `/roadmap`, `/skills/compare`, Streamlit tabs | Env flags above |

## Next 2–3 weeks
1. **Deploy** on Streamlit Community Cloud; run the pending judge pass and 120b re-check when quota allows.
2. **Evaluation depth:**
   - Collect 100+ real questions from `reports/chat_logs/chat_log.jsonl` into a held-out set, disjoint from the router anchors.
   - Grow the career benchmark to 50+ labelled queries with manual relevance labels, not just domain labels.
3. **Retrieval quality:** hybrid BM25 + vector search, a cross-encoder re-ranker, and normalised career titles.
4. **Roadmap v2:** progress tracking, regenerating the remaining days when availability changes (doc §11.2 step 36), and an LLM fallback for categorising unknown skills.
5. **Parsing hardening:** OCR for scanned PDFs, multi-column ordering, and tests with 5–10 real (consented) resumes.
6. **Ops:** request limits, PII-free logging and health checks (doc §12); Groq keys from a second organisation for real extra quota.
7. **Report:** fill the Quarto chapters in `reports/final_project_report/` from these docs and reports.

## Stretch
- Fine-tune MiniLM on (skills → career) pairs once labels exist.
- Resume Builder tab.
- A fact-checker for salary and company claims (`FactChecker/`).
- `meta-llama/llama-prompt-guard-2` (available on Groq) as an extra prompt-injection detector.
