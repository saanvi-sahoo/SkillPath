# Held-out chatbot evaluation (20261109T182912Z)

Frozen set: `src/eval/heldout/heldout_chat.jsonl` (1 cases). Paired design, shared route per case. Completed pairs: 1

| Metric | Target (review doc) | v7 |
|---|---|---|
| pass_rate | - | 1.0 |
| intent_accuracy | - | None |
| scope_accuracy | >= 0.98 | 1.0 |
| false_refusals | as low as possible | 0 |
| out_of_scope_leaks | 0 | 0 |
| constraint_compliance | >= 0.95 | None |
| factual_correctness | >= 0.95 | 1.0 |
| citation_rate | - | 1.0 |
| citation_correctness | >= 0.95 | 1.0 |
| claim_support_rate | higher is better | 0.0 |
| claim_contradiction_rate | 0 | 0.0 |
| profile_consistency | 1.0 | None |
| revised | - | 1 |
| avg_latency_ms | - | 10002 |
| avg_tokens | - | 2676 |

## Pass rate by category

| Category | v7 |
|---|---|
| multi_turn | 1.0 |

## Root causes of failures

- **v7**: {} · models ['gemini-3.1-flash-lite']
