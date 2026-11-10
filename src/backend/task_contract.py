"""
Prompt v8 task layer + task-specific answer validation (E37, review 2 §6-7).

  task_prompt(intent)            the task template for the primary intent (+ one line per secondary intent);
                                 only the template that applies is sent, not every template on every turn
  contract_v8(intent)            the parsed request as explicit, checkable requirements
  check_v8(...)                  deterministic contract checks + claim-level citation verification (NLI)
  roadmap_evidence(...)          30-day / N-week plan requests get the validated roadmap generator's plan as a source
  pick_examples(intent)          only the few-shot examples that match this intent
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from src.backend.answer_check import _body, check_answer, count_items, fact_issues, sentences

TASK_DIR = Path(__file__).resolve().parents[1] / "prompts" / "tasks"
_EXAMPLES_BY_INTENT = {  # indexes into few_shots_v7.json
    "learning_plan": [0], "profile_progress": [2], "career_discovery": [4, 3], "profile_analysis": [5, 6],
    "concept_explanation": [6], "study_help": [], "job_preparation": [], "out_of_scope": [1],
}


def task_prompt(intent: Dict) -> str:
    def load(name):
        p = TASK_DIR / f"{name}.md"
        return p.read_text(encoding="utf-8").strip() if p.exists() else ""
    out = [load(intent["primary_intent"])]
    for s in intent.get("secondary_intents", []):
        first = load(s).splitlines()[:2]
        if first:
            out.append("Also requested: " + " ".join(first))
    return "\n".join(x for x in out if x)


def contract_v8(intent: Dict) -> str:
    from src.backend.question_profile import _TYPE_RULES
    qp = intent["question_profile"]
    L = [f"- The student wants to: {intent['user_goal']} (form: {qp['type']}). {_TYPE_RULES[qp['type']]}"]
    if len(intent.get("parts", [])) > 1:
        L.append("- The message has several requests. Answer EACH, in order: " + " | ".join(f"({i}) {p}" for i, p in enumerate(intent["parts"], 1)))
    if intent.get("requested_count"):
        L.append(f"- Exactly {intent['requested_count']} items, numbered 1-{intent['requested_count']}; no extra item.")
    if intent.get("n_sentences"):
        L.append(f"- Exactly {intent['n_sentences']} sentences, no list, no heading.")
    if intent.get("examples_each"):
        L.append(f"- Give exactly {intent['examples_each']} examples for EACH item asked about.")
    if intent.get("needs_example"):
        lang = intent.get("example_language")
        L.append(f"- Include a concrete example" + (f" written in {lang.title()} as a fenced code block." if lang else "."))
    style = intent.get("response_style")
    if style == "one_sentence" and not intent.get("conflict"):
        L.append("- One sentence only (at most 40 words).")
    elif style == "brief":
        L.append("- Brief: at most 120 words, no headings.")
    elif style == "beginner":
        L.append("- The student is a beginner: plain words, no jargon without a one-line explanation, one everyday example.")
    if qp.get("format") == "table":
        L.append("- Present it as a markdown table.")
    if intent.get("conflict"):
        L.append(f"- The request contains a conflict ({intent['conflict']}). Say so in one sentence, then give the most useful version "
                 "(e.g. a one-sentence summary plus the plan) or ask which they prefer.")
    if intent.get("needs_clarification"):
        L.append(f"- Missing information: {intent['missing']}. Do not guess: ask ONE focused question (offer 2-3 options); "
                 "you may add one sentence of general guidance.")
    if intent.get("wants_guarantee"):
        L.append("- The student asks for a guarantee: state clearly that no job/outcome can be guaranteed, then say what improves their chances.")
    if intent.get("refers_to_history"):
        L.append("- This is a follow-up: interpret it using the conversation above (e.g. 'the second one' = the second item you gave).")
    L.append("- First sentence = the direct answer. Nothing unrelated to this request.")
    return "\n".join(L)


def pick_examples(intent: Dict, examples: List[Dict]) -> str:
    idx = _EXAMPLES_BY_INTENT.get(intent["primary_intent"], [])
    chosen = [examples[i] for i in idx if i < len(examples)][:2]
    if not chosen:
        return "(none needed for this kind of question)"
    return "\n\n".join(f"### {ex['situation']}\nUser: {ex['user']}\nAdvisor: {ex['assistant']}" for ex in chosen)


# ── roadmap evidence ─────────────────────────────────────────────────────────────
# Starter skills when a role is named without skills or a profile (core skills of the role, prerequisites first)
ROLE_STARTER = {
    "data engineer": ["SQL", "Python", "Apache Spark", "Airflow", "AWS"], "data analyst": ["Excel", "SQL", "Power BI", "Statistics"],
    "data scientist": ["Python", "Statistics", "SQL", "Machine Learning"], "machine learning": ["Python", "Statistics", "Machine Learning", "Deep Learning"],
    "backend": ["Python", "SQL", "REST APIs", "Git", "Docker"], "frontend": ["HTML", "CSS", "JavaScript", "React"],
    "full stack": ["JavaScript", "React", "Node.js", "SQL"], "devops": ["Linux", "Git", "Docker", "CI/CD", "Kubernetes"],
    "cloud": ["Linux", "AWS", "Docker", "Terraform"], "cybersecurity": ["Networking", "Linux", "Python", "SIEM"],
}
def roadmap_evidence(message: str, intent: Dict, memory: Optional[Dict], state: Optional[Dict] = None) -> Optional[Dict]:
    """For '30-day plan' style requests, run the validated generator and hand its plan to the model as a source.
    E38: `state` (conversation_state) supplies what the student said EARLIER: the selected career, daily minutes, and the
    skills they said they have / don't have ("No. Make me a 30-day plan. I can study one hour daily.")."""
    low = message.lower()
    if intent["primary_intent"] != "learning_plan" and "learning_plan" not in intent.get("secondary_intents", []):
        return None
    if not re.search(r"\b(30|thirty)[- ]?day|\broadmap\b|\b(\d|one|two|three|four)[- ]weeks?\b|\bmonth\b|\bmake it \d+ days\b", low):
        return None
    from src.rag.skill_rerank import query_skills
    from src.roadmap.generator import generate_roadmap
    from src.skills.normalizer import normalize_all
    st = state or {}
    asked = [s.upper() if s in ("sql", "aws", "gcp") else s.title() for s in query_skills(message)]
    have = list((memory or {}).get("candidate_skills") or []) + list(st.get("known_skills") or [])
    m = re.search(r"\b(\d{2,3})\s*(?:min|minutes|mins)\b", low)
    h = re.search(r"\b(\d(?:\.\d)?|one|two|an)\s*(?:h|hr|hrs|hours?)\b", low)
    hw = {"one": 1, "two": 2, "an": 1}
    if m:
        minutes = int(m.group(1))
    elif h:
        minutes = int(float(hw.get(h.group(1), h.group(1))) * 60)
    else:
        minutes = st.get("daily_minutes") or (60 if state is not None else 90)
    know = re.findall(r"\bi (?:know|have|already know)\s+([\w+#. ,]+?)(?: but|\.|,|$)", low)
    have = normalize_all(have + [w.strip() for k in know for w in re.split(r",| and ", k) if w.strip()])
    missing = [x for x in (st.get("missing_skills") or []) if x.lower() not in {y.lower() for y in have}]
    gaps = [g for g in asked if g.lower() not in {x.lower() for x in have}] or None
    if not gaps and missing:
        gaps = normalize_all(missing)
    named = next((r for r in ROLE_STARTER if r in low), "")
    if not named and st.get("selected_career"):
        named = next((r for r in ROLE_STARTER if r in st["selected_career"].lower()), "")
    if named and gaps and missing:  # the role's core skills the student hasn't said they have, after the ones they named
        gaps = list(dict.fromkeys(gaps + [g for g in ROLE_STARTER[named] if g.lower() not in {x.lower() for x in have}]))
    if not gaps and named and not memory:  # "30-day backend roadmap" with no skills named and no profile
        gaps = [g for g in ROLE_STARTER[named] if g.lower() not in {x.lower() for x in have}]
    role = (memory or {}).get("target_role") or (named.title() + (" Developer" if named in ("backend", "frontend", "full stack") else "")
                                                 if named else (f"{gaps[0]} learner" if gaps else ""))
    if not gaps and memory:
        r = generate_roadmap(role, have, required_skills=memory.get("required_skills") or [], daily_minutes=minutes, use_llm=False)
    elif gaps:
        r = generate_roadmap(role, have, gaps=gaps, daily_minutes=minutes, use_llm=False)
    else:
        return None
    assumed = state is not None and not (m or h or st.get("daily_minutes"))
    lines = [f"GENERATED PLAN (validated, {minutes} min/day{' - ASSUMED, the student did not say; state the assumption and ask' if assumed else ''}, "
             f"role: {role or 'not given'}). Skills in order: "
             + ", ".join(f"{s} ({r['days_per_skill'].get(s)} days)" for s in r["gaps_prioritised"][:8])
             + (f". Not scheduled (time): {', '.join(r['deferred_gaps'])}" if r.get("deferred_gaps") else "")
             + f". Capstone: {r['capstone']}."]
    for d in r["days"]:
        lines.append(f"Day {d['day']}: {d['skill']} - {d['topic']}. Task: {d['practice_task']} ({d['estimated_minutes']} min). "
                     f"Done when: {d['completion_criteria']}." + (f" Resource: {d['resources'][0]}" if d.get("resources") else ""))
    return {"id": "generated_plan", "source": "roadmap", "doc_type": "generated_plan", "score": 1.0, "rerank": 10.0,
            "text": "\n".join(lines), "metadata": {"title": "Validated 30-day plan (roadmap generator)", "file": "src/roadmap/generator.py"},
            "user_id": "global", "plan": r}


# ── E38 rules (review 3 §5, §7): real-world situations, added to the contract for every prompt version ─────────
_SALARY = re.compile(r"\b(salary|salaries|pay|package|lpa|ctc|stipend|earn|earning)\b", re.I)
_HIRING = re.compile(r"\b(hiring|demand|job market|openings|vacanc\w*|layoffs?|recession|rn|right now|this year|in 20\d\d)\b", re.I)
_PROGRESS = re.compile(r"\b(missed|skipped|behind|fell behind|couldn'?t (study|do)|too (hard|difficult)|confus\w*|struggl\w*|"
                       r"(finished|completed|done with) (week|day|the first)|already know)\b", re.I)


def e38_rules(message: str, intent: Optional[Dict], state: Optional[Dict]) -> str:
    low = (message or "").lower()
    L = []
    if _SALARY.search(low) or (_HIRING.search(low) and re.search(r"\b(job|jobs|career|demand|hiring|market|role)\b", low)):
        L.append("- Salary / current hiring: the career dataset does not establish current salaries or hiring demand. Do not state figures "
                 "or trends as facts. If you give a range, label it as a rough, unverified indication that varies by city, company and "
                 "skills, and tell the student to check current job portals or salary surveys (name them; no invented URLs).")
    if _PROGRESS.search(low):
        L.append("- The student reports progress or difficulty with a plan. Adapt instead of repeating the original timetable: "
                 "keep completed days, add a short revision block for the hard topic (smaller steps + one easier practice task), "
                 "move missed tasks forward, and say which later tasks shift or get compressed so the plan still fits.")
    if intent and intent.get("primary_intent") == "concept_explanation":
        L.append("- When explaining types or categories (e.g. IaaS/PaaS/SaaS, kinds of ML), name at least one real, well-known example "
                 "for each type.")
    return "\n".join(L)


# ── checks ───────────────────────────────────────────────────────────────────────
_URL = re.compile(r"https?://[^\s)\]>\"']+")
_STOP = set("a an the and or of to in on for with my me i is are be what which how do does should can your you it this that "
            "then also make give list explain suggest create tell show compare recommend about".split())


def url_issues(text: str, hits: List[Dict]) -> List[str]:
    """No fabricated URLs: every link must come from a retrieved source or the curated resource list."""
    from src.roadmap.syllabus import RESOURCES
    allowed = " ".join(h.get("text", "") + " " + str((h.get("metadata") or {}).get("url", "")) for h in hits or [])
    allowed += " " + " ".join(str(x) for v in RESOURCES.values() for x in v)
    bad = []
    for u in _URL.findall(_body(text)):
        u2 = u.rstrip(".,;:")
        host = re.sub(r"^https?://(www\.)?", "", u2).split("/")[0]
        if u2 not in allowed and host not in allowed:
            bad.append(u2)
    return [f"These links are not in any provided source and may be invented: {', '.join(bad[:3])}. Remove them or "
            "name the official site without a URL."] if bad else []


def sentence_count(text: str) -> int:
    body = re.sub(r"```.*?```", " ", _body(text), flags=re.S)
    return len([s for s in re.split(r"(?<=[.!?])\s+", body.strip()) if len(s.split()) >= 3])


def check_v8(text: str, intent: Dict, question: str, memory: Optional[Dict], hits: List[Dict], use_nli: bool = True) -> List[str]:
    qp = intent["question_profile"]
    issues = check_answer(text, qp, question, memory)
    body, low = _body(text), _body(text).lower()
    if intent.get("n_sentences") and sentence_count(text) != intent["n_sentences"]:
        issues.append(f"The student asked for exactly {intent['n_sentences']} sentences; the draft has {sentence_count(text)}.")
    if intent.get("example_language") and "```" not in body:
        issues.append(f"Include a short {intent['example_language'].title()} code example in a fenced code block.")
    elif intent.get("needs_example") and not re.search(r"\bexample|e\.g\.|for instance|```", low):
        issues.append("The student asked for an example: include one concrete example.")
    if intent.get("wants_guarantee") and not re.search(r"\b(can['’]?t|cannot|can not|no one can|not possible to|isn['’]?t possible to)\b.{0,25}\bguarantee|\bno guarantee|\bnot (a )?guarantee", low):
        issues.append("State clearly that no job or outcome can be guaranteed.")
    if (intent.get("needs_clarification") or intent.get("conflict")) and "?" not in body and not intent.get("conflict"):
        issues.append(f"Essential information is missing ({intent.get('missing')}). Ask one focused question instead of guessing.")
    if intent.get("conflict") and not re.search(r"\b(can['’]?t|cannot|won['’]?t fit|too (long|many)|not possible|instead|however)\b", low):
        issues.append(f"Point out the conflict in the request ({intent['conflict']}) before answering.")
    if len(intent.get("parts", [])) > 1:  # every requested part must be addressed
        for p in intent["parts"]:
            keys = [w for w in re.findall(r"[a-z+#]{4,}", p.lower()) if w not in _STOP]
            if keys and not any(k[:6] in low for k in keys):
                issues.append(f"Part of the request is not answered: \"{p}\".")
    if intent["primary_intent"] == "learning_plan" and any(h.get("doc_type") == "generated_plan" for h in hits or []) \
            and re.search(r"\b(30|thirty)[- ]?day\b", question.lower()) and not re.search(r"\bday\s*(30|thirty)\b", low):
        issues.append("Present the generated 30-day plan through Day 30 (all 30 days, compactly).")
    issues += url_issues(text, hits)
    if use_nli:
        from src.backend.claim_check import claim_issues
        issues += claim_issues(text, hits)
    return issues + fact_issues(text, memory)
