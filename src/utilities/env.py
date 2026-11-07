"""Single place that loads .env (E26). Set SKILLPATH_NO_DOTENV=1 to ignore .env entirely, e.g. for a
keyless public demo instance running from the same checkout (no API keys can leak into it)."""
import os

from dotenv import load_dotenv


def load_env() -> None:
    if os.getenv("SKILLPATH_NO_DOTENV") == "1":
        return
    load_dotenv(override=True)
