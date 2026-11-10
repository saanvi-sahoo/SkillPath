# Held-out chatbot evaluation (20261110T034010Z)

Frozen set: `heldout_v3` (50 cases). Paired design, shared route per case. Completed pairs: 50

| Metric | Target (review doc) | v7 | v7+e38 |
|---|---|---|---|
| pass_rate | - | 0.5 | 0.62 |
| intent_accuracy | - | None | 1.0 |
| scope_accuracy | >= 0.98 | 0.9 | 0.9 |
| false_refusals | as low as possible | 5 | 5 |
| out_of_scope_leaks | 0 | 0 | 0 |
| constraint_compliance | >= 0.95 | 0.667 | 0.75 |
| factual_correctness | >= 0.95 | 0.626 | 0.78 |
| citation_rate | - | 0.191 | 0.277 |
| citation_correctness | >= 0.95 | 0.647 | 0.833 |
| claim_support_rate | higher is better | 0.4 | 0.474 |
| claim_contradiction_rate | 0 | 0.0 | 0.0 |
| profile_consistency | 1.0 | 1.0 | 1.0 |
| revised | - | 9 | 10 |
| avg_latency_ms | - | 37080 | 40902 |
| p95_latency_ms | - | 94183 | 157010 |
| avg_tokens | - | 2602 | 2871 |

## Pass rate by category

| Category | v7 | v7+e38 |
|---|---|---|
| multi_turn | 0.468 | 0.596 |
| out_of_scope | 1.0 | 1.0 |

## Root causes of failures

- **v7**: {"retrieval": 17, "scope_router": 5, "prompt": 3} · models ['None', 'mistral']
- **v7+e38**: {"prompt": 6, "retrieval": 6, "scope_router": 5, "instruction_following": 2} · models ['None', 'mistral']

## Failed cases

| Version | Case | Failed checks | Root cause |
|---|---|---|---|
| v7 | mt01 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt01 | must_include_any2 | prompt (facts available but not used) |
| v7 | mt02 | must_include_any, must_include_any2, must_include_any3 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt02 | must_include_any3 | prompt (facts available but not used) |
| v7 | mt03 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt03 | must_include_any2 | prompt (facts available but not used) |
| v7 | mt04 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt04 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt05 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt08 | must_include_any, mentions_day30 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt08 | must_include_any | prompt (facts available but not used) |
| v7 | mt09 | not_refused, must_include_any | scope_router (valid question refused) |
| v7+e38 | mt09 | not_refused, must_include_any | scope_router (valid question refused) |
| v7 | mt10 | must_include_any, n_items | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt10 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt13 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7 | mt14 | not_refused, must_include_any, must_include_any2 | scope_router (valid question refused) |
| v7+e38 | mt14 | not_refused, must_include_any, must_include_any2 | scope_router (valid question refused) |
| v7 | mt15 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt16 | must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt16 | must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt17 | must_include_any, must_include_any2, asks_question | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt17 | asks_question | instruction_following (asks_question) |
| v7 | mt19 | not_refused, must_include_any | scope_router (valid question refused) |
| v7+e38 | mt19 | not_refused, must_include_any | scope_router (valid question refused) |
| v7 | mt22 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt25 | must_include_any | prompt (facts available but not used) |
| v7 | mt26 | must_include_any2 | prompt (facts available but not used) |
| v7+e38 | mt26 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7 | mt31 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt31 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt32 | must_include_any2 | prompt (facts available but not used) |
| v7 | mt36 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt44 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt44 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt45 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt45 | mentions_day30 | instruction_following (mentions_day30) |
| v7 | mt46 | not_refused, n_sentences | scope_router (valid question refused) |
| v7+e38 | mt46 | not_refused, n_sentences | scope_router (valid question refused) |
| v7 | mt47 | not_refused, must_include_any, must_include_any2 | scope_router (valid question refused) |
| v7+e38 | mt47 | not_refused, must_include_any, must_include_any2 | scope_router (valid question refused) |
| v7 | mt48 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt49 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt50 | must_include_any | retrieval (expected facts not in retrieved context) |
