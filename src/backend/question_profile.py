"""
Question profiler (prompt v5, docs/prompt_scripting.md §2): what exactly is the user asking, and in what form?

Deterministic (no LLM): regex rules over the message. Output drives
  * retrieval quotas per question type (retriever pulls what this question needs, not a fixed mix)
  * the per-question ANSWER CONTRACT injected into prompt v5 (direct answer first, exact item count,
    length, format, stay on the question)
"""
from __future__ import annotations

import re
from typing import Dict, Optional

_WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

# order matters: first match wins
_TYPES = [
    # E33: questions that compare the resume WITH the job description
    ("fit_analysis", r"\b(do i|am i|can i)\b.*\b(fit|match|meet|qualify|eligible|ready|suitable)\b|"
                     r"\brequirements?\b.*\b(i (already )?(have|meet|match)|my (resume|cv|profile))\b|"
                     r"\b(skills?)\b.*\b(i (already )?(have|meet|match))\b.*\b(job|role|jd|position)\b|"
                     r"\b(missing|lack|gaps?)\b.*\b(this|the|that) (job|role|position|jd)\b|"
                     r"\b(match|fit|alignment) (between|with)\b.*\b(resume|cv|job|jd|role)\b|"
                     r"\bhighlight\b.*\b(resume|cv)\b|\btailor\b.*\b(resume|cv)\b|\b(chances|shortlisted)\b|"
                     r"\bshould i apply\b|\b(my )?(current )?profile\b.*\b(suitable|enough|good enough|ready|fit|match)\b|"
                     r"\b(suitable|ready|qualified|eligible) for (this|the|that) (job|role|position)\b|\bjob[- ]ready\b|"
                     r"\b(emphasi[sz]e|showcase)\b.*\b(experience|skills?|resume)\b|\b(experience|skills?|resume)\b.*\b(emphasi[sz]e|showcase)\b|"
                     r"\b(the )?(jd|job)'s (skills|requirements)\b|\bof the (jd|job description|job)\b.*\b(i|my)\b"),
    # E33: questions about the job description itself
    ("jd_requirements", r"\b(jd|job description|this job|this role|the role|the job|the position)\b.*\b(require|requires|required|requirements?|ask(ing)? for|want|looking for|need|mention|responsibilit\w*|qualifications?|experience)\b|"
                        r"\b(what|which)\b.*\b(does|do) (the|this) (jd|job|role|position|company)\b"),
    ("profile_fact", r"\b(first|prioriti[sz]e|start with|focus on first|most important)\b.*\b(gap|gaps|missing skill|skill gap)\b|\bwhich (skill )?(gap|missing skill)\b|"
                     r"\b(my|mine)\b.*\b(ats|score|gap|gaps|skills?|resume|cv|profile|summary|missing)\b|\bam i\b|\bwhat should i learn first\b|\b(skills|tools|experience) do i (already )?(have|know)\b|\bwhat do i (already )?know\b"),
    ("comparison", r"\b(vs\.?|versus|difference between|compare|comparison|better than|which is better|or)\b.*\?|\bdifference\b"),
    ("plan", r"\b(plan|roadmap|schedule|week|weeks|month|months|days?)\b.*\b(learn|study|prepare|become|plan)\b|\b(study|learning) plan\b"),
    ("list", r"\b(list|top|best|which|what are( the)?|suggest|name|give me|recommend some)\b.*\b(courses?|certifications?|skills?|tools?|resources?|books?|projects?|websites?|companies|questions?|techniques|platforms)\b"),
    ("recommendation", r"\b(which|what) (career|role|job|field|path)s?\b|\b(suit|suits|fit|fits|recommend|should i (choose|become|pursue|take))\b|\bcareers? (can|could) i\b"),
    ("how_to", r"^\s*how\b|\bhow (do|can|should|to)\b|\btips\b|\bsteps?\b|\bprepare\b|\bimprove\b"),
    ("definition", r"^\s*(what is|what's|what are|explain|define|describe)\b|\bwhat (is|does|do)\b (an? |the )?[\w\s-]{2,40}(do|mean|involve)?\??$|\bmeaning of\b"),
    ("yes_no", r"^\s*(is|are|can|could|should|do|does|will|would|am)\b"),
]


def profile_question(message: str) -> Dict:
    m = (message or "").strip()
    low = m.lower()
    jd_first = [t for t in _TYPES if t[0] in ("fit_analysis", "jd_requirements")]
    qtype = next((t for t, pat in jd_first if re.search(pat, low)), None)  # E33: resume-vs-JD / JD questions first
    if qtype is None and re.search(r"\b(in|from|according to) the (jd|job description)\b|\b(jd|job description) (mentions?|lists?)\b", low):
        qtype = "jd_requirements"
    if qtype is None:
        if re.match(r"^\s*how\b", low):  # "How can I make my resume ATS friendly?" is a how-to, not a profile lookup
            qtype = "how_to"
        else:
            qtype = next((t for t, pat in _TYPES if re.search(pat, low)), "other")
    if re.search(r"\b(salary|salaries|ctc|lpa|package|pay)\b", low):
        qtype = "salary"
    elif qtype in ("fit_analysis", "other", "profile_fact") and re.search(r"\b(plan|schedule|roadmap)\b|\b\d+[- ]weeks?\b|\bnext \d+ (weeks|days|months)\b|\bone[- ]month\b", low):
        qtype = "plan"  # "4-week plan to close my gaps" is a plan (gaps come from the profile anyway)

    n_items: Optional[int] = None
    mm = re.search(r"\b(top|list|give me|suggest|name|any)?\s*(\d{1,2}|" + "|".join(_WORDNUM) + r")\s+(\w+\s+)?"
                   r"(courses?|certifications?|skills?|tools?|resources?|books?|projects?|tips?|ways?|steps?|"
                   r"careers?|roles?|jobs?|questions?|options?|reasons?|websites?|points?|examples?)\b", low)
    if mm:
        tok = mm.group(2)
        n_items = int(tok) if tok.isdigit() else _WORDNUM.get(tok)

    if n_items and qtype in ("other", "definition", "how_to"):
        qtype = "list"  # "give me 3 X" is a list request

    max_words = None
    if re.search(r"\b(one|1|single) (line|sentence)\b|\bin a sentence\b|\bone-liner\b", low):
        max_words = 40
    elif re.search(r"\b(briefly|brief|short|quick|in short|tl;?dr|concise|summari[sz]e)\b", low):
        max_words = 120

    fmt = "table" if re.search(r"\btable\b", low) else "steps" if re.search(r"\bstep[- ]by[- ]step\b|\bsteps\b", low) else None
    return {"type": qtype, "n_items": n_items, "max_words": max_words, "format": fmt}


# What each question type needs from the knowledge base (replaces one fixed mix of 4/3/2/1)
QUOTAS = {
    "fit_analysis":    {"profile": 6, "knowledge": 1, "careers": 1, "jobs": 0},
    "jd_requirements": {"profile": 6, "knowledge": 0, "careers": 1, "jobs": 0},
    "profile_fact":   {"profile": 5, "knowledge": 1, "careers": 1, "jobs": 0},
    "recommendation": {"profile": 2, "knowledge": 1, "careers": 5, "jobs": 1},
    "comparison":     {"profile": 1, "knowledge": 2, "careers": 4, "jobs": 0},
    "list":           {"profile": 3, "knowledge": 2, "careers": 2, "jobs": 1},
    "plan":           {"profile": 4, "knowledge": 2, "careers": 1, "jobs": 0},
    "how_to":         {"profile": 1, "knowledge": 4, "careers": 1, "jobs": 0},
    "definition":     {"profile": 0, "knowledge": 3, "careers": 2, "jobs": 0},
    "yes_no":         {"profile": 2, "knowledge": 2, "careers": 2, "jobs": 0},
    "salary":         {"profile": 1, "knowledge": 1, "careers": 4, "jobs": 2},
    "other":          {"profile": 3, "knowledge": 2, "careers": 4, "jobs": 1},
}

_TYPE_RULES = {
    "fit_analysis": ("Compare the candidate WITH the target job using the CANDIDATE PROFILE (current skills, JD skills, gaps, "
                     "resume and JD excerpts): (1) requirements already met, with the resume evidence; (2) missing requirements "
                     "(the skill gaps, by exact name); (3) related background that only partly covers a gap (related is not "
                     "equivalent); (4) a one-line verdict that mentions the ATS estimate. Never call a skill missing if the profile lists it as a current skill."),
    "jd_requirements": ("Answer from the TARGET JOB DESCRIPTION (profile JD skills and JD excerpt): list what the JD asks for, "
                        "grouped as skills/tools, experience/education and responsibilities when present. Use the JD's own wording "
                        "and do not add requirements that are not in the JD."),
    "profile_fact": "Answer from the CANDIDATE PROFILE first: state the exact value(s) asked for (numbers, skill names) in the first sentence, then a short explanation.",
    "recommendation": "Name 2-4 options from the career records, each with a one-line reason tied to the user's skills/interests. If evidence is weak, ask clarifying questions instead.",
    "comparison": "Start with a one-sentence verdict on the key difference, then compare side by side (a small table is ideal) on 3-5 dimensions relevant to the question.",
    "list": "Give exactly the list asked for, one item per bullet, each with a one-line why. No long preamble.",
    "plan": "Give a time-boxed plan (weeks or days) with concrete tasks and a checkable outcome per step, tailored to the user's gaps.",
    "how_to": "Give numbered, actionable steps in the order to do them. Lead with the most important step.",
    "definition": "Define it in the first 1-2 sentences in plain language, then explain why it matters for careers/study with one example.",
    "yes_no": "Start with a clear Yes / No / It depends, then give the reasons.",
    "salary": "Only quote non-placeholder figures present in the context (label them dataset values, unverified); otherwise say the data isn't available and point to Glassdoor/AmbitionBox/LinkedIn Salary.",
    "other": "Answer the question directly in the first sentence, then support it.",
}


def answer_contract(qp: Dict) -> str:
    """Per-question instructions injected into prompt v5 (the 'precise answer' part of prompt training)."""
    lines = [f"- Question type: **{qp['type']}**. {_TYPE_RULES[qp['type']]}",
             "- Your FIRST sentence must directly answer the question. Do not restate the question.",
             "- Include only information that helps answer THIS question; skip unrelated profile details, jobs or tips."]
    if qp.get("n_items"):
        lines.append(f"- The user asked for exactly {qp['n_items']} items: give exactly {qp['n_items']}, numbered 1-{qp['n_items']}.")
    if qp.get("max_words"):
        lines.append(f"- The user asked for a short answer: at most {qp['max_words']} words, no headings.")
    if qp.get("format") == "table":
        lines.append("- Present the answer as a markdown table.")
    elif qp.get("format") == "steps":
        lines.append("- Present the answer as numbered steps.")
    return "\n".join(lines)
