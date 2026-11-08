# Feedback learning ("recurrence learning") and precise answers (prompt v5)

Goal: the Career Advisor should answer **exactly what was asked** and get **better from user feedback** over time, without retraining any model weights.

## 1. Precise answers: the question profiler + answer contract (`src/backend/question_profile.py`)

Every career/study question is profiled deterministically (no LLM):

| Question type | Example | Retrieval mix (profile / knowledge / careers / jobs) | Answer rule injected into prompt v5 |
|---|---|---|---|
| profile_fact | "What is my ATS score?" | 5 / 1 / 1 / 0 | Exact value(s) in the first sentence, then a short explanation |
| recommendation | "Which career fits Python, SQL and dashboards?" | 2 / 1 / 5 / 1 | 2–4 options from career records, one-line reason each; clarify if evidence is weak |
| comparison | "Difference between data analyst and data scientist?" | 1 / 2 / 4 / 0 | One-sentence verdict, then a side-by-side comparison (table) |
| list | "Give me 3 certifications for cloud" | 3 / 2 / 2 / 1 | Exactly the list asked for, one item per bullet |
| plan | "Make me a 4-week plan to learn Tableau" | 4 / 2 / 1 / 0 | Time-boxed plan with checkable outcomes |
| how_to | "How do I prepare for a data analyst interview?" | 1 / 4 / 1 / 0 | Numbered, ordered steps |
| definition | "What is SQL?" | 0 / 3 / 2 / 0 | Plain definition in 1–2 sentences, then why it matters |
| yes_no | "Is a master's required to become a data analyst?" | 2 / 2 / 2 / 0 | Start with Yes / No / It depends |
| salary | "What salary does a Big Data Engineer get?" | 1 / 1 / 4 / 2 | Only non-placeholder dataset values; else say unavailable + where to check |

Constraints detected from the wording: **item count** ("3 certifications", "five courses"), **length** ("in one sentence" → ≤ 40 words, "briefly" → ≤ 120), **format** ("in a table", "step by step").

The **ANSWER CONTRACT** block of prompt v5 always says: the first sentence must directly answer, include only what helps answer *this* question, give exactly N items when N was asked, respect the length and format.

**Relevance filter:** within each source, chunks scoring more than 0.15 below that source's best match are dropped before the prompt is built, so weakly related snippets don't dilute the answer.

## 2. Learning from feedback (`src/backend/feedback_store.py`)

```
 user rates an answer ──► 👍  saved (question, answer, embedding)
                     └──► 👎  "What went wrong?"  reason + "what should a good answer include?"  ──► saved
                                                                                             │
 next similar question (cosine ≥ 0.75 on the question embedding)  ◄──────────────────────────┘
   ├─ 👎 reasons, counted ("REPEATEDLY … (3x)")  ─► "avoid" instructions in prompt v5
   ├─ 👎 comments ("should name the PL-300 exam") ─► explicit "must include" instructions
   ├─ 👍 answers (top 2)                           ─► "answers users rated helpful" (follow focus, not facts)
   └─ "wrongly refused" by ≥ 2 different users     ─► scope-router anchor: that question is accepted from now on
```

| Design rule | Why |
|---|---|
| Stored in **MongoDB Atlas** `skillpath_ai.feedback_v1` when available, else `reports/chat_logs/feedback.jsonl` | Learning survives redeploys (Streamlit Cloud's disk is ephemeral) |
| Similarity in Python, no vector index | The feedback set is small, and M0 allows only 3 search indexes |
| Feedback on **profile-specific** questions ("my ATS…") is reused **only for the same user** | Never leak one person's profile into another's answer |
| A router anchor needs **≥ 2 distinct users** | One malicious or mistaken user can't open the guardrail |
| Repeated complaints are labelled "REPEATEDLY … (n×)" | Recurring problems get stronger instructions |
| Never blocks answering | If the store is unavailable, the advisor answers without guidance |
| API keys are never stored | Only question, answer, rating, reason, comment, route, prompt version and user id |

**UI:** under every answer, 👍 saves immediately. 👎 opens *What went wrong?* (Didn't answer my question · Wrong/inaccurate · Too long/unfocused · Not specific enough · Wrongly refused · Other) plus an optional "what should a good answer include?". When an answer used feedback, it shows: *"Improved using feedback on N similar question(s) (x helpful, y not helpful)"*.

## 3. Verified (2026-11-08, `python -m src.eval.feedback_learning_test`, isolated store, gemini-3.1-flash-lite)

| Test | Result |
|---|---|
| 👎 + comment "point to the free *Microsoft Learn* PL-300 learning path", then a **paraphrased** question | Run 1: marker absent before (false) → **present after (true)**, feedback used. Run 2: present both times (retrieval now included it), feedback used. **Pass** |
| 👍 on "How should I prepare for a data analyst interview?" → "How do I get ready for a data analyst interview?" | The helpful answer was used as guidance (n_good = 1). **Pass** |
| "How do I make friends in a new college?" | Refused before (`out_of_scope`); after 2 different users reported "wrongly refused" → **accepted** (`learned-from-feedback`). **Pass** |

Reports: `reports/prompt_eval/feedback_learning_*.json`.

## 4. The offline prompt-training loop
1. Real users rate answers in the app; feedback accumulates in Atlas.
2. Review it: `python -c "from src.backend.feedback_store import summary; print(summary())"` (counts by reason, learned anchors).
3. Turn recurring 👎 into permanent eval cases (`src/eval/prompt_eval_set.jsonl`) and, if needed, a new prompt version (prompt_scripting.md §7).
4. A/B the new version against the live one (paired, same model) before activating it.

Feedback guidance fixes recurring problems **immediately and locally** (similar questions only). The offline loop turns the patterns into **permanent** prompt improvements.
