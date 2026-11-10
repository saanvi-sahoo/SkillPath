# End-to-end journeys (20261110T043249Z)

10 live conversations (`src/eval/heldout/journeys_v1.jsonl`). A journey succeeds only if every turn passes.

| Metric | v7 | v7+e38 |
|---|---|---|
| journeys | 8 | 8 |
| excluded_model_fallback | 1 | 0 |
| task_success | 0.625 | 0.5 |
| turn_pass_rate | 0.871 | 0.839 |
| avg_latency_ms | 3496 | 5080 |
| p95_latency_ms | 6285.0 | 6614.0 |

| Journey | v7 | v7+e38 |
|---|---|---|
| j01 | ✗ t1 | ✗ t1 |
| j02 | ✓ | ✓ |
| j03 | ✗ t1, t3 | ✗ t1, t3 |
| j04 | ✓ | ✗ t2 |
| j05 | ✓ | ✓ |
| j06 | ✓ | ✓ |
| j07 | ✓ | ✓ |
| j08 | ✗ t3 | ✗ t3 |
| j09 | ✓ | - |

Failed turns:

- **v7**: j01 t1: min_numbered; j03 t1: min_numbered; j03 t3: profile_consistent; j08 t3: must_include_any
- **v7+e38**: j01 t1: min_numbered; j03 t1: min_numbered; j03 t3: mentions_day30; j04 t2: max_words; j08 t3: must_include_any
