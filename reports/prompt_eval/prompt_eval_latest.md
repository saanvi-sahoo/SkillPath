# Prompt evaluation (20261107T213644Z)

Cases: 42 - router mode for answers: `hybrid`
Design: paired, strict model `openai/gpt-oss-120b`, completed pairs 1/42

## Router

| Mode | Label acc | Allow/refuse acc | False refusals | Leaks | LLM calls | Avg ms |
|---|---|---|---|---|---|---|
| knn | 0.952 | 1.0 | 0 | 0 | 0 | 147.6 |

**knn errors:** gr02 (exp greeting, got career_study), doc05 (exp prompt_attack, got out_of_scope)

## Answers by system-prompt version

| Version | Pass rate | Citation rate | Avg words | Avg ms | Judge rel | Judge grounded | Judge scope | Judge action |
|---|---|---|---|---|---|---|---|---|
| v4 | 1.0 | 0.0 | 195.0 | 3254.8 | - | - | - | - |

### v4 pass rate by category

{"profile": 1.0}

Answering models: {"openai/gpt-oss-120b": 1} - errors: None
