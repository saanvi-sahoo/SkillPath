"""Progress bars for the E38 evaluation runs:  python -m src.eval.progress  (reads the result files, no LLM)."""
from __future__ import annotations

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "reports" / "heldout"


def _bar(done: int, total: int, width: int = 24) -> str:
    total = max(total, 1)
    n = round(width * min(done, total) / total)
    return f"[{'█' * n}{'░' * (width - n)}] {done:>3}/{total:<3} {100 * done / total:5.1f}%"


def _latest(pattern, pred):
    for f in sorted(glob.glob(str(ROOT / pattern)), reverse=True):
        try:
            d = json.loads(Path(f).read_text())
        except Exception:  # noqa: BLE001 - file being written
            continue
        if pred(d):
            return d
    return None


def _pass(rows, v):
    rs = [r for r in rows if r["version"] == v]
    return f"{v} {sum(r['passed'] for r in rs)}/{len(rs)}" if rs else ""


def main():
    runs = [
        ("Hosted Gemini · 120 cases (v7, v7+e38)", "heldout_eval_heldout_v3_*_p*.json",
         lambda d: d.get("set") == "heldout_v3" and "v8+e38" in d["versions"] + d.get("versions_partial", []) and len(d["rows"]) > 3, 262),
        ("Local Mistral · 50 multi-turn × 2", "heldout_eval_heldout_v3_*_p*.json",
         lambda d: d.get("set") == "heldout_v3" and any(r.get("model") == "mistral" for r in d["rows"]), 100),
        ("Keyless · 120 cases × 2", "heldout_eval_heldout_v3_*_p*.json",
         lambda d: d.get("set") == "heldout_v3" and len(d["rows"]) >= 200 and all(r.get("model") is None for r in d["rows"]), 240),
    ]
    print("E38 evaluation progress")
    for name, pat, pred, total in runs:
        d = _latest(pat, pred)
        rows = d["rows"] if d else []
        extra = "  ".join(x for x in (_pass(rows, v) for v in (d["versions"] if d else [])) if x)
        print(f"  {name:36s} {_bar(len(rows), total)}  {extra}")
    for name, pat, total in [("Deployed Groq · 10 journeys × 2", "journeys_deployed_*_p*.json", 20),
                             ("Local Mistral · 10 journeys × 2", "journeys_local_*_p*.json", 20)]:
        d = _latest(pat, lambda x: True)
        rows = d["rows"] if d else []
        extra = "  ".join(f"{v} {sum(r['success'] for r in rows if r['version'] == v)}/{sum(r['version'] == v for r in rows)} journeys"
                          for v in (d["versions"] if d else []))
        print(f"  {name:36s} {_bar(len(rows), total)}  {extra}")


if __name__ == "__main__":
    main()
