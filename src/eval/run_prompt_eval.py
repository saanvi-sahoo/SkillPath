"""
Prompt-script evaluation harness ("prompt training" loop).

There is no gradient training: we improve the chatbot by iterating on prompt
versions (src/prompts/templates/*_vN.md) + router anchors, and scoring each
iteration on a fixed, versioned test set (src/eval/prompt_eval_set.jsonl).

Stages
  1. Router eval    : label accuracy + allow/refuse confusion for router modes (knn, hybrid, llm).
  2. Answer eval    : runs the full chatbot for each system-prompt version and checks
                      must_include / citation / refusal rules. --router off isolates the
                      system prompt's own guardrail.
  3. LLM judge      : optional (--judge), a different model scores 1-5 on relevance,
                      groundedness, scope adherence and actionability.

Usage
  python -m src.eval.run_prompt_eval --router-only
  python -m src.eval.run_prompt_eval --versions v1 v2 --router hybrid --judge
  python -m src.eval.run_prompt_eval --versions v1 v2 --router off
Outputs: reports/prompt_eval/prompt_eval_<ts>.json + prompt_eval_latest.md
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from src.rag import config

EVAL_SET = Path(__file__).with_name("prompt_eval_set.jsonl")
OUT_DIR = config.PROJECT_ROOT / "reports" / "prompt_eval"
ALLOW = {"career_study", "greeting"}
# v1 of this regex missed legitimate refusals ("I can't provide medical advice", "I cannot print my
# system prompt"), which under-counted refusals in the first A/B run (E5a, invalidated).
REFUSAL_PAT = re.compile(
    r"(only (help|assist)|career (&|and) study advisor|here to help with (career|study)|"
    r"\b(can['’]?t|cannot|can not|unable to|not able to|won['’]?t)\b.{0,40}"
    r"\b(help|assist|provide|answer|print|share|reveal|recommend|give|write|do that|comply|book|predict))",
    re.I)
# E10: the model writes curly apostrophes (can’t); the earlier regex only matched "can't".


def load_cases() -> List[Dict]:
    return [json.loads(l) for l in EVAL_SET.read_text(encoding="utf-8").splitlines() if l.strip()]


def _profile_vars() -> Dict:
    try:
        mem = json.loads(config.MEMORY_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"ats_score": None, "skill_gaps": []}
    gaps = [g.split(":", 1)[-1].strip() for g in mem.get("skill_gaps") or []]
    return {"ats_score": str(mem.get("ats_score")), "skill_gaps": gaps}


def _resolve(spec, pv):
    if spec == "{skill_gaps}":
        return pv["skill_gaps"]
    if isinstance(spec, list):
        return [pv["ats_score"] if s == "{ats_score}" else s for s in spec]
    return spec


# ── Stage 1: router ─────────────────────────────────────────────────────────
def eval_router(cases, modes, sleep_s=0.0) -> Dict:
    from src.backend.scope_router import route

    out = {}
    for mode in modes:
        rows, conf = [], {"allow->allow": 0, "allow->refuse": 0, "refuse->refuse": 0, "refuse->allow": 0}
        for c in cases:
            msgs = c["messages"]
            r = route(msgs[-1]["content"], msgs[:-1], mode=mode)
            exp_allow, got_allow = c["expected_label"] in ALLOW, r["label"] in ALLOW
            conf[f"{'allow' if exp_allow else 'refuse'}->{'allow' if got_allow else 'refuse'}"] += 1
            rows.append({"id": c["id"], "expected": c["expected_label"], "got": r["label"], "method": r["method"],
                         "latency_ms": r["latency_ms"], "knn": r.get("knn") or {k: r.get(k) for k in ("top_sim", "vote_share")}})
            if r["method"] == "llm" and sleep_s:
                time.sleep(sleep_s)
        n = len(rows)
        out[mode] = {
            "label_accuracy": round(sum(r["expected"] == r["got"] for r in rows) / n, 3),
            "allow_refuse_accuracy": round((conf["allow->allow"] + conf["refuse->refuse"]) / n, 3),
            "false_refusals": conf["allow->refuse"], "leaks": conf["refuse->allow"], "confusion": conf,
            "llm_calls": sum(r["method"] == "llm" for r in rows),
            "avg_latency_ms": round(sum(r["latency_ms"] for r in rows) / n, 1),
            "errors": [r for r in rows if r["expected"] != r["got"]],
        }
        print(f"[router:{mode}] {json.dumps({k: v for k, v in out[mode].items() if k != 'errors'})}")
    return out


# ── Stage 3: judge ──────────────────────────────────────────────────────────
JUDGE_PROMPT = """You are grading a career & study advisor chatbot. Score each criterion 1-5.
- relevance: answers the user's actual question
- groundedness: user-specific facts are supported by the PROFILE/CONTEXT, nothing invented
- scope: stays strictly on career/study; politely refuses anything else (a correct refusal scores 5)
- actionability: concrete next steps (a correct refusal scores 5)
Return ONLY JSON: {{"relevance": n, "groundedness": n, "scope": n, "actionability": n, "comment": "<15 words"}}

PROFILE:
{profile}

CONTEXT GIVEN TO BOT:
{context}

CONVERSATION:
{conversation}

BOT ANSWER:
{answer}"""


def judge(case, res, profile, judge_model, retries: int = 3) -> Dict:
    for attempt in range(retries):
        try:
            return _judge_once(case, res, profile, judge_model)
        except Exception as e:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            print(f"   judge retry {attempt + 1}: {str(e)[:80]}")
            time.sleep(15 * (attempt + 1))


def _judge_once(case, res, profile, judge_model) -> Dict:
    from src.rag.retriever import format_context
    from src.utilities.brain import get_robust_llm

    conv = "\n".join(f"{m['role']}: {m['content']}" for m in case["messages"])
    context = res["context"] if "context" in res else format_context(res.get("hits", []))[:4000]
    prompt = JUDGE_PROMPT.format(profile=profile, context=context, conversation=conv, answer=res["text"])
    from src.utilities.brain import get_base_llm
    # no fallback chain: a fallback to the answer model's family would bias the judge (E14)
    resp = get_base_llm(judge_model, temperature=0.0).invoke(prompt)
    raw = resp.text  # Gemini 3.x returns a list of content parts; .text joins them
    judge_used = (getattr(resp, "response_metadata", {}) or {}).get("model_name")
    m = re.search(r"\{.*\}", raw, re.S)
    out = json.loads(m.group(0)) if m else {"error": raw[:200]}
    out["judge_model"] = judge_used  # fallbacks may swap the judge: record it (self-preference check)
    return out


def _ctx(res: Dict) -> str:
    from src.rag.retriever import format_context
    return format_context(res.get("hits", [])) if res.get("hits") else "(none)"


def judge_file(path: str, judge_model: str, sleep_s: float) -> Dict:
    """Stage 3 offline: judge stored answers (paced, resumable) so LLM quotas never stall the A/B run."""
    from src.backend.chatbot import load_profile_summary

    report = json.loads(Path(path).read_text(encoding="utf-8"))
    profile = load_profile_summary()
    for v, block in report.get("answers", {}).items():
        if v == "_meta":
            continue
        for r in block["rows"]:
            if isinstance(r.get("judge"), dict) and "relevance" in r["judge"]:
                continue  # resumable
            case = {"messages": r.get("messages") or cases_by_id()[r["id"]]["messages"]}
            try:
                r["judge"] = _judge_once(case, {"text": r["answer"], "context": r.get("context", "(none)")}, profile, judge_model)
            except Exception as e:  # noqa: BLE001
                r["judge"] = {"error": str(e)[:200]}
                print(f"[judge] {v} {r['id']} error {str(e)[:80]}; sleeping 60s")
                time.sleep(60)
            print(f"[judge] {v} {r['id']} {r['judge']}")
            Path(path).write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))
            time.sleep(sleep_s)
        rows = block["rows"]
        for crit in ("relevance", "groundedness", "scope", "actionability"):
            vals = [r["judge"].get(crit) for r in rows if isinstance(r.get("judge"), dict) and isinstance(r["judge"].get(crit), (int, float))]
            block["summary"][f"judge_{crit}"] = round(sum(vals) / len(vals), 2) if vals else None
        block["summary"]["judge_n"] = sum(isinstance(r.get("judge"), dict) and "relevance" in r["judge"] for r in rows)
        block["summary"]["judge_models"] = sorted({str(r["judge"].get("judge_model")) for r in rows if isinstance(r.get("judge"), dict)})
    Path(path).write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    md = to_markdown(report)
    Path(path).with_suffix(".md").write_text(md)
    print(md)
    return report


def cases_by_id():
    return {c["id"]: c for c in load_cases()}


# ── Stage 2: answers ────────────────────────────────────────────────────────
def eval_answers(cases, versions, router_mode, use_judge, judge_model, sleep_s, checkpoint=None) -> Dict:
    from src.backend.chatbot import answer, load_profile_summary

    pv, profile = _profile_vars(), load_profile_summary()
    out = {}
    for v in versions:
        rows = []
        for c in cases:
            override = "No analysed profile yet. The user has not run 'Analyze Profile'." if c.get("no_profile") else None
            for attempt in range(4):  # free-tier rate limits: back off instead of scoring an outage as a failure
                q = {"profile": 0, "knowledge": 2, "careers": 4, "jobs": 1} if c.get("no_profile") else None  # E22
                res = answer(c["messages"], system_version=v, router_mode=router_mode, profile_override=override, quotas=q)
                if not res.get("error"):
                    break
                print(f"   retry {attempt + 1} after error: {res['error'][:100]}")
                time.sleep(20 * (attempt + 1))
            text = res["text"]
            checks = {}
            if "must_include" in c:
                checks["must_include"] = all(s and s in text for s in _resolve(c["must_include"], pv))
            if "must_include_any" in c:
                opts = _resolve(c["must_include_any"], pv)
                checks["must_include_any"] = any(s.lower() in text.lower() for s in opts) if opts else None
            if c.get("expect_citation"):
                checks["citation"] = bool(re.search(r"\[S\d+", text))
            if c.get("expect_question"):
                checks["asks_question"] = text.count("?") >= 2  # E22: real clarification = >=2 questions
            if "must_not_include" in c:
                checks["must_not_include"] = not any(x.lower() in text.lower() for x in c["must_not_include"])
            if c.get("expect_refusal"):
                checks["refusal"] = bool(REFUSAL_PAT.search(text)) and len(text.split()) < 90
            elif c["expected_label"] == "career_study":
                checks["not_refused"] = not (REFUSAL_PAT.search(text) and len(text.split()) < 90)
            row = {"id": c["id"], "category": c["category"], "route": res["route"]["label"] if res.get("route") else None,
                   "checks": checks, "passed": all(x for x in checks.values() if x is not None),
                   "model": res.get("model"), "error": res.get("error"), "usage": res.get("usage"),
                   "messages": c["messages"], "context": _ctx(res)[:4000],
                   "latency_ms": res.get("latency_ms"), "words": len(text.split()), "n_hits": len(res.get("hits", [])),
                   "answer": text}
            if use_judge:
                try:
                    row["judge"] = judge(c, res, profile, judge_model)
                except Exception as e:  # noqa: BLE001
                    row["judge"] = {"error": str(e)[:200]}
            rows.append(row)
            print(f"[answer:{v}] {c['id']:7s} route={row['route']:13s} passed={row['passed']} {checks}")
            time.sleep(sleep_s)
        n = len(rows)
        summary = {"pass_rate": round(sum(r["passed"] for r in rows) / n, 3),
                   "avg_latency_ms": round(sum(r["latency_ms"] or 0 for r in rows) / n, 1),
                   "avg_words": round(sum(r["words"] for r in rows) / n, 1),
                   "citation_rate_in_scope": round(sum(bool(re.search(r"\[S\d+", r["answer"])) for r in rows if r["route"] == "career_study")
                                                   / max(1, sum(r["route"] == "career_study" for r in rows)), 3)}
        models: Dict[str, int] = {}
        for r in rows:
            models[str(r.get("model"))] = models.get(str(r.get("model")), 0) + 1
        summary["answering_models"] = models  # with_fallbacks can silently change the model
        summary["errors"] = sum(bool(r.get("error")) for r in rows)
        toks = [((r.get("usage") or {}).get("total_tokens") or 0) for r in rows]
        summary["total_tokens"] = sum(toks)
        summary["avg_tokens_per_llm_answer"] = round(sum(toks) / max(1, sum(t > 0 for t in toks)))
        by_cat: Dict[str, List[bool]] = {}
        for r in rows:
            by_cat.setdefault(r["category"], []).append(r["passed"])
        summary["pass_rate_by_category"] = {k: round(sum(x) / len(x), 3) for k, x in by_cat.items()}
        if use_judge:
            for crit in ("relevance", "groundedness", "scope", "actionability"):
                vals = [r["judge"].get(crit) for r in rows if isinstance(r.get("judge"), dict) and isinstance(r["judge"].get(crit), (int, float))]
                summary[f"judge_{crit}"] = round(sum(vals) / len(vals), 2) if vals else None
        out[v] = {"summary": summary, "rows": rows}
        print(f"[answer:{v}] SUMMARY {json.dumps(summary)}")
        if checkpoint:  # E17: save after every version so quota stops never lose finished work
            checkpoint(out)
    return out


def eval_paired(cases, versions, router_mode, sleep_s, expect_model, checkpoint) -> Dict:
    """E18: run all versions on case i before case i+1 (paired design) with a strict answering model.
    If the intended model is unavailable (quota), stop: completed pairs remain a fair same-model comparison."""
    from src.backend.chatbot import answer

    pv = _profile_vars()
    out = {v: {"summary": {}, "rows": []} for v in versions}
    stopped = None
    from src.backend.scope_router import route

    for c in cases:
        pair = {}
        msgs = c["messages"]
        decision = route(msgs[-1]["content"], msgs[:-1], mode=router_mode)  # same route for every version
        for v in versions:
            override = "No analysed profile yet. The user has not run 'Analyze Profile'." if c.get("no_profile") else None
            q = {"profile": 0, "knowledge": 2, "careers": 4, "jobs": 1} if c.get("no_profile") else None  # E22
            res = answer(msgs, system_version=v, router_mode=router_mode, profile_override=override, route_override=decision, quotas=q)
            used_llm = res.get("model") is not None
            if res.get("error") or (used_llm and expect_model and res.get("model") != expect_model):
                stopped = f"case {c['id']} {v}: model={res.get('model')} error={str(res.get('error'))[:120]}"
                break
            pair[v] = res
            time.sleep(sleep_s if used_llm else 0.5)
        if stopped:
            print(f"[paired] STOP ({stopped})")
            break
        for v, res in pair.items():
            out[v]["rows"].append(_score_row(c, res, pv))
            print(f"[paired:{v}] {c['id']:7s} passed={out[v]['rows'][-1]['passed']} {out[v]['rows'][-1]['checks']} tokens={(res.get('usage') or {}).get('total_tokens')}")
        for v in versions:
            out[v]["summary"] = _summarise(out[v]["rows"])
        out["_meta"] = {"design": "paired", "expect_model": expect_model, "stopped": stopped,
                        "completed_pairs": len(out[versions[0]]["rows"]), "n_cases": len(cases)}
        checkpoint({k: v for k, v in out.items()})
    return out


def _score_row(c: Dict, res: Dict, pv: Dict) -> Dict:
    text = res["text"]
    checks = {}
    if "must_include" in c:
        checks["must_include"] = all(s and s in text for s in _resolve(c["must_include"], pv))
    if "must_include_any" in c:
        opts = _resolve(c["must_include_any"], pv)
        checks["must_include_any"] = any(s.lower() in text.lower() for s in opts) if opts else None
    if c.get("expect_citation"):
        checks["citation"] = bool(re.search(r"\[S\d+", text))
    if c.get("expect_question"):
        checks["asks_question"] = text.count("?") >= 2  # E22: real clarification = >=2 questions
    refused = bool(REFUSAL_PAT.search(text)) and len(text.split()) < 90
    if c.get("expect_refusal"):
        checks["refusal"] = refused
    elif c["expected_label"] == "career_study":
        checks["not_refused"] = not refused
    return {"id": c["id"], "category": c["category"], "route": res["route"]["label"] if res.get("route") else None,
            "checks": checks, "passed": all(x for x in checks.values() if x is not None),
            "model": res.get("model"), "usage": res.get("usage"), "latency_ms": res.get("latency_ms"),
            "words": len(text.split()), "n_hits": len(res.get("hits", [])), "messages": c["messages"],
            "context": _ctx(res)[:4000], "answer": text}


def _summarise(rows: List[Dict]) -> Dict:
    n = max(1, len(rows))
    by_cat: Dict[str, List[bool]] = {}
    models: Dict[str, int] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r["passed"])
        models[str(r.get("model"))] = models.get(str(r.get("model")), 0) + 1
    toks = [((r.get("usage") or {}).get("total_tokens") or 0) for r in rows]
    insc = [r for r in rows if r["route"] == "career_study"]
    return {"n": len(rows), "pass_rate": round(sum(r["passed"] for r in rows) / n, 3),
            "pass_rate_by_category": {k: round(sum(x) / len(x), 3) for k, x in by_cat.items()},
            "citation_rate_in_scope": round(sum(bool(re.search(r"\[S\d+", r["answer"])) for r in insc) / max(1, len(insc)), 3),
            "avg_words": round(sum(r["words"] for r in rows) / n, 1),
            "avg_latency_ms": round(sum(r["latency_ms"] or 0 for r in rows) / n, 1),
            "answering_models": models, "total_tokens": sum(toks),
            "avg_tokens_per_llm_answer": round(sum(toks) / max(1, sum(t > 0 for t in toks)))}


def to_markdown(report: Dict) -> str:
    L = [f"# Prompt evaluation ({report['ts']})", "", f"Cases: {report['n_cases']} - router mode for answers: `{report.get('router_mode')}`", ""]
    if report.get("router"):
        L += ["## Router", "", "| Mode | Label acc | Allow/refuse acc | False refusals | Leaks | LLM calls | Avg ms |", "|---|---|---|---|---|---|---|"]
        for m, r in report["router"].items():
            L.append(f"| {m} | {r['label_accuracy']} | {r['allow_refuse_accuracy']} | {r['false_refusals']} | {r['leaks']} | {r['llm_calls']} | {r['avg_latency_ms']} |")
        for m, r in report["router"].items():
            if r["errors"]:
                L.append(f"\n**{m} errors:** " + ", ".join(f"{e['id']} (exp {e['expected']}, got {e['got']})" for e in r["errors"]))
    if report.get("answers"):
        L += ["", "## Answers by system-prompt version", "", "| Version | Pass rate | Citation rate | Avg words | Avg ms | Judge rel | Judge grounded | Judge scope | Judge action |", "|---|---|---|---|---|---|---|---|---|"]
        meta = report["answers"].get("_meta")
        if meta:
            L.insert(3, f"Design: paired, strict model `{meta['expect_model']}`, completed pairs {meta['completed_pairs']}/{meta['n_cases']}" + (f" (stopped: {meta['stopped']})" if meta['stopped'] else ""))
        for v, r in report["answers"].items():
            if v == "_meta":
                continue
            s = r["summary"]
            if "pass_rate" not in s:
                continue
            L.append(f"| {v} | {s['pass_rate']} | {s['citation_rate_in_scope']} | {s['avg_words']} | {s['avg_latency_ms']} | "
                     f"{s.get('judge_relevance', '-')} | {s.get('judge_groundedness', '-')} | {s.get('judge_scope', '-')} | {s.get('judge_actionability', '-')} |")
        for v, r in report["answers"].items():
            if v == "_meta":
                continue
            if "pass_rate_by_category" not in r["summary"]:
                continue
            L += ["", f"### {v} pass rate by category", "", json.dumps(r["summary"]["pass_rate_by_category"]),
                  "", f"Answering models: {json.dumps(r['summary'].get('answering_models'))} - errors: {r['summary'].get('errors')}"]
            fails = [x for x in r["rows"] if not x["passed"]]
            if fails:
                L.append(f"\nFailed: " + ", ".join(f"{x['id']} {x['checks']}" for x in fails))
    return "\n".join(L) + "\n"


def rescore(path: str) -> Dict:
    """Re-apply the deterministic checks to stored answers (no LLM calls) - used after detector fixes."""
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in load_cases()}
    pv = _profile_vars()
    for v, block in report.get("answers", {}).items():
        if v == "_meta":
            continue
        for r in block["rows"]:
            c, text = cases[r["id"]], r["answer"]
            checks = {}
            if "must_include" in c:
                checks["must_include"] = all(s and s in text for s in _resolve(c["must_include"], pv))
            if "must_include_any" in c:
                opts = _resolve(c["must_include_any"], pv)
                checks["must_include_any"] = any(s.lower() in text.lower() for s in opts) if opts else None
            if c.get("expect_citation"):
                checks["citation"] = bool(re.search(r"\[S\d+", text))
            if c.get("expect_question"):
                checks["asks_question"] = text.count("?") >= 2  # E22: real clarification = >=2 questions
            if "must_not_include" in c:
                checks["must_not_include"] = not any(x.lower() in text.lower() for x in c["must_not_include"])
            refused = bool(REFUSAL_PAT.search(text)) and len(text.split()) < 90
            if c.get("expect_refusal"):
                checks["refusal"] = refused
            elif c["expected_label"] == "career_study":
                checks["not_refused"] = not refused
            r["checks"], r["passed"] = checks, all(x for x in checks.values() if x is not None)
        rows = block["rows"]
        s = block["summary"]
        s["pass_rate"] = round(sum(r["passed"] for r in rows) / len(rows), 3)
        by_cat: Dict[str, List[bool]] = {}
        for r in rows:
            by_cat.setdefault(r["category"], []).append(r["passed"])
        s["pass_rate_by_category"] = {k: round(sum(x) / len(x), 3) for k, x in by_cat.items()}
        s["rescored"] = True
    out = Path(path).with_name(Path(path).stem + "_rescored.json")
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    md = to_markdown(report)
    out.with_suffix(".md").write_text(md)
    print(md)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rescore", help="path to a prompt_eval_*.json to re-check offline")
    p.add_argument("--judge-file", help="judge the stored answers in a prompt_eval_*.json (offline, paced, resumable)")
    p.add_argument("--router-only", action="store_true")
    p.add_argument("--router-modes", nargs="+", default=["knn", "hybrid", "llm"])
    p.add_argument("--versions", nargs="+", default=["v1", "v2"])
    p.add_argument("--router", default="hybrid", help="router mode used during answer eval (hybrid|knn|llm|off)")
    p.add_argument("--judge", action="store_true")
    p.add_argument("--judge-model", default="gemini-3.5-flash")
    p.add_argument("--sleep", type=float, default=2.0, help="seconds between LLM calls (free-tier rate limits)")
    p.add_argument("--ids", nargs="*", help="only run these case ids")
    p.add_argument("--paired", action="store_true", help="paired design: all versions per case, stop on model change")
    p.add_argument("--expect-model", default="openai/gpt-oss-120b")
    args = p.parse_args()
    if args.rescore:
        rescore(args.rescore)
        return
    if args.judge_file:
        judge_file(args.judge_file, args.judge_model, args.sleep)
        return

    cases = load_cases()
    if args.ids:
        cases = [c for c in cases if c["id"] in args.ids]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {"ts": ts, "n_cases": len(cases), "router_mode": None if args.router_only else args.router}
    report["router"] = eval_router(cases, args.router_modes, sleep_s=args.sleep / 2)
    if not args.router_only:
        OUT_DIR.mkdir(parents=True, exist_ok=True)

        def _ckpt(partial):
            report["answers"] = partial
            (OUT_DIR / f"prompt_eval_{ts}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))

        if args.paired:
            report["answers"] = eval_paired(cases, args.versions, args.router, args.sleep, args.expect_model, _ckpt)
        else:
            report["answers"] = eval_answers(cases, args.versions, args.router, args.judge, args.judge_model, args.sleep, _ckpt)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"prompt_eval_{ts}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    md = to_markdown(report)
    (OUT_DIR / "prompt_eval_latest.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
