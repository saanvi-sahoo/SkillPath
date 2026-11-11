"""
Career Advisor chat UI (Streamlit). Always available as the first tab, with or without an analysed profile.

Features
  * starter questions for both journeys (doc §3): target role known / exploring careers
  * status chips: profile state, knowledge base backend, prompt version, scope rule
  * answers with collapsible cited sources
  * "How this answer was built" panel (router decision, retrieved records + scores, model, latency)
    for team discussions and demos
  * thumbs feedback per answer -> reports/chat_logs/feedback.jsonl (input for prompt training)
  * new conversation / download conversation
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import streamlit as st

from src.rag import config

FEEDBACK_LOG = config.PROJECT_ROOT / "reports" / "chat_logs" / "feedback.jsonl"
SOURCES_MARKER = "\n\n---\n**Sources**\n"

STARTERS_PROFILE = [
    "What are my skill gaps and what should I learn first?",
    "Explain my ATS score and how to improve it",
    "Which jobs match my profile?",
]
STARTERS_EXPLORE = [
    "Which career fits Python, SQL and dashboards?",
    "I like design and art, which tech careers suit me?",
    "How do I prepare for a data analyst interview?",
    "What are the most effective study techniques for exams?",
]


def _qa(idx: int):
    msgs = st.session_state["advisor_messages"]
    question = next((m["content"] for m in reversed(msgs[:idx]) if m["role"] == "user"), "")
    return question, msgs[idx]


def _save_feedback(idx: int, rating: str, reason: str = "", comment: str = "") -> None:
    """E32: feedback goes to the learning store (Atlas when configured) used by prompt v5 for similar questions."""
    question, ans = _qa(idx)
    meta = ans.get("meta") or {}
    try:
        from src.backend.feedback_store import record
        record(question, ans["content"], rating, st.session_state.get("uid", "default"), reason=reason, comment=comment,
               route=meta.get("route"), prompt_version=meta.get("system_version") or "")
    except Exception as e:  # noqa: BLE001
        st.caption(f"(feedback not saved: {e})")


def _status_chips(data) -> None:
    from src.prompts.registry import ACTIVE
    from src.rag.vector_store import resolve_backend
    from src.utilities.llm_provider import provider_label

    backend = "MongoDB Atlas" if resolve_backend() == "mongo" else "Local vector store"
    if data:
        role = data.get("target_role") or "target role not set"
        profile = f":green-badge[:material/person: Profile loaded: {role} · ATS {data.get('ats_score', 'n/a')}]"
    else:
        profile = ":orange-badge[:material/person_off: No profile yet: upload a CV in the sidebar for personal advice]"
    st.markdown(
        f"{profile} :blue-badge[:material/database: {backend} · 2,899 career records] "
        f":violet-badge[:material/psychology: Prompt {ACTIVE['advisor_system']} · {provider_label()}] "
        f":gray-badge[:material/verified_user: Career & study questions only]"
    )


def _render_answer(i: int, msg: dict, show_debug: bool) -> None:
    text = msg["content"]
    body, _, sources = text.partition(SOURCES_MARKER)
    st.markdown(body)
    if sources:
        n = sources.count("- [S")
        with st.expander(f":material/menu_book: Sources ({n})"):
            st.markdown(sources)
    meta = msg.get("meta") or {}
    if show_debug and meta:
        with st.expander(":material/troubleshoot: How this answer was built"):
            r = meta.get("route") or {}
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Route", r.get("label", "-"))
            c2.metric("Decided by", r.get("method", "-"))
            c3.metric("Latency", f"{(meta.get('latency_ms') or 0) / 1000:.1f}s")
            c4.metric("Model", (meta.get("model") or "retrieval-only").split("/")[-1])
            if meta.get("generation"):
                st.caption(f"Generation: {meta['generation']} · question type: {meta.get('question_type') or '-'}")
            if meta.get("hits"):
                st.caption("Retrieved from the knowledge base (cosine similarity; floor 0.30, career weak-match floor 0.40)")
                st.dataframe(meta["hits"], hide_index=True, use_container_width=True)
            elif r.get("label") in ("out_of_scope", "prompt_attack"):
                st.caption("Refused by the scope guardrail before any retrieval or LLM call.")
    if meta.get("learned", {}).get("n_similar"):
        lg = meta["learned"]
        st.caption(f":material/school: Improved using feedback on {lg['n_similar']} similar question(s) "
                   f"({lg['n_good']} helpful, {lg['n_bad']} not helpful).")
    fb = st.feedback("thumbs", key=f"advisor_fb_{i}")
    done = st.session_state.get(f"advisor_fb_done_{i}")
    if fb == 1 and done != "up":
        _save_feedback(i, "up")
        st.session_state[f"advisor_fb_done_{i}"] = "up"
        st.toast("Thanks! After a quick review, similar questions will learn from it.")
    elif fb == 0 and done is None:
        from src.backend.feedback_store import REASONS
        with st.form(key=f"advisor_fb_form_{i}", border=True):
            st.caption("What went wrong? After a team review, your feedback teaches the advisor for similar questions.")
            reason = st.radio("Reason", list(REASONS), horizontal=True, key=f"advisor_fb_reason_{i}",
                              format_func=lambda r: {"not_answered": "Didn't answer my question", "inaccurate": "Wrong / inaccurate",
                                                     "too_long": "Too long / unfocused", "no_sources": "Not specific enough",
                                                     "wrong_refusal": "Wrongly refused", "other": "Other"}[r])
            comment = st.text_input("What should a good answer include? (optional)", key=f"advisor_fb_comment_{i}")
            if st.form_submit_button("Send feedback"):
                _save_feedback(i, "down", reason, comment)
                st.session_state[f"advisor_fb_done_{i}"] = "down"
                st.toast("Thanks! The advisor will use this for similar questions.")
                st.rerun()
    elif done == "down":
        st.caption(":material/check: Feedback recorded. Similar questions will avoid this.")


def _ask(question: str, uid: str) -> None:
    """Answer one question. The user + assistant turn is appended only when the answer is complete, so a run
    interrupted by a newly submitted question leaves no half-finished turn (the question stays queued)."""
    from src.backend.chatbot import answer

    msgs = st.session_state["advisor_messages"]
    history = [{"role": m["role"], "content": m["content"]} for m in msgs] + [{"role": "user", "content": question}]
    try:
        res = answer(history, user_id=uid)
        hits = [{"#": f"S{k}", "source": h.get("source"), "type": h.get("doc_type"),
                 "score": round(float(h.get("score", 0)), 3),
                 "ref": (h.get("metadata") or {}).get("career_id") or (h.get("metadata") or {}).get("career_name")
                 or (h.get("metadata") or {}).get("title") or (h.get("metadata") or {}).get("section") or "",
                 "text": (h.get("text") or "")[:160]} for k, h in enumerate(res.get("hits") or [], 1)]
        reply = {"role": "assistant", "content": res.get("text") or "I couldn't generate an answer, please rephrase.",
                 "meta": {"route": res.get("route"), "model": res.get("model"), "latency_ms": res.get("latency_ms"),
                          "system_version": res.get("system_version"), "hits": hits,
                          "generation": res.get("generation"), "learned": res.get("learned") or {},
                          "question_type": (res.get("question_profile") or {}).get("type"),
                          "revised": res.get("revised")}}
    except Exception as e:  # noqa: BLE001
        reply = {"role": "assistant", "content": f"Sorry, something went wrong: {e}"}
    msgs.append({"role": "user", "content": question})
    msgs.append(reply)


def _transcript() -> str:
    lines = [f"# SkillPath AI Career Advisor conversation ({datetime.now():%Y-%m-%d %H:%M})", ""]
    for m in st.session_state["advisor_messages"]:
        lines += [f"**{'You' if m['role'] == 'user' else 'Advisor'}:**", m["content"], ""]
    return "\n".join(lines)


def render_career_advisor(data, uid: str = None) -> None:
    st.session_state.setdefault("advisor_messages", [])
    msgs = st.session_state["advisor_messages"]

    head, ctrl = st.columns([3, 2], vertical_alignment="bottom")
    with head:
        st.markdown("### :material/forum: SkillPath Career Advisor")
        st.caption("Your AI mentor for careers and studies. Answers are grounded in our career knowledge base "
                   "and your analysed profile, with sources you can check.")
        # Final validation (review 4 §2 items 6-7): say clearly what the current mode can and cannot do
        from src.utilities.llm_provider import llm_provider as _mode
        if _mode() == "none":
            st.info("**Retrieval-only mode (no AI key).** Answers are assembled from our knowledge base, so they can't follow "
                    "exact counts, word limits or tables, and plans are shown as generated. Add a free key in the sidebar for "
                    "full conversational answers.", icon=":material/info:")
        elif _mode() == "local":
            st.info("**Local model (experimental).** Answers come from a small model on this computer: expect 30-120 seconds per "
                    "answer and less precise formatting than the hosted model.", icon=":material/info:")
    with ctrl:
        b1, b2, b3 = st.columns(3)
        if b1.button(":material/add_comment: New chat", use_container_width=True, disabled=not msgs):
            st.session_state["advisor_messages"] = []
            for k in [k for k in st.session_state if str(k).startswith("advisor_fb")]:
                del st.session_state[k]
            st.rerun()
        b2.download_button(":material/download: Save", _transcript(), file_name="skillpath_advisor_chat.md",
                           use_container_width=True, disabled=not msgs)
        show_debug = b3.toggle("Explain", value=st.session_state.get("advisor_debug", False), key="advisor_debug",
                               help="Show how each answer was built: route, retrieved records, scores, model, latency")
    _status_chips(data)

    if not msgs:
        with st.chat_message("assistant", avatar=":material/school:"):
            st.markdown("**Hi! I'm your Career Advisor.** I only help with careers and studies: choosing a path, "
                        "closing skill gaps, resumes and ATS, interviews, courses, certifications and study plans. "
                        "Pick a question below or type your own.")
        groups = ([("Using your profile", STARTERS_PROFILE)] if data else []) + [("Exploring careers & studies", STARTERS_EXPLORE)]
        for title, qs in groups:
            st.caption(title)
            cols = st.columns(len(qs))
            for col, q in zip(cols, qs):
                if col.button(q, key=f"starter_{q}", use_container_width=True):
                    st.session_state["advisor_pending"] = q
                    st.rerun()

    for i, m in enumerate(msgs):
        with st.chat_message(m["role"], avatar=":material/person:" if m["role"] == "user" else ":material/school:"):
            if m["role"] == "user":
                st.markdown(m["content"])
            else:
                _render_answer(i, m, show_debug)

    # E34: question QUEUE. The input box stays usable while an answer is being generated: a new submission
    # interrupts the run, joins the queue, and every queued question is answered in order. A question leaves
    # the queue only after its answer has been stored, so an interrupted answer is simply redone.
    queue = st.session_state.setdefault("advisor_queue", [])
    pending = st.session_state.pop("advisor_pending", None)
    if pending:
        queue.append(pending)
    typed = st.chat_input("Ask about careers, skills, interviews or studies… (you can send the next question anytime)")
    if typed and (not queue or queue[-1] != typed):
        queue.append(typed)
    if queue:
        for i, q in enumerate(queue):
            with st.chat_message("user", avatar=":material/person:"):
                st.markdown(q)
                if i > 0:
                    st.caption(":material/schedule: queued, will be answered next")
        with st.chat_message("assistant", avatar=":material/school:"):
            with st.spinner(f"Answering… ({len(queue)} question{'s' if len(queue) > 1 else ''} in the queue)"):
                _ask(queue[0], uid)
        queue.pop(0)
        st.rerun()
