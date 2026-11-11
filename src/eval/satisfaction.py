"""
Question Satisfaction Rate (QSR) + the review's evaluation-judge prompt (E37, review 2 §10 and kit §5).

QSR is a HUMAN metric: for each answer a reviewer decides whether it actually fulfilled the request.
  0 = incorrect, irrelevant or failed to answer   1 = partially correct or incomplete
  2 = correct, relevant, complete and follows the user's instructions
QSR = mean score / 2 (also reported: share of 2s). Reviewers see the question, history and answer, never the prompt
version (answers are shuffled and labelled A/B; the key is kept in a separate file).

  python -m src.eval.satisfaction export reports/heldout/heldout_eval_<ts>.json --n 40     # -> CSV to fill in
  python -m src.eval.satisfaction score  reports/heldout/qsr_<ts>.csv                      # -> QSR per version
  python -m src.eval.satisfaction judge  reports/heldout/heldout_eval_<ts>.json --n 30 --judge groq:openai/gpt-oss-120b

The LLM judge is a secondary signal only: objective rules (counts, labels, 30 days) are Python checks, and
subjective usefulness is decided by people.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
from pathlib import Path

JUDGE_PROMPT = """You are evaluating a Career and Study Advisor.

You receive: the user's question, the relevant conversation history, the authorized profile information, the retrieved
source records, the expected behaviour, and the chatbot's response.

Evaluate the response independently on these dimensions:
- scope_correctness: was the question accepted or refused appropriately?
- intent_satisfaction: did the response answer the actual question?
- factual_correctness: are its claims accurate according to the available evidence?
- grounding: are source-dependent claims supported by the retrieved information?
- citation_correctness: does each citation refer to a real source that supports that claim?
- profile_consistency: did the response use only the correct student's authorized information?
- constraint_compliance: did it follow requested counts, format, language and length?
- clarity: is it understandable at the student's level?
- actionability: does it give useful next steps when appropriate?

For each dimension return {{"score": 0|1|2|"not_evaluable", "reason": "...", "evidence": "quoted text"}}.
Also return "overall_pass" (true/false), "failure_category" and "recommended_fix".
Do not assume the chatbot's answer is correct. Do not give a high score because citations are present: check whether
they support the claims. Use "not_evaluable" when the evidence is insufficient. Return valid JSON only.

QUESTION: {question}
HISTORY: {history}
PROFILE: {profile}
SOURCES: {sources}
EXPECTED BEHAVIOUR: {expected}
RESPONSE: {answer}"""
DIMS = ["scope_correctness", "intent_satisfaction", "factual_correctness", "grounding", "citation_correctness",
        "profile_consistency", "constraint_compliance", "clarity", "actionability"]


def _body(t: str) -> str:
    return t.split("\n\n---\n**Sources**")[0]


# Final validation (review 4): stratified so every area the review names is scored, with the conversation shown.
STRATA = {"cv_jd": lambda r: r["category"] == "profile",
          "career_transition": lambda r: "transition" in (r.get("tags") or []),
          "roadmap": lambda r: bool({"plan", "time_budget", "missing_time", "adaptive_plan"} & set(r.get("tags") or [])),
          "study": lambda r: r["id"] in {"rw14", "rw15", "rw25", "rw29", "rw36", "rw44", "rw48", "mt04", "mt24", "mt37", "mt47"},
          "follow_up": lambda r: r["category"] == "multi_turn"}


def export(report: Path, n: int, per_stratum: int = 0) -> Path:
    rep = json.loads(report.read_text())
    versions = rep["versions"]
    rows_all = [r for r in rep["rows"] if r["version"] in versions and r["category"] != "out_of_scope"]
    if per_stratum:
        rnd, chosen = random.Random(3), []
        for name, pred in STRATA.items():
            pool = sorted({r["id"] for r in rows_all if pred(r)} - set(chosen))
            rnd.shuffle(pool)
            chosen += pool[:per_stratum]
        ids = set(chosen)
    else:
        ids = sorted({r["id"] for r in rows_all})
        random.Random(3).shuffle(ids)
        ids = set(ids[:n])
    rows = [r for r in rows_all if r["id"] in ids]
    random.Random(5).shuffle(rows)
    try:
        from src.eval.heldout_eval import SETS, load_cases
        hist = {c["id"]: c["messages"][:-1] for c in load_cases(SETS[rep.get("set", "heldout")])}
    except Exception:  # noqa: BLE001
        hist = {}
    stratum = {i: next((k for k, p in STRATA.items() if p(r)), "other") for r in rows for i in [r["id"]]}
    out = report.with_name(report.stem.replace("heldout_eval", "qsr").split("_p")[0] + ".csv")
    key = {}
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "area", "conversation_so_far", "question", "answer", "reviewer1_0_1_2", "reviewer2_0_1_2", "notes"])
        for i, r in enumerate(rows, 1):
            key[f"item{i:03d}"] = {"version": r["version"], "test_id": r["id"]}
            conv = " || ".join(f"{m['role']}: {m['content'][:300]}" for m in hist.get(r["id"], []))
            w.writerow([f"item{i:03d}", stratum[r["id"]], conv, r["question"], _body(r["answer"]), "", "", ""])
    out.with_suffix(".key.json").write_text(json.dumps(key, indent=1))
    print(f"{len(rows)} answers -> {out} (key: {out.with_suffix('.key.json').name})")
    return out


def score(csv_path: Path) -> dict:
    """QSR per version (mean of the reviewers' scores / 2), share scored 2/2, and agreement between the two reviewers."""
    key = json.loads(csv_path.with_suffix(".key.json").read_text())
    by_v: dict = {}
    pairs, by_area = [], {}
    with open(csv_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            k = key[row["item"]]
            v = k["version"] if isinstance(k, dict) else k
            sc = [int(row.get(c, "").strip()) for c in ("reviewer1_0_1_2", "reviewer2_0_1_2", "score_0_1_2") if row.get(c, "").strip() in ("0", "1", "2")]
            if not sc:
                continue
            if len(sc) >= 2:
                pairs.append((sc[0], sc[1]))
            m = sum(sc) / len(sc)
            by_v.setdefault(v, []).append(m)
            by_area.setdefault((v, row.get("area", "")), []).append(m)
    res = {v: {"n": len(x), "qsr": round(sum(x) / (2 * len(x)), 3), "share_fully_satisfied": round(sum(s == 2 for s in x) / len(x), 3)}
           for v, x in by_v.items()}
    res["by_area"] = {f"{v} / {a}": round(sum(x) / (2 * len(x)), 3) for (v, a), x in sorted(by_area.items())}
    if pairs:
        res["reviewer_agreement"] = {"n": len(pairs), "exact": round(sum(a == b for a, b in pairs) / len(pairs), 3),
                                     "within_1": round(sum(abs(a - b) <= 1 for a, b in pairs) / len(pairs), 3)}
    print(json.dumps(res, indent=2))
    return res


def judge(report: Path, n: int, judge_model: str, sleep_s: float) -> None:
    from src.backend.chatbot import load_profile_summary
    from src.utilities.brain import get_base_llm
    rep = json.loads(report.read_text())
    ids = sorted({r["id"] for r in rep["rows"] if r["category"] != "out_of_scope"})
    random.Random(9).shuffle(ids)
    ids = set(ids[:n])
    cases = {}
    try:
        from src.eval.heldout_eval import SETS, load_cases
        for c in load_cases(SETS[rep.get("set", "heldout")]):
            cases[c["id"]] = c
    except Exception:  # noqa: BLE001
        pass
    llm = get_base_llm(judge_model, temperature=0.0)
    for r in [x for x in rep["rows"] if x["id"] in ids]:
        if isinstance(r.get("judge_v2"), dict) and "overall_pass" in r["judge_v2"]:
            continue
        hist = cases.get(r["id"], {}).get("messages", [])[:-1]
        prompt = JUDGE_PROMPT.format(question=r["question"], history=json.dumps(hist)[:1500] or "(none)",
                                     profile=load_profile_summary(r["user"]) if r.get("user") else "No analysed profile.",
                                     sources=(r.get("context") or "(none)")[:3500], expected=r.get("expected_behavior", ""),
                                     answer=_body(r["answer"]))
        try:
            resp = llm.invoke(prompt)
            m = re.search(r"\{.*\}", resp.text, re.S)
            r["judge_v2"] = json.loads(m.group(0)) if m else {"error": resp.text[:200]}
            r["judge_v2"]["judge_model"] = (resp.response_metadata or {}).get("model_name")
        except Exception as e:  # noqa: BLE001
            r["judge_v2"] = {"error": str(e)[:200]}
            time.sleep(30)
        print(r["version"], r["id"], r["judge_v2"].get("overall_pass"), r["judge_v2"].get("failure_category"))
        report.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        time.sleep(sleep_s)
    for v in rep["versions"]:
        js = [r["judge_v2"] for r in rep["rows"] if r["version"] == v and isinstance(r.get("judge_v2"), dict) and "overall_pass" in r["judge_v2"]]
        if not js:
            continue
        dims = {d: [j[d]["score"] for j in js if isinstance(j.get(d), dict) and isinstance(j[d].get("score"), int)] for d in DIMS}
        print(v, f"n={len(js)} overall_pass={round(sum(bool(j['overall_pass']) for j in js) / len(js), 3)}",
              {d: round(sum(x) / (2 * len(x)), 2) for d, x in dims.items() if x})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["export", "score", "judge"])
    ap.add_argument("path")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--per-stratum", type=int, default=0, help="stratified export: N cases per area (CV/JD, transition, roadmap, study, follow-up)")
    ap.add_argument("--judge", default="groq:openai/gpt-oss-120b")
    ap.add_argument("--sleep", type=float, default=3.0)
    a = ap.parse_args()
    {"export": lambda: export(Path(a.path), a.n, a.per_stratum), "score": lambda: score(Path(a.path)),
     "judge": lambda: judge(Path(a.path), a.n, a.judge, a.sleep)}[a.cmd]()


if __name__ == "__main__":
    main()
