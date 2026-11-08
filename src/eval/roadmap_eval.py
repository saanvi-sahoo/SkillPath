"""
Roadmap evaluation (E35, docs/skills_and_roadmap.md §4). Deterministic, no LLM.
For each persona: valid 30-day plan, every gap covered, prerequisites scheduled before dependants,
time budget respected, curated resource on every learning day of a known skill, role-specific capstone,
no generic 'part N' topics.
    python -m src.eval.roadmap_eval
"""
import json
from datetime import datetime, timezone

from src.eval.persona_eval import PERSONAS
from src.rag import config
from src.roadmap.generator import PREREQS, generate_roadmap
from src.roadmap.syllabus import RESOURCES
from src.skills.extractor import rule_based_analysis


def evaluate(uid, p, minutes=90):
    a = rule_based_analysis(p["resume"], p["jd"])
    r = generate_roadmap(p["role"], a["candidate_skills"], required_skills=a["required_skills"], daily_minutes=minutes, use_llm=False)
    first = {}
    for d in r["days"]:
        if d["kind"] == "learn":
            first.setdefault(d["skill"], d["day"])
    prereq_ok = all(first[pre] < first[g] for g in first for pre in PREREQS.get(g, []) if pre in first)
    known = [d for d in r["days"] if d["kind"] == "learn" and d["skill"] in RESOURCES]
    checks = {
        "valid_30_days": r["validation"]["valid"] and len(r["days"]) == 30,
        "all_gaps_covered": set(r["gaps_prioritised"][:8]) <= set(first),
        "prereqs_before_dependants": prereq_ok,
        "within_time_budget": max(d["estimated_minutes"] for d in r["days"]) <= minutes,
        "resources_on_known_skill_days": all(d.get("resources") for d in known),
        "role_specific_capstone": not r["capstone"].startswith("Portfolio project for"),
        "no_generic_part_topics": not any(" - part " in d["topic"] for d in r["days"]),
    }
    return {"persona": uid, "role": p["role"], "gaps": r["gaps_prioritised"], "days_per_skill": r["days_per_skill"],
            "capstone": r["capstone"], "checks": checks, "passed": all(checks.values()), "latency_ms": r["latency_ms"]}


def main():
    rows = [evaluate(uid, p) for uid, p in PERSONAS.items()]
    for row in rows:
        print(row["persona"], "passed" if row["passed"] else "FAILED", {k: v for k, v in row["checks"].items() if not v} or "", "|", row["capstone"][:80])
    out = config.PROJECT_ROOT / "reports" / "roadmaps" / f"roadmap_eval_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2))
    print(f"{sum(r['passed'] for r in rows)}/{len(rows)} personas passed all checks -> {out.name}")


if __name__ == "__main__":
    main()
