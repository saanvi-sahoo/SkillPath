# Prompt evaluation (20261108T084136Z)

Cases: 51 - router mode for answers: `hybrid`
Design: paired, strict model `gemini-3.1-flash-lite`, completed pairs 51/51

## Router

| Mode | Label acc | Allow/refuse acc | False refusals | Leaks | LLM calls | Avg ms |
|---|---|---|---|---|---|---|
| knn | 0.961 | 1.0 | 0 | 0 | 0 | 194.7 |

**knn errors:** gr02 (exp greeting, got career_study), doc05 (exp prompt_attack, got out_of_scope)

## Answers by system-prompt version

| Version | Pass rate | Citation rate | Avg words | Avg ms | Judge rel | Judge grounded | Judge scope | Judge action |
|---|---|---|---|---|---|---|---|---|
| v4 | 0.922 | 0.889 | 200.6 | 3537.2 | - | - | - | - |
| v5 | 0.98 | 0.778 | 155.6 | 2155.5 | - | - | - | - |

### v4 pass rate by category

{"profile": 1.0, "general_career": 1.0, "study": 1.0, "follow_up": 1.0, "greeting": 1.0, "out_of_scope": 1.0, "prompt_attack": 1.0, "edge": 1.0, "career_reco": 0.5, "ambiguous": 1.0, "weak_evidence": 1.0, "skill_equivalence": 1.0, "salary": 1.0, "precision": 0.667}

Answering models: {"gemini-3.1-flash-lite": 39, "None": 12} - errors: None

Failed: doc01 {'must_include_any': False, 'citation': True, 'not_refused': True}, p03 {'list_count': False, 'not_refused': True}, p05 {'must_include_any': True, 'max_words': False, 'not_refused': True}, p08 {'first_sentence': False, 'not_refused': True}

### v5 pass rate by category

{"profile": 1.0, "general_career": 1.0, "study": 1.0, "follow_up": 1.0, "greeting": 1.0, "out_of_scope": 1.0, "prompt_attack": 1.0, "edge": 1.0, "career_reco": 1.0, "ambiguous": 1.0, "weak_evidence": 1.0, "skill_equivalence": 1.0, "salary": 1.0, "precision": 0.889}

Answering models: {"gemini-3.1-flash-lite": 39, "None": 12} - errors: None

Failed: p01 {'list_count': False, 'not_refused': True}
