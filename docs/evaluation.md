# Evaluation and prompt training v7: held-out tests, precision and grounding (E36)

This chapter implements the team review "How to make your Career Advisor more precise and accurate" and the
follow-up list (bigger real test set, v6 activation decision, per-sentence grounding, better examples, regular
quality ratings). The aim is **the correct answer to the user's exact question, from the correct information,
without assumptions**, and an evaluation that can show whether a change really helps.

## 1. What the review asked for, and what was built

| Review recommendation | Implemented as | Where |
|---|---|---|
| Separate, unseen test set; existing sets become the regression suite | 170 frozen held-out cases (120 chatbot + 30 career retrieval + 20 roadmap), SHA-256 recorded before any v7 work | `src/eval/heldout/` (§2) |
| New metrics with targets | Scope accuracy, false refusals, leakage, P@5, constraint compliance, factual correctness, **citation correctness**, profile consistency, **profile isolation** | `src/eval/heldout_eval.py`, `heldout_offline.py` (§3) |
| Hybrid retrieval + rule-based reranker (exact ≠ related skills, career intent) | Cross-encoder **+ skill-aware re-ranker**: domain consensus, exact skills (incl. implied: MySQL⇒SQL), related skills as partial credit only, the student's own skills for recommendations | `src/rag/skill_rerank.py` (§4) |
| Question-understanding step before answering | **Parsed intent**: task, primary source, number of items, length, format, **missing information** | `question_profile.parsed_intent()` |
| Source routing | No profile → profile retrieval slots go to guides/careers; recommendations re-rank careers by the student's skills; greetings and refusals skip retrieval | `chatbot.answer()` |
| Layered prompt (system / task / context), proposed v7 | `advisor_system_v7.md`: Layer 1 system rules (from the review's draft), Layer 2 task = parsed intent, Layer 3 context = profile (confirmed facts) + sources with the **allowed citation labels** | `src/prompts/templates/` |
| ATS from the existing analysis, labelled as an estimate | Profile block says "stored AI estimate, not an official ATS result"; the checker flags any other number | `answer_check.fact_issues()` |
| Answer validation (facts, citations, format, unsupported claims) | v6 checks + clarification rule + invalid/unsupported citation detection + profile contradiction detection → one revision | `answer_check.check_answer_v7()` |
| Fixed refusal via a separate scope step | Already in place (router → fixed refusal template, no LLM); measured again on 20 new out-of-scope cases | `scope_router.py` |
| Profile access enforced at the database level | `user_id` filter in every profile search (Atlas pre-filter + local store); **security test** with 40 cross-user probes | `heldout_offline.run_isolation()` |
| Don't rely only on LLM-as-judge | Deterministic checks are primary; a **blind** judge (no version, no expected answer, shuffled, different model family) is secondary | `src/eval/judge_heldout.py` |
| Shared results table + root cause before changing a prompt | `results_<ts>.csv` with `test_id, question, expected_behavior, actual_answer, retrieved_sources, pass_fail, failure_reason, root_cause, prompt_version` | `reports/heldout/` (§5) |
| Controlled v6 vs v7 experiment, then a separate retrieval experiment | Paired A/B, same model/temperature/retrieval/questions; retrieval measured separately with the prompt out of the loop | §4, §6 |
| Grow the test set from real usage (follow-up list) | Harvester for real chat questions and 👎 feedback → candidates for labelling | `src/eval/harvest_real_questions.py` |

## 2. The held-out set (frozen before v7 was written)

| Category | n | Purpose | Run by |
|---|---|---|---|
| career_study | 30 | Correct career/study answers with exact form (counts, length, tables, steps) | `heldout_eval` |
| out_of_scope | 20 | Fixed refusal, no partial answer | `heldout_eval` |
| ambiguous_followup | 20 | Clarify when information is missing; use conversation context in follow-ups | `heldout_eval` |
| resume_jd | 30 | 10 intents × 3 test students (data analyst, backend developer, mechanical engineer → ML) | `heldout_eval` |
| skill_confusion | 20 | Related ≠ equivalent (Docker vs Kubernetes, Power BI vs Tableau), implied = covered (MySQL ⇒ SQL) | `heldout_eval` |
| career_retrieval | 30 | Relevant top-5 career records (strict: right domain AND a matching skill/keyword) | `heldout_offline` |
| roadmap | 20 | Roles × gaps × daily minutes: 30 valid days, exact gaps, no known skill taught, prerequisites first, budget, resources, role-specific capstone | `heldout_offline` |
| **Total** | **170** | | |

Rules that keep it honest:
- Written **before** prompt v7, the parsed-intent rules and the skill re-ranker. SHA-256 at freeze time:
  `heldout_chat.jsonl` `ca891e15…0dbd`, `heldout_careers.jsonl` `62752128…0851`. `shasum -a 256 src/eval/heldout/*.jsonl` shows whether they changed.
- Question wordings differ from every earlier set (`prompt_eval_set.jsonl`, persona questions and paraphrases). Four come from real users in the chat log ("what i need to be a AI engineer", "what will be best job role , if i want to switch", "give me according to my profile skills").
- Retrieval weights were tuned **only** on the 24 old career queries; the held-out career set was then measured once.
- A label is not changed after seeing results. Debatable labels are listed in §7 instead.

## 3. Metrics and targets

| Metric | Definition (deterministic) | Target (review doc) |
|---|---|---|
| Scope accuracy | allowed answered + out-of-scope refused, over all cases | ≥ 0.98 |
| False refusals | in-scope questions refused | as low as possible |
| Out-of-scope leakage | out-of-scope questions answered | 0 |
| Precision@5 (careers) | share of top-5 career records with the right domain and a matching skill/keyword | ≥ 0.90 |
| Constraint compliance | item count, word limit, first-sentence answer, table, numbered steps, clarifying question | ≥ 0.95 |
| Factual correctness | required facts present (the student's real gaps/skills/ATS/role, topic facts) | ≥ 0.95 |
| **Citation correctness** | cited label exists **and** the cited source shares ≥ 15% of the sentence's content words | ≥ 0.95 |
| Profile consistency | no ATS number other than the stored one; never says the student has a skill that is a gap | 1.0 |
| Profile isolation | cross-user probes on local + Atlas stores returning only the user's own chunks | 1.0 |

**Why citation correctness was added:** "citation rate" (any [S#] present) reached 0.94–1.0 for v5/v6, but checking 636
stored cited sentences against their sources showed **12.7% cite a source that doesn't contain the claim** (e.g. a
"Graphic Designer" line citing a *Multimedia Learning Developer* record). A model can cite and still misread; the new
metric measures that. The 0.15 support threshold was calibrated on those 636 pairs (0.10 → 6.9% flagged, 0.20 → 17%).

## 4. Retrieval experiment (prompt out of the loop, no LLM)

`python -m src.eval.heldout_offline --only careers` (strict P@5, local store, MiniLM):

| Query set | Vector only | + cross-encoder (E35) | + skill-aware re-ranker (E36) |
|---|---|---|---|
| Tuning set (24, used for E35 and E36 tuning) | 0.767 | 0.858 | **0.933** |
| **Held-out (30, unseen)** | 0.727 | 0.713 | **0.773** |

How the weights were chosen (tuning set only): skill-overlap weights alone gave 0.842–0.858 (no gain, because career
records list many skills); a **career-intent bonus** (share of the top-10 vector matches that are in the record's
domain) gave 0.883 / 0.925 / 0.933 / 0.933 for weights 2 / 4 / 6 / 10. Weight 6 was chosen (10 behaves like a hard
domain filter). Exact skills (+1.0, implied skills count), related-only skills (+0.5) and the student's own skills
(+1.0, recommendations) are kept with small weights because they implement "related ≠ equivalent" without hurting P@5.

What this shows:
- The E35 cross-encoder gain (0.767 → 0.858) **did not hold on unseen queries** (0.727 → 0.713). The tuning set had
  overstated it, exactly the risk the review describes.
- The skill-aware re-ranker improves held-out precision by **+6 points (0.713 → 0.773)**, but it is still **below the
  0.90 target**. Remaining misses are mostly records whose domain label is borderline (`domain_basis`: "classified from
  career title… review borderline roles") and broad queries that span domains. Next steps: §8.

## 5. The shared results table and root causes

Every held-out run writes `reports/heldout/results_<ts>.csv`, one row per (case, prompt version):
`test_id, category, user, question, expected_behavior, actual_answer, retrieved_sources, pass_fail, failure_reason,
root_cause, prompt_version, model, citation_correct_rate, latency_ms, tokens`.

`root_cause` is assigned before anyone edits a prompt:

| Root cause | Meaning | Fix in… |
|---|---|---|
| scope_router | out-of-scope answered, or a valid question refused by the router | router anchors / router prompt, not the advisor prompt |
| retrieval | the facts the answer needed were not in the retrieved context | retriever, quotas, knowledge base |
| grounding | the answer contradicts the student's profile | prompt rules / checker |
| prompt | the facts were available but not used, or the model refused | advisor prompt / few-shots |
| instruction_following | count, length, first sentence, format or clarifying question wrong | answer contract / checker |

"Do not try to fix a retrieval failure by rewriting the system prompt": a failure classified as retrieval goes to the RAG owner.

## 6. Prompt experiment: v6 vs v7 (controlled, paired)

`LLM_PROVIDER=api CHAT_MODEL=gemini-3.5-flash python -m src.eval.heldout_eval --versions v6 v7 --expect-model gemini-3.6-flash`

Kept constant: answering model (Gemini 3.5 Flash, which reports itself as `gemini-3.6-flash`), temperature 0.3,
retrieval configuration, scope route (decided once per case and shared), questions, empty feedback store.
Acceptance rule (review §9): adopt v7 only if it improves important outcomes without materially worsening any category.

**Final (120/120 pairs).** Models, recorded per row: the first 10 pairs on `gemini-3.5-flash` (served as
`gemini-3.6-flash`); its free daily quota ran out (429), so the remaining pairs ran on `gemini-3.1-flash-lite`. Both
versions answer every case on the same model; out-of-scope cases use the fixed refusal (no model).

| Metric | Target | v6 | v7 |
|---|---|---|---|
| All checks pass | – | 0.900 | **0.950** |
| Scope accuracy | ≥ 0.98 | 0.992 | 0.992 |
| False refusals / leaks | low / 0 | 1 / 0 | 1 / 0 |
| Constraint compliance | ≥ 0.95 | 0.863 | **0.980** |
| Factual correctness | ≥ 0.95 | 0.960 | 0.960 |
| Citation correctness (labels exist + lexical support) | ≥ 0.95 | 0.853 | **0.933** |
| Profile consistency | 1.0 | 0.977 | 0.977 |
| Answers revised by the self-check | – | 2 | 35 |
| Average latency | – | 9.0 s | 13.7 s |

| Category | v6 | v7 |
|---|---|---|
| career_study (30) | 1.0 | 1.0 |
| out_of_scope (20) | 1.0 | 1.0 |
| ambiguous_followup (20) | 0.80 | **0.90** |
| resume_jd (30) | 0.833 | **0.933** |
| skill_confusion (20) | 0.85 | **0.90** |

**Decision: v7 activated** (`src/prompts/registry.py`): better overall, better or equal in every category, no new
leaks. Cost: +4.7 s average latency from self-check revisions (35 of 120).

Two scoring corrections were made after the run, both applied to both versions alike and documented here:
1. The h-sc04 label was replaced by the rubric in §7 (review 2 §1).
2. The profile-contradiction detector produced false alarms on correct sentences ("…which are currently identified as
   gaps in your profile", "Once you have completed a project in Tableau…"). It now only reads the clause directly after
   "you have/know", stops at contrast words and skips conditionals. With the faulty detector the pass rates were
   0.817 / 0.883; the corrected ones are above. Both are in `reports/heldout/heldout_eval_20261109T140538Z.json`.

Remaining failures (v7, 6): one valid question refused by the router ("Which one is better?" with no context: it
should be clarified, not refused), one real profile contradiction, two misses on exact counts or facts, and one
debatable first-sentence check. Full table: `reports/heldout/results_20261109T140538Z.csv`.

## 7. Label review notes (not changed after the run)
- `h-sc04` "Is MySQL experience the same as knowing SQL?": the label expected "yes", but "not the same, though it shows
  SQL use" is also correct. Resolved with a rubric (`src/eval/heldout/rubrics.json`): correct = (a) MySQL experience is
  evidence of SQL use and (b) MySQL is a DBMS while SQL is the language. Applied to every version; the frozen case file
  is unchanged.

## 8. Next steps
1. Label the harvested real questions (`reports/heldout/real_question_candidates.jsonl`) into a second held-out file; target 100+ real questions.
2. Career retrieval to ≥ 0.90 on unseen queries: review borderline domain labels in the dataset, and try a domain classifier on the query (trained on the tuning set only).
3. Run `judge_heldout` monthly with the same judge model; add 20 human-reviewed reference answers for the most critical CV/JD questions.
4. Fine-tuning a small open model only after 500+ approved question-answer pairs exist; free hosting can't serve it today.

## 9. Team workflow (review §8)

| Owner | Area | Owns these categories / files |
|---|---|---|
| Amrit Singh | Scope classification, unrelated, ambiguous and follow-up questions | `out_of_scope`, `ambiguous_followup`; `scope_router.py`, `scope_examples.json`, `missing_information()` |
| Saanvi Sahoo | CV/JD accuracy, skill-gap correctness, roadmap quality, source verification | `resume_jd`, `skill_confusion`, `roadmap`; `answer_check.py`, `normalizer.py`, `src/roadmap/` |
| Isa Ahmed Khan | Retrieval evaluation, embeddings, RAG grounding, citation validity, performance | `career_retrieval`, citation correctness, isolation; `src/rag/`, `heldout_offline.py` |

One loop for everyone: run the held-out evals → read `results_<ts>.csv` → fix by root cause in the owner's area →
re-run the regression suite (`run_prompt_eval`, `persona_eval`, `pytest`) and the held-out set → log the result in
`experiment_log.md` → only then change `ACTIVE` in `src/prompts/registry.py`. Nobody edits the master prompt
without a paired A/B.

## 10. Commands
```bash
python -m src.eval.heldout_offline                                  # careers P@5, 20 roadmaps, 40 isolation probes (no LLM)
LLM_PROVIDER=api CHAT_MODEL=gemini-3.5-flash python -m src.eval.heldout_eval --versions v6 v7 --expect-model gemini-3.6-flash
python -m src.eval.heldout_eval --resume reports/heldout/heldout_eval_<ts>.json      # after a quota stop
python -m src.eval.heldout_eval --report reports/heldout/heldout_eval_<ts>.json      # re-score, rebuild CSV + tables
python -m src.eval.judge_heldout reports/heldout/heldout_eval_<ts>.json --judge groq:openai/gpt-oss-120b --n 30
python -m src.eval.harvest_real_questions                           # real questions + 👎 to label
python -m pytest -q tests                                           # 47 offline tests
```

---

# Part 2: Review 2 implementation (E37, prompt v8)

The second review said the automatic checks looked good but didn't prove that answers are precise and useful, and asked
for: real-intent understanding, evidence chosen per question type, retrieval fixed before more prompting, claim-level
citation checks, task-specific contracts, a focused v8 prompt with task templates, feedback kept separate from
evaluation, a development question bank with hard tests and multi-turn conversations, and a human Question
Satisfaction Rate. Each item and where it lives:

| Review 2 item | Implemented as | Where |
|---|---|---|
| Finish E36 (120 pairs), category-level results, preliminary vs final | Completed; final table in §6 with per-category and per-model results | `reports/heldout/` |
| Reconcile the model configuration | Every row records `model_configured` (CHAT_MODEL) and `model_id` (what the API reported). `gemini-3.5-flash` is served as `gemini-3.6-flash`; after its daily quota ran out the run continued on `gemini-3.1-flash-lite`; each pair is same-model | `heldout_eval.py`, `reports/baselines/` |
| MySQL ⇔ SQL label | Rubric file (`heldout/rubrics.json`): correct = "evidence of SQL use" + "MySQL is a DBMS, SQL the language"; applied to all versions; frozen label unchanged | §7 |
| Identify the real intent (8 labels, structured output) | `src/backend/intent.py`: the review's schema (in_scope, primary/secondary intents, user_goal, requested_count, response_style, requires_profile, requires_retrieval, needs_clarification) + sentence counts, examples, conflicts, guarantees, follow-up references, multi-request parts | §11 |
| Source-aware routing | `ROUTES` per intent: concepts/study → guides + general knowledge, never career records; careers → career records; profile → this student's analysis only; plans → the validated roadmap generator | §11 |
| Improve retrieval before prompting: hybrid, per-type evaluation, audit, fewer arbitrary bonuses, MySQL nuance | Per-type P@5, audit of all 30 unseen queries, hybrid BM25 re-tested, domain bonus 6/3/0 compared, implied skills at 0.75 weight, interest/transition expansion, one record per career title | §14 |
| Claim-level citation verification | `src/backend/claim_check.py`: ID validity (deterministic) + NLI cross-encoder → supported / contradicted / insufficient; used in v8's self-check and as an eval metric | §12 |
| Task-specific answer contracts | `src/backend/task_contract.py`: every part answered, exact sentence counts, code examples, N examples each, no guarantees, no invented URLs, conflicts acknowledged, plans to Day 30 | §13 |
| Focused v8 core + task templates | `advisor_system_v8.md` (10 rules) + `src/prompts/tasks/<intent>.md`; only the template for the detected intent and at most 2 matching examples are sent | §13 |
| Keep feedback separate from evaluation | Feedback is stored `pending`; only teammate-approved rows guide answers; approved corrections export to dev cases, never to held-out | §15 |
| 40-question bank, hard tests, 20 multi-turn conversations | `src/eval/dev/dev_set.jsonl` (67 cases; development, may be used for tuning) | §16 |
| Fresh unseen sets for the final decision | `heldout_v2.jsonl` (40 chat cases) and `heldout_careers_v2.jsonl` (20 career queries), frozen before v8 was evaluated | §16 |
| Question Satisfaction Rate + judge prompt | `src/eval/satisfaction.py`: blinded 0/1/2 human scoring + the review's 9-dimension judge (secondary) | §17 |
| Baseline freeze | `reports/baselines/baseline_<ts>.json`: live prompt, file hashes, models, retrieval settings, test-set hashes | — |

## 11. Intent understanding and source-aware routing

```json
{"in_scope": true, "primary_intent": "career_discovery", "secondary_intents": ["learning_plan"],
 "user_goal": "find or compare career options", "requested_count": null, "n_sentences": null, "examples_each": null,
 "needs_example": false, "response_style": "default", "requires_profile": false, "requires_retrieval": true,
 "needs_clarification": false, "conflict": null, "refers_to_history": false,
 "parts": ["Compare data science and data engineering", "make me a learning plan"]}
```
(real output for "Compare data science and data engineering, then make me a learning plan.")

| Intent | Evidence retrieved (profile / guides / careers / jobs) | Answer rests on |
|---|---|---|
| career_discovery | 2 / 1 / 5 / 0 | career records + the student's skills/interests |
| concept_explanation | 0 / 2 / 0 / 0 | well-established knowledge; a guide only if relevant |
| profile_analysis | 6 / 1 / 0 / 0 | this student's analysed CV + JD only |
| learning_plan | 3 / 3 / 0 / 0 + generated plan | gaps, current skills, time budget, roadmap generator |
| study_help | 0 / 3 / 0 / 0 | knowledge; study guides |
| job_preparation | 2 / 4 / 0 / 1 | guides; profile when personal |
| profile_progress | 5 / 0 / 0 / 0 | stored analysis, uploads, progress only |

Deterministic, so it behaves the same locally (Mistral), deployed (visitor key) and keyless. Keyless mode now always
uses this routing: on the 65-case regression it scores the same as before (0.877, same 8 failures, all exact-count
or word-limit cases that a retrieval-only answer can't meet), and concept answers no longer cite career records
(citation rate 0.864 → 0.795 for that reason).

"Make me a 30-day plan" style requests run the roadmap generator first (time budget parsed from "45 minutes daily",
known skills removed, role starter skills when only a role is named) and give the validated plan to the model as a
source; keyless mode shows it directly.

## 12. Claim-level citation verification

Review 2's example is now caught: source "Required skills: Python, SQL…", answer "The Data Engineer role does not
require Python or SQL [S1]" → **contradicted** (NLI 1.0), while "requires Python and SQL [S1]" → **supported** (0.99).
Only real statements are checked (a verb, ≥ 6 words; titles and fragments are skipped), cited advice ("Mirror the JD
keywords…") is counted separately, contradiction needs ≥ 0.85 confidence, and a near-verbatim restatement with no
contradiction signal counts as supported. On 376 stored v5/v6 cited claims: 33.8% supported, 52.9% insufficient
(the source doesn't state it), 3.5% contradicted, 9.8% invalid IDs (inflated: stored contexts were cut at 4,000
characters). The word-overlap check had passed 87% of the same citations, which shows why the review was right.

## 13. Prompt v8 and task contracts
- Core (`advisor_system_v8.md`): 10 rules from review 2's draft, including "never refuse an in-scope request because it
  is impossible as worded; say what can't be done, then give the closest useful answer" (added after the dev test
  "one-sentence answer containing 30 daily tasks" was refused).
- Task layer: `src/prompts/tasks/<intent>.md` + `contract_v8()` (the parsed request as numbered requirements).
- Self-check (`check_v8`): v6/v7 checks + sentence count, code example, examples, guarantee, conflict, every part,
  Day 30, invented URLs, NLI contradictions/unsupported claims, profile contradictions → one revision.

## 14. Retrieval: per-type results, audit, changes

`python -m src.eval.career_audit` → `reports/heldout/career_audit_latest.md` (top-5 of every audited query with a diagnosis).

Strict P@5 by configuration (`career_audit_latest.md`; dedupe by title was on for the skill configs in this table):

| Set | Vector | + cross-encoder | + skill (domain bonus 6) | bonus 3 | bonus 0 | BM25 hybrid + skill (3) |
|---|---|---|---|---|---|---|
| Tuning (24) | 0.767 | 0.858 | 0.933 | 0.892 | 0.858 | 0.892 |
| E36 held-out (30, audited) | 0.727 | 0.713 | 0.773 | 0.753 | 0.707 | 0.780 |
| **Held-out v2 (20, frozen)** | 0.61 | 0.64 | **0.69** | 0.67 | 0.65 | 0.60 |

Per query type on held-out v2 (5 each): titles 0.92, skill lists 0.84, **interests 0.52, career changes 0.48**. One
P@5 number had hidden that the weak spot is students describing interests or a change of field, not skills or titles.

What was decided, and why:
- **Domain bonus kept at 6.** Review 2 asked to reduce arbitrary bonuses; the comparison chose by the tuning set (as
  the protocol requires) and the frozen v2 set agrees: 6 > 3 > 0 (0.69 / 0.67 / 0.65). The bonus is the share of the
  top-10 cosine matches in a record's domain, so it follows the query, not a fixed category.
- **BM25 hybrid rejected again**: it helps the audited set slightly (0.780) but hurts the frozen v2 set (0.60) and
  guide retrieval (E35). Atlas-native text+vector fusion would also need a 4th search index, which the free M0 tier
  doesn't allow (limit 3, all used).
- **Implied skills weighted 0.75** (MySQL in a record is evidence of SQL use, weaker than "SQL" itself).
- **Interest / career-change expansion adopted** (`expand_career_query`): a general interest → career-area taxonomy
  (privacy/hackers → cybersecurity, organising people → project management, clients → sales/customer success, puzzles
  and maths → data science, drawing/design → UI/UX…), only when the query describes interests or a change of field.
  Tuning set unchanged (0.933), v2 0.69 → **0.76** (interests 0.52 → 0.72, career changes 0.48 → 0.56). Caveat: the same
  person wrote the taxonomy and the v2 queries.
- **One record per career title** (`title_key`: case and level suffixes like "II", "Senior" ignored). The dataset has
  duplicates ("Information Security Analyst" ×3 with different skills) that a model could merge into an invented
  requirement (review 2's "duplicate titles" test). Every top-5 now has 5 distinct careers (was 4.2-4.7). The strict
  metric drops slightly because duplicates had each counted as relevant: v2 0.76 → 0.73, tuning 0.933 → 0.925.

**Final configuration** (live): cross-encoder + skill re-ranker (bonus 6, implied 0.75) + interest expansion + one record per title.

| Set | P@5 | by type |
|---|---|---|
| Tuning (24) | 0.925 | interest 0.89, skill 1.0 |
| E36 held-out (30, audited) | 0.773 | interest 0.80, skill 0.83, title 0.63 |
| **Held-out v2 (20, frozen)** | **0.73** | title 0.88, skill 0.80, interest 0.68, career change 0.56 |

Still below the 0.90 target. Audit of the 30 E36 queries (top-5 of each in `career_audit_latest.md`): 19 have ≥ 4/5
relevant, 8 are **ranking** problems (relevant records were in the 20-candidate pool but not the top 5), 3 are
**source data** (records that match the skills carry another domain label, e.g. analytics roles labelled "Project and
Business Management"; the dataset's own `domain_basis` says "review borderline roles"). Next: relabel borderline
domains in the dataset (source-data fix) and a larger candidate pool for career-change queries.

## 15. Feedback kept separate from evaluation
Every 👍/👎 is saved with `status: pending`. `python -m src.backend.feedback_store --review` lets a teammate approve or
reject each row; only approved rows become guidance (and router anchors still need ≥ 2 users). `--export-dev` writes
approved corrections as development cases. The app now says feedback is used "after a team review".

## 16. Test sets
| Set | Cases | Use | SHA-256 (start) |
|---|---|---|---|
| `prompt_eval_set.jsonl` | 65 | regression | — |
| `heldout/heldout_chat.jsonl` (E36) | 120 | v6 vs v7 final; failures since inspected | `ca891e15` |
| `dev/dev_set.jsonl` | 67 (41 review bank, 16 extra multi-turn, 10 hard tests) | development: may be used for tuning | `61fcb4dc` |
| `heldout/heldout_v2.jsonl` | 40 | **final v7 vs v8 decision**, frozen before v8 was evaluated | `e2d7198a` |
| `heldout/heldout_careers.jsonl` (E36) | 30 | audited (now seen) | `62752128` |
| `heldout/heldout_careers_v2.jsonl` | 20, typed (title/skill/transition/interest) | **final career-retrieval number** | `b4f65bd6` |

Caveat: all sets were written by the same author as the rules (no real users yet beyond 17 harvested questions), so
"unseen" means "not used for tuning", not "independent". QSR from teammates is the check on that.

## 17. Question Satisfaction Rate
`python -m src.eval.satisfaction export <run.json> --n 40` writes a blinded CSV (items shuffled, versions hidden, key in
a separate file). Each teammate scores 0 / 1 / 2; `score` computes QSR = mean/2 and the share of fully satisfied
answers per version. `judge` runs the review's 9-dimension judge (0/1/2 + evidence + overall_pass + failure_category +
recommended_fix) with a different model family, as a secondary signal only.

## 18. Results: v7 vs v8 (E37)

**Held-out v2, deployed-style model (Gemini 3.1 Flash-Lite), 40/40 pairs** (`reports/heldout/heldout_eval_heldout_v2_final_v7_v8.json`):

| Metric | v7 (live) | v8 |
|---|---|---|
| All checks pass | 0.925 | **0.950** |
| Scope accuracy / wrongly refused / leaks | 0.925 / 1 / 0 | **0.950 / 0** / 0 |
| Constraint compliance | 1.0 | 1.0 |
| Factual correctness | 0.938 | 0.938 |
| Citation labels valid + lexical support | 0.960 | **0.977** |
| Cited claims supported (NLI, re-checked from saved sources) | 0.167 | **0.250** |
| Cited claims contradicted | 0 | 0 |
| Tokens per answer | 2,274 | **1,422** (−37%) |
| Average latency | 6.3 s | 7.7 s |

| Category | v7 | v8 |
|---|---|---|
| career (8) · profile (8) · study (4) | 1.0 · 1.0 · 1.0 | 1.0 · 1.0 · 1.0 |
| concept (4) | 0.80 | **1.0** |
| scope (4) | 0.75 | **1.0** |
| roadmap (4) | 0.75 | 0.75 |
| multi_turn (8) | **1.0** | 0.875 |

**Decision: v7 stays live, v8 stays the candidate.** v8 is better overall, but it lost one multi-turn case (asked for
"two examples" of cloud computing it explained IaaS and SaaS without naming a provider; v7 named Google Cloud and
Azure). The acceptance rule allows no category more than 5 points worse, and with 8 cases one answer is 12.5 points.
Next step: the concept template should require concrete, named examples; test on the dev set; confirm on new unseen
cases.

How the comparison was kept fair:
- v8 was re-run after the intent-routing fixes; v7 doesn't use the intent classifier, so its answers from the same
  model stayed valid. The one case whose route changed with the router fix (v2-m02) was re-run for v7 too.
- Three scoring corrections were applied to every version alike:
  1. The refusal detector no longer counts clarifying questions or numbered answers as refusals. "I cannot provide a
     career recommendation without knowing more… which of these areas appeals to you?" is the expected clarification.
  2. The fixed refusal template is always a refusal. Its example question had looked like a clarification.
  3. The entailment check no longer labels correct absence or count statements about the student's own profile as
     contradictions ("AutoCAD… are not listed in the JD", "you meet 1 of 6"). Those facts are checked by the
     deterministic profile check.

**Intent routing accuracy** (v8, no LLM, `classify()` vs the expected label):

| Set | Before the routing fixes | After |
|---|---|---|
| Development (63 in-scope) | 0.857 | 0.968 |
| Held-out v2 (38 in-scope) | **0.68** (clean) | 0.92 (seen: the misses were inspected) |

The fixes are general rules: "where can I learn/start" → plan; an exam → study help before plan; an explicit "N-day
plan" → plan even when it mentions gaps; "my skills match / requirements in the JD / do I know enough" → profile
analysis; "how do I become…" → career; "what do you know about me" → profile facts.

**Router fixes (all versions):**
- A short follow-up inside an in-scope conversation inherits its scope, unless the follow-up alone looks off-topic.
  "Give me two examples." after "Explain cloud computing" had been refused, while "what about pasta recipes?" is still
  sent to the model router.
- "What can you help me with?" is a greeting by rule. The hosted router model (gpt-oss-20b) had started refusing it,
  which shows why the review said not to depend on the model alone.
- Router suite: hybrid 1.0, kNN 1.0 allow/refuse.

**Local model (Mistral 7B, Ollama), 40/40 pairs** (earlier v8, before the routing and router fixes): all checks v8
0.825 vs v7 0.80; constraint compliance 0.867 vs 0.733; tokens 1,752 vs 2,574; career 1.0 vs 0.75 and roadmap 1.0 vs
0.50, but concept 0.80 vs 1.0 and profile 0.75 vs 1.0. Mixed, so the same decision: v7 stays live locally too.

**Local router fix (all versions, found by the Mistral run):** without a hosted router model, scope fell back to
nearest-example voting and refused "Explain Big-O notation in exactly two sentences" (best match only 0.19). Now a weak
"out of scope" vote (similarity < 0.4 and < 80% agreement) is overruled when the message clearly carries study/career
content (a known skill/tool or an academic/career term). Checked locally on every set: 45/45 off-topic cases still
refused (the first version leaked "Who won the last Formula 1 race?", fixed by the agreement condition); 245/247
in-scope cases allowed (the two left are "Which is better?" with no context).
