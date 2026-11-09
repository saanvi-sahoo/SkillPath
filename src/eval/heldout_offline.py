"""
Held-out evaluation, deterministic part (E36, docs/evaluation.md). No LLM calls.

  careers    30 frozen held-out career queries (+ the 24 tuning queries) -> strict P@5 per retrieval config
  roadmap    20 roadmap cases (roles x gaps x daily minutes) -> 8 checks each
  isolation  profile-isolation security tests: one user's question must never retrieve another user's profile

  python -m src.eval.heldout_offline              # all
  python -m src.eval.heldout_offline --only careers
Writes reports/heldout/heldout_offline_<ts>.json + heldout_offline_latest.md
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import numpy as np

from src.rag import config

HERE = Path(__file__).parent
OUT = config.PROJECT_ROOT / "reports" / "heldout"
CONFIGS = ["vector", "vector+ce", "vector+ce+skill"]


def _load(p: Path) -> List[Dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


# ── careers ──────────────────────────────────────────────────────────────────
def career_search(query: str, cfg: str, k: int = 5) -> List[Dict]:
    from src.rag.embedder import embed_query
    from src.rag.hybrid import rerank
    from src.rag.skill_rerank import skill_rerank
    from src.rag.vector_store import get_vector_store

    qv = embed_query(query)
    pool = get_vector_store("careers", "local").search(qv, k=20 if cfg != "vector" else k, sources=["careers"])
    if cfg == "vector":
        return pool[:k]
    ce = rerank(query, pool, top=len(pool))
    if cfg == "vector+ce":
        return ce[:k]
    return skill_rerank(query, ce, top=k)


def careers_task(queries: List[Dict], cfg: str) -> Dict:
    from src.eval.evaluate_career_retrieval import _kw_hit
    per = []
    for q in queries:
        hits = career_search(q["query"], cfg)
        ok = [((h.get("metadata") or {}).get("domain") in q["domains"]) and
              _kw_hit(f"{(h.get('metadata') or {}).get('career_name')} {(h.get('metadata') or {}).get('required_skills')}", q["keywords"])
              for h in hits]
        per.append({"id": q["id"], "p@5": sum(ok) / 5, "top": [(h.get("metadata") or {}).get("career_name") for h in hits[:3]]})
    return {"strict_p@5": round(float(np.mean([p["p@5"] for p in per])), 3), "worst": sorted(per, key=lambda p: p["p@5"])[:5]}


def run_careers() -> Dict:
    sets = {"tuning_24": _load(HERE / "career_queries.jsonl"), "heldout_30": _load(HERE / "heldout" / "heldout_careers.jsonl")}
    res = {name: {cfg: careers_task(qs, cfg) for cfg in CONFIGS} for name, qs in sets.items()}
    for name in res:
        print(name, {cfg: r["strict_p@5"] for cfg, r in res[name].items()})
    return res


# ── roadmap ──────────────────────────────────────────────────────────────────
ROADMAP_CASES = [  # (role, candidate skills, required skills, daily minutes)
    ("Data Analyst", ["Excel"], ["SQL", "Power BI", "Statistics", "Python"], 60),
    ("Data Analyst", ["Python", "SQL"], ["Tableau", "Statistics"], 30),
    ("Data Analyst", ["SQL", "Power BI"], ["Python", "Tableau", "Statistics", "Excel", "Data Visualization"], 120),
    ("Backend Developer", ["Java"], ["Spring Boot", "Docker", "Kubernetes", "AWS"], 90),
    ("Backend Developer", ["Python", "Django"], ["Docker", "PostgreSQL", "REST APIs"], 45),
    ("Backend Developer", ["Java", "Spring Boot"], ["Microservices", "Kafka", "Docker", "Kubernetes", "AWS", "CI/CD"], 120),
    ("Machine Learning Engineer", ["Python"], ["Machine Learning", "Statistics", "SQL", "TensorFlow"], 90),
    ("Machine Learning Engineer", ["Python", "Pandas", "scikit-learn"], ["Deep Learning", "PyTorch", "Docker"], 60),
    ("Machine Learning Engineer", ["MATLAB"], ["Python", "Machine Learning", "Statistics", "Docker", "SQL", "TensorFlow", "AWS"], 120),
    ("Data Engineer", ["SQL", "Python"], ["Apache Spark", "Airflow", "AWS"], 90),
    ("Data Engineer", ["Python"], ["SQL", "Apache Spark", "Kafka", "Docker"], 60),
    ("Cloud Engineer", ["Linux"], ["AWS", "Docker", "Kubernetes", "Terraform"], 90),
    ("DevOps Engineer", ["Git", "Linux"], ["CI/CD", "Docker", "Kubernetes", "Jenkins"], 60),
    ("Frontend Developer", ["HTML", "CSS"], ["JavaScript", "React", "TypeScript"], 90),
    ("Full Stack Developer", ["JavaScript"], ["React", "Node.js", "MongoDB", "Docker"], 120),
    ("Business Analyst", ["Excel", "Communication"], ["SQL", "Power BI", "Statistics"], 45),
    ("Data Scientist", ["Python", "SQL"], ["Statistics", "Machine Learning", "Deep Learning"], 90),
    ("Cybersecurity Analyst", ["Linux"], ["Networking", "Python", "SIEM"], 60),
    ("Data Analyst", ["Python", "SQL", "Power BI", "Tableau", "Statistics"], ["Python", "SQL", "Communication"], 60),
    ("Backend Developer", ["MySQL"], ["SQL", "Java", "Spring Boot"], 90),   # MySQL proves SQL: SQL must NOT be a gap
]


def roadmap_case(i: int, role, have, req, minutes) -> Dict:
    from src.roadmap.generator import PREREQS, generate_roadmap
    from src.roadmap.syllabus import RESOURCES
    from src.skills.normalizer import compare

    r = generate_roadmap(role, have, required_skills=req, daily_minutes=minutes, use_llm=False)
    gaps = compare(have, req)["gaps"]
    first: Dict[str, int] = {}
    for d in r["days"]:
        if d["kind"] == "learn":
            first.setdefault(d["skill"], d["day"])
    have_l = {h.lower() for h in have}
    known = [d for d in r["days"] if d["kind"] == "learn" and d["skill"] in RESOURCES]
    checks = {
        "valid_30_days": r["validation"]["valid"] and len(r["days"]) == 30,
        "gaps_exact": [g.lower() for g in r["gaps_prioritised"]] == [g.lower() for g in r["gaps_prioritised"] if g in gaps or g.lower() in {x.lower() for x in gaps}]
                      and set(x.lower() for x in r["gaps_prioritised"]) == set(x.lower() for x in gaps),
        "all_gaps_covered": set(r["gaps_prioritised"][:8]) <= set(first),
        "never_teaches_known_skill": not any(s.lower() in have_l for s in first),
        "prereqs_before_dependants": all(first[p] < first[g] for g in first for p in PREREQS.get(g, []) if p in first),
        "within_time_budget": max(d["estimated_minutes"] for d in r["days"]) <= minutes,
        "resources_on_known_skill_days": all(d.get("resources") for d in known),
        "role_specific_capstone": not r["capstone"].startswith("Portfolio project for")
                                  and not ("secur" in role.lower() and "dashboard" in r["capstone"].lower()),
    }
    if not gaps:  # nothing to learn: the plan must say so rather than invent gaps
        checks = {"no_gaps_handled": not r["gaps_prioritised"]}
    return {"id": f"rm{i:02d}", "role": role, "gaps": gaps, "days_per_skill": r.get("days_per_skill"),
            "checks": checks, "passed": all(checks.values())}


def run_roadmap() -> Dict:
    rows = [roadmap_case(i, *c) for i, c in enumerate(ROADMAP_CASES, 1)]
    for r in rows:
        print(r["id"], r["role"], "PASS" if r["passed"] else "FAIL", {k: v for k, v in r["checks"].items() if not v} or "")
    return {"pass_rate": round(sum(r["passed"] for r in rows) / len(rows), 3), "rows": rows}


# ── profile isolation (security) ─────────────────────────────────────────────
def run_isolation() -> Dict:
    from src.eval.persona_eval import setup_personas
    from src.rag.embedder import embed_query
    from src.rag.vector_store import get_vector_store, resolve_backend

    setup_personas()
    probes = ["What is my ATS score and my skill gaps?", "Spring Boot microservices AWS backend resume",
              "Power BI Tableau dashboards data analyst resume", "mechanical engineer MATLAB AutoCAD machine learning",
              "Show me the resume and job description"]
    users = ["persona_da", "persona_be", "persona_ml", "nobody_without_profile"]
    rows = []
    for backend in sorted({"local", resolve_backend()}):
        store = get_vector_store("profile", backend)
        for uid in users:
            for p in probes:
                hits = store.search(embed_query(p), k=8, sources=["profile"], user_id=uid)
                foreign = [h.get("user_id") for h in hits if h.get("user_id") != uid]
                rows.append({"backend": backend, "user": uid, "probe": p, "n": len(hits), "foreign": foreign, "passed": not foreign})
    bad = [r for r in rows if not r["passed"]]
    print(f"isolation: {len(rows) - len(bad)}/{len(rows)} probes clean", bad[:3])
    return {"pass_rate": round((len(rows) - len(bad)) / len(rows), 3), "n": len(rows), "failures": bad}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["careers", "roadmap", "isolation"])
    a = ap.parse_args()
    res = {"ts": datetime.now(timezone.utc).isoformat()}
    for name, fn in (("careers", run_careers), ("roadmap", run_roadmap), ("isolation", run_isolation)):
        if not a.only or a.only == name:
            res[name] = fn()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"heldout_offline_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json").write_text(json.dumps(res, indent=2, default=str))
    L = ["# Held-out evaluation (deterministic part)", "", res["ts"], ""]
    if "careers" in res:
        L += ["| Query set | " + " | ".join(CONFIGS) + " |", "|---|" + "---|" * len(CONFIGS)]
        for name, r in res["careers"].items():
            L.append(f"| {name} | " + " | ".join(str(r[c]["strict_p@5"]) for c in CONFIGS) + " |")
    if "roadmap" in res:
        L += ["", f"Roadmap cases passing all checks: {res['roadmap']['pass_rate']} (n={len(res['roadmap']['rows'])})"]
    if "isolation" in res:
        L += ["", f"Profile isolation: {res['isolation']['pass_rate']} of {res['isolation']['n']} probes clean"]
    (OUT / "heldout_offline_latest.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
