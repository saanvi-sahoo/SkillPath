# Prompt evaluation (20261107T210556Z)

Cases: 2 - router mode for answers: `hybrid`
Design: paired, strict model `gemini-3.1-flash-lite`, completed pairs 2/2

## Router

| Mode | Label acc | Allow/refuse acc | False refusals | Leaks | LLM calls | Avg ms |
|---|---|---|---|---|---|---|
| knn | 1.0 | 1.0 | 0 | 0 | 0 | 2625.8 |

## Answers by system-prompt version

| Version | Pass rate | Citation rate | Avg words | Avg ms | Judge rel | Judge grounded | Judge scope | Judge action |
|---|---|---|---|---|---|---|---|---|
| v3 | 0.0 | 1.0 | 246.0 | 19572.6 | - | - | - | - |
| v4 | 1.0 | 1.0 | 187.0 | 4856.7 | - | - | - | - |

### v3 pass rate by category

{"weak_evidence": 0.0}

Answering models: {"gemini-3.1-flash-lite": 2} - errors: None

Failed: doc06 {'asks_question': False, 'not_refused': True}, doc09 {'asks_question': False, 'not_refused': True}

### v4 pass rate by category

{"weak_evidence": 1.0}

Answering models: {"gemini-3.1-flash-lite": 2} - errors: None
