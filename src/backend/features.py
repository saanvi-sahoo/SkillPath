"""
Per-request feature switch for the E38 pipeline (conversation state, structured career-query rewrite, adaptive
roadmap inputs, failure notices). A context variable, not a global, so an A/B evaluation can answer the same case
with and without E38 in parallel threads without one arm leaking into the other.

  E38_PIPELINE=true|false   default for the app (true after E38 passed its held-out comparison)
"""
from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Optional

_E38: ContextVar[Optional[bool]] = ContextVar("e38", default=None)


def e38_on() -> bool:
    v = _E38.get()
    return (os.getenv("E38_PIPELINE", "true").lower() == "true") if v is None else v


def set_e38(value: Optional[bool]):
    return _E38.set(value)
