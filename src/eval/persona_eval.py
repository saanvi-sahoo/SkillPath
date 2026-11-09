"""
Persona evaluation: questions about the PROFILE, the JOB DESCRIPTION, or BOTH, plus recursive feedback
learning (E33, docs/prompt_scripting.md §8, docs/feedback_learning.md §5).

Three test users (resume + JD) are analysed with the deterministic extractor, stored as real profiles
(memory file + private profile chunks), and asked 10 questions each. Checks use facts computed from that
persona's own data: {have} current skills, {required} JD skills, {gaps}, {matched}, {ats}, {role}.

Recursive learning (isolated feedback store, never the real one):
  R0  original questions            -> every failed check becomes 👎 feedback (reason + comment from the check)
  R1  paraphrase #1  WITH feedback   vs   paraphrase #1 with an EMPTY store (control)
  R2  paraphrase #2  WITH feedback from R0+R1   vs   control
The difference learned-vs-control isolates the effect of feedback learning on unseen wordings.

  LLM_PROVIDER=api CHAT_MODEL=gemini-3.1-flash-lite ROUTER_MODEL=gemini-3.1-flash-lite \
  python -m src.eval.persona_eval --versions v4 v5 --rounds
Writes reports/prompt_eval/persona_eval_<ts>.json + .md
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from src.rag import config

PERSONAS = {
    "persona_da": {
        "role": "Data Analyst",
        "resume": "Riya Sharma. B.Tech Computer Science 2025. Skills: Python, Excel, SQL, Pandas. Projects: sales dashboard "
                  "in Power BI for a college fest; Excel pivot-table analysis of hostel expenses. Internship: 2 months data entry and reporting.",
        "jd": "Data Analyst (0-2 years). Required: Python, SQL, Power BI, Tableau, Statistics, Data Visualization, Communication. "
              "Responsibilities: build dashboards, write SQL reports, present insights to business teams. Education: Bachelor's degree.",
    },
    "persona_be": {
        "role": "Backend Developer",
        "resume": "Arjun Mehta. B.E. Information Technology 2023. 1.5 years as Java developer. Skills: Java, Spring Boot, MySQL, Git, "
                  "REST APIs. Built an order-management REST API with Spring Boot and MySQL.",
        "jd": "Backend Developer (2+ years). Required: Java, Spring Boot, Microservices, Docker, Kubernetes, AWS, REST APIs. "
              "Responsibilities: design microservices, deploy containers on AWS, maintain CI/CD pipelines.",
    },
    "persona_ml": {
        "role": "Machine Learning Engineer",
        "resume": "Kavya Rao. B.Tech Mechanical Engineering 2022. 2 years design engineer. Skills: AutoCAD, MATLAB, Excel, Python. "
                  "Completed an online Python course and a regression project on fuel efficiency.",
        "jd": "Machine Learning Engineer. Required: Python, Machine Learning, TensorFlow, SQL, Statistics, Docker. "
              "Responsibilities: train and deploy ML models, build data pipelines. Education: Bachelor's in a technical field.",
    },
}

# (id, kind, question, paraphrase1, paraphrase2, checks)
CASES = [
    ("ats", "profile", "What is my ATS score?", "Tell me my ATS match score", "How well does my resume score against the ATS?",
     {"first_sentence_any": "{ats}"}),
    ("have", "profile", "What skills do I already have?", "Which skills are on my resume?", "List the skills I currently have",
     {"include_frac": ("{have}", 0.8)}),
    ("jdreq", "jd", "What does the job description require?", "What skills is the job asking for?", "Which requirements are listed in the JD?",
     {"include_frac": ("{required}", 0.8)}),
    ("jdresp", "jd", "What responsibilities does this role involve?", "What would I do day to day in this job according to the JD?",
     "What are the main duties mentioned in the job description?", {"must_include_any": ["dashboard", "microservice", "deploy", "model", "report", "pipeline"]}),
    ("missing", "both", "What am I missing for this job?", "Which skills do I lack for this role?", "What are my gaps for this position?",
     {"include_frac": ("{gaps}", 1.0)}),
    ("met", "both", "Which requirements of this job do I already meet?", "Which of the JD's skills do I already have?",
     "What job requirements match my resume?", {"include_frac": ("{matched}", 1.0)}),
    ("fit", "both", "Am I a good fit for this role?", "Should I apply for this job with my current profile?", "Is my profile suitable for this position?",
     {"first_sentence_any": ["yes", "no", "partial", "partly", "good fit", "not yet", "moderate", "strong", "decent", "fit"], "must_include_any": "{gaps}"}),
    ("highlight", "both", "What should I highlight in my resume for this job?", "Which parts of my experience should I emphasise for this role?",
     "How should I tailor my resume for this job?", {"include_frac": ("{matched}", 0.5)}),
    ("plan", "both", "Make a 4-week plan to close my gaps for this job", "Give me a one-month study plan for the missing skills",
     "How should I spend the next 4 weeks to become job-ready for this role?", {"include_frac": ("{gaps}", 0.75), "must_include_any": ["week", "Week"]}),
    ("first", "both", "Which missing skill should I learn first and why?", "What is the first gap I should work on?",
     "Which skill gap should I prioritise first?", {"first_sentence_any": "{gaps}"}),
]


def setup_personas() -> Dict[str, Dict]:
    """Create each persona's analysed profile exactly as the app stores it (memory file + profile chunks)."""
    from src.rag.ingest import ingest_profile_safely
    from src.skills.extractor import rule_based_analysis
    from src.skills.normalizer import compare

    facts = {}
    for uid, p in PERSONAS.items():
        a = rule_based_analysis(p["resume"], p["jd"])
        mem = {"resume_text": p["resume"], "job_description": p["jd"], "target_role": p["role"],
               "candidate_skills": a["candidate_skills"], "required_skills": a["required_skills"], "skill_gaps": a["skill_gaps"],
               "ats_score": a["ats_score"], "learning_path": a["learning_path"], "job_listings": [], "static_resources": [],
               "career_summary": f"Profile for {p['role']}: has {', '.join(a['candidate_skills'][:5])}; gaps {', '.join(a['skill_gaps'])}."}
        path = config.memory_path(uid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(mem, indent=2), encoding="utf-8")
        ingest_profile_safely(uid)
        cmp = compare(a["candidate_skills"], a["required_skills"])
        facts[uid] = {"have": a["candidate_skills"], "required": a["required_skills"], "gaps": a["skill_gaps"],
                      "matched": cmp["matched"], "ats": str(a["ats_score"]), "role": p["role"]}
    return facts


def _resolve(v, f):
    if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
        x = f[v[1:-1]]
        return x if isinstance(x, list) else [x]
    return v


def _body(t):
    return t.split("\n\n---\n**Sources**")[0]


def check(text: str, checks: Dict, f: Dict) -> Dict:
    body, out = _body(text).lower(), {}
    first = re.sub(r"^[#>*\s_]+", "", _body(text).strip())
    m = re.search(r"(.+?[.!?])(\s|$)", first, re.S)
    first = (m.group(1) if m else first)[:400].lower()
    for k, v in checks.items():
        if k == "include_frac":
            items, need = _resolve(v[0], f), v[1]
            got = sum(1 for i in items if str(i).lower() in body)
            out[k] = (got / len(items) >= need) if items else True
        elif k == "must_include_any":
            opts = _resolve(v, f)
            out[k] = any(str(o).lower() in body for o in opts) if opts else True
        elif k == "first_sentence_any":
            opts = _resolve(v, f)
            out[k] = any(str(o).lower() in first for o in opts) if opts else True
    return out


def feedback_from_failure(checks: Dict, failed: Dict, f: Dict) -> (str, str):
    """Turn a failed check into the kind of 👎 a careful user would leave (reason, comment)."""
    if "include_frac" in failed:
        items = _resolve(checks["include_frac"][0], f)
        return "inaccurate", "A good answer must name these exactly: " + ", ".join(map(str, items))
    if "first_sentence_any" in failed:
        opts = _resolve(checks["first_sentence_any"], f)
        return "not_answered", "Answer directly in the FIRST sentence, e.g. mention: " + ", ".join(map(str, opts[:4]))
    if "must_include_any" in failed:
        return "no_sources", "Be specific to the job description and my profile; mention: " + ", ".join(map(str, _resolve(checks["must_include_any"], f)[:4]))
    return "other", ""


EXPECT_MODEL = ""


def ask(q: str, uid: str, version: str) -> Dict:
    """E34: strict model. If a fallback model answered (rate limit), wait and retry; rows that still came from
    another model are flagged `excluded` and left out of the statistics (the R1 confound of the first run)."""
    from src.backend.chatbot import answer
    for attempt in range(4):
        r = answer([{"role": "user", "content": q}], system_version=version, user_id=uid)
        if not EXPECT_MODEL or r.get("model") in (EXPECT_MODEL, None):
            break
        time.sleep(20 * (attempt + 1))
    return {"text": r["text"], "model": r.get("model"), "learned": r.get("learned") or {}, "revised": r.get("revised"),
            "excluded": bool(EXPECT_MODEL and r.get("model") not in (EXPECT_MODEL, None)),
            "qtype": (r.get("question_profile") or {}).get("type"), "route": (r.get("route") or {}).get("label")}


def run_set(facts, version, qidx, sleep_s, store_feedback=False, fs=None) -> List[Dict]:
    rows = []
    for uid, f in facts.items():
        for case in CASES:
            cid, kind, qs, checks = case[0], case[1], case[2:5], case[5]
            q = qs[qidx]
            res = ask(q, uid, version)
            c = check(res["text"], checks, f)
            failed = {k: v for k, v in c.items() if not v}
            rows.append({"persona": uid, "id": cid, "kind": kind, "q": q, "qtype": res["qtype"], "route": res["route"],
                         "excluded": res["excluded"], "revised": res["revised"],
                         "checks": c, "passed": not failed, "model": res["model"], "learned": res["learned"],
                         "answer": res["text"][:1500]})
            print(f"[{version} q{qidx}] {uid:10s} {cid:9s} {kind:7s} {res['qtype'] or '-':15s} passed={not failed} {failed or ''}")
            if store_feedback and failed and fs is not None:
                reason, comment = feedback_from_failure(checks, failed, f)
                fs.record(q, res["text"], "down", uid, reason=reason, comment=comment, prompt_version=version)
            if store_feedback and not failed and fs is not None:
                fs.record(q, res["text"], "up", uid, prompt_version=version)
            time.sleep(sleep_s)
    return rows


def summarise(rows):
    rows = [r for r in rows if not r.get("excluded")]
    n = len(rows) or 1
    by_kind = {}
    for r in rows:
        by_kind.setdefault(r["kind"], []).append(r["passed"])
    return {"n": len(rows), "pass_rate": round(sum(r["passed"] for r in rows) / n, 3),
            "by_kind": {k: round(sum(v) / len(v), 3) for k, v in by_kind.items()},
            "models": sorted({str(r["model"]) for r in rows}), "revised": sum(bool(r.get("revised")) for r in rows)}


def isolated_store(path: Path):
    from src.backend import feedback_store as fs
    fs.LOCAL_FILE = path
    fs.REQUIRE_APPROVAL = False  # isolated experiment: simulated feedback counts as reviewed
    fs._mongo = lambda: None
    fs._cache.update(t=0.0, rows=None)
    return fs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", nargs="+", default=["v4", "v5"])
    ap.add_argument("--rounds", action="store_true", help="recursive feedback-learning rounds on the last version")
    ap.add_argument("--sleep", type=float, default=3.0)
    ap.add_argument("--expect-model", default="")
    ap.add_argument("--qidx", type=int, default=0, help="0 = original questions, 1/2 = paraphrase sets (unseen wording)")
    a = ap.parse_args()
    global EXPECT_MODEL
    EXPECT_MODEL = a.expect_model
    facts = setup_personas()
    print("facts:", json.dumps(facts))
    tmp = Path(tempfile.mkdtemp())
    rep = {"ts": datetime.now(timezone.utc).isoformat(), "facts": facts, "versions": {}, "rounds": {}}
    for v in a.versions:  # A/B on the original questions, empty feedback store
        isolated_store(tmp / f"empty_{v}.jsonl")
        rows = run_set(facts, v, a.qidx, a.sleep)
        rep["versions"][v] = {"summary": summarise(rows), "rows": rows, "qidx": a.qidx}
    if a.rounds:
        v = a.versions[-1]
        fs = isolated_store(tmp / "learning.jsonl")
        r0 = run_set(facts, v, 0, a.sleep, store_feedback=True, fs=fs)              # R0 -> feedback
        rep["rounds"]["R0_original"] = {"summary": summarise(r0), "rows": r0}
        for qi in (1, 2):
            fs = isolated_store(tmp / "learning.jsonl")                                # learned store
            learned = run_set(facts, v, qi, a.sleep, store_feedback=True, fs=fs)      # recursive: feeds the next round
            isolated_store(tmp / f"control_{qi}.jsonl")                               # empty store = control
            control = run_set(facts, v, qi, a.sleep)
            rep["rounds"][f"R{qi}_paraphrase"] = {"learned": summarise(learned), "control": summarise(control),
                                                  "learned_rows": learned, "control_rows": control}
    out = config.PROJECT_ROOT / "reports" / "prompt_eval" / f"persona_eval_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    out.write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    print("\n=== SUMMARY ===")
    for v, d in rep["versions"].items():
        print(v, json.dumps(d["summary"]))
    for k, d in rep["rounds"].items():
        print(k, json.dumps({kk: vv for kk, vv in d.items() if not kk.endswith("rows")}))
    print("saved", out)


if __name__ == "__main__":
    main()
