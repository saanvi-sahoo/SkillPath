# Prompt evaluation (20261110T080722Z)

Cases: 65 - router mode for answers: `hybrid`
Design: paired, strict model ``, completed pairs 65/65

## Router

| Mode | Label acc | Allow/refuse acc | False refusals | Leaks | LLM calls | Avg ms |
|---|---|---|---|---|---|---|
| hybrid | 0.985 | 1.0 | 0 | 0 | 0 | 76.9 |

**hybrid errors:** doc05 (exp prompt_attack, got out_of_scope)

## Answers by system-prompt version

| Version | Pass rate | Citation rate | Avg words | Avg ms | Judge rel | Judge grounded | Judge scope | Judge action |
|---|---|---|---|---|---|---|---|---|
| v4 | 0.877 | 0.767 | 139.1 | 140.1 | - | - | - | - |

### v4 pass rate by category

{"profile": 1.0, "general_career": 1.0, "study": 1.0, "follow_up": 1.0, "greeting": 1.0, "out_of_scope": 1.0, "prompt_attack": 1.0, "edge": 1.0, "career_reco": 1.0, "ambiguous": 1.0, "weak_evidence": 1.0, "skill_equivalence": 1.0, "salary": 1.0, "precision": 0.222, "scope_in": 0.857, "scope_out": 1.0}

Answering models: {"None": 65} - errors: None

Failed: p01 {'list_count': False, 'not_refused': True}, p02 {'max_words': False, 'not_refused': True}, p03 {'list_count': False, 'not_refused': True}, p05 {'must_include_any': False, 'max_words': True, 'not_refused': True}, p06 {'first_sentence': False, 'not_refused': True}, p07 {'must_include_any': False, 'not_refused': True}, p09 {'list_count': False, 'max_words': False, 'not_refused': True}, s04 {'first_sentence': False, 'not_refused': True}
