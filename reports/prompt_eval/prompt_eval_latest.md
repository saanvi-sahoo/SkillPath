# Prompt evaluation (20261107T214739Z)

Cases: 42 - router mode for answers: `hybrid`
Design: paired, strict model ``, completed pairs 42/42

## Router

| Mode | Label acc | Allow/refuse acc | False refusals | Leaks | LLM calls | Avg ms |
|---|---|---|---|---|---|---|
| hybrid | 0.952 | 1.0 | 0 | 0 | 0 | 113.8 |

**hybrid errors:** gr02 (exp greeting, got career_study), doc05 (exp prompt_attack, got out_of_scope)

## Answers by system-prompt version

| Version | Pass rate | Citation rate | Avg words | Avg ms | Judge rel | Judge grounded | Judge scope | Judge action |
|---|---|---|---|---|---|---|---|---|
| v4 | 1.0 | 0.929 | 154.8 | 240.3 | - | - | - | - |

### v4 pass rate by category

{"profile": 1.0, "general_career": 1.0, "study": 1.0, "follow_up": 1.0, "greeting": 1.0, "out_of_scope": 1.0, "prompt_attack": 1.0, "edge": 1.0, "career_reco": 1.0, "ambiguous": 1.0, "weak_evidence": 1.0, "skill_equivalence": 1.0, "salary": 1.0}

Answering models: {"None": 42} - errors: None
