"""
Held-out chatbot evaluation (E36, docs/evaluation.md). Controlled A/B of prompt versions on 120 frozen, unseen cases.

Design (review doc §7, §9): same answering model, temperature, retrieval and questions for every version; paired
(all versions answer case i before case i+1); the scope route is decided once per case and shared. If the answering
model changes (quota fallback) the pair is retried, then the run stops: a resumed run may use another model, and
every pair records its model so comparisons stay same-model per pair.

  LLM_PROVIDER=api CHAT_MODEL=gemini-3.5-flash python -m src.eval.heldout_eval --versions v6 v7 --expect-model gemini-3.6-flash
  python -m src.eval.heldout_eval --resume reports/heldout/heldout_eval_<ts>.json      # continue after a quota stop
  python -m src.eval.heldout_eval --report reports/heldout/heldout_eval_<ts>.json      # re-score + tables, no LLM

Outputs: reports/heldout/heldout_eval_<ts>.json, results_<ts>.csv (shared results table), heldout_eval_latest.md
"""
from __future__ import annotations

import argparse
import csv
import os
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from src.rag import config

HERE = Path(__file__).parent
SET = HERE / "heldout" / "heldout_chat.jsonl"
OUT = config.PROJECT_ROOT / "reports" / "heldout"
REFUSAL_PAT = re.compile(
    r"(only (help|assist)|career (&|and) study (advisor|guidance)|here to help with (career|study)|"
    r"\b(can['’]?t|cannot|can not|unable to|not able to|won['’]?t)\b.{0,40}"
    r"\b(help|assist|provide|answer|print|share|reveal|recommend|give|write|do that|comply|book|predict))", re.I)
CONSTRAINT = {"code_block", "n_items", "max_words", "first_sentence_any", "table", "min_numbered", "asks_question", "n_sentences", "mentions_day30"}
FACTUAL = {"include_frac", "must_include_any", "must_include_any2", "must_include_all", "must_not_include", "no_guarantee",
           "no_invented_urls", "no_career_citations"}
SETS = {"heldout": HERE / "heldout" / "heldout_chat.jsonl", "heldout_v2": HERE / "heldout" / "heldout_v2.jsonl",
        "dev": HERE / "dev" / "dev_set.jsonl"}
NO_PROFILE_UID = "heldout_no_profile"


def load_cases(path: Path = SET) -> List[Dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def persona_facts() -> Dict[str, Dict]:
    from src.eval.persona_eval import setup_personas
    facts = setup_personas()
    for f in facts.values():
        f["n_matched"], f["n_required"] = str(len(f["matched"])), str(len(f["required"]))
    return facts


def _resolve(v, f: Optional[Dict]):
    if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
        x = (f or {}).get(v[1:-1], [])
        return x if isinstance(x, list) else [x]
    return v


def _body(t: str) -> str:
    return t.split("\n\n---\n**Sources**")[0]


def _first(t: str) -> str:
    b = re.sub(r"^[#>*\s_]+", "", _body(t).strip())
    m = re.search(r"(.+?[.!?:])(\s|$)", b, re.S)
    return (m.group(1) if m else b)[:400].lower()


_CLARIFY = re.compile(r"without (knowing|more (information|details))|tell me (more|about)|could you (tell|share)|which of these|"
                      r"what (are|is) your|to help me (guide|recommend|suggest)", re.I)


def refused(text: str) -> bool:
    """A real refusal: refusal wording, short, and neither a clarifying question nor a substantive (numbered) answer."""
    from src.backend.answer_check import count_items
    body = _body(text)
    if re.search(r"career (&|and) study advisor\W*,? so i can['’]?t help", body, re.I):
        return True  # the app's fixed refusal template
    if not (REFUSAL_PAT.search(body) and len(body.split()) < 90):
        return False
    if _CLARIFY.search(body) and "?" in body:
        return False  # asking for the student's background is clarification, not refusal
    return count_items(text) < 2


RUBRICS = {k: v for k, v in json.loads((HERE / "heldout" / "rubrics.json").read_text()).items() if not k.startswith("_")}


def score(case: Dict, text: str, hits: List[Dict], f: Optional[Dict], memory: Optional[Dict], intent: Optional[Dict] = None) -> Dict:
    if case["id"] in RUBRICS:  # review 2 §1: ambiguous label -> explicit rubric, applied to every version alike
        case = {**case, "checks": RUBRICS[case["id"]]["checks"]}
    from src.backend.answer_check import citation_report, count_items, fact_issues
    from src.backend.task_contract import sentence_count, url_issues
    body, low = _body(text), _body(text).lower()
    ch: Dict[str, Optional[bool]] = {}
    if case["expect"] == "refuse":
        ch["refusal"] = refused(text)
    else:
        ch["not_refused"] = not refused(text)
    for k, v in case["checks"].items():
        if k == "n_items":
            ch[k] = count_items(text) == v
        elif k == "max_words":
            ch[k] = len(body.split()) <= v
        elif k == "first_sentence_any":
            opts = _resolve(v, f)
            ch[k] = any(str(o).lower() in _first(text) for o in opts) if opts else None
        elif k == "table":
            ch[k] = len([l for l in body.splitlines() if l.strip().startswith("|")]) >= 3
        elif k == "min_numbered":
            ch[k] = len([l for l in body.splitlines() if re.match(r"^\s*\d+[.)]\s+\S", l)]) >= v
        elif k == "asks_question":
            ch[k] = "?" in body
        elif k in ("must_include_any", "must_include_any2"):
            opts = _resolve(v, f)
            ch[k] = any(str(o).lower() in low for o in opts) if opts else None
        elif k == "must_include_all":
            opts = _resolve(v[0] if isinstance(v, list) and len(v) == 1 else v, f)
            ch[k] = all(re.search(rf"(?<!\d){re.escape(str(o).lower())}(?!\d)", low) for o in opts) if opts else None
        elif k == "include_frac":
            items, need = _resolve(v[0], f), v[1]
            ch[k] = (sum(str(i).lower() in low for i in items) / len(items) >= need) if items else None
        elif k == "citation":
            ch[k] = bool(re.search(r"\[S\d+", text))
        elif k == "n_sentences":
            ch[k] = sentence_count(text) == v
        elif k == "must_not_include":
            ch[k] = not any(str(x).lower() in low for x in _resolve(v, f))
        elif k == "no_guarantee":
            ch[k] = bool(re.search(r"(can['’]?t|cannot|can not|no one can|not possible to|isn['’]?t possible to)\b.{0,25}\bguarantee|\bno guarantee|\bnot (a )?guarantee|\bguarantees? (are|is) not\b", low))
        elif k == "no_invented_urls":
            ch[k] = not url_issues(text, hits)
        elif k == "mentions_day30":
            ch[k] = bool(re.search(r"\bday\s*30\b|\bday\s*2[5-9]\s*[-–]\s*30\b|\bdays?\s*\d{1,2}\s*[-–]\s*30\b", low))
        elif k == "no_career_citations":
            cited = {int(n) for n in re.findall(r"\[S(\d+)", text)}
            ch[k] = not any(0 < n <= len(hits) and hits[n - 1].get("source") == "careers" for n in cited)
        elif k == "code_block":
            ch[k] = "```" in body
        elif k == "no_contradicted_claims":
            pass  # scored from the claim check below
    cr = citation_report(text, hits) if case["expect"] == "allow" else {"citations": 0, "invalid": [], "unsupported": [], "correct_rate": None}
    claims = {"n": 0, "counts": {}, "support_rate": None, "claims": []}
    if case["expect"] == "allow":
        from src.backend.claim_check import verify
        claims = verify(text, hits)  # E37: claim-level support (NLI), the review's citation-support metric
    if "no_contradicted_claims" in case["checks"]:
        ch["no_contradicted_claims"] = not claims["counts"].get("contradicted")
    if case.get("intent") and intent:
        ch["intent"] = intent.get("primary_intent") == case["intent"]
    contradictions = fact_issues(text, memory)
    ch["profile_consistent"] = not contradictions if memory else None
    passed = all(x for k, x in ch.items() if x is not None and k != "intent")  # routing is reported separately
    return {"checks": ch, "passed": passed, "citations": cr, "contradictions": contradictions,
            "claims": {k: claims[k] for k in ("n", "counts", "support_rate")} | {"method": claims.get("method"),
                       "items": [{kk: c[kk] for kk in ("claim", "id", "label")} for c in claims["claims"]][:12]}}


def root_cause(case: Dict, row: Dict, f: Optional[Dict]) -> str:
    """Classify a failure before anyone edits a prompt (review doc §8)."""
    ch = row["checks"]
    if ch.get("refusal") is False:
        return "scope_router (out-of-scope answered)"
    if ch.get("not_refused") is False:
        return "scope_router (valid question refused)" if row["route"] != "career_study" else "prompt (model refused)"
    if ch.get("profile_consistent") is False:
        return "grounding (contradicts the student's profile)"
    if ch.get("no_contradicted_claims") is False:
        return "grounding (claim contradicts its cited source)"
    failed = {k for k, v in ch.items() if v is False}
    if failed & FACTUAL:
        need = []
        for k in failed & FACTUAL:
            v = case["checks"].get(k)
            if isinstance(v, (list, str)):
                need += [str(x).lower() for x in _resolve(v[0] if k == "include_frac" else v, f)]
        if failed & {"no_guarantee", "no_invented_urls", "no_career_citations", "must_not_include"}:
            return "prompt (forbidden content: " + ", ".join(sorted(failed & {"no_guarantee", "no_invented_urls", "no_career_citations", "must_not_include"})) + ")"
        ctx = (row.get("context") or "").lower()
        if case.get("user") is None and need and not any(n in ctx for n in need):
            return "retrieval (expected facts not in retrieved context)"
        return "prompt (facts available but not used)"
    if failed & CONSTRAINT:
        return "instruction_following (" + ", ".join(sorted(failed & CONSTRAINT)) + ")"
    return "other"


def ask(case: Dict, version: str, decision: Dict) -> Dict:
    from src.backend.chatbot import answer
    uid = case.get("user") or NO_PROFILE_UID
    return answer(case["messages"], system_version=version, route_override=decision, user_id=uid, extra_hits=case.get("extra_hits"))


def run(cases: List[Dict], versions: List[str], expect_model: str, sleep_s: float, rep: Dict, path: Path, workers: int = 1) -> Dict:
    from src.backend.chatbot import load_memory
    from src.backend.scope_router import route
    from src.rag.retriever import format_context

    import threading
    from concurrent.futures import ThreadPoolExecutor

    facts = rep.setdefault("facts", persona_facts())
    done = {r["id"] for r in rep["rows"]}
    lock, stop_flag = threading.Lock(), threading.Event()

    def one(c: Dict) -> None:
        if stop_flag.is_set():
            return
        msgs = c["messages"]
        decision = route(msgs[-1]["content"], msgs[:-1])
        pair, stop = {}, None
        for v in versions:
            for attempt in range(3):
                res = ask(c, v, decision)
                model = res.get("model")
                if not res.get("error") and (model is None or not expect_model or model == expect_model):
                    break
                print(f"   [{c['id']} {v}] retry {attempt + 1}: model={model} error={str(res.get('error'))[:80]}", flush=True)
                time.sleep(30 * (attempt + 1))
            else:
                stop = f"{c['id']} {v}: model={model} error={str(res.get('error'))[:120]}"
            if stop:
                break
            pair[v] = res
            time.sleep(sleep_s if res.get("model") else 0.3)
        if stop:
            rep["stopped"] = stop
            stop_flag.set()
            print("[heldout] STOP", stop)
            return
        f = facts.get(c.get("user") or "")
        mem = load_memory(c.get("user")) if c.get("user") else None
        rows_out = []
        for v, res in pair.items():
            sc = score(c, res["text"], res.get("hits", []), f, mem, res.get("intent"))
            row = {"id": c["id"], "category": c["category"], "user": c.get("user"), "version": v, "route": decision["label"],
                   "question": msgs[-1]["content"], "expected_behavior": c["expected_behavior"], "answer": res["text"],
                   "model": res.get("model"), "model_configured": os.getenv("CHAT_MODEL", "default"), "latency_ms": res.get("latency_ms"),
                   "intent_got": (res.get("intent") or {}).get("primary_intent"), "intent_expected": c.get("intent"),
                   "tokens": (res.get("usage") or {}).get("total_tokens"), "revised": res.get("revised"),
                   "intent": {k: (res.get("question_profile") or {}).get(k) for k in ("type", "missing", "n_items", "max_words")},
                   "sources": [f"S{i}:{h['source']}:{(h.get('metadata') or {}).get('career_name') or (h.get('metadata') or {}).get('section') or h.get('doc_type')}"
                               for i, h in enumerate(res.get("hits", []), 1)],
                   "context": format_context(res.get("hits", []))[:3000] if res.get("hits") else "", **sc}
            row["root_cause"] = None if row["passed"] else root_cause(c, row, f)
            rows_out.append(row)
            print(f"[{v}] {c['id']:12s} {c['category']:18s} passed={row['passed']} "
                  f"{ {k: x for k, x in row['checks'].items() if x is False} or ''} cit={row['citations']['correct_rate']} model={row['model']}")
        with lock:
            rep["rows"].extend(rows_out)
            path.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str))

    todo = [c for c in cases if c["id"] not in done]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, todo))
    order = {c["id"]: i for i, c in enumerate(cases)}
    rep["rows"].sort(key=lambda r: (order.get(r["id"], 1e9), r["version"]))
    return rep


def summarise(rep: Dict) -> Dict:
    out = {}
    for v in rep["versions"]:
        rows = [r for r in rep["rows"] if r["version"] == v]
        if not rows:
            continue
        allow = [r for r in rows if r["category"] != "out_of_scope"]
        oos = [r for r in rows if r["category"] == "out_of_scope"]

        def rate(rs, keys):
            vals = [x for r in rs for k, x in r["checks"].items() if k in keys and x is not None]
            return round(sum(vals) / len(vals), 3) if vals else None
        cits = [r["citations"] for r in allow if r["citations"]["citations"]]
        tot = sum(c["citations"] for c in cits)
        bad = sum(len(c["invalid"]) + len(c["unsupported"]) for c in cits)
        by_cat: Dict[str, List[bool]] = {}
        causes: Dict[str, int] = {}
        for r in rows:
            by_cat.setdefault(r["category"], []).append(r["passed"])
            if r["root_cause"]:
                key = r["root_cause"].split(" (")[0]
                causes[key] = causes.get(key, 0) + 1
        prof = [r for r in rows if r["checks"].get("profile_consistent") is not None]
        toks = [r["tokens"] for r in rows if r.get("tokens")]
        out[v] = {
            "n": len(rows), "pass_rate": round(sum(r["passed"] for r in rows) / len(rows), 3),
            "pass_rate_by_category": {k: round(sum(x) / len(x), 3) for k, x in by_cat.items()},
            "scope_accuracy": round((sum(r["checks"].get("not_refused") is True for r in allow) + sum(r["checks"].get("refusal") is True for r in oos)) / len(rows), 3),
            "false_refusals": sum(r["checks"].get("not_refused") is False for r in allow),
            "out_of_scope_leaks": sum(r["checks"].get("refusal") is False for r in oos),
            "constraint_compliance": rate(allow, CONSTRAINT),
            "factual_correctness": rate(allow, FACTUAL),
            "citation_rate": round(sum(bool(re.search(r"\[S\d+", r["answer"])) for r in allow) / max(1, len(allow)), 3),
            "citation_correctness": round((tot - bad) / tot, 3) if tot else None, "citations": tot,
            "profile_consistency": round(sum(r["checks"]["profile_consistent"] for r in prof) / len(prof), 3) if prof else None,
            "revised": sum(bool(r.get("revised")) for r in rows),
            "avg_latency_ms": round(sum(r["latency_ms"] or 0 for r in rows) / len(rows)),
            "avg_tokens": round(sum(toks) / len(toks)) if toks else None,
            "models": sorted({str(r["model"]) for r in rows}), "root_causes": causes,
            "claim_support_rate": (lambda n, sup: round(sup / n, 3) if n else None)(
                sum(r.get("claims", {}).get("n", 0) for r in allow), sum(r.get("claims", {}).get("counts", {}).get("supported", 0) for r in allow)),
            "claim_contradiction_rate": (lambda n, c: round(c / n, 3) if n else None)(
                sum(r.get("claims", {}).get("n", 0) for r in allow), sum(r.get("claims", {}).get("counts", {}).get("contradicted", 0) for r in allow)),
            "intent_accuracy": (lambda xs: round(sum(xs) / len(xs), 3) if xs else None)(
                [r["checks"]["intent"] for r in rows if r["checks"].get("intent") is not None]),
            "pass_rate_by_model": {m: round(sum(r["passed"] for r in rows if str(r["model"]) == m) / n_m, 3)
                                   for m in {str(r["model"]) for r in rows}
                                   for n_m in [sum(str(r["model"]) == m for r in rows)]},
        }
    return out


TARGETS = {"claim_support_rate": "higher is better", "claim_contradiction_rate": "0", "intent_accuracy": "-",
           "scope_accuracy": ">= 0.98", "false_refusals": "as low as possible", "out_of_scope_leaks": "0",
           "constraint_compliance": ">= 0.95", "factual_correctness": ">= 0.95", "citation_correctness": ">= 0.95",
           "profile_consistency": "1.0"}


def apply_rubrics(rep: Dict) -> None:
    """Re-score stored answers of rubric cases (text checks only; same rubric for every version)."""
    for r in rep["rows"]:
        if r["id"] in RUBRICS and not r.get("rubric_applied"):
            low = _body(r["answer"]).lower()
            for k, v in RUBRICS[r["id"]]["checks"].items():
                r["checks"].pop("first_sentence_any", None)
                r["checks"][k] = any(str(o).lower() in low for o in v)
            r["passed"] = all(x for k, x in r["checks"].items() if x is not None and k != "intent")
            r["root_cause"] = None if r["passed"] else (r.get("root_cause") or "prompt (rubric)")
            r["rubric_applied"] = True


def recheck_profile(rep: Dict) -> None:
    """Re-run the (corrected) profile-contradiction detector on stored answers; text-only, no model calls."""
    from src.backend.answer_check import fact_issues
    from src.backend.chatbot import load_memory
    mems: Dict = {}
    for r in rep["rows"]:
        if not r.get("user") or r["checks"].get("profile_consistent") is None:
            continue
        mem = mems.setdefault(r["user"], load_memory(r["user"]))
        r["contradictions"] = fact_issues(r["answer"], mem)
        r["checks"]["profile_consistent"] = not r["contradictions"]
        r["passed"] = all(x for k, x in r["checks"].items() if x is not None and k != "intent")
        if r["passed"]:
            r["root_cause"] = None
        elif not r.get("root_cause") or r["root_cause"].startswith("grounding (contradicts"):
            r["root_cause"] = root_cause({"checks": {}, "user": r.get("user")}, r, None)


def recheck_refusals(rep: Dict) -> None:
    """Re-apply the (corrected) refusal detector to stored answers, every version alike."""
    for r in rep["rows"]:
        ch = r["checks"]
        if "refusal" in ch:
            ch["refusal"] = refused(r["answer"])
        if "not_refused" in ch:
            ch["not_refused"] = not refused(r["answer"])
        r["passed"] = all(x for k, x in ch.items() if x is not None and k != "intent")
        if r["passed"]:
            r["root_cause"] = None
        elif not r.get("root_cause") or "refus" in (r.get("root_cause") or ""):
            r["root_cause"] = root_cause({"checks": {}, "user": r.get("user")}, r, None)


def _hits_from_context(ctx: str) -> List[Dict]:
    blocks = re.findall(r"\[S(\d+)\] \(source=([a-z_]+)/[^)]*\)\n(.*?)(?=\n\n\[S\d+\] \(|\Z)", ctx or "", re.S)
    if not blocks:
        return []
    by = {int(n): {"source": src, "text": t} for n, src, t in blocks}
    return [by.get(i, {"source": "?", "text": ""}) for i in range(1, max(by) + 1)]


def recheck_claims(rep: Dict) -> None:
    """Re-run the (corrected) claim verifier on stored answers using their saved sources, every version alike."""
    from src.backend.claim_check import verify
    for r in rep["rows"]:
        if r["category"] == "out_of_scope" or not r.get("context"):
            continue
        c = verify(r["answer"], _hits_from_context(r["context"]))
        r["claims"] = {k: c[k] for k in ("n", "counts", "support_rate")} | {"method": c.get("method"),
                       "items": [{kk: x[kk] for kk in ("claim", "id", "label")} for x in c["claims"]][:12], "rechecked": True}
        if "no_contradicted_claims" in r["checks"]:
            r["checks"]["no_contradicted_claims"] = not c["counts"].get("contradicted")
            r["passed"] = all(x for k, x in r["checks"].items() if x is not None and k != "intent")


def write_outputs(rep: Dict, path: Path) -> str:
    apply_rubrics(rep)
    recheck_profile(rep)
    recheck_refusals(rep)
    if os.getenv("RECHECK_CLAIMS", "true") == "true":
        recheck_claims(rep)
    from src.eval.heldout_eval import summarise as _s
    rep["summary"] = _s(rep)
    path.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
    csv_path = path.with_name(path.stem.replace("heldout_eval", "results") + ".csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["test_id", "category", "user", "question", "expected_behavior", "actual_answer", "retrieved_source_ids",
                    "pass_fail", "failure_reason", "root_cause", "prompt_version", "model_id", "model_configured",
                    "scope_pass", "intent_pass", "citation_support_pass", "factual_pass", "claim_support_rate",
                    "citation_correct_rate", "latency_ms", "tokens"])
        for r in rep["rows"]:
            reason = "; ".join(k for k, v in r["checks"].items() if v is False)
            reason += ("; " if reason and r["citations"]["unsupported"] else "") + \
                ("unsupported citations: " + ", ".join(f"S{i}" for i, _ in r["citations"]["unsupported"]) if r["citations"]["unsupported"] else "")
            w.writerow([r["id"], r["category"], r["user"] or "", r["question"], r["expected_behavior"], _body(r["answer"]),
                        " | ".join(r["sources"]), "PASS" if r["passed"] else "FAIL", reason, r["root_cause"] or "",
                        r["version"], r["model"], r.get("model_configured", ""),
                        r["checks"].get("refusal", r["checks"].get("not_refused")), r["checks"].get("intent"),
                        not (r.get("claims", {}).get("counts", {}).get("contradicted") or r["citations"]["invalid"]),
                        all(v for k, v in r["checks"].items() if k in FACTUAL and v is not None),
                        r.get("claims", {}).get("support_rate"), r["citations"]["correct_rate"], r["latency_ms"], r["tokens"]])
    S = rep["summary"]
    vs = [v for v in rep["versions"] if v in S]
    L = [f"# Held-out chatbot evaluation ({rep['ts']})", "",
         f"Frozen set: `src/eval/heldout/heldout_chat.jsonl` ({rep['n_cases']} cases). Paired design, shared route per case. "
         f"Completed pairs: {len([r for r in rep['rows'] if r['version'] == vs[0]]) if vs else 0}" + (f" (stopped: {rep['stopped']})" if rep.get("stopped") else ""), "",
         "| Metric | Target (review doc) | " + " | ".join(vs) + " |", "|---|---|" + "---|" * len(vs)]
    for m in ["pass_rate", "intent_accuracy", "scope_accuracy", "false_refusals", "out_of_scope_leaks", "constraint_compliance",
              "factual_correctness", "citation_rate", "citation_correctness", "claim_support_rate", "claim_contradiction_rate",
              "profile_consistency", "revised", "avg_latency_ms", "avg_tokens"]:
        L.append(f"| {m} | {TARGETS.get(m, '-')} | " + " | ".join(str(S[v].get(m)) for v in vs) + " |")
    L += ["", "## Pass rate by category", "", "| Category | " + " | ".join(vs) + " |", "|---|" + "---|" * len(vs)]
    cats = sorted({c for v in vs for c in S[v]["pass_rate_by_category"]})
    for c in cats:
        L.append(f"| {c} | " + " | ".join(str(S[v]["pass_rate_by_category"].get(c)) for v in vs) + " |")
    L += ["", "## Root causes of failures", ""] + [f"- **{v}**: {json.dumps(S[v]['root_causes'])} · models {S[v]['models']}" for v in vs]
    fails = [r for r in rep["rows"] if not r["passed"]]
    if fails:
        L += ["", "## Failed cases", "", "| Version | Case | Failed checks | Root cause |", "|---|---|---|---|"]
        for r in fails:
            L.append(f"| {r['version']} | {r['id']} | {', '.join(k for k, v in r['checks'].items() if v is False)} | {r['root_cause']} |")
    md = "\n".join(L) + "\n"
    path.with_suffix(".md").write_text(md)
    (OUT / "heldout_eval_latest.md").write_text(md)
    return md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", nargs="+", default=["v6", "v7"])
    ap.add_argument("--expect-model", default="")
    ap.add_argument("--sleep", type=float, default=4.0)
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--resume")
    ap.add_argument("--set", default="heldout", choices=sorted(SETS), help="heldout (E36) | heldout_v2 (frozen before v8) | dev")
    ap.add_argument("--workers", type=int, default=1, help="cases answered in parallel (each pair stays same-model)")
    ap.add_argument("--report")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.report:
        p = Path(a.report)
        print(write_outputs(json.loads(p.read_text()), p))
        return
    cases = load_cases(SETS[a.set])
    if a.ids:
        cases = [c for c in cases if c["id"] in a.ids]
    if a.resume:
        path = Path(a.resume)
        rep = json.loads(path.read_text())
        rep.pop("stopped", None)
        cases = load_cases(SETS[rep.get("set", "heldout")])
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = OUT / f"heldout_eval_{a.set}_{ts}.json" if a.set != "heldout" else OUT / f"heldout_eval_{ts}.json"
        rep = {"ts": ts, "versions": a.versions, "n_cases": len(cases), "rows": [], "set": a.set}
    rep = run(cases, rep["versions"], a.expect_model, a.sleep, rep, path, workers=a.workers)
    print(write_outputs(rep, path))


if __name__ == "__main__":
    main()
