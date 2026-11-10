# End-to-end journeys (20261110T081031Z)

10 live conversations (`src/eval/heldout/journeys_v1.jsonl`). A journey succeeds only if every turn passes.

| Metric | v7 | v7+e38 |
|---|---|---|
| journeys | 10 | 10 |
| excluded_model_fallback | 0 | 0 |
| task_success | 0.0 | 0.1 |
| turn_pass_rate | 0.436 | 0.462 |
| avg_latency_ms | 195 | 139 |
| p95_latency_ms | 186.7 | 219.9 |

| Journey | v7 | v7+e38 |
|---|---|---|
| j01 | ✗ t1, t2, t4 | ✗ t1, t4 |
| j02 | ✗ t3, t4 | ✗ t2, t3, t4 |
| j03 | ✗ t1, t4 | ✗ t1, t4 |
| j04 | ✗ t1, t3, t4 | ✗ t1, t3, t4 |
| j05 | ✗ t2, t3 | ✗ t3, t4 |
| j06 | ✗ t4 | ✓ |
| j07 | ✗ t1, t3 | ✗ t1, t3 |
| j08 | ✗ t4 | ✗ t4 |
| j09 | ✗ t1, t3, t4 | ✗ t1, t3, t4 |
| j10 | ✗ t1, t3, t4 | ✗ t1, t3, t4 |

Failed turns:

- **v7**: j01 t1: min_numbered; j01 t2: mentions_item_of_turn; j01 t4: must_include_any; j02 t3: must_include_any, must_include_any2; j02 t4: must_include_any, must_include_any2; j03 t1: min_numbered; j03 t4: must_include_any; j04 t1: must_include_any; j04 t3: code_block, must_include_any; j04 t4: n_items; j05 t2: mentions_item_of_turn; j05 t3: mentions_item_of_turn, must_include_any; j06 t4: must_include_any, must_include_any2; j07 t1: must_include_any; j07 t3: n_items, must_include_any; j08 t4: must_include_any; j09 t1: must_include_any; j09 t3: must_include_any, must_include_any2; j09 t4: mentions_day30, must_include_any, must_include_any2; j10 t1: must_include_any; j10 t3: no_guarantee; j10 t4: must_include_any
- **v7+e38**: j01 t1: min_numbered; j01 t4: must_include_any; j02 t2: must_include_any; j02 t3: must_include_any, must_include_any2; j02 t4: must_include_any, must_include_any2; j03 t1: min_numbered; j03 t4: must_include_any; j04 t1: must_include_any; j04 t3: code_block, must_include_any; j04 t4: n_items; j05 t3: mentions_item_of_turn, must_include_any; j05 t4: must_include_any; j07 t1: must_include_any; j07 t3: n_items, must_include_any; j08 t4: must_include_any; j09 t1: must_include_any; j09 t3: must_include_any, must_include_any2; j09 t4: mentions_day30, must_include_any, must_include_any2; j10 t1: must_include_any; j10 t3: no_guarantee; j10 t4: must_include_any
