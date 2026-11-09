"""
Feedback learning ("recurrence learning", docs/feedback_learning.md).

Every 👍/👎 is stored with the question's embedding. When a new question arrives, similar past feedback is
retrieved and turned into guidance for prompt v5:
  * 👍 answers to similar questions  -> "answers users rated helpful" (style/content to follow)
  * 👎 with reasons / comments        -> "avoid / must include" instructions; repeated complaints weigh more
  * "wrongly refused" reported by >= 2 different users -> new career/study anchor for the scope router

Storage: MongoDB Atlas collection `feedback_v1` when MONGODB_URI is set (survives redeploys; plain collection,
no search index needed: similarity is computed in Python over the small feedback set), else a local JSONL file.
Privacy: feedback on profile-specific questions is only reused for the same user; API keys are never stored.

E37 (review 2 §8): user feedback can itself be wrong, so it never changes answers automatically. Every new row is
stored with status "pending"; only rows a teammate approves (`python -m src.backend.feedback_store --review`) are
used as guidance. Approved corrections are also exported as development test cases, never into the held-out set.
FEEDBACK_REQUIRE_APPROVAL=false restores the old immediate behaviour (used only by isolated experiments).
"""
from __future__ import annotations

import argparse
import os

import json
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np

from src.rag import config

LOCAL_FILE = config.PROJECT_ROOT / "reports" / "chat_logs" / "feedback.jsonl"
COLLECTION = "feedback_v1"
SIM_THRESHOLD = 0.75      # how similar a past question must be to count as "the same kind of question"
ANCHOR_MIN_USERS = 2      # distinct users needed before a "wrongly refused" question becomes a router anchor
REQUIRE_APPROVAL = os.getenv("FEEDBACK_REQUIRE_APPROVAL", "true").lower() == "true"
REASONS = {
    "not_answered": "did not answer the actual question",
    "inaccurate": "was inaccurate or wrong",
    "too_long": "was too long / unfocused",
    "no_sources": "lacked sources or specifics",
    "wrong_refusal": "wrongly refused a career/study question",
    "other": "was unhelpful",
}

_lock = threading.Lock()
_cache = {"t": 0.0, "rows": None}


def _mongo():
    if not config.MONGODB_URI:
        return None
    from src.rag.retriever import atlas_degraded
    if atlas_degraded():  # E32: Atlas unreachable -> local feedback file (no timeouts per click)
        return None
    try:
        from src.rag.vector_store import _mongo_client
        return _mongo_client()[config.MONGODB_DB][COLLECTION]
    except Exception:  # noqa: BLE001
        return None


def _is_profile_question(q: str) -> bool:
    from src.backend.question_profile import profile_question
    return profile_question(q)["type"] == "profile_fact"


def record(question: str, answer: str, rating: str, user_id: str, reason: str = "", comment: str = "",
           route: Optional[Dict] = None, prompt_version: str = "") -> Dict:
    from src.rag.embedder import embed_symmetric

    row = {"ts": datetime.now(timezone.utc).isoformat(), "question": question[:1000], "answer": answer[:3000],
           "rating": rating, "reason": reason, "comment": comment[:500], "user_id": user_id,
           "route_label": (route or {}).get("label"), "prompt_version": prompt_version,
           "profile_specific": _is_profile_question(question), "status": "pending",
           "q_vec": [round(float(x), 5) for x in embed_symmetric(question)]}
    coll = _mongo()
    with _lock:
        if coll is not None:
            try:
                coll.insert_one(dict(row))
            except Exception as e:  # noqa: BLE001
                print(f"[feedback] Atlas write failed, using local file: {e}")
                coll = None
        if coll is None:
            LOCAL_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(LOCAL_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        _cache["t"] = 0.0  # invalidate
    return row


def _rows(ttl_s: float = 30.0) -> List[Dict]:
    if _cache["rows"] is not None and time.time() - _cache["t"] < ttl_s:
        return _cache["rows"]
    rows: List[Dict] = []
    coll = _mongo()
    if coll is not None:
        try:
            rows = list(coll.find({"q_vec": {"$exists": True}}, {"_id": 0}).sort("ts", -1).limit(5000))
        except Exception:  # noqa: BLE001
            rows = []
    if not rows and LOCAL_FILE.exists():
        for line in LOCAL_FILE.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if r.get("q_vec"):
                    rows.append(r)
            except json.JSONDecodeError:
                continue
    _cache.update(t=time.time(), rows=rows)
    return rows


def _usable(r: Dict) -> bool:
    return (not REQUIRE_APPROVAL) or r.get("status") == "approved"


def similar_feedback(question: str, user_id: str, k: int = 6) -> List[Dict]:
    rows = [r for r in _rows() if _usable(r)]
    if not rows:
        return []
    from src.rag.embedder import embed_symmetric

    qv = embed_symmetric(question)
    mat = np.asarray([r["q_vec"] for r in rows], dtype=np.float32)
    sims = mat @ qv
    out = []
    for i in np.argsort(-sims)[: k * 4]:
        r = rows[i]
        if sims[i] < SIM_THRESHOLD:
            break
        if r.get("profile_specific") and r.get("user_id") != user_id:
            continue  # someone else's profile-specific Q&A is never reused
        out.append({**{k2: v for k2, v in r.items() if k2 != "q_vec"}, "sim": round(float(sims[i]), 3)})
        if len(out) >= k:
            break
    return out


def learned_guidance(question: str, user_id: str) -> Dict:
    """Prompt-ready guidance from similar past feedback (empty strings when there is none)."""
    sim = similar_feedback(question, user_id)
    good = [r for r in sim if r["rating"] == "up"][:2]
    bad = [r for r in sim if r["rating"] == "down"]
    lines = []
    if bad:
        counts: Dict[str, int] = {}
        for r in bad:
            counts[r.get("reason") or "other"] = counts.get(r.get("reason") or "other", 0) + 1
        for reason, n in sorted(counts.items(), key=lambda x: -x[1]):
            strength = "REPEATEDLY " if n >= 2 else ""
            lines.append(f"- Answers to similar questions were {strength}rated unhelpful because they "
                         f"{REASONS.get(reason, REASONS['other'])} ({n}x). Avoid that.")
        for r in bad:
            if r.get("comment"):
                lines.append(f"- A user asking \"{r['question'][:120]}\" said a good answer should: {r['comment'][:200]}")
    examples = "\n\n".join(f"Question: {r['question'][:200]}\nHelpful answer (rated 👍): {r['answer'][:700]}" for r in good)
    return {"avoid": "\n".join(lines), "examples": examples, "n_similar": len(sim), "n_good": len(good), "n_bad": len(bad)}


def learned_scope_anchors() -> List[str]:
    """Questions that >= ANCHOR_MIN_USERS distinct users reported as wrongly refused -> career_study anchors."""
    users: Dict[str, set] = {}
    for r in _rows():
        if r.get("rating") == "down" and r.get("reason") == "wrong_refusal" and _usable(r):
            users.setdefault(r["question"].strip(), set()).add(r.get("user_id"))
    return [q for q, u in users.items() if len(u) >= ANCHOR_MIN_USERS]


def summary() -> Dict:
    rows = _rows(ttl_s=0)
    by_reason: Dict[str, int] = {}
    for r in rows:
        if r["rating"] == "down":
            by_reason[r.get("reason") or "other"] = by_reason.get(r.get("reason") or "other", 0) + 1
    return {"total": len(rows), "up": sum(r["rating"] == "up" for r in rows), "down": sum(r["rating"] == "down" for r in rows),
            "pending": sum(r.get("status", "pending") == "pending" for r in rows),
            "approved": sum(r.get("status") == "approved" for r in rows), "rejected": sum(r.get("status") == "rejected" for r in rows),
            "down_by_reason": by_reason, "learned_anchors": learned_scope_anchors()}


def set_status(ts: str, question: str, status: str) -> bool:
    """Approve or reject one feedback row (identified by its timestamp + question)."""
    coll = _mongo()
    if coll is not None:
        res = coll.update_one({"ts": ts, "question": question}, {"$set": {"status": status}})
        _cache["t"] = 0.0
        return res.modified_count > 0
    if not LOCAL_FILE.exists():
        return False
    rows, hit = [], False
    for line in LOCAL_FILE.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("ts") == ts and r.get("question") == question:
            r["status"], hit = status, True
        rows.append(json.dumps(r, ensure_ascii=False))
    LOCAL_FILE.write_text("\n".join(rows) + "\n", encoding="utf-8")
    _cache["t"] = 0.0
    return hit


def export_dev_cases(path) -> int:
    """Approved 👎 corrections -> development test cases (never the held-out set)."""
    rows = [r for r in _rows(ttl_s=0) if r.get("status") == "approved" and r["rating"] == "down" and r.get("comment")]
    with open(path, "w", encoding="utf-8") as f:
        for i, r in enumerate(rows, 1):
            f.write(json.dumps({"id": f"fb{i:03d}", "category": "feedback", "user": None, "expect": "allow",
                                "messages": [{"role": "user", "content": r["question"]}],
                                "expected_behavior": r["comment"], "checks": {}, "source_ts": r["ts"]}, ensure_ascii=False) + "\n")
    return len(rows)


def review_cli():
    """Interactive review: approve (a) / reject (r) / skip (s) each pending row."""
    for r in [x for x in _rows(ttl_s=0) if x.get("status", "pending") == "pending"]:
        print("\n" + "-" * 70 + f"\n{r['ts']}  {r['rating']}  reason={r.get('reason')}\nQ: {r['question']}\nA: {r['answer'][:600]}\n"
              f"Comment: {r.get('comment') or '-'}")
        choice = input("approve (a) / reject (r) / skip (s) / quit (q)? ").strip().lower()
        if choice == "q":
            break
        if choice in ("a", "r"):
            set_status(r["ts"], r["question"], "approved" if choice == "a" else "rejected")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--export-dev", help="write approved corrections as development test cases (jsonl)")
    a = ap.parse_args()
    if a.review:
        review_cli()
    if a.export_dev:
        print(export_dev_cases(a.export_dev), "cases ->", a.export_dev)
    if a.summary or not (a.review or a.export_dev):
        print(json.dumps(summary(), indent=2))
