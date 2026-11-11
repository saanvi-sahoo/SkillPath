# Final validation of SkillPath AI v7 + E38 (review 4)

Review 4 judged the project ready for a college demonstration and an internship report with limitations, conditional
for a supervised pilot, and not ready for a public production release. It asked for a final validation round instead of a new
development cycle: no v9, no redesign. This page records what was executed, what was fixed, and what is left for the team.

## What was executed (11 Nov 2026)

| Review 4 item | Done | Result |
|---|---|---|
| Fix the failed hosted journeys (j01, j03, j04, j08) | 5 fixes, re-tested on the deployed model (Groq gpt-oss-120b) | j01 ✓, j04 ✓ ("make it easier" verified), j08 ✓; j03 turns 1-3 ✓ on gpt-oss-120b, turn 4 passed but was answered by a fallback model after Groq's daily quota ran out, so it isn't counted as a clean success |
| Test fresh journeys | 8 new journeys (`journeys_v2.jsonl`, frozen in 785d364 before running) | **8/8 fully successful**, 32/32 turns, every turn on gpt-oss-120b, p95 5.2 s |
| Release smoke tests | `python -m src.eval.release_smoke` | **8/9 pass**: deployed app health, Atlas retrieval (0.8 s), Atlas outage → local copy, CV upload (scanned PDF rejected), roadmap generate + adapt, user isolation (0 cross-user records), LLM outage → notice, keyless follow-up. **Fail: hosted latency** p50 3.8 s but p95 92 s, because Groq's free daily quota ran out mid-test and the fallback chain answered (gpt-oss-20b, qwen) |
| Citation audit checklist | fresh 58-claim sample from the final E38 run + teammate columns | 0 invalid-ID artifacts now (9 before the fix); 3 "contradicted" labels, all NLI false alarms in the first pass; rest open for the team |
| Blinded QSR | 50 answers, 10 per area, two reviewer columns, agreement score | prepared; scores need two people |
| Career label audit | first pass over 240 flagged records | 127 likely mislabeled, 113 ambiguous; proposed relabels in `career_domain_corrections_v1_PROPOSED.csv`; dataset unchanged |
| Local Mistral latency | measured from the E38 local run | median 26-29 s per turn without the self-check revision, 64-72 s with it; the 102 s p95 is a whole turn (retrieval + draft + revision). The 90 s timeout applies to hosted APIs; Ollama uses 300 s. Local mode is now labelled experimental in the app |
| Keyless limitations | labelled in the chat header | "Retrieval-only mode: no exact counts, word limits or tables" |

### Fixes made in this round (verified unless stated)
1. Options, careers, skill gaps and steps are given as a numbered list (j01, j03 turn 1 now pass).
2. Plans label every day "Day N" and end on the last day of the period (j03 turn 3, j08 turn 3 now pass).
3. A self-check revision that returns a fragment no longer replaces the full draft; the revision prompt asks for the complete answer (j01 turn 3 had stopped at Day 10).
4. "Simpler" means shorter for beginners (j04 turn 2 now passes on the deployed model).
5. Empty model reply → one retry → knowledge-base answer with a notice (unit test; j03 turn 3 passed on gpt-oss-120b after the fix).
6. Hugging Face models load from the local cache first (a first career search once waited ~15 minutes on the hub check).
7. Journey runner resume bug (resumed runs used the wrong journey set) fixed.

### Readiness (agrees with review 4)
| Use | Status |
|---|---|
| Internal college demonstration | Ready |
| Internship report and evaluation | Ready, with the limitations below |
| Supervised pilot with students | Conditional: after QSR scoring and citation confirmation by the team, and with a paid or visitor key (free-tier quotas make p95 latency spike to ~90 s when exhausted) |
| Public production release | Not yet |

### Limitations that remain
- Human QSR, citation confirmation and label decisions are not done (they need people).
- Free-tier quotas: when Groq's daily quota is used up, answers come from fallback models and p95 latency reaches ~90 s.
- Career P@5 0.895 (target 0.90); 240 flagged labels unresolved.
- Local Mistral is slow and weaker; it is labelled experimental. The hosted model is the primary experience.
- The journey and case sets are written by the team in a realistic style; only 17 questions are genuine user questions.



## Team tasks (prepared; they need people, not code)

### A. Confirm citation correctness (owner: Saanvi + one teammate)
Files: `reports/heldout/claim_audit_heldout_v2_final_v7_v8.csv` (64 claims, first pass done) and
`reports/heldout/claim_audit_heldout_v3_20261110T032543Z_p62210.csv` (58 claims from the final E38 run; full sources saved).
For each row read `claim` against `source_excerpt` and fill `teammate1_review` / `teammate2_review` with one of
`supported`, `true_uncited`, `false`, `unclear`, `evaluator_artifact`; agree a `final_decision`. Then:
`python -m src.eval.claim_audit score <csv>` (reads `review`; copy `final_decision` into `review` first).
Look first at: rows labelled `contradicted` (3 in the E38 sample, all judged NLI false alarms in the first pass) and
`insufficient` rows with a cited source (most are paraphrases or wrong-source citations, not hallucinations).

### B. Human Question Satisfaction Rate (two reviewers, independently)
File: `reports/heldout/qsr_heldout_v3_20261110T032543Z.csv` — 50 blinded answers, 10 per area (CV/JD, career transition,
roadmap, study, follow-up), shuffled; the version of each answer is only in the `.key.json` file (don't open it before scoring).
Score each answer 0 (wrong / irrelevant / didn't answer), 1 (partly right or incomplete), 2 (correct, relevant, complete, follows
the instructions). Read `conversation_so_far` for follow-ups. Each reviewer fills only their own column. Then
`python -m src.eval.satisfaction score reports/heldout/qsr_heldout_v3_20261110T032543Z.csv` → QSR per version and area, share
scored 2/2, and reviewer agreement (exact and within 1). Target from review 3: ≥ 90% of answers scored 2/2.

### C. Career label audit (owner: Isa / Ahmed)
File: `reports/data_quality/career_label_review.csv` — 240 flagged records with a first pass (127 `likely_mislabeled`,
113 `ambiguous`). Fill `decision` with `incorrect_label`, `correct_label` or `ambiguous`. Proposed relabels are in
`reports/data_quality/career_domain_corrections_v1_PROPOSED.csv`; set `verified_by` and `apply=yes` only for verified rows.
Nothing is applied automatically: verified corrections go into a new dataset version, then career retrieval is re-measured on a
NEW frozen query set (not heldout_careers_v3).
