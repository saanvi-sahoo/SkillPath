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

## 6. Recursive learning at answer time (prompt v6, E34)
Learning from users (§2) works **across** conversations. v6 adds a loop **inside** each answer:
```
draft = LLM(prompt v6)  ->  problems = check_answer(draft, question profile, user profile)
if problems:  answer = LLM(prompt + draft + "fix only these problems: …")      # max 1 revision
```
The checks are deterministic and specific to the user. For example, for "What am I missing for this job?" the draft must name every gap in *this user's* analysed profile, and for "Which gap first?" the first sentence must name one of their gaps.

## 7. Feedback is reviewed before it is used (E37, review 2 §8)
User feedback can be wrong, so it no longer changes answers automatically. Each 👍/👎 is stored as `pending`;
`python -m src.backend.feedback_store --review` shows each one and a teammate approves or rejects it. Only approved
rows become guidance; router anchors still need ≥ 2 different users. `--export-dev dev_feedback.jsonl` turns approved
corrections into development test cases (never into a held-out set). The app now says feedback is used "after a team
review". Isolated experiments (`persona_eval`, `feedback_learning_test`, unit tests) simulate approved feedback.
