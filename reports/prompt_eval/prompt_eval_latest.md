# Prompt evaluation (20261107T214826Z)

Cases: 42 - router mode for answers: `hybrid`
Design: paired, strict model ``, completed pairs 42/42

## Router

| Mode | Label acc | Allow/refuse acc | False refusals | Leaks | LLM calls | Avg ms |
|---|---|---|---|---|---|---|
| knn | 0.952 | 1.0 | 0 | 0 | 0 | 131.7 |

**knn errors:** gr02 (exp greeting, got career_study), doc05 (exp prompt_attack, got out_of_scope)

## Answers by system-prompt version

| Version | Pass rate | Citation rate | Avg words | Avg ms | Judge rel | Judge grounded | Judge scope | Judge action |
|---|---|---|---|---|---|---|---|---|
| v4 | 0.881 | 0.296 | 180.7 | 38583.5 | - | - | - | - |

### v4 pass rate by category

{"profile": 0.8, "general_career": 0.8, "study": 1.0, "follow_up": 1.0, "greeting": 1.0, "out_of_scope": 1.0, "prompt_attack": 1.0, "edge": 1.0, "career_reco": 0.0, "ambiguous": 1.0, "weak_evidence": 0.5, "skill_equivalence": 1.0, "salary": 1.0}

Answering models: {"mistral": 30, "None": 12} - errors: None

Failed: cs04 {'citation': False, 'not_refused': True}, cs07 {'must_include_any': True, 'citation': False, 'not_refused': True}, doc01 {'must_include_any': True, 'citation': False, 'not_refused': True}, doc09 {'asks_question': False, 'not_refused': True}, doc10 {'must_include_any': True, 'citation': False, 'not_refused': True}
