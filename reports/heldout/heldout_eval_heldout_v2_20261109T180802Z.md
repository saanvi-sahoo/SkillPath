# Held-out chatbot evaluation (20261109T180802Z)

Frozen set: `src/eval/heldout/heldout_chat.jsonl` (40 cases). Paired design, shared route per case. Completed pairs: 40

| Metric | Target (review doc) | v7 | v8 |
|---|---|---|---|
| pass_rate | - | 0.9 | 0.975 |
| intent_accuracy | - | None | 0.676 |
| scope_accuracy | >= 0.98 | 0.9 | 0.925 |
| false_refusals | as low as possible | 2 | 1 |
| out_of_scope_leaks | 0 | 0 | 0 |
| constraint_compliance | >= 0.95 | 1.0 | 1.0 |
| factual_correctness | >= 0.95 | 0.906 | 0.969 |
| citation_rate | - | 0.45 | 0.425 |
| citation_correctness | >= 0.95 | 0.958 | 0.982 |
| claim_support_rate | higher is better | 0.268 | 0.436 |
| claim_contradiction_rate | 0 | 0.036 | 0.051 |
| profile_consistency | 1.0 | 1.0 | 1.0 |
| revised | - | 6 | 8 |
| avg_latency_ms | - | 6004 | 5669 |
| avg_tokens | - | 2263 | 1477 |

## Pass rate by category

| Category | v7 | v8 |
|---|---|---|
| career | 1.0 | 1.0 |
| concept | 0.8 | 1.0 |
| multi_turn | 0.875 | 0.875 |
| profile | 1.0 | 1.0 |
| roadmap | 0.75 | 1.0 |
| scope | 0.75 | 1.0 |
| study | 1.0 | 1.0 |

## Root causes of failures

- **v7**: {"prompt": 3, "scope_router": 1} · models ['None', 'gemini-3.1-flash-lite']
- **v8**: {"scope_router": 1} · models ['None', 'gemini-3.1-flash-lite']

## Failed cases

| Version | Case | Failed checks | Root cause |
|---|---|---|---|
| v7 | v2-s01 | no_career_citations | prompt (forbidden content: no_career_citations) |
| v7 | v2-r04 | no_invented_urls | prompt (forbidden content: no_invented_urls) |
| v7 | v2-o03 | not_refused | prompt (model refused) |
| v7 | v2-m02 | not_refused, must_include_any | scope_router (valid question refused) |
| v8 | v2-m02 | not_refused, must_include_any | scope_router (valid question refused) |
