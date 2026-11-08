"""
Rule-based skill extraction: the no-LLM replacement for brain.analyse_node (docs/keyless_mode.md).

Vocabulary = canonical skills from the alias table (src/skills/normalizer.py) + skills that appear in
>= MIN_FREQ career records of the source-of-truth dataset. A skill is "found" when the term (or one of
its aliases) occurs in the text as a whole word. Output has the same shape as brain.analyse_node, so
the rest of the pipeline (gaps, roadmap, chatbot) works unchanged.

ATS here = share of the JD's skills evidenced in the resume (exact canonical match): an honest,
explainable keyword-coverage estimate. It is labelled `analysis_method: rule_based`.
"""
from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from typing import Dict, List

from src.skills.normalizer import ALIASES, compare, normalize

MIN_FREQ = 5
# short / ambiguous tokens that produce false positives in prose ("go to", "R&D", "C-level")
AMBIGUOUS = {"go", "r", "c", "rest", "apis", "spring", "react", "node", "excel", "stats", "ml", "dl", "cv", "ts", "tf", "js", "py"}


# Ambiguous English words that are also skills: only counted when written exactly like the skill name
CASE_SENSITIVE = ["Go", "Excel", "R", "C", "React", "Spring", "Node.js", "Rust", "Swift", "Ruby"]
_CASE_SENSITIVE_LOWER = {x.lower() for x in CASE_SENSITIVE}
_CS_PATTERN = re.compile(r"(?<![A-Za-z0-9+#])(" + "|".join(re.escape(x) for x in CASE_SENSITIVE) + r")(?![A-Za-z0-9+#])")


@lru_cache(maxsize=1)
def vocabulary() -> Dict[str, str]:
    """term (lowercase surface form) -> canonical skill name."""
    terms: Dict[str, str] = {}
    for alias, canon in ALIASES.items():
        if alias not in AMBIGUOUS and len(alias) >= 2:
            terms[alias] = canon
        if canon.lower() not in AMBIGUOUS and canon.lower() not in _CASE_SENSITIVE_LOWER:
            terms.setdefault(canon.lower(), canon)
    try:
        from src.rag.documents import load_career_frame

        df = load_career_frame()
        counts = Counter()
        for cell in df["required_skills"]:
            for raw in str(cell).split(","):
                n = normalize(raw.strip().strip("."))
                if 2 < len(n) <= 40 and len(n.split()) <= 4:
                    counts[n] += 1
        for skill, c in counts.items():
            if c >= MIN_FREQ and skill.lower() not in _CASE_SENSITIVE_LOWER and skill.lower() not in AMBIGUOUS:
                terms.setdefault(skill.lower(), skill)
    except Exception as e:  # noqa: BLE001 - alias vocabulary alone still works
        print(f"[extractor] dataset vocabulary unavailable: {e}")
    return terms


@lru_cache(maxsize=1)
def _pattern():
    terms = sorted(vocabulary(), key=len, reverse=True)  # longest first: "power bi" before "bi"
    return re.compile(r"(?<![a-z0-9+#])(" + "|".join(re.escape(t) for t in terms) + r")(?![a-z0-9+#])")


def extract_skills(text: str) -> List[str]:
    voc, seen, out = vocabulary(), set(), []
    found = [(m.start(), voc[m.group(1)]) for m in _pattern().finditer((text or "").lower())]
    # case-sensitive skills; "Excel" at a sentence start followed by "at" is the verb, not the tool
    found += [(m.start(), m.group(1)) for m in _CS_PATTERN.finditer(text or "")
              if not (m.group(1) == "Excel" and re.match(r"\s+(at|in)\b", (text or "")[m.end():]))]
    for _, canon in sorted(found):
        if canon.lower() not in seen:
            seen.add(canon.lower())
            out.append(canon)
    return out


# E33: not skills - degree fields and generic words that the dataset vocabulary contains
NOT_SKILLS = {"computer science", "information technology", "mechanical engineering", "electrical engineering",
              "electronics", "civil engineering", "engineering", "science", "commerce", "arts", "analysis", "design",
              "reporting", "sales", "development", "research", "management", "support", "operations", "documentation",
              "planning", "dashboards", "containers", "data entry", "regression", "responsibilities"}

_REQ_HEAD = re.compile(r"(required|requirements|must[- ]have|skills( required)?|qualifications|key skills|tech stack)\s*[:\-]", re.I)
_OTHER_HEAD = re.compile(r"\b(responsibilities|duties|what you(?:'ll| will) do|about (us|the company)|benefits|education|"
                         r"nice[- ]to[- ]have|preferred)\s*[:\-]", re.I)


def requirements_section(jd_text: str) -> str:
    """E33: if the JD has a requirements/skills section, only that text lists *required* skills
    (responsibilities like "build dashboards" or "design microservices" are not requirements)."""
    m = _REQ_HEAD.search(jd_text or "")
    if not m:
        return jd_text or ""
    rest = jd_text[m.end():]
    end = _OTHER_HEAD.search(rest)
    return rest[: end.start()] if end else rest


def _clean(skills: List[str]) -> List[str]:
    return [x for x in skills if x.lower() not in NOT_SKILLS]


def rule_based_analysis(resume_text: str, jd_text: str) -> Dict:
    cand = _clean(extract_skills(resume_text))
    req = _clean(extract_skills(requirements_section(jd_text)))
    cmp = compare(cand, req)
    ats = round(100 * (cmp["match_ratio"] or 0))
    return {
        "candidate_skills": cmp["candidate"],
        "required_skills": cmp["required"],
        "skill_gaps": cmp["gaps"],
        "ats_score": ats,
        "learning_path": [{"skill": g, "search_queries": [f"{g} tutorial for beginners", f"{g} hands-on project ideas",
                                                          f"free {g} course with certificate"]} for g in cmp["gaps"]],
        "related_background": cmp["related_background"],
        "analysis_method": "rule_based",
        "error": "",
    }
