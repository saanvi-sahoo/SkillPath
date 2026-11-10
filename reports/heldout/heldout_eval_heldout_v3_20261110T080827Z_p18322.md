# Held-out chatbot evaluation (20261110T080827Z)

Frozen set: `heldout_v3` (120 cases). Paired design, shared route per case. Completed pairs: 120

| Metric | Target (review doc) | v7 | v7+e38 |
|---|---|---|---|
| pass_rate | - | 0.392 | 0.45 |
| intent_accuracy | - | 1.0 | 1.0 |
| scope_accuracy | >= 0.98 | 0.983 | 0.983 |
| false_refusals | as low as possible | 2 | 2 |
| out_of_scope_leaks | 0 | 0 | 0 |
| constraint_compliance | >= 0.95 | 0.429 | 0.429 |
| factual_correctness | >= 0.95 | 0.384 | 0.454 |
| citation_rate | - | 0.467 | 0.542 |
| citation_correctness | >= 0.95 | 1.0 | 1.0 |
| claim_support_rate | higher is better | 1.0 | 1.0 |
| claim_contradiction_rate | 0 | 0.0 | 0.0 |
| profile_consistency | 1.0 | 1.0 | 1.0 |
| revised | - | 0 | 0 |
| avg_latency_ms | - | 122 | 121 |
| p95_latency_ms | - | 173 | 224 |
| avg_tokens | - | None | None |

## Pass rate by category

| Category | v7 | v7+e38 |
|---|---|---|
| multi_turn | 0.17 | 0.319 |
| out_of_scope | 1.0 | 1.0 |
| profile | 0.75 | 0.75 |
| real_world | 0.354 | 0.354 |

## Root causes of failures

- **v7**: {"retrieval": 54, "prompt": 14, "scope_router": 2, "instruction_following": 3} · models ['None']
- **v7+e38**: {"prompt": 17, "retrieval": 44, "scope_router": 2, "instruction_following": 3} · models ['None']

## Failed cases

| Version | Case | Failed checks | Root cause |
|---|---|---|---|
| v7 | mt01 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt02 | must_include_any, must_include_any2, must_include_any3, mentions_day30 | retrieval (expected facts not in retrieved context) |
| v7 | mt03 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt03 | must_include_any2 | prompt (facts available but not used) |
| v7 | mt04 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt04 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt05 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt05 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt06 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt06 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt08 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt09 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt10 | must_include_any, n_items | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt10 | must_include_any, n_items | retrieval (expected facts not in retrieved context) |
| v7 | mt12 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt12 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt13 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7+e38 | mt13 | must_include_any2 | prompt (facts available but not used) |
| v7 | mt14 | must_not_include | prompt (forbidden content: must_not_include) |
| v7+e38 | mt14 | must_not_include | prompt (forbidden content: must_not_include) |
| v7 | mt15 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt15 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt16 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt16 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt17 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt17 | must_include_any2, asks_question | retrieval (expected facts not in retrieved context) |
| v7 | mt19 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt19 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt22 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt22 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt23 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt23 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt24 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt24 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt25 | must_include_any | prompt (facts available but not used) |
| v7 | mt27 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt27 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt28 | table, must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt28 | table, must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt29 | must_include_any2 | prompt (facts available but not used) |
| v7+e38 | mt29 | must_include_any2 | prompt (facts available but not used) |
| v7 | mt30 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt31 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt31 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt33 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt33 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt34 | code_block, must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt34 | code_block, must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt35 | n_items, must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt35 | n_items, must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt36 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt37 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt37 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt38 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt38 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt39 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt39 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt43 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt43 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt44 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt44 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt45 | mentions_day30, must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt45 | mentions_day30, must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt46 | not_refused, n_sentences | scope_router (valid question refused) |
| v7+e38 | mt46 | not_refused, n_sentences | scope_router (valid question refused) |
| v7 | mt47 | not_refused, must_include_any, must_include_any2 | scope_router (valid question refused) |
| v7+e38 | mt47 | not_refused, must_include_any, must_include_any2 | scope_router (valid question refused) |
| v7 | mt48 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | mt48 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | mt49 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | mt50 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | rw01 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw01 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | rw04 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7+e38 | rw04 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7 | rw06 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw06 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | rw07 | must_include_any2, asks_question | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw07 | must_include_any2, asks_question | retrieval (expected facts not in retrieved context) |
| v7 | rw11 | no_guarantee | prompt (forbidden content: no_guarantee) |
| v7+e38 | rw11 | no_guarantee | prompt (forbidden content: no_guarantee) |
| v7 | rw12 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw12 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | rw13 | table, must_include_any | prompt (facts available but not used) |
| v7+e38 | rw13 | table, must_include_any | prompt (facts available but not used) |
| v7 | rw14 | must_include_any, must_include_any2, must_include_any3 | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw14 | must_include_any, must_include_any2, must_include_any3 | retrieval (expected facts not in retrieved context) |
| v7 | rw15 | must_include_any, must_include_any2, must_include_any3 | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw15 | must_include_any, must_include_any2, must_include_any3 | retrieval (expected facts not in retrieved context) |
| v7 | rw16 | n_items | instruction_following (n_items) |
| v7+e38 | rw16 | n_items | instruction_following (n_items) |
| v7 | rw19 | must_include_any | prompt (facts available but not used) |
| v7+e38 | rw19 | must_include_any | prompt (facts available but not used) |
| v7 | rw20 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw20 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | rw21 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw21 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | rw23 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7+e38 | rw23 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7 | rw24 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw24 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | rw25 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw25 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | rw27 | n_items | instruction_following (n_items) |
| v7+e38 | rw27 | n_items | instruction_following (n_items) |
| v7 | rw28 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw28 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7 | rw29 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw29 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | rw32 | must_include_any | prompt (facts available but not used) |
| v7+e38 | rw32 | must_include_any | prompt (facts available but not used) |
| v7 | rw34 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw34 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | rw35 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw35 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | rw36 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw36 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | rw37 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw37 | must_include_any, must_include_any2 | retrieval (expected facts not in retrieved context) |
| v7 | rw38 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7+e38 | rw38 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7 | rw39 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw39 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | rw40 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw40 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7 | rw43 | must_include_any2 | prompt (facts available but not used) |
| v7+e38 | rw43 | must_include_any2 | prompt (facts available but not used) |
| v7 | rw44 | must_include_any, must_include_any2, must_include_any3 | retrieval (expected facts not in retrieved context) |
| v7+e38 | rw44 | must_include_any, must_include_any2, must_include_any3 | retrieval (expected facts not in retrieved context) |
| v7 | rw45 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7+e38 | rw45 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7 | rw48 | n_sentences | instruction_following (n_sentences) |
| v7+e38 | rw48 | n_sentences | instruction_following (n_sentences) |
| v7 | pf04 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7+e38 | pf04 | must_include_any, must_include_any2 | prompt (facts available but not used) |
| v7 | pf05 | include_frac | prompt (facts available but not used) |
| v7+e38 | pf05 | include_frac | prompt (facts available but not used) |
| v7 | pf11 | must_include_any | retrieval (expected facts not in retrieved context) |
| v7+e38 | pf11 | must_include_any | retrieval (expected facts not in retrieved context) |
