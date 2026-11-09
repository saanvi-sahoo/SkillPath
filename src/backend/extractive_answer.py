"""
Retrieval-only answers: the Career Advisor without any LLM (docs/keyless_mode.md).

The answer is composed from the retrieved, cited records only; nothing is generated or invented:
  * profile facts (ATS estimate, gaps) from the user's analysed profile
  * matching career records with the skill overlap / missing skills against the user's profile
  * the best-matching guide section (knowledge base)
  * learning resources (profile learning path) and job listings when asked for
  * clarifying questions when the evidence is weak (same rule as prompt v4 rule 9)
Citations use the same [S#] numbering as the hits list, so the UI sources panel works unchanged.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from src.rag import config
from src.skills.normalizer import compare

_INTENTS = {
    "profile": r"\b(my|me|mine|i have|ats|score|gap|gaps|missing|resume|cv|profile|summary)\b",
    "resources": r"\b(course|courses|resource|resources|learn|learning|free|tutorial|certif\w*|study plan|roadmap)\b",
    "jobs": r"\b(job|jobs|hiring|opening|openings|vacanc\w*|companies|company|apply)\b",
    "careers": r"\b(career|careers|role|roles|become|suit|suits|fit|fits|path|switch|field|domain)\b",
    "salary": r"\b(salary|salaries|pay|package|ctc|earn|compensation|lpa)\b",
    "equivalence": r"\b(cover|covers|enough|same|equivalent|satisfy|satisfies|replace|count as|instead of|vs|versus|difference)\b",
    "howto": r"\b(how|prepare|preparation|tips|improve|write|explain|study|studying|interview|negotiate|switch)\b",
}


def _intents(message: str) -> set:
    m = message.lower()
    return {k for k, pat in _INTENTS.items() if re.search(pat, m)}


_STOP = set("""a an the i me my mine you your for to of in on at with and or is are am be can could should would
what which who how why when where do does did please tell give suggest recommend help some any good best right
career careers job jobs role roles path paths field option options me? for? this that it about want like need""".split())


def _content_words(message: str) -> List[str]:
    """Informative words left after removing stop/intent words ("Recommend a career for me" -> [])."""
    return [w for w in re.findall(r"[a-z+#]+", message.lower()) if w not in _STOP and len(w) > 1]


def _trim(text: str, words: int) -> str:
    w = (text or "").split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def _skills(s: str) -> List[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def compose_answer(message: str, decision: Dict, hits: List[Dict], memory: Optional[Dict]) -> str:
    from src.prompts.registry import load_prompt

    label = (decision or {}).get("label")
    if label == "greeting":
        return load_prompt("greeting")
    idx = {id(h): i for i, h in enumerate(hits, 1)}
    plan = next((h for h in hits if h.get("doc_type") == "generated_plan"), None)
    if plan:  # E37: N-day plan requests -> the validated roadmap generator's plan, shown as-is
        lines = plan["text"].splitlines()
        return (f"**Your 30-day plan** [S{idx[id(plan)]}]\n\n{lines[0].replace('GENERATED PLAN', 'Plan')}\n\n"
                + "\n".join(f"- {l}" for l in lines[1:]) +
                "\n\nA 30-day plan builds working familiarity; it doesn't guarantee mastery or a job. Open *Learning Paths* to "
                "generate it from your analysed profile.\n\n_Retrieval-only mode: built by the roadmap generator (no LLM)._")
    intents = _intents(message)
    by_src = lambda *srcs: [h for h in hits if h.get("source") in srcs]  # noqa: E731
    careers = by_src("careers")
    best_career = max((h["score"] for h in careers), default=0.0)
    have = (memory or {}).get("candidate_skills") or []

    # weak evidence: asking for a career with nothing to go on -> clarify (prompt v4 rule 9)
    vague = len(_content_words(message)) < 2
    if "careers" in intents and not have and (best_career < config.CAREER_MIN_SCORE or vague):
        return ("I'd like to help, but I don't know enough about you yet to suggest careers responsibly. Could you tell me:\n"
                "1. **What is your current education or experience level?** (e.g. B.Tech 2nd year, B.Com graduate, working professional)\n"
                "2. **Which skills or tools do you already know**, even basic ones?\n"
                "3. **What kind of work do you enjoy?** (building things, analysing data, designing, helping people…)\n\n"
                "With that I can match you against our 2,899 career records and explain why each option fits.")

    parts: List[str] = []
    # 0. skill equivalence from explicit rules (normalizer.IMPLIES / RELATED), e.g. Docker vs Kubernetes
    if "equivalence" in intents:
        from src.skills.extractor import extract_skills
        from src.skills.normalizer import IMPLIES, RELATED
        sk = extract_skills(message)
        if len(sk) >= 2:
            a, b = sk[0], sk[1]
            if b in IMPLIES.get(a, []):
                verdict = f"**Yes:** experience with **{a}** demonstrates **{b}** (using {a} means using {b})."
            elif a in IMPLIES.get(b, []):
                verdict = f"**Not fully:** **{b}** is more specific than **{a}**. Knowing {a} doesn't prove {b} experience, so treat {b} as a gap."
            elif any(a in g and b in g for g in RELATED):
                verdict = (f"**No, related but not the same:** **{a}** and **{b}** are related skills, but {a} experience does not "
                           f"satisfy a {b} requirement. Count it as *related background* and keep **{b}** as a skill gap to close.")
            else:
                verdict = f"**No:** **{a}** and **{b}** are different skills; a {b} requirement needs {b} experience."
            parts.append(verdict)
    kb = by_src("knowledge")
    kb_part = ""
    if kb:
        h = kb[0]
        txt = re.sub(r"^[^:]{0,80}:\s*", "", h.get("text", ""), count=1)
        kb_part = f"**Guidance** ({(h.get('metadata') or {}).get('section', 'guide')}) [S{idx[id(h)]}]: {_trim(txt, 110)}"
    # 1. profile facts
    if memory and ("profile" in intents or not intents):
        prof = next((h for h in hits if h.get("doc_type") == "profile_overview"), None)
        cite = f" [S{idx[id(prof)]}]" if prof else ""
        gaps = memory.get("skill_gaps") or []
        parts.append(f"**Your profile**{cite}: target role *{memory.get('target_role') or 'not specified'}*, "
                     f"estimated ATS match **{memory.get('ats_score', 'n/a')}/100**"
                     + (f", skill gaps: **{', '.join(map(str, gaps))}**." if gaps else ", no major skill gaps found."))

    # 2. learning resources from the user's own analysis (first when the user asks for them)
    if "resources" in intents:
        res = [h for h in hits if h.get("doc_type") in ("learning_path", "learning_resource", "static_resource")]
        if res:
            parts.append("**Learning resources from your analysis:**\n" + "\n".join(f"- {_trim(h['text'], 70)} [S{idx[id(h)]}]" for h in res[:2]))

    # 3. careers: only when the question is about careers, or nothing more specific was asked
    if careers and ("careers" in intents or not (intents - {"careers"})) and not ("howto" in intents and "careers" not in intents):
        lines = []
        for h in careers[:3]:
            m = h.get("metadata") or {}
            req = _skills(m.get("required_skills"))
            line = f"- **{m.get('career_name')}** ({m.get('domain')}) [S{idx[id(h)]}]: needs {', '.join(req[:6]) or 'n/a'}"
            if have and req:
                c = compare(have, req)
                if c["matched"]:
                    line += f". You already have: {', '.join(c['matched'][:4])}"
                if c["gaps"]:
                    line += f". To learn: {', '.join(c['gaps'][:4])}"
            lines.append(line + ".")
        if not have:  # no skills/education known: suggest, but also ask (doc §9.2: follow-up questions)
            lines.append("\nTo narrow this down: **which skills or tools do you already know?** "
                         "And **what is your current education or experience level?**")
        head = "**Careers from our records that match your question**" + (" (weak matches, tell me more about your interests)" if best_career < config.CAREER_MIN_SCORE else "")
        parts.append(head + ":\n" + "\n".join(lines))

    # 3. salary (dataset values are mostly placeholders: be explicit)
    if "salary" in intents:
        real = [(h, (h.get("metadata") or {})) for h in careers if not (h.get("metadata") or {}).get("salary_is_placeholder", True)]
        if real:
            h, m = real[0]
            parts.append(f"**Salary:** our dataset lists {m.get('average_salary'):,.0f} for *{m.get('career_name')}* [S{idx[id(h)]}] "
                         "(dataset value, unverified). Check current figures for your city on Glassdoor, AmbitionBox or LinkedIn Salary.")
        else:
            parts.append("**Salary:** our career records don't contain reliable salary data for this role, so I won't guess. "
                         "Check current figures for your city and experience on Glassdoor, AmbitionBox or LinkedIn Salary.")

    # 4. guidance from the knowledge base (moved to the top for how-to questions)
    if kb_part:
        if "howto" in intents:
            parts.insert(1 if (memory and parts and parts[0].startswith("**Your profile**")) else 0, kb_part)
        else:
            parts.append(kb_part)

    # 6. jobs
    if "jobs" in intents:
        jobs = [h for h in hits if h.get("doc_type") in ("job_listing", "matched_job")]
        if jobs:
            parts.append("**Job listings:**\n" + "\n".join(
                f"- {(h.get('metadata') or {}).get('title')} at {(h.get('metadata') or {}).get('company') or 'n/a'} "
                f"({(h.get('metadata') or {}).get('location') or 'n/a'}) [S{idx[id(h)]}]" for h in jobs[:3]))

    if not parts:
        return ("I couldn't find records in our knowledge base that match this question closely. Could you rephrase it, "
                "or tell me your skills and the kind of role you're interested in?")
    parts.append("**Next steps:** open *Learning Paths → Generate 30-day roadmap* for a day-by-day plan, "
                 "or ask me about any career above.")
    return "\n\n".join(parts) + "\n\n_Retrieval-only mode: this answer is composed directly from the cited records (no LLM)._"
