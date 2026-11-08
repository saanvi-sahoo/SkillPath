"""
Personalised 30-day roadmap generator (project doc section 11).

Pipeline
  1. gaps        : exact canonical comparison (src/skills/normalizer.compare), or given gaps
  2. prioritise  : prerequisite order (PREREQS) and then market importance = share of the target role's
                   career records (source-of-truth dataset, via retrieve_careers) that list the skill
  3. skeleton    : deterministic 30-day plan: review on days 7/14/21/28, project on days 29-30,
                   learn days split across gaps by weight (min 2 each, max 8 gaps; rest deferred)
  4. fill        : LLM fills topics/tasks with a validated pydantic schema (prompt roadmap_v1)
  5. validate    : exactly 30 days, numbering 1..30, skills/kinds unchanged, minutes within budget,
                   every scheduled gap covered, required fields non-empty; repairs and reports issues
  6. resources   : attach curated links from the latest profile analysis when skills match

CLI:  python -m src.roadmap.generator --from-profile --minutes 90
API:  POST /roadmap   (src/backend/fastapi_ends/api_endpoint.py)
"""
from __future__ import annotations

import argparse
import json
import re
import time
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from src.prompts.registry import load_prompt
from src.rag import config
from src.skills.normalizer import compare, normalize, normalize_all

PREREQS: Dict[str, List[str]] = {
    "Machine Learning": ["Python", "Statistics"], "Deep Learning": ["Machine Learning"],
    "Natural Language Processing": ["Machine Learning"], "Computer Vision": ["Deep Learning"],
    "Large Language Models": ["Natural Language Processing"], "Generative AI": ["Machine Learning"],
    "TensorFlow": ["Python"], "PyTorch": ["Python"], "scikit-learn": ["Python"], "Pandas": ["Python"],
    "Kubernetes": ["Docker"], "Terraform": ["AWS"], "CI/CD": ["Git"],
    "Apache Spark": ["Python", "SQL"], "Apache Airflow": ["Python"], "Data Warehousing": ["SQL"], "ETL": ["SQL"],
    "Power BI": ["Excel"], "Tableau": [], "Data Visualization": [],
    "React": ["JavaScript"], "Node.js": ["JavaScript"], "Spring Boot": ["Java"], "Microservices": ["REST APIs"],
}
REVIEW_DAYS = (7, 14, 21, 28)
PROJECT_DAYS = (29, 30)
MAX_GAPS = 8
LLM_TIMEOUT_S = 75


class RoadmapDay(BaseModel):
    day: int = Field(..., ge=1, le=30)
    skill: str
    kind: str = Field(..., description="learn | review | project")
    topic: str
    prerequisite: str
    learning_task: str
    practice_task: str
    estimated_minutes: int
    completion_criteria: str


class Roadmap(BaseModel):
    days: List[RoadmapDay]


# ── 2. prioritise ────────────────────────────────────────────────────────────
def market_importance(gaps: List[str], target_role: str, k: int = 25) -> Dict[str, float]:
    """Share of the role's top-k career records whose required_skills mention each gap skill."""
    try:
        from src.rag.retriever import retrieve_careers

        recs = retrieve_careers(target_role or "career", top_k=k, min_score=0.0)
    except Exception as e:  # noqa: BLE001 - roadmap still works without the vector store
        print(f"[roadmap] importance unavailable: {e}")
        recs = []
    if not recs:
        return {g: 0.5 for g in gaps}
    rec_skills = [set(normalize_all((r.get("required_skills") or "").split(","))) for r in recs]
    return {g: round(sum(g in s for s in rec_skills) / len(rec_skills), 3) for g in gaps}


def prioritise(gaps: List[str], importance: Dict[str, float]) -> List[str]:
    """Prerequisites first (only among the gaps), otherwise by importance (desc)."""
    remaining = sorted(gaps, key=lambda g: -importance.get(g, 0))
    ordered: List[str] = []
    while remaining:
        for g in remaining:
            if not any(p in remaining and p != g for p in PREREQS.get(g, [])):
                ordered.append(g)
                remaining.remove(g)
                break
        else:  # cycle guard
            ordered.extend(remaining)
            break
    return ordered


# ── 3. skeleton ──────────────────────────────────────────────────────────────
def build_skeleton(ordered_gaps: List[str], importance: Dict[str, float]) -> Dict:
    scheduled, deferred = ordered_gaps[:MAX_GAPS], ordered_gaps[MAX_GAPS:]
    learn_days = [d for d in range(1, 31) if d not in REVIEW_DAYS and d not in PROJECT_DAYS]  # 24
    if not scheduled:
        scheduled = ["Interview Preparation"]
    weights = [max(importance.get(g, 0.5), 0.2) for g in scheduled]
    alloc = [2] * len(scheduled)
    spare = len(learn_days) - 2 * len(scheduled)
    for _ in range(max(spare, 0)):  # largest remainder, weighted
        i = max(range(len(scheduled)), key=lambda j: weights[j] / alloc[j])
        alloc[i] += 1
    seq = [g for g, n in zip(scheduled, alloc) for _ in range(n)]
    skeleton, it = [], iter(seq)
    for d in range(1, 31):
        if d in REVIEW_DAYS:
            skeleton.append({"day": d, "skill": "Review", "kind": "review"})
        elif d in PROJECT_DAYS:
            skeleton.append({"day": d, "skill": "Capstone Project", "kind": "project"})  # capstone text added later
        else:
            skeleton.append({"day": d, "skill": next(it), "kind": "learn"})
    return {"skeleton": skeleton, "scheduled": scheduled, "deferred": deferred,
            "days_per_skill": dict(zip(scheduled, alloc))}


# ── 4. fill (LLM) + deterministic fallback ───────────────────────────────────
def _fallback_day(s: Dict, minutes: int, idx_in_skill: int) -> Dict:
    k, skill = s["kind"], s["skill"]
    if k == "review":
        return {**s, "topic": "Weekly review", "prerequisite": "previous days",
                "learning_task": "Re-read notes from this week and list 3 things you are unsure about",
                "practice_task": "Redo one exercise from each skill studied this week without notes",
                "estimated_minutes": minutes, "completion_criteria": "All redo exercises completed; doubts written down"}
    if k == "project":
        cap = s.get("capstone") or "Portfolio project using the skills from this roadmap"
        if s["day"] == PROJECT_DAYS[0]:
            return {**s, "topic": "Capstone: plan & build", "prerequisite": "days 1-28", "learning_task": cap,
                    "practice_task": "Define the problem and data, then build a working first version",
                    "estimated_minutes": minutes, "completion_criteria": "A working first version runs end to end"}
        return {**s, "topic": "Capstone: polish & present", "prerequisite": "Capstone: plan & build",
                "learning_task": "Write the README (problem, approach, results, how to run) and add screenshots",
                "practice_task": "Push to GitHub, add it to your resume and practise a 2-minute walkthrough",
                "estimated_minutes": minutes, "completion_criteria": "Public repo + resume line + recorded walkthrough"}
    # E33: curriculum-based template (ordered topics per skill) instead of "part 1/2/3" placeholders
    from src.roadmap.syllabus import topics_for
    topics = topics_for(skill)
    t = topics[min(idx_in_skill - 1, len(topics) - 1)]
    extra = idx_in_skill - len(topics)
    topic = t[0] if extra <= 0 else f"{t[0]} (deeper practice {extra})"
    prev = "none" if idx_in_skill == 1 else topics[min(idx_in_skill - 2, len(topics) - 1)][0]
    return {**s, "topic": topic, "prerequisite": prev, "learning_task": t[1],
            "practice_task": t[2] if extra <= 0 else f"Extend the previous {skill} exercise with a harder variant",
            "estimated_minutes": minutes, "completion_criteria": t[3]}


def fill_with_llm(skel: List[Dict], target_role: str, level: str, minutes: int, candidate: List[str]) -> List[Dict]:
    from src.utilities.brain import get_robust_structured_llm

    prompt = load_prompt("roadmap", "v1").format(
        target_role=target_role or "not specified", level=level, daily_minutes=minutes,
        candidate_skills=", ".join(candidate) or "not provided", skeleton=json.dumps(skel))
    llm = get_robust_structured_llm(Roadmap, primary_model="groq:openai/gpt-oss-120b", temperature=0.2)
    res = llm.invoke(prompt)
    return [d.model_dump() for d in res.days]


# ── 5. validate + repair ─────────────────────────────────────────────────────
def validate_and_repair(days: List[Dict], skel: List[Dict], minutes: int) -> Dict:
    issues: List[str] = []
    by_day = {}
    for d in days:
        if isinstance(d.get("day"), int) and 1 <= d["day"] <= 30 and d["day"] not in by_day:
            by_day[d["day"]] = d
    if len(days) != 30:
        issues.append(f"LLM returned {len(days)} days (expected 30)")
    counters: Dict[str, int] = {}
    final = []
    for s in skel:
        counters[s["skill"]] = counters.get(s["skill"], 0) + 1
        d = by_day.get(s["day"])
        if d is None:
            issues.append(f"day {s['day']} missing -> template")
            final.append(_fallback_day(s, minutes, counters[s["skill"]]))
            continue
        if d.get("skill") != s["skill"] or d.get("kind") != s["kind"]:
            issues.append(f"day {s['day']} skill/kind changed ({d.get('skill')}/{d.get('kind')}) -> restored")
            d["skill"], d["kind"] = s["skill"], s["kind"]
        em = d.get("estimated_minutes")
        if not isinstance(em, int) or em <= 0 or em > round(minutes * 1.1):
            issues.append(f"day {s['day']} minutes {em} outside budget -> {minutes}")
            d["estimated_minutes"] = min(max(int(em or minutes), 15), minutes)
        for f in ("topic", "learning_task", "practice_task", "completion_criteria"):
            if not str(d.get(f, "")).strip():
                issues.append(f"day {s['day']} empty {f} -> template")
                d[f] = _fallback_day(s, minutes, counters[s["skill"]])[f]
        d.setdefault("prerequisite", "none")
        final.append(d)
    covered = {d["skill"] for d in final if d["kind"] == "learn"}
    missing = [s["skill"] for s in skel if s["kind"] == "learn" and s["skill"] not in covered]
    return {"days": final, "issues": issues, "valid": not missing and len(final) == 30,
            "checks": {"n_days": len(final), "days_numbered_1_30": [d["day"] for d in final] == list(range(1, 31)),
                       "all_gaps_covered": not missing, "max_minutes": max(d["estimated_minutes"] for d in final),
                       "budget_minutes": minutes}}


# ── 6. resources ─────────────────────────────────────────────────────────────
def profile_resources(user_id: Optional[str] = None) -> Dict[str, List[str]]:
    try:
        mem = json.loads(config.memory_path(user_id).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    out: Dict[str, List[str]] = {}
    for block in re.split(r"(?=^skill:)", mem.get("skill_resources") or "", flags=re.M):
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if lines:
            out[normalize(lines[0].replace("skill:", ""))] = [l.replace("resource:", "").strip() for l in lines[1:]]
    return out


def generate_roadmap(target_role: str, candidate_skills: List[str], required_skills: Optional[List[str]] = None,
                     gaps: Optional[List[str]] = None, daily_minutes: int = 90, level: str = "beginner",
                     use_llm: bool = True, user_id: Optional[str] = None) -> Dict:
    t0 = time.perf_counter()
    cmp = compare(candidate_skills, required_skills or []) if required_skills else None
    gap_list = normalize_all(gaps) if gaps else (cmp["gaps"] if cmp else [])
    importance = market_importance(gap_list, target_role)
    ordered = prioritise(gap_list, importance)
    sk = build_skeleton(ordered, importance)
    from src.roadmap.syllabus import RESOURCES, capstone_for
    capstone = capstone_for(target_role, sk["scheduled"])
    for d in sk["skeleton"]:
        if d["kind"] == "project":
            d["capstone"] = capstone
    source = "template"
    days: List[Dict] = []
    from src.utilities.llm_provider import llm_provider
    # E33: local Mistral needed ~216 s for the 30-day JSON (looked broken in the UI) -> curriculum template.
    # Hosted / visitor-key models still write the days, with a hard time limit and template fallback.
    if use_llm and llm_provider() in ("api", "byok"):
        import concurrent.futures
        import contextvars
        ctx = contextvars.copy_context()  # carries the visitor's own key (BYOK) into the worker thread
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(ctx.run, fill_with_llm, sk["skeleton"], target_role, level, daily_minutes, normalize_all(candidate_skills))
        try:
            days = fut.result(timeout=LLM_TIMEOUT_S)
            source = "llm"
        except Exception as e:  # noqa: BLE001 - timeout or model error
            print(f"[roadmap] LLM fill unavailable ({type(e).__name__}: {str(e)[:120]}); using curriculum template")
            source = "template (LLM timed out)" if isinstance(e, concurrent.futures.TimeoutError) else "template"
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
    val = validate_and_repair(days, sk["skeleton"], daily_minutes)
    res = profile_resources(user_id)
    for d in val["days"]:
        links = [r for k, v in res.items() if k.lower() in d["skill"].lower() or d["skill"].lower() in k.lower() for r in v]
        if not links:  # E35: curated free resource for the skill when the profile analysis had none
            links = next((v for k2, v in RESOURCES.items() if k2.lower() == d["skill"].lower()), [])
        d["resources"] = links[:2]
    return {
        "target_role": target_role, "daily_minutes": daily_minutes, "level": level,
        "gap_analysis": cmp, "gaps_prioritised": ordered, "market_importance": importance,
        "days_per_skill": sk["days_per_skill"], "deferred_gaps": sk["deferred"],
        "generation": source, "validation": {k: val[k] for k in ("valid", "checks", "issues")},
        "capstone": capstone, "days": val["days"], "latency_ms": round((time.perf_counter() - t0) * 1000),
        "note": "A 30-day roadmap builds working familiarity; it does not guarantee mastery or a job.",
    }


def roadmap_from_profile(daily_minutes: int = 90, level: str = "beginner", use_llm: bool = True,
                         user_id: Optional[str] = None) -> Dict:
    mem = json.loads(config.memory_path(user_id).read_text(encoding="utf-8"))
    return generate_roadmap(mem.get("target_role") or "", mem.get("candidate_skills") or [],
                            required_skills=mem.get("required_skills") or [], daily_minutes=daily_minutes,
                            level=level, use_llm=use_llm, user_id=user_id)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--from-profile", action="store_true")
    p.add_argument("--role", default="")
    p.add_argument("--have", nargs="*", default=[])
    p.add_argument("--gaps", nargs="*", default=[])
    p.add_argument("--minutes", type=int, default=90)
    p.add_argument("--no-llm", action="store_true")
    a = p.parse_args()
    r = (roadmap_from_profile(a.minutes, use_llm=not a.no_llm) if a.from_profile
         else generate_roadmap(a.role, a.have, gaps=a.gaps, daily_minutes=a.minutes, use_llm=not a.no_llm))
    out = config.PROJECT_ROOT / "reports" / "roadmaps"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"roadmap_{time.strftime('%Y%m%dT%H%M%S')}.json"
    path.write_text(json.dumps(r, indent=2, ensure_ascii=False))
    print(json.dumps({k: r[k] for k in ("gaps_prioritised", "market_importance", "days_per_skill", "deferred_gaps", "generation", "validation", "latency_ms")}, indent=2))
    for d in r["days"][:8]:
        print(f"Day {d['day']:2d} [{d['kind']}] {d['skill']}: {d['topic']} | {d['practice_task']} | {d['estimated_minutes']}m | done when: {d['completion_criteria']}")
    print(f"... saved {path}")


if __name__ == "__main__":
    main()
