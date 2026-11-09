# Held-out chatbot evaluation (20261109T162953Z)

Frozen set: `src/eval/heldout/heldout_chat.jsonl` (4 cases). Paired design, shared route per case. Completed pairs: 4

| Metric | Target (review doc) | v8 |
|---|---|---|
| pass_rate | - | 1.0 |
| intent_accuracy | - | 1.0 |
| scope_accuracy | >= 0.98 | 1.0 |
| false_refusals | as low as possible | 0 |
| out_of_scope_leaks | 0 | 0 |
| constraint_compliance | >= 0.95 | None |
| factual_correctness | >= 0.95 | 1.0 |
| citation_rate | - | 0.0 |
| citation_correctness | >= 0.95 | None |
| claim_support_rate | higher is better | None |
| claim_contradiction_rate | 0 | None |
| profile_consistency | 1.0 | 1.0 |
| revised | - | 2 |
| avg_latency_ms | - | 4337 |
| avg_tokens | - | 1781 |

## Pass rate by category

| Category | v8 |
|---|---|
| concept | 1.0 |
| hard | 1.0 |
| multi_turn | 1.0 |
| resume_jd | 1.0 |

## Root causes of failures

- **v8**: {} · models ['openai/gpt-oss-120b']
