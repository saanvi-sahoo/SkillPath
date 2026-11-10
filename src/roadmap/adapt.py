"""
Adaptive 30-day roadmap (E38, review 3 §5: "make the roadmap adaptive, not just valid").

Each day carries a status: not_started | completed | needs_revision | skipped | already_known.
`adapt_roadmap(roadmap, progress, today)` rebalances the REMAINING days instead of insisting on the original timetable:

  * completed days are kept as history (same day number)
  * a needs_revision day gets an easier revision day immediately (smaller steps + simpler practice), then the queue resumes
  * missed days (not_started / skipped before `today`) move forward in their original order
  * already_known days are removed, which pulls later topics forward
  * if the remaining work no longer fits in the days left, weekly-review days are dropped first, then the lowest-priority
    learning days are deferred (listed, never silently lost); the capstone days are always kept last
  * the daily minute budget never changes

Metric (review 3 §5, §10): roadmap task completion rate = completed days / days due so far.
"""
from __future__ import annotations

from typing import Dict, List

STATUSES = ("not_started", "completed", "needs_revision", "skipped", "already_known")
TOTAL_DAYS = 30


def _revision_day(d: Dict, minutes: int) -> Dict:
    return {"kind": "revision", "skill": d.get("skill"), "topic": f"Revision: {d.get('topic')}",
            "prerequisite": d.get("prerequisite", ""),
            "learning_task": f"Re-learn '{d.get('topic')}' with a different, simpler resource and split it into two smaller steps; "
                             "write down exactly which part is unclear",
            "practice_task": f"An easier version first, then retry: {d.get('practice_task')}",
            "estimated_minutes": minutes, "completion_criteria": f"You can do the original task: {d.get('completion_criteria')}",
            "resources": d.get("resources", []), "status": "not_started", "adapted": "revision added"}


def completion_rate(progress: Dict[int, str], today: int) -> Dict:
    due = [d for d in range(1, max(1, today))]
    done = sum(progress.get(d) == "completed" for d in due)
    return {"days_due": len(due), "completed": done, "rate": round(done / len(due), 3) if due else None,
            "needs_revision": sum(progress.get(d) == "needs_revision" for d in due)}


def adapt_roadmap(roadmap: Dict, progress: Dict[int, str], today: int) -> Dict:
    """Return a new roadmap dict; `progress` maps day number -> status; `today` is the day the student is on (1-30)."""
    progress = {int(k): v for k, v in (progress or {}).items() if v in STATUSES}
    today = max(1, min(int(today), TOTAL_DAYS))
    minutes = int(roadmap.get("daily_minutes") or 60)
    days = [dict(d) for d in roadmap["days"]]
    changes: List[str] = []
    history = [{**d, "status": "completed"} for d in days if progress.get(d["day"]) == "completed" and d["day"] < today]
    known = [d for d in days if progress.get(d["day"]) == "already_known"]
    if known:
        changes.append(f"Removed {len(known)} day(s) you already know: " + ", ".join(sorted({str(d['topic']) for d in known})[:5]))
    queue: List[Dict] = []
    for d in days:
        st = progress.get(d["day"], "not_started")
        if st == "needs_revision":
            queue.append(_revision_day(d, minutes))
            changes.append(f"Added a revision day for '{d['topic']}' (day {d['day']} was hard).")
    missed = [d for d in days if d["day"] < today and progress.get(d["day"], "not_started") in ("not_started", "skipped")]
    if missed:
        changes.append(f"Moved {len(missed)} missed day(s) forward: days " + ", ".join(str(d['day']) for d in missed[:8]))
    future = [d for d in days if d["day"] >= today and progress.get(d["day"]) not in ("completed", "already_known", "needs_revision")]
    queue += [{**d, "status": "not_started"} for d in missed if d["kind"] != "review"] + [{**d, "status": "not_started"} for d in future]
    projects = [d for d in queue if d["kind"] == "project"]
    queue = [d for d in queue if d["kind"] != "project"]
    slots = TOTAL_DAYS - today + 1 - len(projects)
    deferred: List[Dict] = []
    if len(queue) > slots:
        reviews = [d for d in queue if d["kind"] == "review"]
        drop = min(len(reviews), len(queue) - slots)
        if drop:
            ids = {id(d) for d in reviews[-drop:]}
            queue = [d for d in queue if id(d) not in ids]
            changes.append(f"Dropped {drop} weekly review day(s) to make room.")
    if len(queue) > slots:
        # defer the lowest-priority skill = the last skill in the original priority order, from the end of the queue
        order = list(dict.fromkeys(d["skill"] for d in days if d["kind"] == "learn"))
        while len(queue) > slots:
            victim_skill = next((s for s in reversed(order) if any(q["skill"] == s and q["kind"] == "learn" for q in queue)), None)
            if victim_skill is None:
                deferred.append(queue.pop())
                continue
            idx = max(i for i, q in enumerate(queue) if q["skill"] == victim_skill and q["kind"] == "learn")
            deferred.append(queue.pop(idx))
        changes.append(f"Deferred {len(deferred)} lower-priority task(s) to after day 30: "
                       + ", ".join(sorted({f"{d['skill']}: {d['topic']}" for d in deferred})[:4]))
    scheduled = queue + projects
    for i, d in enumerate(scheduled):
        d["day"] = today + i
    spare = TOTAL_DAYS - (today - 1) - len(scheduled)
    if spare > 0:
        changes.append(f"The plan now finishes {spare} day(s) early; use them for extra practice on the capstone.")
    if not changes:
        changes.append("You're on track: no changes needed.")
    return {**roadmap, "days": history + scheduled, "deferred_tasks": deferred, "adapted_from_day": today,
            "changes": changes, "progress": completion_rate(progress, today),
            "validation": {**roadmap.get("validation", {}), "adapted": True,
                           "max_minutes": max((d.get("estimated_minutes") or 0) for d in scheduled) if scheduled else 0}}


def save_progress(user_id, roadmap: Dict) -> None:
    """Store a progress summary in the student's analysed profile so the advisor can answer 'how am I doing?'."""
    import json
    from src.rag import config
    path = config.memory_path(user_id)
    if not path.exists() or not roadmap.get("progress"):
        return
    try:
        mem = json.loads(path.read_text(encoding="utf-8"))
        p = roadmap["progress"]
        mem["roadmap_progress"] = {**p, "on_day": roadmap.get("adapted_from_day"), "target_role": roadmap.get("target_role"),
                                   "revising": [d["topic"] for d in roadmap["days"] if d.get("kind") == "revision"][:5],
                                   "deferred": [f"{d['skill']}: {d['topic']}" for d in roadmap.get("deferred_tasks", [])][:5]}
        path.write_text(json.dumps(mem, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001 - progress tracking must never break the page
        print(f"[roadmap] progress not saved: {e}")
