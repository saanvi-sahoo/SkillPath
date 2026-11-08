"""Single place that loads .env (E26). Set SKILLPATH_NO_DOTENV=1 to ignore .env entirely, e.g. for a
keyless instance running from the same checkout (no API keys can leak into it).

E29: third-party libraries also call load_dotenv() at import time (webdriver_manager does, and it finds
the repo's .env by walking up from .venv). PYTHON_DOTENV_DISABLED=1 is python-dotenv's global switch
(>= 1.1) and stops *every* load_dotenv() in the process, ours and theirs."""
import os

from dotenv import load_dotenv

if os.getenv("SKILLPATH_NO_DOTENV") == "1":
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"


def load_env() -> None:
    if os.getenv("SKILLPATH_NO_DOTENV") == "1":
        os.environ["PYTHON_DOTENV_DISABLED"] = "1"
        return
    # E29: real environment variables (shell, Streamlit/hosting secrets) take precedence over .env;
    # the inherited code used override=True, which silently ignored e.g. `LLM_PROVIDER=none streamlit run ...`
    load_dotenv(override=False)
