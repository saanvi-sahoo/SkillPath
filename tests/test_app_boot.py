"""Boot the real Streamlit script the way `streamlit run` / Streamlit Cloud do: from a different working
directory, so only the script's own folder is on sys.path. Catches import-order bugs such as
`ModuleNotFoundError: No module named 'src'` (E28). Keyless env -> no network/LLM calls."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r'''
import sys
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(sys.argv[1], default_timeout=300)
at.run()
errs = [e.value for e in at.exception]
print("EXCEPTIONS:", errs)
print("TABS:", [t.label for t in at.tabs][:1])
sys.exit(1 if errs else 0)
'''


def test_frontend_boots_outside_repo(tmp_path):
    env = {**os.environ, "SKILLPATH_NO_DOTENV": "1", "LLM_PROVIDER": "none", "VECTOR_BACKEND": "local",
           "MONGODB_URI": "", "GROQ_API_KEY": "", "GEMINI_API_KEY": "", "PYTHONPATH": ""}
    r = subprocess.run([sys.executable, "-c", SCRIPT, str(ROOT / "src" / "frontend" / "frontend.py")],
                       cwd=tmp_path, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "Career Advisor" in r.stdout
