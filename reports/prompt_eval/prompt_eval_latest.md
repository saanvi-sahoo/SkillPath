# Prompt evaluation (20261108T092839Z)

Cases: 65 - router mode for answers: `hybrid`
Design: paired, strict model `gemini-3.1-flash-lite`, completed pairs 30/65 (stopped: case edge01 v5: model=openai/gpt-oss-20b error=None)

## Router

| Mode | Label acc | Allow/refuse acc | False refusals | Leaks | LLM calls | Avg ms |
|---|---|---|---|---|---|---|
| knn | 0.969 | 1.0 | 0 | 0 | 0 | 80.0 |

**knn errors:** gr02 (exp greeting, got career_study), doc05 (exp prompt_attack, got out_of_scope)

## Answers by system-prompt version

| Version | Pass rate | Citation rate | Avg words | Avg ms | Judge rel | Judge grounded | Judge scope | Judge action |
|---|---|---|---|---|---|---|---|---|
| v5 | 1.0 | 0.941 | 161.4 | 1851.0 | - | - | - | - |
| v6 | 1.0 | 1.0 | 168.4 | 2010.0 | - | - | - | - |

### v5 pass rate by category

{"profile": 1.0, "general_career": 1.0, "study": 1.0, "follow_up": 1.0, "greeting": 1.0, "out_of_scope": 1.0, "prompt_attack": 1.0}

Answering models: {"gemini-3.1-flash-lite": 20, "None": 10} - errors: None

### v6 pass rate by category

{"profile": 1.0, "general_career": 1.0, "study": 1.0, "follow_up": 1.0, "greeting": 1.0, "out_of_scope": 1.0, "prompt_attack": 1.0}

Answering models: {"gemini-3.1-flash-lite": 20, "None": 10} - errors: None
