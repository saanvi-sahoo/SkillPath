"""
Prompt registry: prompts are versioned files in src/prompts/templates/<name>_<version>.md.

Why files instead of inline strings?
  * diffs show exactly what changed between prompt versions
  * the evaluation harness (src/eval/run_prompt_eval.py) can A/B any two versions
  * docs/prompt_scripting.md records why each version exists and its scores

Switch the live version with env vars, e.g. PROMPT_ADVISOR_SYSTEM=v1, or edit ACTIVE below.
"""
import json
import os
from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PROMPT_DIR / "templates"

ACTIVE = {
    "advisor_system": os.getenv("PROMPT_ADVISOR_SYSTEM", "v5"),  # E32: v5 > v4 (paired, 51 cases) > v3 > v2 > v1
    "scope_router": os.getenv("PROMPT_SCOPE_ROUTER", "v1"),
    "refusal": "v1",
    "greeting": "v1",
}


@lru_cache(maxsize=None)
def load_prompt(name: str, version: str | None = None) -> str:
    version = version or ACTIVE[name]
    path = TEMPLATE_DIR / f"{name}_{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt '{name}' version '{version}' not found at {path}")
    return path.read_text(encoding="utf-8")


def list_versions(name: str) -> list[str]:
    return sorted(p.stem.rsplit("_", 1)[1] for p in TEMPLATE_DIR.glob(f"{name}_v*.md"))


@lru_cache(maxsize=None)
def load_json(filename: str):
    return json.loads((PROMPT_DIR / filename).read_text(encoding="utf-8"))
