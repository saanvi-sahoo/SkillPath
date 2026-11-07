"""
Single entry point for "run the analysis pipeline and persist it", shared by the FastAPI route
(/pipeline/run) and the Streamlit UI's in-process mode (used where no separate API server can run,
e.g. Streamlit Community Cloud; see docs/deployment.md).
"""
from __future__ import annotations

import json
import os
from typing import Dict

from src.rag import config


async def run_and_persist(resume_input: str, jd_input: str, target_role: str = "", location: str = "",
                          user_id: str | None = None) -> Dict:
    from src.backend.main_runner import build_main_graph
    from src.rag.ingest import ingest_profile_safely
    import asyncio

    state = {"resume_input": resume_input, "jd_input": jd_input, "target_role": target_role,
             "location": location, "status_messages": []}
    final_state = await build_main_graph().ainvoke(state)
    path = config.memory_path(user_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(final_state, f, indent=4, default=str)
    except Exception as e:  # noqa: BLE001
        print(f"Failed to save memory.json: {e}")
    await asyncio.to_thread(ingest_profile_safely, user_id)  # re-embed profile for the chatbot; never raises
    return final_state


def run_and_persist_sync(*args, **kwargs) -> Dict:
    import asyncio
    return asyncio.run(run_and_persist(*args, **kwargs))


API_URL = os.getenv("SKILLPATH_API_URL", "http://127.0.0.1:8000")
# api      : always call the FastAPI server (local default)
# inprocess: run the LangGraph pipeline inside the Streamlit process (Streamlit Cloud)
# auto     : try the API, fall back to in-process if it is unreachable
PIPELINE_MODE = os.getenv("PIPELINE_MODE", "auto").lower()
