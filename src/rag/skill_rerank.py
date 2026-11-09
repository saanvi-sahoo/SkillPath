"""
Skill-aware re-ranking for career records (E36, docs/rag.md §10).

The cross-encoder (hybrid.rerank) judges how well a passage answers the question as text. It can't tell that
Docker experience doesn't satisfy a Kubernetes requirement, because the two are semantically close.
This rule-based stage adds what the project doc asks for (§10: exact canonical skills, related != equivalent):

    final = cross-encoder logit
          + DELTA * share of the top-10 vector matches that are in this record's domain (career-intent consensus)
          + ALPHA * share of the skills named in the question that the record requires (exact, or proved via IMPLIES)
          + BETA  * share that the record only has RELATED skills for (partial credit, deliberately smaller)
          + GAMMA * share of the user's own profile skills that the record requires (recommendation questions)

Records with no evidence get no bonus; nothing is ever removed here (the score floors still apply).
Weights were tuned ONLY on src/eval/career_queries.jsonl (24 queries); the frozen held-out set
(src/eval/heldout/heldout_careers.jsonl, 30 queries) measures the result once. Tuning-set grid (strict P@5):
cross-encoder only 0.858; skill weights alone 0.842-0.858 (no gain: records list many skills); domain consensus
DELTA 2/4/6/10 -> 0.883/0.925/0.933/0.933. DELTA=6 chosen (10 is close to a hard domain filter).
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Set

ALPHA = float(os.getenv("SKILL_RERANK_ALPHA", "1.0"))
BETA = float(os.getenv("SKILL_RERANK_BETA", "0.5"))
GAMMA = float(os.getenv("SKILL_RERANK_GAMMA", "1.0"))
DELTA = float(os.getenv("SKILL_RERANK_DELTA", "6.0"))
VOTE_TOP = 10
DEDUPE_TITLES = os.getenv("CAREER_DEDUPE_TITLES", "true").lower() == "true"


def _norm_set(skills: Iterable[str]) -> Set[str]:
    from src.skills.extractor import NOT_SKILLS
    from src.skills.normalizer import normalize_all
    return {s.lower() for s in normalize_all(skills) if s.lower() not in NOT_SKILLS}


IMPLIED_WEIGHT = 0.75  # E37 (review 2 §4): a record requiring MySQL shows SQL use, but is weaker evidence than "SQL" itself


@lru_cache(maxsize=4096)
def _record_parts(required: str):
    """(skills the record names, general skills they prove but don't name: MySQL -> SQL)."""
    from src.skills.normalizer import IMPLIES
    base = _norm_set(x.strip().strip(".") for x in re.split(r"[,;/]", required or "") if x.strip())
    implied = {i.lower() for s in base for canon, gen in IMPLIES.items() if canon.lower() == s for i in gen} - base
    return frozenset(base), frozenset(implied)


def _record_skills(required: str) -> frozenset:
    base, implied = _record_parts(required)
    return base | implied


@lru_cache(maxsize=1)
def _related_map() -> Dict[str, Set[str]]:
    from src.skills.normalizer import RELATED
    out: Dict[str, Set[str]] = {}
    for group in RELATED:
        low = {g.lower() for g in group}
        for g in low:
            out.setdefault(g, set()).update(low - {g})
    return out


def query_skills(text: str) -> Set[str]:
    from src.skills.extractor import extract_skills
    return _norm_set(extract_skills(text))


def explain(qs: Set[str], rs: frozenset) -> Dict[str, List[str]]:
    rel = _related_map()
    exact = sorted(qs & rs)
    related = sorted(q for q in qs - rs if rel.get(q, set()) & rs)
    return {"exact": exact, "related_only": related, "missing": sorted(qs - rs - set(related))}


def skill_rerank(query: str, hits: List[Dict], top: int, user_skills: Optional[Iterable[str]] = None) -> List[Dict]:
    """Re-order career hits (already scored by the cross-encoder) using exact / related / profile skill overlap."""
    if not hits:
        return hits
    qs = query_skills(query)
    us = _norm_set(user_skills or [])
    rel = _related_map()
    by_cos = sorted(hits, key=lambda h: h.get("score", 0.0), reverse=True)[:VOTE_TOP]
    votes: Dict[str, int] = {}
    for h in by_cos:
        d = (h.get("metadata") or {}).get("domain")
        votes[d] = votes.get(d, 0) + 1
    out = []
    for h in hits:
        base_s, implied_s = _record_parts(str((h.get("metadata") or {}).get("required_skills") or ""))
        rs = base_s | implied_s
        exact = (len(qs & base_s) + IMPLIED_WEIGHT * len((qs & implied_s) - base_s)) / len(qs) if qs else 0.0
        related = (sum(1 for q in qs - rs if rel.get(q, set()) & rs) / len(qs)) if qs else 0.0
        prof = len(us & rs) / len(us) if us else 0.0
        base = h["rerank"] if "rerank" in h else 10.0 * h.get("score", 0.0)
        intent = votes.get((h.get("metadata") or {}).get("domain"), 0) / max(1, len(by_cos))
        out.append({**h, "skill_match": {"exact": round(exact, 2), "related": round(related, 2), "profile": round(prof, 2),
                                         "domain_consensus": round(intent, 2)},
                    "skill_score": round(base + DELTA * intent + ALPHA * exact + BETA * related + GAMMA * prof, 3)})
    out.sort(key=lambda h: h["skill_score"], reverse=True)
    if DEDUPE_TITLES:  # E37: one record per career title, so the model never merges duplicates into invented requirements
        seen, uniq = set(), []
        for h in out:
            t = title_key((h.get("metadata") or {}).get("career_name") or h.get("id", ""))
            if t not in seen:
                seen.add(t)
                uniq.append(h)
        out = uniq
    return out[:top]


_LEVEL = re.compile(r"\b(senior|sr|junior|jr|lead|principal|associate|staff|entry level|i{1,3}|iv|v|[1-5])\b\.?|[(),\-/]")


def title_key(title: str) -> str:
    return re.sub(r"\s+", " ", _LEVEL.sub(" ", str(title).lower())).strip()


# ── E37: interest / career-change query expansion (review 2 §4: interest and transition queries were weakest) ──
# A general interest -> career-area taxonomy (RIASEC-style), written as general vocabulary, not from test queries.
# Only applied to CAREER search when the query describes interests or a change of field rather than skills/titles.
INTEREST_MAP = [
    (r"\b(hack\w*|privacy|safe|secure|protect\w*|threat\w*|fraud)\b", "cybersecurity security analyst information security"),
    (r"\b(organi[sz]\w*|deadlines?|coordinat\w*|manag\w* (people|teams?|projects?)|plan(ning)? events?|leading teams?)\b", "project manager program coordinator scrum master"),
    (r"\b(clients?|customers?|talking|persuad\w*|negotiat\w*|explain\w* (technology|tech)|selling|sales)\b", "sales engineer customer success account manager technical consultant"),
    (r"\b(puzzles?|math\w*|numbers|logic|statistic\w*|patterns?)\b", "data scientist data analyst quantitative analyst statistics"),
    (r"\b(draw\w*|art|artistic|design\w*|visual|creative|colou?rs?|interfaces?)\b", "ui ux designer graphic designer product designer"),
    (r"\b(games?|gaming)\b", "game developer unity c++ game designer"),
    (r"\b(teach\w*|explain\w*|training|tutor\w*|e-?learning|instructional)\b", "instructional designer e-learning developer corporate trainer"),
    (r"\b(writ\w*|content|storytelling|blog\w*)\b", "technical writer content strategist documentation"),
    (r"\b(health|medical|biolog\w*|hospital|patients?)\b", "health informatics bioinformatics clinical data analyst"),
    (r"\b(money|finance|financial|bank\w*|account\w*|invest\w*)\b", "financial analyst risk analyst fintech"),
    (r"\b(build\w* (things|apps?|websites?)|coding|program\w*|software)\b", "software developer engineer"),
    (r"\b(fix\w* (computers?|laptops?|systems?)|help ?desk|troubleshoot\w*|support)\b", "it support help desk technician system administrator"),
    (r"\b(test\w*|qa|quality)\b", "qa engineer test automation software tester"),
    (r"\b(environment\w*|climate|sustainab\w*|energy)\b", "sustainability analyst energy data analyst"),
    (r"\b(marketing|social media|brand\w*|advertis\w*)\b", "digital marketing analyst marketing specialist"),
]
_INTEREST_SIGNAL = re.compile(r"\b(i (like|love|enjoy|care|want|am good|prefer|hate|dislike)|interested in|passion|switch\w*|moving|move into|"
                              r"transition|career change|from \w+ to|i'?m an? \w+ (who|wanting|looking))\b", re.I)


def expand_career_query(query: str) -> str:
    """Append career-area words for interest/transition queries; unchanged otherwise."""
    if not _INTEREST_SIGNAL.search(query or ""):
        return query
    low = query.lower()
    extra = [words for pat, words in INTEREST_MAP if re.search(pat, low)]
    return f"{query}. Related careers: {'; '.join(extra[:3])}" if extra else query
