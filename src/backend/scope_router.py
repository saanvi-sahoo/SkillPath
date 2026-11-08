"""
Scope router: decides whether a message is career/study (answer), greeting (chat),
out_of_scope (polite refusal) or prompt_attack (refusal).

Hybrid design (see docs/chatbot.md#scope-guardrail):
  1. Embedding kNN over labelled anchors in src/prompts/scope_examples.json.
     ~5 ms, no API call. Decides when it is confident.
  2. LLM classifier (prompt: scope_router_vN) only for ambiguous messages or
     short follow-ups that need chat history to interpret.

Mode can be forced with SCOPE_ROUTER_MODE = hybrid | knn | llm (used by the eval harness).
"""
from __future__ import annotations

import json
import os
import re
import time
from functools import lru_cache
from typing import Dict, List

import numpy as np

from src.prompts.registry import load_json, load_prompt
from src.rag.embedder import embed_symmetric, embed_texts

LABELS = ("career_study", "greeting", "out_of_scope", "prompt_attack")
KNN_K = 5
# Tuned with src/eval/run_prompt_eval.py; log changes in docs/experiment_log.md
KNN_MIN_TOP_SIM = float(os.getenv("SCOPE_KNN_MIN_TOP_SIM", "0.55"))
KNN_MIN_VOTE_SHARE = float(os.getenv("SCOPE_KNN_MIN_VOTE_SHARE", "0.80"))
FOLLOWUP_MAX_WORDS = 6
# llama-3.1-8b-instant was retired by Groq (found 2026-11-08); gpt-oss-20b is the cheapest served model
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "groq:openai/gpt-oss-20b")

_ATTACK_PATTERNS = re.compile(
    r"(ignore (all|any|the|your) (previous|prior|above)|system prompt|you are now|jailbreak|\bDAN\b|"
    r"forget (your|all) (rules|instructions)|reveal (your|the) (instructions|prompt))",
    re.I,
)


@lru_cache(maxsize=1)
def _anchors():
    data = load_json("scope_examples.json")
    texts, labels = [], []
    for label in LABELS:
        for t in data.get(label, []):
            texts.append(t)
            labels.append(label)
    return embed_texts(texts), labels


def knn_classify(message: str) -> Dict:
    vecs, labels = _anchors()
    sims = vecs @ embed_symmetric(message)
    top = np.argsort(-sims)[:KNN_K]
    votes: Dict[str, float] = {}
    for i in top:
        votes[labels[i]] = votes.get(labels[i], 0.0) + max(float(sims[i]), 0.0)
    total = sum(votes.values()) or 1.0
    label = max(votes, key=votes.get)
    return {"label": label, "vote_share": round(votes[label] / total, 3), "top_sim": round(float(sims[top[0]]), 3)}


def llm_classify(message: str, history: List[Dict]) -> Dict:
    from src.utilities.brain import get_robust_llm

    hist = "\n".join(f"{m['role']}: {m['content'][:300]}" for m in history[-6:]) or "(none)"
    prompt = load_prompt("scope_router").format(history=hist, message=message)
    llm = get_robust_llm(primary_model=ROUTER_MODEL, temperature=0.0)
    raw = llm.invoke(prompt).text
    m = re.search(r"\{.*\}", raw, re.S)
    data = json.loads(m.group(0)) if m else {}
    label = data.get("label", "career_study")
    return {"label": label if label in LABELS else "career_study", "reason": data.get("reason", "")}


def route(message: str, history: List[Dict] | None = None, mode: str | None = None) -> Dict:
    """Return {'label', 'method', 'latency_ms', ...diagnostics}."""
    history = history or []
    mode = (mode or os.getenv("SCOPE_ROUTER_MODE", "hybrid")).lower()
    t0 = time.perf_counter()

    def done(res: Dict) -> Dict:
        res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return res

    if mode == "off":  # eval only: measures the system prompt's own guardrail without the router
        return done({"label": "career_study", "method": "off"})

    if _ATTACK_PATTERNS.search(message):
        return done({"label": "prompt_attack", "method": "regex"})

    knn = knn_classify(message)
    if mode == "knn":
        return done({**knn, "method": "knn"})

    is_followup = len(message.split()) <= FOLLOWUP_MAX_WORDS and any(m["role"] == "assistant" for m in history)
    confident = knn["top_sim"] >= KNN_MIN_TOP_SIM and knn["vote_share"] >= KNN_MIN_VOTE_SHARE
    # follow-ups ("any free ones?") are meaningless without history -> always ask the LLM
    if mode == "hybrid" and confident and not is_followup:
        return done({**knn, "method": "knn"})

    from src.utilities.llm_provider import llm_provider
    if llm_provider() in ("none", "local"):
        # E26: no LLM -> kNN on the follow-up expanded with the previous user turn.
        # E29: also for local Ollama (a 7B router call adds 10-40 s; kNN allow/refuse accuracy is 1.0 on 42 cases)
        prev = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        k2 = knn_classify(f"{prev} {message}") if (is_followup and prev) else knn
        return done({**k2, "method": "knn (no-LLM)"})
    try:
        llm = llm_classify(message, history)
        return done({**llm, "knn": knn, "method": "llm"})
    except Exception as e:  # noqa: BLE001 - classifier failure: be permissive inside an ongoing career chat
        fallback = "career_study" if (history and knn["label"] == "out_of_scope" and knn["top_sim"] < 0.4) else knn["label"]
        return done({"label": fallback, "knn": knn, "method": "knn_fallback", "error": str(e)[:200]})
