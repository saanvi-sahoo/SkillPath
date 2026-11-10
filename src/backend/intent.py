"""
Intent understanding + source-aware routing (E37, docs/evaluation.md §11; review 2 §2-3).

Before any retrieval or prompting, every message gets a structured intent record (the review's proposed schema):

    {"in_scope": true, "primary_intent": "career_discovery", "secondary_intents": ["learning_plan"],
     "user_goal": "...", "requested_count": 2, "response_style": "brief", "requires_profile": true,
     "requires_retrieval": true, "needs_clarification": false, ...}

Eight routing labels (labels, not rigid boundaries; a message can carry several):
  career_discovery     careers, comparisons of careers, transitions, salaries
  concept_explanation  technical/skill concepts ("What is Docker?", "Docker vs Kubernetes")
  profile_analysis     resume vs JD, skill gaps, fit, "does my X cover Y"
  learning_plan        plans, roadmaps, "what should I learn first/next", prerequisites
  study_help           academic study: exams, revision, subjects, study techniques
  job_preparation      internships, interviews, applications, resumes (general), offers
  profile_progress     facts stored about the student: ATS, uploaded CV/JD, roadmap progress
  out_of_scope         decided by the scope router

Deterministic (regex + the existing question profile), so it behaves identically locally, on the deployed app,
and in keyless mode. Each intent picks its evidence (ROUTES): concept and study questions are answered from guides
and general knowledge and never from career records; career questions use career records; profile questions
use only this student's analysed profile; 30-day plans use the validated roadmap generator.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from src.backend.question_profile import parsed_intent, profile_question

INTENTS = ["career_discovery", "concept_explanation", "profile_analysis", "learning_plan", "study_help",
           "job_preparation", "profile_progress", "out_of_scope"]

_CAREER_NOUN = r"(career|careers|role|roles|job title|profession|field|fields|domain|path|analyst|engineer|scientist|developer|" \
               r"architect|manager|designer|consultant|administrator|tester|specialist|researcher)"
_RULES = [  # (intent, pattern) -- first match wins for the primary intent; all matches become candidates
    ("profile_progress", r"\b(my|mine) (ats|score|match score)\b|\bats (score|estimate)\b.*\b(my|mine|i)\b|\bwhat did i upload\b|"
                         r"\b(latest|last|current) (job description|jd|resume|cv) i (uploaded|added|gave)\b|"
                         r"\b(skills|languages|programming languages|tools)\b.*\b(in|on|from) my (uploaded )?(cv|resume)\b|"
                         r"\bi (have )?(completed|finished|done) (the )?(first )?(\d+|one|two|three|four|five|six|seven|eight|nine|ten) (days?|weeks?)\b|"
                         r"\bmy progress\b|\bwhat (job )?title am i targeting\b|\bremind me\b.*\bmy\b|\bwhat (do )?you know about (me|my)\b|"
                         r"\b(show|tell) me (about )?my (background|profile)\b"),
    ("profile_analysis", r"\b(am i|do i|i am) (ready|qualified|eligible|a (good )?fit|suitable)\b|\bdo i (meet|match|fit)\b|"
                         r"\b(missing|lack|gaps?)\b.*\b(job|role|jd|job description|position|my)\b|\bmy (skill )?gaps?\b|"
                         r"\b(my|this) (resume|cv|profile)\b.*\b(job|role|jd|position|ready|good enough|tailor|highlight)\b|"
                         r"\b(tailor|highlight)\b.*\b(resume|cv)\b|\bmy resume says\b|\b(does|do|is) my\b.*\b(cover|count|mean|satisfy|enough)\b|"
                         r"\b(jd|job description|this job|this role)\b.*\b(require|requires|asks?|want|need|responsibilit\w*|mention)\b|"
                         r"\bshould i apply\b|\bwhich (three |two |\d )?missing skills?\b|\bmy skills\b.*\b(match|fit|meet|needed)\b|"
                         r"\b(requirements?|skills?)\b.*\b(in|of|from|listed in) the (job description|jd|job posting|posting)\b|\bdo i know enough\b|"
                         r"\b(not needed|unnecessary|irrelevant)\b.*\b(job|role)\b|\bcan i (put|list|add|claim|mention)\b.*\b(resume|cv)\b|"
                         r"\bwhy is (it|my (ats )?score) (so )?low\b"),
    ("learning_plan", r"\b(\d+|thirty|one|two|three|four)[- ]?(day|days|week|weeks|month|months)\b.*\b(plan|roadmap|schedule)\b|"
                      r"\b(plan|roadmap|schedule|learning path)\b|\bwhat should i learn (first|next|before)\b|"
                      r"\b(learn|study) before (starting|learning)\b|\bprerequisites?\b|\bwhat next\b|\bmake it \d+ days\b|"
                      r"\bshould i (learn|study)\b.*\b(first|next|before)\b|\b(daily|study|learning) tasks\b|\bwhere (can|do|should) i (learn|start)\b|"
                      r"\bi want to learn\b|\b(courses?|tutorials?)\b|\b(free )?(resources?|courses?|tutorials?|books?)\b.*\b(learn|for|to)\b"),
    ("study_help", r"\b(exam|exams|revise|revision|semester|syllabus|homework|assignment|viva|test tomorrow|marks|"
                   r"gate|cat|gre|jee|neet|gmat|study (techniques?|tips|habits|schedule)|procrastinat\w*|concentrat\w*|memori[sz]e|"
                   r"for my (exam|class|course|test)|in exactly \w+ sentences)\b|\bhow (do|can|should) i study\b|\bhelp me (learn|understand|revise)\b|"
                   r"\blearn \w+ (using|with) \w+ examples\b"),
    ("career_discovery", r"\bhow (do|can|should) i become\b|\bcareer options?\b|\b(suggest|recommend|name)\b.*\bcareers?\b"),
    ("job_preparation", r"\b(interview|interviews|internship|internships|placement|placements|apply|applying|application|referral|"
                        r"linkedin|cover letter|resume|cv|ats[- ]friendly|negotiat\w*|offer letter|stipend|job offer|hr round|"
                        r"tell me about yourself|portfolio)\b"),
    ("career_discovery", rf"\b(career|careers|job role|switch|transition|become an?|which field|scope of|salary|salaries|"
                         rf"guarantee|future of)\b|\b(suggest|recommend|which|what)\b.*\b{_CAREER_NOUN}\b|"
                         rf"\b{_CAREER_NOUN}\b.*\b(vs\.?|versus|or|compare|difference)\b"),
    ("concept_explanation", r"^\s*(what is|what.s|what are|explain|define|describe|how does|how do|compare)\b|\bdifference between\b|"
                            r"\bin simple terms\b|\bwith (an? )?(\w+ )?examples?\b|\bvs\.?\b|\bversus\b|\bmean\b"),
]
_CAREER_WORDS = re.compile(rf"\b{_CAREER_NOUN}\b|\bdata (science|engineering|analytics)\b|\bcybersecurity\b|\bdevops\b|\bui/?ux\b")

# Evidence per intent (review 2 §3): which sources are retrieved, and what the answer should rest on.
ROUTES: Dict[str, Dict] = {
    "career_discovery":    {"quotas": {"profile": 2, "knowledge": 1, "careers": 5, "jobs": 0}, "evidence": "career records + the student's skills/interests"},
    "concept_explanation": {"quotas": {"profile": 0, "knowledge": 2, "careers": 0, "jobs": 0}, "evidence": "well-established knowledge; a guide only if relevant"},
    "profile_analysis":    {"quotas": {"profile": 6, "knowledge": 1, "careers": 0, "jobs": 0}, "evidence": "this student's analysed CV + target JD only"},
    "learning_plan":       {"quotas": {"profile": 3, "knowledge": 3, "careers": 0, "jobs": 0}, "evidence": "gaps, current skills, time budget, the roadmap generator"},
    "study_help":          {"quotas": {"profile": 0, "knowledge": 3, "careers": 0, "jobs": 0}, "evidence": "well-established knowledge; study guides"},
    "job_preparation":     {"quotas": {"profile": 2, "knowledge": 4, "careers": 0, "jobs": 1}, "evidence": "guides; the student's profile when personal"},
    "profile_progress":    {"quotas": {"profile": 5, "knowledge": 0, "careers": 0, "jobs": 0}, "evidence": "stored analysis / uploads / progress only"},
}

_STYLE = [("one_sentence", r"\b(one|1|single)[- ](line|sentence)\b|\bin a sentence\b|\bone-liner\b"),
          ("brief", r"\b(briefly|brief|short|quick|in short|tl;?dr|concise|nothing else|just)\b"),
          ("detailed", r"\b(in detail|detailed|step[- ]by[- ]step|deep dive|thorough|comprehensive)\b"),
          ("beginner", r"\blike i'?m (a )?(beginner|five|5)\b|\bin simple terms\b|\bsimply\b|\bfor (a )?beginners?\b|"
                       r"\bi'?m (a )?(complete |total )?beginner\b|\bmake it (easier|simpler)\b|\b(easier|simpler) (version|way|explanation)\b")]  # E38
_WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_SPLIT = re.compile(r"\?\s+(?=\w)|;\s*|\b(?:and then|then|also|after that|plus)\b|,?\s+and\s+(?=(?:make|give|list|explain|suggest|"
                    r"create|tell|show|compare|recommend|build|write|name)\b)", re.I)


def _num(tok: str) -> Optional[int]:
    return int(tok) if tok.isdigit() else _WORDNUM.get(tok.lower())


def parts(message: str) -> List[str]:
    """Split a multi-request message ("Compare X and Y, then make me a plan") into its requests."""
    ps = [p.strip(" ,.") for p in _SPLIT.split(message or "") if p and p.strip(" ,.")]
    return [p for p in ps if len(p.split()) >= 2] or [message.strip()]


_EXPLICIT_PLAN = re.compile(r"\b(plan|roadmap|schedule)\b")
_EXAM = re.compile(r"\b(exam|exams|revise|revision|semester|syllabus|test tomorrow|viva)\b")


def _intents_of(text: str, has_history: bool = False) -> List[str]:
    low = text.lower()
    found = list(dict.fromkeys(name for name, pat in _RULES if re.search(pat, low)))
    if "study_help" in found and _EXAM.search(low) and "learning_plan" in found and not _EXPLICIT_PLAN.search(low):
        found.remove("learning_plan")
        found.insert(0, "study_help")  # "exam in 3 days, what should I study first?" is study help
    if "learning_plan" in found and _EXPLICIT_PLAN.search(low) and "profile_analysis" in found:
        found.remove("profile_analysis")
        found.insert(found.index("learning_plan") + 1, "profile_analysis")
        found.remove("learning_plan")
        found.insert(0, "learning_plan")  # "a 30-day plan to close my gaps" is a plan (gaps come from the profile)
    if "concept_explanation" in found and _CAREER_WORDS.search(low) and "career_discovery" not in found:
        found.insert(found.index("concept_explanation"), "career_discovery")  # "difference between data analyst and scientist"
    if "concept_explanation" in found and "career_discovery" in found and not _CAREER_WORDS.search(low) and "become" not in low:
        found.remove("career_discovery")
    return found


def classify(message: str, history: Optional[List[Dict]] = None, has_profile: bool = False, route_label: str = "career_study") -> Dict:
    history = history or []
    low = (message or "").lower().strip()
    qp = parsed_intent(profile_question(message), message, has_profile, len(history))
    if route_label in ("out_of_scope", "prompt_attack"):
        return {"in_scope": False, "primary_intent": "out_of_scope", "secondary_intents": [], "user_goal": "unrelated request",
                "requested_count": None, "response_style": "default", "requires_profile": False, "requires_retrieval": False,
                "needs_clarification": False, "question_profile": qp, "parts": [message], "route": ROUTES.get("career_discovery")}
    ps = parts(message)
    per_part = [(_intents_of(p) or ["concept_explanation" if qp["type"] == "definition" else "career_discovery"])[0] for p in ps]
    allc = _intents_of(message)
    primary = per_part[0] if per_part else (allc[0] if allc else "career_discovery")
    if route_label == "greeting":
        primary = "career_discovery"
    # follow-ups inherit the earlier topic's intent when the new message has no own signal ("which is easier?")
    pointer = bool(re.search(r"\b(the (first|second|third|fourth|last|other) one|that one|this one|those|them|it)\b", low)) and len(low.split()) <= 7
    if history and (not allc or pointer):
        prev = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        prev_int = _intents_of(prev)
        if prev_int:
            primary = prev_int[0]
        last_bot = next((m["content"] for m in reversed(history) if m["role"] == "assistant"), "")
        offer = re.search(r"[^.!?\n]*\b(plan|roadmap|schedule)\b[^.!?\n]*\?\s*$", last_bot.split("\n\n---")[0].strip(), re.I)
        if offer and not allc and len(low.split()) <= 6:  # E38: "yes" / "30 days" answering "Do you want a day-by-day plan?"
            primary = "learning_plan"
    # secondary intents: separate requests in the message, plus a plan/profile request hidden inside one sentence
    secondary = [i for i in dict.fromkeys(per_part[1:] + [i for i in allc if i in ("learning_plan", "profile_analysis")]) if i != primary][:2]

    count = qp.get("n_items")
    mm = re.search(r"\b(?:exactly|only|just)?\s*(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten) sentences?\b", low)
    n_sentences = _num(mm.group(1)) if mm else None
    mm = re.search(r"\b(\d|one|two|three|four|five) examples? (each|for each|per)\b", low)
    examples_each = _num(mm.group(1)) if mm else None
    mm = re.search(r"\bwith (an? |some |\w+ )?(?:(java|python|sql|javascript|c\+\+|c#|c|go|r)\s+)?(code )?examples?\b|\bexample in (\w+)\b", low)
    needs_example = bool(mm) or bool(examples_each)
    example_lang = (mm.group(2) or mm.group(4)) if mm else None
    if examples_each:
        count = None  # "two examples each" is not a list length
    style = next((s for s, pat in _STYLE if re.search(pat, low)), "default")
    if qp.get("max_words") == 40:
        style = "one_sentence"
    requires_profile = primary in ("profile_analysis", "profile_progress") or bool(re.search(r"\b(my|me|i)\b.*\b(gaps?|resume|cv|profile|skills)\b", low))
    requires_retrieval = primary not in ("concept_explanation", "study_help") or bool(re.search(r"\b(guide|resources?|courses?|certif\w*)\b", low))
    conflict = None
    if (style == "one_sentence" or (n_sentences and n_sentences <= 2)) and re.search(r"\b(30|thirty)[- ]day\b|\bdaily tasks\b", low):
        conflict = "a very short answer cannot contain a full multi-day plan"
    elif style == "one_sentence" and (count or 0) > 3:
        conflict = f"one sentence cannot hold {count} separate items"
    missing = qp.get("missing")
    if primary == "profile_progress" and re.search(r"\bi (have )?(completed|finished|done)\b", low):
        missing = missing or "roadmap progress: use the 30-day roadmap progress line in the profile if present; otherwise ask which day they are on and what was hard"
    goal = {"career_discovery": "find or compare career options", "concept_explanation": "understand a concept",
            "profile_analysis": "assess their profile against a job", "learning_plan": "get a learning plan",
            "study_help": "study or prepare for an exam", "job_preparation": "prepare for applications or interviews",
            "profile_progress": "look up their own stored information"}[primary]
    return {
        "in_scope": True, "primary_intent": primary, "secondary_intents": secondary, "user_goal": goal,
        "requested_count": count, "n_sentences": n_sentences, "examples_each": examples_each,
        "needs_example": needs_example, "example_language": example_lang, "response_style": style,
        "format": qp.get("format"), "requires_profile": requires_profile, "requires_retrieval": requires_retrieval,
        "needs_clarification": bool(missing), "missing": missing, "conflict": conflict,
        "refers_to_history": bool(history) and (not allc or bool(re.search(r"\b(it|that|those|them|the (first|second|third)( one)?|which one)\b", low))),
        "wants_guarantee": bool(re.search(r"\bguarantee\w*\b", low)), "parts": ps,
        "question_profile": qp, "route": ROUTES[primary],
    }


def quotas_for(intent: Dict, has_profile: bool) -> Dict[str, int]:
    """Retrieval quotas from the primary intent, widened for secondary intents; no profile -> no profile slots."""
    q = dict(intent["route"]["quotas"])
    for s in intent.get("secondary_intents", []):
        for src, k in ROUTES.get(s, {}).get("quotas", {}).items():
            q[src] = max(q.get(src, 0), min(k, 2))
    if not has_profile:
        q["profile"] = 0
    if not intent.get("requires_retrieval"):
        q = {"knowledge": min(q.get("knowledge", 0), 2), "profile": q.get("profile", 0) if intent.get("requires_profile") else 0}
    return {k: v for k, v in q.items() if v > 0}
