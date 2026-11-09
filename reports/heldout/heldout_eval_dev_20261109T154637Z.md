# Held-out chatbot evaluation (20261109T154637Z)

Frozen set: `src/eval/heldout/heldout_chat.jsonl` (7 cases). Paired design, shared route per case. Completed pairs: 7

| Metric | Target (review doc) | v8 |
|---|---|---|
| pass_rate | - | 0.857 |
| intent_accuracy | - | 0.714 |
| scope_accuracy | >= 0.98 | 0.857 |
| false_refusals | as low as possible | 1 |
| out_of_scope_leaks | 0 | 0 |
| constraint_compliance | >= 0.95 | 1.0 |
| factual_correctness | >= 0.95 | 0.857 |
| citation_rate | - | 0.286 |
| citation_correctness | >= 0.95 | 0.967 |
| claim_support_rate | higher is better | 0.875 |
| claim_contradiction_rate | 0 | 0.0 |
| profile_consistency | 1.0 | None |
| revised | - | 1 |
| avg_latency_ms | - | 3340 |
| avg_tokens | - | 1659 |

## Pass rate by category

| Category | v8 |
|---|---|
| career_discovery | 1.0 |
| hard | 0.5 |
| multi_turn | 1.0 |
| resume_jd | 1.0 |
| roadmap | 1.0 |
| study | 1.0 |

## Root causes of failures

- **v8**: {"prompt": 1} · models ['openai/gpt-oss-120b']

## Failed cases

| Version | Case | Failed checks | Root cause |
|---|---|---|---|
| v8 | H08 | not_refused, must_include_any, intent | prompt (model refused) |
