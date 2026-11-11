# Held-out chatbot evaluation (20261110T032543Z)

Frozen set: `heldout_v3` (120 cases). Paired design, shared route per case. Completed pairs: 120

| Metric | Target (review doc) | v7 | v7+e38 |
|---|---|---|---|
| pass_rate | - | 0.933 | 0.975 |
| intent_accuracy | - | None | 1.0 |
| scope_accuracy | >= 0.98 | 1.0 | 1.0 |
| false_refusals | as low as possible | 0 | 0 |
| out_of_scope_leaks | 0 | 0 | 0 |
| constraint_compliance | >= 0.95 | 0.857 | 1.0 |
| factual_correctness | >= 0.95 | 0.962 | 0.984 |
| citation_rate | - | 0.495 | 0.598 |
| citation_correctness | >= 0.95 | 0.909 | 0.921 |
| claim_support_rate | higher is better | 0.28 | 0.34 |
| claim_contradiction_rate | 0 | 0.011 | 0.005 |
| profile_consistency | 1.0 | 1.0 | 1.0 |
| revised | - | 29 | 37 |
| avg_latency_ms | - | 5988 | 5998 |
| p95_latency_ms | - | 21914 | 18216 |
| avg_tokens | - | 2393 | 2592 |

## Pass rate by category

| Category | v7 | v7+e38 |
|---|---|---|
| multi_turn | 0.936 | 0.979 |
| out_of_scope | 1.0 | 1.0 |
| profile | 1.0 | 1.0 |
| real_world | 0.896 | 0.958 |

## Root causes of failures

- **v7**: {"retrieval": 6, "instruction_following": 2} · models ['None', 'gemini-3.1-flash-lite']
- **v7+e38**: {"retrieval": 2, "prompt": 1} · models ['None', 'gemini-3.1-flash-lite']

## Failed cases

| Version | Case | Failed checks | Root cause |
|---|---|---|---|
| v7 | mt01 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt02 | mentions_day30 | instruction_following (mentions_day30) |
| v7+e38 | mt16 | must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt17 | must_include_any2, asks_question | retrieval (expected facts not in retrieved context) |
| v7 | rw01 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | rw07 | asks_question | instruction_following (asks_question) |
| v7+e38 | rw08 | must_include_any | prompt (facts available but not used) |
| v7 | rw20 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | rw24 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | rw30 | must_include_any3 | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw45 | must_include_any2 | retrieval (expected facts not in retrieved context) |
