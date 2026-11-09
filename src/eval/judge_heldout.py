"""
Blind LLM-judge pass over a held-out run (E36, docs/evaluation.md §5). Run monthly with the SAME judge model so
scores stay comparable.

Blind: the judge sees the question, the student profile, the retrieved sources and one answer. It never sees the
prompt version, the expected answer or the other version's answer, and rows are shuffled. The judge must be a
different model family from the answering model (self-preference bias, E14).

  python -m src.eval.judge_heldout reports/heldout/heldout_eval_<ts>.json --judge groq:openai/gpt-oss-120b --n 30
Writes the scores into the report (row["judge"]) and prints the per-version means. Resumable.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

PROMPT = """You are grading one answer from a career & study advisor for students. You do not know which system wrote it.
Score 1-5 for each criterion:
- correctness: every factual claim is right and supported by the PROFILE or SOURCES (or is well-established general knowledge)
- precision: answers exactly the question asked, in the requested form and length, without padding
- grounding: claims about the student match the PROFILE exactly; citations [S#] point to sources that support them
- usefulness: a student could act on it
Return ONLY JSON: {{"correctness": n, "precision": n, "grounding": n, "usefulness": n, "comment": "<20 words"}}

PROFILE:
{profile}

SOURCES:
{context}

QUESTION:
{question}

ANSWER:
{answer}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--judge", default="groq:openai/gpt-oss-120b")
    ap.add_argument("--n", type=int, default=30, help="cases (same ids judged for every version)")
    ap.add_argument("--sleep", type=float, default=3.0)
    a = ap.parse_args()
    from src.backend.chatbot import load_profile_summary
    from src.utilities.brain import get_base_llm

    path = Path(a.report)
    rep = json.loads(path.read_text())
    allow = sorted({r["id"] for r in rep["rows"] if r["category"] != "out_of_scope"})
    random.Random(7).shuffle(allow)
    ids = set(allow[:a.n])
    rows = [r for r in rep["rows"] if r["id"] in ids]
    random.Random(11).shuffle(rows)
    llm = get_base_llm(a.judge, temperature=0.0)
    for r in rows:
        if isinstance(r.get("judge"), dict) and "correctness" in r["judge"]:
            continue
        prompt = PROMPT.format(profile=load_profile_summary(r["user"]) if r.get("user") else "No analysed profile.",
                               context=r.get("context") or "(none)", question=r["question"],
                               answer=r["answer"].split("\n\n---\n**Sources**")[0])
        try:
            resp = llm.invoke(prompt)
            m = re.search(r"\{.*\}", resp.text, re.S)
            r["judge"] = {**json.loads(m.group(0)), "judge_model": (resp.response_metadata or {}).get("model_name")} if m else {"error": resp.text[:200]}
        except Exception as e:  # noqa: BLE001
            r["judge"] = {"error": str(e)[:200]}
            time.sleep(30)
        print(r["version"], r["id"], r["judge"])
        path.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        time.sleep(a.sleep)
    for v in rep["versions"]:
        js = [r["judge"] for r in rep["rows"] if r["version"] == v and isinstance(r.get("judge"), dict) and "correctness" in r["judge"]]
        if js:
            print(v, {k: round(sum(j[k] for j in js) / len(js), 2) for k in ("correctness", "precision", "grounding", "usefulness")}, f"n={len(js)}")


if __name__ == "__main__":
    main()
