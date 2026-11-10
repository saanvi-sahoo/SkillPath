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


# ── E36 (prompt v7): grounding and fact checks ───────────────────────────────────────────────────────────────
_CIT = re.compile(r"\[(S\d+(?:\s*[,\-‐-—]\s*S?\d+)*)\]")
_GENERIC = {"skill", "skills", "career", "careers", "role", "roles", "job", "jobs", "work", "data", "use", "using", "learn",
            "good", "strong", "need", "needs", "required", "requires", "also", "like", "well", "help", "helps", "experience"}


def cited_ids(fragment: str) -> List[int]:
    ids: List[int] = []
    for group in _CIT.findall(fragment):
        for a, b in re.findall(r"S?(\d+)(?:\s*[\-‐-—]\s*S?(\d+))?", group):
            ids.extend(range(int(a), int(b or a) + 1))
    return ids


def sentences(text: str) -> List[str]:
    body = _body(text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z*\-\d])|\n+", body)
    return [p.strip() for p in parts if p.strip()]


def support(sentence: str, chunk: str) -> float:
    """Share of the sentence's content words that appear in the cited chunk (lexical grounding proxy)."""
    from src.rag.hybrid import tokens
    s = {t for t in tokens(_CIT.sub(" ", sentence)) if t not in _GENERIC and not t.isdigit()}
    if not s:
        return 1.0
    c = set(tokens(chunk))
    return len(s & c) / len(s)


SUPPORT_MIN = 0.15  # E36 calibration on 636 cited pairs from stored v5/v6 answers: 12.7% fall below (mostly real mis-citations)


def citation_report(text: str, hits: List[Dict]) -> Dict:
    """Every cited label must exist and its source must share content with the sentence that cites it."""
    n = len(hits or [])
    invalid, unsupported, total = set(), [], 0
    for sent in sentences(text):
        ids = cited_ids(sent)
        if not ids:
            continue
        for i in ids:
            total += 1
            if i < 1 or i > n:
                invalid.add(i)
            elif support(sent, hits[i - 1].get("text", "")) < SUPPORT_MIN:
                unsupported.append((i, sent[:160]))
    ok = total - len(invalid) - len(unsupported)
    return {"citations": total, "invalid": sorted(invalid), "unsupported": unsupported,
            "correct_rate": round(ok / total, 3) if total else None}


def fact_issues(text: str, memory: Optional[Dict]) -> List[str]:
    """Claims about the student that contradict the analysed profile."""
    if not memory:
        return []
    out, body = [], _body(text)
    ats = str(memory.get("ats_score", "")).strip()
    for m in re.finditer(r"\bats\b[^.\n]{0,60}?\b(\d{1,3})\s*(?:/\s*100|%|out of 100)?", body, re.I):
        if ats and m.group(1) != ats and not re.search(r"\b(above|over|at least|aim|target|reach|improve to)\b", m.group(0), re.I):
            out.append(f"The ATS estimate in the profile is {ats}/100; the draft says {m.group(1)}. Use the stored value.")
            break
    gaps = [str(g).split(":")[-1].strip() for g in (memory.get("skill_gaps") or [])]
    claim = re.compile(r"(?<!once )(?<!after )(?<!when )(?<!if )(?<!until )\byou (already )?(have|know|possess)( experience (in|with))?\b|"
                       r"\byour (resume|cv) (lists|shows|includes|mentions)\b")
    stop = re.compile(r",|;|:|\.|\bbut\b|\bwhile\b|\bwhereas\b|\bwhich\b|\bthat\b|\bhowever\b|\band (the|this|it)\b|\brequire|\bneed|\bmissing|\bgaps?\b")
    for sent in sentences(body):
        low = sent.lower()
        for m in claim.finditer(low):
            seg = low[m.end():]
            cut = stop.search(seg)
            seg = seg[:cut.start()] if cut else seg  # only the clause that states what the student has
            if re.search(r"\b(not|n't|no|never|yet|lack)\b", low[max(0, m.start() - 12):m.end()] + seg[:20]):
                continue
            claimed = [g for g in gaps if re.search(r"(?<![a-z])" + re.escape(g.lower()) + r"(?![a-z])", seg)]
            if claimed:
                out.append(f"The draft says the student has {', '.join(claimed)}, but the profile lists it as a gap. Correct this.")
                return out
    from src.backend.features import e38_on
    if e38_on():
        out += count_issues(body, memory)
    return out


_COUNT = re.compile(r"\b(\d{1,2})\s+(?:of|out of)\s+(?:the\s+|your\s+)?(\d{1,2})\s+(?:\w+\s+){0,2}?(?:skills|requirements|required skills)\b", re.I)


def count_issues(body: str, memory: Optional[Dict]) -> List[str]:
    """E38 (review 3 §6: deterministic validation for structured CV/JD facts): "you match N of M skills" must equal the
    stored comparison. Found in the claim audit: 'You match 5 of the 7 skills' when the profile matches 3 of 7."""
    req = memory.get("required_skills") or []
    if not req:
        return []
    from src.skills.normalizer import compare
    matched = compare(memory.get("candidate_skills") or [], req)["matched"]
    for m in _COUNT.finditer(body):
        n, tot = int(m.group(1)), int(m.group(2))
        if tot == len(req) and n != len(matched):
            return [f"The profile matches {len(matched)} of {len(req)} required skills ({', '.join(matched) or 'none'}); the draft says "
                    f"{n} of {tot}. Use the stored comparison."]
    return []


def check_answer_v7(text: str, pi: Dict, question: str, memory: Optional[Dict], hits: List[Dict]) -> List[str]:
    """v6 contract checks + clarification rule + citation validity/support + profile fact consistency."""
    issues = check_answer(text, pi, question, memory)
    if pi.get("missing") and "?" not in _body(text):
        issues.append(f"Essential information is missing ({pi['missing']}). Ask ONE short clarifying question instead of guessing.")
    cr = citation_report(text, hits)
    if cr["invalid"]:
        issues.append(f"You cited {', '.join(f'[S{i}]' for i in cr['invalid'])}, which do not exist (allowed: S1-S{len(hits)}). "
                      "Remove or correct those citations.")
    for i, sent in cr["unsupported"][:2]:
        issues.append(f"[S{i}] does not support: \"{sent}\". Cite the source that supports it, or drop the citation.")
    return issues + fact_issues(text, memory)
