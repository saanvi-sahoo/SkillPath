# Held-out chatbot evaluation (20261109T_merged)

Frozen set: `src/eval/heldout/heldout_chat.jsonl` (40 cases). Paired design, shared route per case. Completed pairs: 40

| Metric | Target (review doc) | v7 | v8 |
|---|---|---|---|
| pass_rate | - | 0.925 | 0.95 |
| intent_accuracy | - | None | 0.921 |
| scope_accuracy | >= 0.98 | 0.925 | 0.95 |
| false_refusals | as low as possible | 1 | 0 |
| out_of_scope_leaks | 0 | 0 | 0 |
| constraint_compliance | >= 0.95 | 1.0 | 1.0 |
| factual_correctness | >= 0.95 | 0.938 | 0.938 |
| citation_rate | - | 0.475 | 0.4 |
| citation_correctness | >= 0.95 | 0.96 | 0.977 |
| claim_support_rate | higher is better | 0.167 | 0.25 |
| claim_contradiction_rate | 0 | 0.0 | 0.0 |
| profile_consistency | 1.0 | 1.0 | 1.0 |
| revised | - | 7 | 8 |
| avg_latency_ms | - | 6254 | 7727 |
| avg_tokens | - | 2274 | 1422 |

## Pass rate by category

| Category | v7 | v8 |
|---|---|---|
| career | 1.0 | 1.0 |
| concept | 0.8 | 1.0 |
| multi_turn | 1.0 | 0.875 |
| profile | 1.0 | 1.0 |
| roadmap | 0.75 | 0.75 |
| scope | 0.75 | 1.0 |
| study | 1.0 | 1.0 |

## Root causes of failures

- **v7**: {"prompt": 3} · models ['None', 'gemini-3.1-flash-lite']
- **v8**: {"prompt": 1, "retrieval": 1} · models ['None', 'gemini-3.1-flash-lite']

## Failed cases

| Version | Case | Failed checks | Root cause |
|---|---|---|---|
| v7 | v2-s01 | no_career_citations | prompt (forbidden content: no_career_citations) |
| v7 | v2-r04 | no_invented_urls | prompt (forbidden content: no_invented_urls) |
| v8 | v2-r04 | no_invented_urls | prompt (forbidden content: no_invented_urls) |
| v7 | v2-o03 | not_refused | prompt (model refused) |
| v8 | v2-m02 | must_include_any | retrieval (expected facts not in retrieved context) |
