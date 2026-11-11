"""
End-to-end task success (E38, review 3 §10: "test whether a student could complete a meaningful journey").

Each journey is a LIVE multi-turn conversation (src/eval/heldout/journeys_v1.jsonl, 10 journeys, frozen in 167fe13):
the advisor's own earlier answers become the history of the next turn, exactly as in the app. Every turn has checks;
a journey succeeds only if every turn passes. Same model for all arms; arms run the same journey independently.

  LLM_PROVIDER=api CHAT_MODEL=gemini-3.1-flash-lite python -m src.eval.journey_eval --versions v7 v7+e38 v8+e38
  python -m src.eval.journey_eval --report reports/heldout/journeys_<ts>.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from src.eval.heldout_eval import NO_PROFILE_UID, OUT, _body, arm, persona_facts, score

SET = Path(__file__).parent / "heldout" / "journeys_v1.jsonl"
SETS = {"v1": SET, "v2": Path(__file__).parent / "heldout" / "journeys_v2.jsonl"}  # v2: fresh, frozen for the final validation


def _items(text: str) -> List[str]:
    from src.backend.conversation_state import list_items
    return list_items(text)


def run_journey(j: Dict, version: str, facts: Dict, expect_model: str, sleep_s: float) -> Dict:
    from src.backend.chatbot import answer, load_memory
    from src.backend.scope_router import route
    base, e38 = arm(version)
    uid = j.get("user") or NO_PROFILE_UID
    mem = load_memory(j["user"]) if j.get("user") else None
    hist: List[Dict] = []
    answers: List[str] = []
    turns = []
    for i, t in enumerate(j["turns"]):
        hist.append({"role": "user", "content": t["q"]})
        for attempt in range(3):
            res = answer(hist, system_version=base, route_override=route(t["q"], hist[:-1]), user_id=uid, e38=e38)
            if not res.get("error") and (res.get("model") is None or not expect_model or res.get("model") == expect_model):
                break
            time.sleep(45 * (attempt + 1))
        items = {}
        for (ti, n) in [tuple(t["checks"]["mentions_item_of_turn"])] if "mentions_item_of_turn" in t["checks"] else []:
            lst = _items(answers[ti]) if ti < len(answers) else []
            if 0 < n <= len(lst):
                items[(ti, n)] = lst[n - 1]
        case = {"id": f"{j['id']}-t{i + 1}", "expect": t.get("expect", "allow"), "checks": t["checks"], "_items": items}
        sc = score(case, res["text"], res.get("hits", []), facts.get(j.get("user") or ""), mem, res.get("intent"))
        turns.append({"turn": i + 1, "q": t["q"], "answer": res["text"], "passed": sc["passed"],
                      "failed": [k for k, v in sc["checks"].items() if v is False], "item_expected": list(items.values()),
                      "model": res.get("model"), "latency_ms": res.get("latency_ms"), "state": res.get("state"),
                      "tokens": (res.get("usage") or {}).get("total_tokens")})
        answers.append(res["text"])
        hist.append({"role": "assistant", "content": res["text"]})
        print(f"[{version}] {j['id']} t{i + 1} passed={sc['passed']} {turns[-1]['failed'] or ''} model={res.get('model')}", flush=True)
        time.sleep(sleep_s if res.get("model") else 0.2)
    return {"id": j["id"], "goal": j["goal"], "version": version, "user": j.get("user"), "turns": turns,
            "success": all(t["passed"] for t in turns), "turn_pass_rate": round(sum(t["passed"] for t in turns) / len(turns), 3)}


def summarise(rep: Dict) -> Dict:
    out = {}
    for v in rep["versions"]:
        allr = [r for r in rep["rows"] if r["version"] == v]
        exp = rep.get("expect_model")  # same-model rule: a journey with any turn answered by a fallback model is excluded
        rs = [r for r in allr if not exp or all(t.get("model") in (exp, None) for t in r["turns"])]
        if not rs:
            continue
        lat = sorted(t["latency_ms"] for r in rs for t in r["turns"] if t.get("latency_ms"))
        out[v] = {"journeys": len(rs), "excluded_model_fallback": len(allr) - len(rs), "task_success": round(sum(r["success"] for r in rs) / len(rs), 3),
                  "turn_pass_rate": round(sum(t["passed"] for r in rs for t in r["turns"]) / sum(len(r["turns"]) for r in rs), 3),
                  "p95_latency_ms": lat[min(len(lat) - 1, int(round(0.95 * (len(lat) - 1))))] if lat else None,
                  "avg_latency_ms": round(sum(lat) / len(lat)) if lat else None,
                  "models": sorted({str(t["model"]) for r in rs for t in r["turns"]}),
                  "failed_turns": [f"{r['id']} t{t['turn']}: {', '.join(t['failed'])}" for r in rs for t in r["turns"] if not t["passed"]]}
    return out


def rescore(rep: Dict) -> None:
    """Re-run each turn's checks on the stored answers (scorer fixes apply to every arm alike)."""
    from src.backend.chatbot import load_memory
    js = {j["id"]: j for j in (json.loads(l) for l in SETS[rep.get("set", "v1")].read_text().splitlines() if l.strip())}
    facts = persona_facts() if any(r.get("user") for r in rep["rows"]) else {}
    for r in rep["rows"]:
        j = js[r["id"]]
        mem = load_memory(r["user"]) if r.get("user") else None
        answers = [t["answer"] for t in r["turns"]]
        for i, t in enumerate(r["turns"]):
            spec = j["turns"][i]
            items = {}
            if "mentions_item_of_turn" in spec["checks"]:
                ti, n = spec["checks"]["mentions_item_of_turn"]
                lst = _items(answers[ti]) if ti < len(answers) else []
                if 0 < n <= len(lst):
                    items[(ti, n)] = lst[n - 1]
            case = {"id": f"{r['id']}-t{i + 1}", "expect": spec.get("expect", "allow"), "checks": spec["checks"], "_items": items}
            sc = score(case, t["answer"], [], facts.get(r.get("user") or ""), mem, None)
            t["passed"], t["failed"] = sc["passed"], [k for k, v in sc["checks"].items() if v is False]
        r["success"] = all(t["passed"] for t in r["turns"])
        r["turn_pass_rate"] = round(sum(t["passed"] for t in r["turns"]) / len(r["turns"]), 3)


def write(rep: Dict, path: Path) -> str:
    if os.getenv("RESCORE", "true") == "true":
        rescore(rep)
    rep["summary"] = summarise(rep)
    path.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
    S = rep["summary"]
    vs = [v for v in rep["versions"] if v in S]
    L = [f"# End-to-end journeys ({rep['ts']})", "", f"Live conversations (`journeys_{rep.get('set', 'v1')}.jsonl`). A journey succeeds only if every turn passes.", "",
         "| Metric | " + " | ".join(vs) + " |", "|---|" + "---|" * len(vs)]
    for m in ("journeys", "excluded_model_fallback", "task_success", "turn_pass_rate", "avg_latency_ms", "p95_latency_ms"):
        L.append(f"| {m} | " + " | ".join(str(S[v][m]) for v in vs) + " |")
    L += ["", "| Journey | " + " | ".join(vs) + " |", "|---|" + "---|" * len(vs)]
    for jid in sorted({r["id"] for r in rep["rows"]}):
        cells = []
        for v in vs:
            r = next((x for x in rep["rows"] if x["id"] == jid and x["version"] == v), None)
            cells.append("-" if not r else ("✓" if r["success"] else "✗ " + ", ".join(f"t{t['turn']}" for t in r["turns"] if not t["passed"])))
        L.append(f"| {jid} | " + " | ".join(cells) + " |")
    L += ["", "Failed turns:", ""] + [f"- **{v}**: " + ("; ".join(S[v]["failed_turns"]) or "none") for v in vs]
    md = "\n".join(L) + "\n"
    path.with_suffix(".md").write_text(md)
    return md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", nargs="+", default=["v7", "v7+e38"])
    ap.add_argument("--expect-model", default="")
    ap.add_argument("--sleep", type=float, default=3.0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--resume")
    ap.add_argument("--report")
    ap.add_argument("--tag", default="")
    ap.add_argument("--set", default="v1", choices=sorted(SETS))
    a = ap.parse_args()
    if a.report:
        p = Path(a.report)
        print(write(json.loads(p.read_text()), p))
        return
    global SET
    SET = SETS[a.set]
    js = [json.loads(l) for l in SET.read_text().splitlines() if l.strip()]
    if a.ids:
        js = [j for j in js if j["id"] in a.ids]
    if a.resume:
        path = Path(a.resume)
        rep = json.loads(path.read_text())
        SET = SETS[rep.get("set", "v1")]  # resume must use the run's own journey set
        js = [json.loads(l) for l in SET.read_text().splitlines() if l.strip()]
        if a.ids:
            js = [j for j in js if j["id"] in a.ids]
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = OUT / f"journeys_{a.tag + '_' if a.tag else ''}{ts}_p{os.getpid()}.json"
        rep = {"ts": ts, "versions": a.versions, "set": a.set, "rows": [], "model_configured": os.getenv("CHAT_MODEL", "default"),
               "provider": os.getenv("LLM_PROVIDER"), "expect_model": a.expect_model}
    facts = persona_facts()
    done = {(r["id"], r["version"]) for r in rep["rows"]}
    jobs = [(j, v) for j in js for v in rep["versions"] if (j["id"], v) not in done]

    def one(jv):
        r = run_journey(jv[0], jv[1], facts, a.expect_model, a.sleep)
        rep["rows"].append(r)
        path.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(one, jobs))
    print(write(rep, path))


if __name__ == "__main__":
    main()
