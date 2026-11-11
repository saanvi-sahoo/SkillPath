# End-to-end journeys (20261111T095653Z)

Live conversations (`journeys_v1.jsonl`). A journey succeeds only if every turn passes.

| Metric | v7+e38 |
|---|---|
| journeys | 4 |
| excluded_model_fallback | 0 |
| task_success | 0.75 |
| turn_pass_rate | 0.938 |
| avg_latency_ms | 3249 |
| p95_latency_ms | 4589.0 |

| Journey | v7+e38 |
|---|---|
| j01 | ✓ |
| j03 | ✗ t3 |
| j04 | ✓ |
| j08 | ✓ |

Failed turns:

- **v7+e38**: j03 t3: mentions_day30, must_include_any
