# Held-out chatbot evaluation (20261109T173239Z)

Frozen set: `src/eval/heldout/heldout_chat.jsonl` (40 cases). Paired design, shared route per case. Completed pairs: 40

| Metric | Target (review doc) | v7 | v8 |
|---|---|---|---|
| pass_rate | - | 0.8 | 0.825 |
| intent_accuracy | - | None | 0.667 |
| scope_accuracy | >= 0.98 | 0.9 | 0.9 |
| false_refusals | as low as possible | 2 | 2 |
| out_of_scope_leaks | 0 | 0 | 0 |
| constraint_compliance | >= 0.95 | 0.733 | 0.867 |
| factual_correctness | >= 0.95 | 0.875 | 0.844 |
| citation_rate | - | 0.2 | 0.25 |
| citation_correctness | >= 0.95 | 0.929 | 0.92 |
| claim_support_rate | higher is better | 0.667 | 0.5 |
| claim_contradiction_rate | 0 | 0.0 | 0.0 |
| profile_consistency | 1.0 | 1.0 | 1.0 |
| revised | - | 5 | 9 |
| avg_latency_ms | - | 47198 | 45262 |
| avg_tokens | - | 2574 | 1752 |

## Pass rate by category

| Category | v7 | v8 |
|---|---|---|
| career | 0.75 | 1.0 |
| concept | 1.0 | 0.8 |
| multi_turn | 0.625 | 0.625 |
| profile | 1.0 | 0.75 |
| roadmap | 0.5 | 1.0 |
| scope | 1.0 | 1.0 |
| study | 0.667 | 0.667 |

## Root causes of failures

- **v7**: {"scope_router": 2, "instruction_following": 3, "prompt": 3} · models ['None', 'mistral']
- **v8**: {"scope_router": 2, "retrieval": 1, "prompt": 3, "instruction_following": 1} · models ['None', 'mistral']

## Failed cases

| Version | Case | Failed checks | Root cause |
|---|---|---|---|
| v7 | v2-s04 | not_refused, n_sentences | scope_router (valid question refused) |
| v8 | v2-s04 | not_refused, n_sentences | scope_router (valid question refused) |
| v8 | v2-s07 | must_include_all, intent | retrieval (expected facts not in retrieved context) |
| v7 | v2-c02 | first_sentence_any | instruction_following (first_sentence_any) |
| v7 | v2-c06 | no_guarantee | prompt (forbidden content: no_guarantee) |
| v8 | v2-p01 | include_frac, intent | prompt (facts available but not used) |
| v8 | v2-p06 | must_include_any, intent | prompt (facts available but not used) |
| v7 | v2-r03 | mentions_day30 | instruction_following (mentions_day30) |
| v7 | v2-r04 | no_invented_urls | prompt (forbidden content: no_invented_urls) |
| v7 | v2-m01 | first_sentence_any | instruction_following (first_sentence_any) |
| v8 | v2-m01 | first_sentence_any | instruction_following (first_sentence_any) |
| v7 | v2-m04 | not_refused, must_include_any | scope_router (valid question refused) |
| v8 | v2-m04 | not_refused, must_include_any | scope_router (valid question refused) |
| v7 | v2-m06 | must_include_any | prompt (facts available but not used) |
| v8 | v2-m06 | must_include_any | prompt (facts available but not used) |
