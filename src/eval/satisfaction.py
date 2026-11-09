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


def export(report: Path, n: int) -> Path:
    rep = json.loads(report.read_text())
    ids = sorted({r["id"] for r in rep["rows"]})
    random.Random(3).shuffle(ids)
    ids = set(ids[:n])
    rows = [r for r in rep["rows"] if r["id"] in ids]
    random.Random(5).shuffle(rows)
    out = report.with_name(report.stem.replace("heldout_eval", "qsr") + ".csv")
    key = {}
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "test_id", "question", "answer", "score_0_1_2", "notes"])
        for i, r in enumerate(rows, 1):
            key[f"item{i:03d}"] = r["version"]
            w.writerow([f"item{i:03d}", r["id"], r["question"], _body(r["answer"]), "", ""])
    out.with_suffix(".key.json").write_text(json.dumps(key, indent=1))
    print(f"{len(rows)} answers -> {out} (key: {out.with_suffix('.key.json').name})")
    return out


def score(csv_path: Path) -> dict:
    key = json.loads(csv_path.with_suffix(".key.json").read_text())
    by_v: dict = {}
    with open(csv_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            s = row.get("score_0_1_2", "").strip()
            if s in ("0", "1", "2"):
                by_v.setdefault(key[row["item"]], []).append(int(s))
    res = {v: {"n": len(x), "qsr": round(sum(x) / (2 * len(x)), 3), "share_fully_satisfied": round(x.count(2) / len(x), 3)}
           for v, x in by_v.items()}
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
    ap.add_argument("--judge", default="groq:openai/gpt-oss-120b")
    ap.add_argument("--sleep", type=float, default=3.0)
    a = ap.parse_args()
    {"export": lambda: export(Path(a.path), a.n), "score": lambda: score(Path(a.path)),
     "judge": lambda: judge(Path(a.path), a.n, a.judge, a.sleep)}[a.cmd]()


if __name__ == "__main__":
    main()
