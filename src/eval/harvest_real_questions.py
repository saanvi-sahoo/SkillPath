"""
Grow the test set from REAL usage (E36, docs/evaluation.md §6).

Collects questions people actually asked (chat log) and every 👎 with its reason/comment (feedback store), removes
anything already in an evaluation set, de-duplicates near-identical wording, and writes candidates for a teammate to
label (expected behaviour + checks). Labelled cases go into a NEW held-out file; never into the set used for tuning.

  python -m src.eval.harvest_real_questions
Writes reports/heldout/real_question_candidates.jsonl
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from src.rag import config

HERE = Path(__file__).parent
OUT = config.PROJECT_ROOT / "reports" / "heldout" / "real_question_candidates.jsonl"


def _norm(q: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (q or "").lower()).strip()


def known_questions() -> set:
    seen = set()
    for p in [HERE / "prompt_eval_set.jsonl", HERE / "heldout" / "heldout_chat.jsonl"]:
        for l in p.read_text().splitlines():
            if l.strip():
                seen.add(_norm(json.loads(l)["messages"][-1]["content"]))
    from src.eval.persona_eval import CASES
    for c in CASES:
        seen.update(_norm(q) for q in c[2:5])
    return seen


def main():
    seen, out = known_questions(), {}
    log = config.PROJECT_ROOT / "reports" / "chat_logs" / "chat_log.jsonl"
    if log.exists():
        for l in log.read_text().splitlines():
            try:
                r = json.loads(l)
            except Exception:  # noqa: BLE001
                continue
            k = _norm(r.get("message"))
            if k and k not in seen and len(k) > 3:
                out.setdefault(k, {"question": r["message"], "source": "chat_log", "route": (r.get("route") or {}).get("label"),
                                   "question_type": r.get("question_type"), "times_asked": 0})
                out[k]["times_asked"] += 1
    try:
        from src.backend.feedback_store import _rows as _load
        for f in _load():
            k = _norm(f.get("question"))
            if k and f.get("rating") == "down":
                row = out.setdefault(k, {"question": f["question"], "source": "feedback", "times_asked": 1})
                row.setdefault("thumbs_down", []).append({"reason": f.get("reason"), "comment": f.get("comment")})
    except Exception as e:  # noqa: BLE001
        print(f"feedback store unavailable: {e}")
    rows = sorted(out.values(), key=lambda r: (-len(r.get("thumbs_down", [])), -r["times_asked"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(json.dumps({**r, "expected_behavior": "", "checks": {}}, ensure_ascii=False) for r in rows) + "\n")
    print(f"{len(rows)} new real questions ({sum(bool(r.get('thumbs_down')) for r in rows)} with 👎) -> {OUT}")


if __name__ == "__main__":
    main()
