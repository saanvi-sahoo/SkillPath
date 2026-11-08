"""
Answer self-check for prompt v6 ("generate -> verify -> revise", E34, docs/feedback_learning.md §6).

Deterministic checks derived from the question profile and the user's analysed profile. If a draft violates
any of them, the chatbot asks the model ONCE to revise the draft with the exact problems listed.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional


def _body(text: str) -> str:
    return text.split("\n\n---\n**Sources**")[0]


def _first_sentence(text: str) -> str:
    b = re.sub(r"^[#>*\s_]+", "", _body(text).strip())
    m = re.search(r"(.+?[.!?])(\s|$)", b, re.S)
    return (m.group(1) if m else b)[:400]


def count_items(text: str) -> int:
    lines = _body(text).splitlines()
    numbered = [l for l in lines if re.match(r"^\s*\d+[.)]\s+\S", l)]
    if numbered:
        return len(numbered)
    rows = [l for l in lines if re.match(r"^\s*\|", l) and not re.match(r"^\s*\|\s*:?-", l)]
    if len(rows) >= 2:
        return len(rows) - 1
    return len([l for l in lines if re.match(r"^\s*[-*•]\s+\S", l)])


def check_answer(text: str, qp: Dict, question: str, memory: Optional[Dict]) -> List[str]:
    """Return a list of concrete problems (empty = the draft satisfies the answer contract)."""
    issues: List[str] = []
    body, first, low_q = _body(text), _first_sentence(text).lower(), question.lower()
    t = qp.get("type")
    if qp.get("n_items") and count_items(text) != qp["n_items"]:
        issues.append(f"The user asked for exactly {qp['n_items']} items but the draft has {count_items(text)}. "
                      f"Give exactly {qp['n_items']} numbered items.")
    if qp.get("max_words") and len(body.split()) > qp["max_words"]:
        issues.append(f"The user asked for a short answer: cut it to at most {qp['max_words']} words.")
    if t == "yes_no" and not re.match(r"^\W*(yes|no|it depends|not necessarily|partly|partially)\b", first):
        issues.append("Start the first sentence with a direct Yes / No / It depends.")
    if t == "fit_analysis" and re.search(r"\b(fit|apply|suitable|ready|qualif\w*|eligible|chances|good enough)\b", low_q) and not re.search(
            r"\b(yes|no|partly|partially|not yet|moderate|strong|good fit|decent|weak|almost)\b", first):
        issues.append("Start with a one-line verdict (e.g. 'Partly: you meet X of Y requirements…') before the details.")
    if memory:
        gaps = [str(g).split(":")[-1].strip() for g in (memory.get("skill_gaps") or [])]
        if re.search(r"\b(first|prioriti[sz]e|start with)\b", low_q) and gaps and not any(g.lower() in first.lower() for g in gaps):
            issues.append("Name the single skill gap to learn first in the FIRST sentence (one of: " + ", ".join(gaps) + "), then explain why.")
        req = [str(r).split(":")[-1].strip() for r in (memory.get("required_skills") or [])]
        ats = str(memory.get("ats_score", ""))
        if "ats" in low_q and ats and ats not in first:
            issues.append(f"State the ATS estimate ({ats}/100) in the first sentence.")
        if t == "fit_analysis" and gaps and re.search(r"\b(missing|lack|gaps?|fit|good fit|need)\b", low_q):
            miss = [g for g in gaps if g.lower() not in body.lower()]
            if miss:
                issues.append("Name every skill gap from the profile exactly: missing in the draft: " + ", ".join(miss) + ".")
        if t == "jd_requirements" and req:
            miss = [r for r in req if r.lower() not in body.lower()]
            if len(miss) > max(1, len(req) // 4):
                issues.append("List the job description's requirements; not mentioned yet: " + ", ".join(miss) + ".")
    return issues


REVISE_INSTRUCTION = ("Revise your previous answer to fix ONLY these problems, keeping everything that was correct, "
                      "the same citations and the same scope rules. Return just the revised answer.\nProblems:\n")
