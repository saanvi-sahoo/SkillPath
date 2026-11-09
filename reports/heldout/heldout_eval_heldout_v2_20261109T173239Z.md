# Held-out chatbot evaluation (20261109T173239Z)

Frozen set: `src/eval/heldout/heldout_chat.jsonl` (40 cases). Paired design, shared route per case. Completed pairs: 12

| Metric | Target (review doc) | v7 | v8 |
|---|---|---|---|
| pass_rate | - | 0.833 | 0.833 |
| intent_accuracy | - | None | 0.818 |
| scope_accuracy | >= 0.98 | 0.917 | 0.917 |
| false_refusals | as low as possible | 1 | 1 |
| out_of_scope_leaks | 0 | 0 | 0 |
| constraint_compliance | >= 0.95 | 0.714 | 0.857 |
| factual_correctness | >= 0.95 | 1.0 | 0.909 |
| citation_rate | - | 0.167 | 0.333 |
| citation_correctness | >= 0.95 | 1.0 | 1.0 |
| claim_support_rate | higher is better | 1.0 | 0.889 |
| claim_contradiction_rate | 0 | 0.0 | 0.0 |
| profile_consistency | 1.0 | None | None |
| revised | - | 1 | 3 |
| avg_latency_ms | - | 33696 | 32557 |
| avg_tokens | - | 2538 | 1596 |

## Pass rate by category

| Category | v7 | v8 |
|---|---|---|
| career | 0.75 | 1.0 |
| concept | 1.0 | 0.8 |
| study | 0.667 | 0.667 |

## Root causes of failures

- **v7**: {"scope_router": 1, "instruction_following": 1} · models ['None', 'mistral']
- **v8**: {"scope_router": 1, "retrieval": 1} · models ['None', 'mistral']

## Failed cases

| Version | Case | Failed checks | Root cause |
|---|---|---|---|
| v7 | v2-s04 | not_refused, n_sentences | scope_router (valid question refused) |
| v8 | v2-s04 | not_refused, n_sentences | scope_router (valid question refused) |
| v8 | v2-s07 | must_include_all, intent | retrieval (expected facts not in retrieved context) |
| v7 | v2-c02 | first_sentence_any | instruction_following (first_sentence_any) |
