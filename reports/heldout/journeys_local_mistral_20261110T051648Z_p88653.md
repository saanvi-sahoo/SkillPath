# End-to-end journeys (20261110T051648Z)

10 live conversations (`src/eval/heldout/journeys_v1.jsonl`). A journey succeeds only if every turn passes.

| Metric | v7 | v7+e38 |
|---|---|---|
| journeys | 10 | 10 |
| excluded_model_fallback | 0 | 0 |
| task_success | 0.1 | 0.3 |
| turn_pass_rate | 0.615 | 0.692 |
| avg_latency_ms | 46117 | 51933 |
| p95_latency_ms | 79272.1 | 102256.7 |

| Journey | v7 | v7+e38 |
|---|---|---|
| j01 | ✗ t2, t3 | ✗ t2 |
| j02 | ✗ t4 | ✗ t4 |
| j03 | ✗ t1, t3, t4 | ✗ t1, t4 |
| j04 | ✗ t1, t3 | ✗ t1, t3 |
| j05 | ✓ | ✓ |
| j06 | ✗ t4 | ✓ |
| j07 | ✗ t2 | ✗ t2, t3 |
| j08 | ✗ t3 | ✓ |
| j09 | ✗ t1, t3, t4 | ✗ t3, t4 |
| j10 | ✗ t4 | ✗ t2, t4 |

Failed turns:

- **v7**: j01 t2: mentions_item_of_turn; j01 t3: must_include_any; j02 t4: must_include_any2; j03 t1: min_numbered; j03 t3: mentions_day30; j03 t4: not_refused, must_include_any; j04 t1: not_refused, must_include_any; j04 t3: code_block, must_include_any; j06 t4: must_include_any2; j07 t2: refusal; j08 t3: must_include_any2; j09 t1: must_include_any; j09 t3: not_refused, must_include_any, must_include_any2; j09 t4: mentions_day30, must_include_any; j10 t4: must_include_any
- **v7+e38**: j01 t2: not_refused, mentions_item_of_turn; j02 t4: must_include_any2; j03 t1: min_numbered; j03 t4: not_refused, must_include_any; j04 t1: not_refused, must_include_any; j04 t3: code_block, must_include_any; j07 t2: refusal; j07 t3: must_include_any; j09 t3: not_refused, must_include_any, must_include_any2; j09 t4: mentions_day30, must_include_any, must_include_any2; j10 t2: not_refused; j10 t4: must_include_any
