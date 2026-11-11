"""
UpskillxAI Career Advisor chatbot (RAG).

Flow per user turn (docs/chatbot.md):
    message -> scope_router.route()
        out_of_scope / prompt_attack -> refusal template (no LLM call)
        greeting                     -> LLM with system prompt, no retrieval
        career_study                 -> retrieve (MongoDB Atlas / local vectors)
                                        -> system prompt (profile + [S#] context)
                                        -> few-shots + recent history -> LLM -> answer + sources

Public API (unchanged for the Streamlit frontend):
    chat_with_agent(chat_history: list[dict]) -> str
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.backend.feedback_store import learned_guidance
from src.backend.question_profile import QUOTAS, answer_contract, answer_contract_v7, parsed_intent, profile_question
from src.backend.scope_router import route
from src.prompts.registry import ACTIVE, load_json, load_prompt
from src.rag import config
from src.rag.retriever import retrieve, format_context

# llama-3.3-70b-versatile was retired by Groq (found 2026-11-08); every call had silently been
# going to the fallback chain. gpt-oss-120b is the strongest model currently served on the free tier.
CHAT_MODEL = os.getenv("CHAT_MODEL", "groq:openai/gpt-oss-120b")
HISTORY_TURNS = 8
CHAT_LOG = config.PROJECT_ROOT / "reports" / "chat_logs" / "chat_log.jsonl"


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(i.get("text", "") if isinstance(i, dict) else str(i) for i in content)
    return str(content)


def load_memory(user_id: str | None = None) -> Dict | None:
    path = config.memory_path(user_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def load_profile_summary(user_id: str | None = None, v7: bool = False) -> str:
    """Compact, always-included profile header (cheap and guarantees core facts are present)."""
    mem = load_memory(user_id)
    if mem is None:
        return "No analysed profile yet. The user has not run 'Analyze Profile'."
    ats_note = " (stored AI estimate from the last analysis, not an official ATS result)" if v7 else ""
    return (
        f"- Target role: {mem.get('target_role') or 'not specified'}\n"
        f"- ATS match score: {mem.get('ats_score', 'n/a')}/100{ats_note}\n"
        f"- Current skills: {', '.join(mem.get('candidate_skills') or []) or 'n/a'}\n"
        f"- Skills required by JD: {', '.join(mem.get('required_skills') or []) or 'n/a'}\n"
        f"- Skill gaps: {', '.join(mem.get('skill_gaps') or []) or 'none'}\n"
        f"- Matched jobs found: {len(mem.get('job_listings') or [])}\n"
        f"- Summary: {(mem.get('career_summary') or '')[:600]}\n"
        # E33: short excerpts so questions about the JD or the resume can be answered from the actual text
        f"- Target job description (excerpt): {' '.join(str(mem.get('job_description') or '').split()[:110])}\n"
        f"- Resume (excerpt): {' '.join(str(mem.get('resume_text') or '').split()[:110])}"
        + (_progress_line(mem.get("roadmap_progress")) if mem.get("roadmap_progress") else "")
    )


def _progress_line(p: Dict) -> str:
    """E38: roadmap progress recorded on the roadmap page (task completion rate, revision topics)."""
    return (f"\n- 30-day roadmap progress (recorded by the student): on day {p.get('on_day')}, completed {p.get('completed')}/"
            f"{p.get('days_due')} days due" + (f"; revising: {', '.join(p['revising'])}" if p.get("revising") else "")
            + (f"; deferred: {', '.join(p['deferred'])}" if p.get("deferred") else ""))


def _retrieval_query(history: List[Dict], resolved: str | None = None) -> str:
    """Short follow-ups ('and how long?') are expanded with the previous user turn.
    E38: `resolved` is the message with references made explicit ("the second one" -> "Data Engineer")."""
    users = [m["content"] for m in history if m["role"] == "user"]
    q = resolved or users[-1]
    if len(q.split()) <= 6 and len(users) > 1:
        q = f"{users[-2]} {q}"
    return q


def _suggestion(message: str) -> str:
    examples = load_json("scope_examples.json")["career_study"]
    return examples[int(hashlib.md5(message.encode()).hexdigest(), 16) % len(examples)]


def _sources_footer(answer: str, hits: List[Dict]) -> str:
    cited = set()
    # accepts [S1], [S1][S2], [S1, S3] and ranges like [S1-S4] / [S1‑S4] (the model uses all of them)
    for group in re.findall(r"\[(S\d+(?:\s*[,\-\u2010-\u2014]\s*S?\d+)*)\]", answer):
        for a, b in re.findall(r"S?(\d+)(?:\s*[\-\u2010-\u2014]\s*S?(\d+))?", group):
            lo, hi = int(a), int(b or a)
            cited.update(range(lo, min(hi, len(hits)) + 1))
    cited = sorted(n for n in cited if 0 < n <= len(hits))
    if not cited:
        return ""
    lines = []
    for n in cited:
        h = hits[n - 1]
        meta = h.get("metadata") or {}
        label = meta.get("career_name") or meta.get("title") or meta.get("section") or h["doc_type"].replace("_", " ")
        url = meta.get("url")
        lines.append(f"- [S{n}] {h['source']}: {label}" + (f" ({url})" if url else ""))
    return "\n\n---\n**Sources**\n" + "\n".join(lines)


def _log(entry: Dict) -> None:
    try:
        CHAT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(CHAT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def _relevance_filter(hits: List[Dict], margin: float = 0.15) -> List[Dict]:
    """E32: per source, drop chunks far below that source's best match (noise that diluted answers)."""
    best: Dict[str, float] = {}
    for h in hits:
        best[h["source"]] = max(best.get(h["source"], 0.0), h["score"])
    return [h for h in hits if h["score"] >= best[h["source"]] - margin]


def _few_shot_file(vnum: int) -> str:
    from src.prompts.registry import PROMPT_DIR
    for v in range(vnum, 2, -1):
        if (PROMPT_DIR / f"few_shots_v{v}.json").exists():
            return f"few_shots_v{v}.json"
    return "few_shots_v3.json"


def match_strength(hits: List[Dict]) -> str:
    """Signal for prompt rule 9: weak career evidence -> ask clarifying questions, don't guess."""
    careers = [h for h in hits if h["source"] == "careers"]
    best = max((h["score"] for h in careers), default=0.0)
    label = "WEAK" if best < config.CAREER_MIN_SCORE else "OK"
    return f"MATCH STRENGTH: {label} (best career-record similarity {best:.2f}; floor {config.CAREER_MIN_SCORE})"


def build_messages(history: List[Dict], profile: str, context: str, system_version: str | None = None,
                   contract: str = "", learned: str = "", labels: str = "", intent: Dict | None = None) -> list:
    version = system_version or ACTIVE["advisor_system"]
    vnum = int(version.lstrip("v"))
    template = load_prompt("advisor_system", version)
    if vnum >= 3:
        # v3: examples live INSIDE the system prompt, labelled as fictional users, so the
        # model never mistakes them for its own earlier turns with this user (v2 failure mode).
        examples = "\n\n".join(
            f"### Example {i}: {ex['situation']}\nUser: {ex['user']}\nAdvisor: {ex['assistant']}"
            for i, ex in enumerate(load_json(_few_shot_file(vnum)), 1)
        )
        fields = {"profile": profile, "context": context, "examples": examples}
        if vnum >= 5:  # v5: per-question answer contract + guidance learned from user feedback
            fields.update(contract=contract or "- Answer the question directly in the first sentence.",
                          learned=learned or "(no feedback on similar questions yet)")
        if vnum >= 7:  # v7: layered prompt; the model sees exactly which citation labels exist
            fields["labels"] = labels or "none"
        if vnum >= 8:  # v8: short core + only this intent's task template and matching examples
            from src.backend.task_contract import pick_examples, task_prompt
            it = intent or {"primary_intent": "career_discovery", "secondary_intents": []}
            fields["task"] = task_prompt(it)
            fields["examples"] = pick_examples(it, load_json(_few_shot_file(vnum)))
        system = template.format(**fields)
    else:
        system = template.format(profile=profile, context=context)
    msgs = [SystemMessage(content=system)]
    if vnum == 2:  # v2: few-shots injected as fake prior chat turns
        for ex in load_json("few_shots.json"):
            msgs += [HumanMessage(content=ex["user"]), AIMessage(content=ex["assistant"])]
    for m in history[-HISTORY_TURNS:]:
        msgs.append(HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"]))
    return msgs


def answer(chat_history: List[Dict], system_version: str | None = None, router_mode: str | None = None,
           profile_override: str | None = None, route_override: Dict | None = None,
           quotas: Dict | None = None, user_id: str | None = None, extra_hits: List[Dict] | None = None,
           e38: bool | None = None) -> Dict:
    """Full turn with diagnostics (used by the eval harness and the API). `e38` overrides the E38_PIPELINE default."""
    from src.backend.features import _E38, set_e38
    token = set_e38(e38)
    try:
        return _answer(chat_history, system_version, router_mode, profile_override, route_override, quotas, user_id, extra_hits)
    finally:
        _E38.reset(token)


def _answer(chat_history, system_version, router_mode, profile_override, route_override, quotas, user_id, extra_hits) -> Dict:
    from src.backend.features import e38_on
    t0 = time.perf_counter()
    history = [m for m in chat_history if m.get("role") in ("user", "assistant") and m.get("content")]
    if not history or history[-1]["role"] != "user":
        return {"text": "Please ask a career or study question.", "route": None}
    message = history[-1]["content"]
    decision = route_override or route(message, history[:-1], mode=router_mode)
    out: Dict = {"route": decision, "hits": [], "system_version": system_version or ACTIVE["advisor_system"]}

    if decision["label"] in ("out_of_scope", "prompt_attack"):
        out["text"] = load_prompt("refusal").format(suggestion=_suggestion(message))
    else:
        from src.utilities.brain import get_robust_llm
        from src.utilities.llm_provider import llm_provider
        from src.backend.extractive_answer import compose_answer

        uid = user_id or config.DEFAULT_USER_ID
        version = system_version or ACTIVE["advisor_system"]
        vnum = int(version.lstrip("v"))
        v5, v7, v8 = vnum >= 5, vnum >= 7, vnum >= 8
        if llm_provider() == "none" and os.getenv("KEYLESS_INTENT_ROUTING", "true") == "true":  # keyless: no prompt is used -> v8 routing
            v8 = v7 = v5 = True
        qp = profile_question(message)
        memory = None if profile_override is not None else load_memory(uid)
        intent = None
        e38 = e38_on() and v5
        state, rmsg = None, message
        has_profile = memory is not None or (profile_override is not None and "No analysed profile" not in profile_override)
        if e38:  # E38: structured conversation state ("the second one", "one hour daily", corrections, changes of goal)
            from src.backend.conversation_state import build_state, resolved_message
            state = build_state(history[:-1], message)
            rmsg = resolved_message(message, state)
            out["state"] = {k: v for k, v in state.items() if v and k != "provenance"}
        if v8 or e38:  # E37: structured intent + source-aware routing (review 2 §2-3); E38: v7 uses it for plans only
            from src.backend.intent import classify, quotas_for
            intent = classify(rmsg, history[:-1], has_profile, decision["label"])
            out["intent"] = {k: v for k, v in intent.items() if k not in ("question_profile", "route")}
        if v8:
            qp = intent["question_profile"]
        elif v7:  # E36: parsed intent = task + primary source + missing information
            qp = parsed_intent(qp, message, has_profile, history_len=len(history) - 1)
        out["question_profile"] = qp
        hits = []
        if decision["label"] == "career_study":
            q_quotas = quotas or (QUOTAS[qp["type"]] if v5 else None)  # E32: retrieve what THIS question needs
            user_skills = None
            if v7:
                q_quotas = dict(q_quotas or QUOTAS[qp["type"]])
                if not has_profile and q_quotas.get("profile"):  # source routing: no profile -> spend the slots elsewhere
                    spare = q_quotas.pop("profile")
                    q_quotas["knowledge"] = q_quotas.get("knowledge", 0) + (spare + 1) // 2
                    q_quotas["careers"] = q_quotas.get("careers", 0) + spare // 2
                if memory and qp["type"] in ("recommendation", "list", "other"):
                    user_skills = memory.get("candidate_skills") or None  # career records matching the student's skills rank higher
            if v8:
                q_quotas = quotas or quotas_for(intent, has_profile)
                user_skills = (memory.get("candidate_skills") or None) if memory and intent["primary_intent"] == "career_discovery" else None
            if e38 and state.get("selected_career") and not has_profile and q_quotas is not None and not quotas:
                q_quotas = dict(q_quotas)  # E38: "what am I missing for <the career we discussed>" -> that career's records are the evidence
                q_quotas["careers"] = max(q_quotas.get("careers", 0), 2)
            hits = retrieve(_retrieval_query(history, rmsg if e38 else None), quotas=q_quotas, user_id=uid, user_skills=user_skills) if q_quotas else []
            if v5:
                hits = _relevance_filter(hits)
            if v8 or e38:
                from src.backend.task_contract import roadmap_evidence
                plan = roadmap_evidence(message, intent, memory, state=state)
                if plan:
                    out["roadmap"] = {k: plan["plan"][k] for k in ("gaps_prioritised", "days_per_skill", "capstone", "daily_minutes")}
                    hits = [{k: v for k, v in plan.items() if k != "plan"}] + hits
        if extra_hits:  # evaluation hook (e.g. prompt-injection fixture inside a retrieved record)
            hits = hits + extra_hits
        out["hits"] = hits
        context = format_context(hits) if hits else "(no retrieval for this message)"
        if e38:
            from src.rag.retriever import atlas_degraded
            if atlas_degraded():  # E38 (review 3 §7): say so; never invent career records to fill the gap
                context = ("NOTE: the main database is temporarily unreachable; results come from a local copy and may be incomplete. "
                           "If a needed career record is missing, say the information is unavailable right now; do not invent records.\n\n") + context
        if decision["label"] == "career_study" and not (v8 and intent["primary_intent"] not in ("career_discovery",)):
            context = match_strength(hits) + "\n\n" + context  # v8: the career-evidence signal only where careers are the evidence
        profile = profile_override if profile_override is not None else load_profile_summary(uid, v7=v7)
        contract, learned = "", ""
        if v5 and decision["label"] == "career_study":
            if v8:
                from src.backend.task_contract import contract_v8
                contract = contract_v8(intent)
            else:
                contract = answer_contract_v7(qp) if v7 else answer_contract(qp)
            if e38:
                from src.backend.conversation_state import state_block
                from src.backend.task_contract import e38_rules
                contract = "\n".join(x for x in (state_block(state, intent), contract, e38_rules(message, intent, state)) if x)
            try:
                g = learned_guidance(message, uid)
                out["learned"] = {k: g[k] for k in ("n_similar", "n_good", "n_bad")}
                learned = "\n".join(x for x in (g["avoid"], ("Answers users rated helpful for similar questions (follow their focus "
                                                              "and level of detail, not their facts):\n" + g["examples"]) if g["examples"] else "") if x)
            except Exception as e:  # noqa: BLE001 - learning must never break answering
                print(f"[chatbot] feedback guidance unavailable: {e}")
        labels = f"S1-S{len(hits)}" if hits else "none (do not cite)"
        msgs = build_messages(history, profile, context, system_version, contract=contract, learned=learned, labels=labels, intent=intent)

        def _extractive(reason: str):
            text = compose_answer(message, decision, hits, memory)
            if e38 and state and state.get("reference"):  # E38: say what "the second one" refers to, even without a model
                r = state["reference"]
                text = f"About **{r['resolved']}** (item {r['index']} of my last list):\n\n" + text
            if e38 and reason != "LLM_PROVIDER=none":  # E38: a useful notice; the conversation itself is kept by the UI
                text = ("_The AI model is unavailable right now, so this answer is assembled directly from the knowledge base. "
                        "Your conversation is kept: ask again in a minute for a full answer._\n\n") + text
            out["model"], out["generation"] = None, f"retrieval-only ({reason})"
            out["text"] = text + _sources_footer(text, hits)

        try:
            if llm_provider() == "none":
                raise LookupError("no-llm")
            llm = get_robust_llm(primary_model=CHAT_MODEL, temperature=0.3)
            resp = llm.invoke(msgs)
            out["model"] = (getattr(resp, "response_metadata", {}) or {}).get("model_name")
            out["usage"] = getattr(resp, "usage_metadata", None)
            text = resp.text.strip()
            if not text:  # final validation (journey j03): gpt-oss sometimes spends its whole budget reasoning and returns no text
                out["empty_retry"] = True
                resp = llm.invoke(msgs + [HumanMessage(content="Please give your answer now, directly and completely.")])
                text = resp.text.strip()
            # E34 (v6): generate -> verify against the answer contract -> revise once if needed
            if text and int(version.lstrip("v")) >= 6 and decision["label"] == "career_study":
                from src.backend.answer_check import REVISE_INSTRUCTION, check_answer, check_answer_v7
                if v8:
                    from src.backend.task_contract import check_v8
                    problems = check_v8(text, intent, message, memory, hits)
                else:
                    problems = check_answer_v7(text, qp, message, memory, hits) if v7 else check_answer(text, qp, message, memory)
                if problems:
                    try:
                        rev = llm.invoke(msgs + [AIMessage(content=text),
                                                 HumanMessage(content=REVISE_INSTRUCTION + "\n".join(f"- {p}" for p in problems))])
                        rtext = rev.text.strip()
                        # Final validation (journey j01): a revision once returned only the first 10 days of a 30-day
                        # plan. Keep the draft when the "revision" is a fragment and no problem asked for a shorter answer.
                        asks_shorter = any(re.search(r"\b(words?|sentences?|brief|shorter|one sentence|too long)\b", p, re.I) for p in problems)
                        if rtext and len(rtext) < 0.5 * len(text) and not asks_shorter:
                            out["revision_discarded"] = {"problems": problems, "draft_chars": len(text), "revision_chars": len(rtext)}
                        elif rtext:
                            text = rtext
                            out["revised"] = problems
                    except Exception as e:  # noqa: BLE001 - keep the draft if the revision call fails
                        print(f"[chatbot] revision skipped: {e}")
            out["generation"] = llm_provider()
            if not text:  # still empty: retrieval-only answer with the notice instead of a dead end
                _extractive("empty model reply")
                text = None
            if text is not None:
                out["text"] = text + _sources_footer(text, hits)
        except LookupError:
            _extractive("LLM_PROVIDER=none")
        except Exception as e:  # noqa: BLE001 - every generator failed: degrade to retrieval-only, never a dead end
            out["error"] = str(e)[:300]
            _extractive("all LLMs unavailable")
    out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    _log({"ts": datetime.now(timezone.utc).isoformat(), "message": message, "route": decision,
          "system_version": out["system_version"], "model": out.get("model"), "generation": out.get("generation"), "error": out.get("error"), "n_hits": len(out["hits"]),
          "hit_ids": [h.get("id") for h in out["hits"]], "top_score": out["hits"][0]["score"] if out["hits"] else None,
          "latency_ms": out["latency_ms"], "answer_chars": len(out["text"]),
          "question_type": (out.get("question_profile") or {}).get("type"), "learned": out.get("learned")})
    return out


def chat_with_agent(chat_history: list) -> str:
    """Streamlit entry point: list of {'role','content'} dicts -> assistant reply string."""
    return answer(chat_history)["text"]
