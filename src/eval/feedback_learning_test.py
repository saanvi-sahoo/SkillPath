"""
Does the advisor actually learn from feedback? (E32, docs/feedback_learning.md)

Runs against an isolated, temporary feedback store (never touches real feedback), prompt v5:
  1. 👎 + comment on question Q  -> paraphrase of Q must now follow the comment
  2. 👍 on question Q            -> paraphrase of Q gets the helpful answer as guidance
  3. "wrongly refused" by 2 users -> the scope router accepts that question afterwards

    LLM_PROVIDER=api CHAT_MODEL=gemini-3.1-flash-lite python -m src.eval.feedback_learning_test
Writes reports/prompt_eval/feedback_learning_<ts>.json
"""
from __future__ import annotations

import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from src.backend import feedback_store as fs
from src.backend.chatbot import answer
from src.rag import config


def ask(q: str, uid: str = "learner") -> dict:
    r = answer([{"role": "user", "content": q}], system_version="v5", user_id=uid)
    return {"q": q, "text": r["text"], "route": r["route"]["label"], "model": r.get("model"), "learned": r.get("learned")}


def main():
    tmp = Path(tempfile.mkdtemp()) / "feedback.jsonl"
    fs.LOCAL_FILE = tmp
    fs._mongo = lambda: None          # isolated: never write the real Atlas/local store
    fs._cache.update(t=0.0, rows=None)
    out = {"ts": datetime.now(timezone.utc).isoformat(), "store": str(tmp), "tests": {}}

    # 1. negative feedback with a concrete requirement
    marker = "Microsoft Learn"
    q1, q1b = "Which certification should I do for Power BI?", "What is the best Power BI certification to get?"
    a1 = ask(q1)
    fs.record(q1, a1["text"], "down", "learner", reason="not_answered",
              comment=f"Name the PL-300 exam and point to the free '{marker}' PL-300 learning path as the way to prepare.")
    time.sleep(2)
    a1b = ask(q1b)
    out["tests"]["negative_feedback_followed"] = {
        "before_has_marker": marker in a1["text"], "after_has_marker": marker in a1b["text"],
        "after_used_feedback": (a1b["learned"] or {}).get("n_bad", 0) >= 1,
        "passed": marker in a1b["text"] and (a1b["learned"] or {}).get("n_bad", 0) >= 1,
        "before": a1["text"][:600], "after": a1b["text"][:600]}

    # 2. positive feedback becomes guidance for similar questions
    q2, q2b = "How should I prepare for a data analyst interview?", "How do I get ready for a data analyst interview?"
    a2 = ask(q2)
    fs.record(q2, a2["text"], "up", "learner")
    time.sleep(2)
    a2b = ask(q2b)
    out["tests"]["positive_feedback_reused"] = {"after_n_good": (a2b["learned"] or {}).get("n_good", 0),
                                                "passed": (a2b["learned"] or {}).get("n_good", 0) >= 1}

    # 3. router learns from repeated "wrongly refused" reports (>= 2 distinct users)
    q3 = "How do I make friends in a new college?"  # refused by the router before feedback (checked 2026-11-08)
    before = ask(q3)["route"]
    for u in ("user-a", "user-b"):
        fs.record(q3, "refused", "down", u, reason="wrong_refusal")
    fs._cache.update(t=0.0, rows=None)
    after = ask(q3)["route"]
    out["tests"]["router_learns_wrong_refusal"] = {"before": before, "after": after,
                                                   "passed": after == "career_study" and (before != "career_study")}
    out["model"] = a1b["model"]
    out["passed"] = sum(t["passed"] for t in out["tests"].values())
    rep = config.PROJECT_ROOT / "reports" / "prompt_eval"
    rep.mkdir(parents=True, exist_ok=True)
    path = rep / f"feedback_learning_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("before", "after") or k == "router_learns_wrong_refusal"}
                      for k, v in out["tests"].items()}, indent=1))
    print("model:", out["model"], "| passed", out["passed"], "/ 3 | saved", path)


if __name__ == "__main__":
    main()
