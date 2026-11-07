"""
Deploy the repository to a Hugging Face Space (SDK: docker).

    python deploy/huggingface/push_space.py --space <hf-user>/skillpath-ai [--public] [--no-secrets]

Reads HF_TOKEN (and the app secrets) from .env. Creates the Space (private by default), sets the app
secrets as Space secrets (never as files), and uploads the code, excluding everything in EXCLUDE.
"""
import argparse
import os
from pathlib import Path

from dotenv import dotenv_values
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SECRETS = ["GROQ_API_KEY", "GEMINI_API_KEY", "TAVILY_API_KEY", "MONGODB_URI", "REDUCTO_API_KEY"]
EXCLUDE = [".env", ".env.*", ".git/*", ".venv/*", "**/.venv/*", "embedding_experiment/.venv/*", "**/__pycache__/*",
           "src/backend/memory.json", "src/backend/loaders/resume_data.json", "reports/chat_logs/*",
           "src/data/vector_store/*", "reports/prompt_eval/logs/*", "README.md", "Dockerfile", "*.DS_Store",
           "reports/final_project_report/_extensions/*"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--space", required=True, help="<hf-user>/<space-name>")
    p.add_argument("--public", action="store_true")
    p.add_argument("--no-secrets", action="store_true")
    a = p.parse_args()
    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    api = HfApi(token=env["HF_TOKEN"])
    print("[hf] logged in as", api.whoami()["name"])
    api.create_repo(a.space, repo_type="space", space_sdk="docker", private=not a.public, exist_ok=True)
    if not a.no_secrets:
        for k in SECRETS:
            if env.get(k):
                api.add_space_secret(a.space, k, env[k])
                print(f"[hf] secret set: {k}")
    api.upload_folder(folder_path=str(ROOT), repo_id=a.space, repo_type="space", ignore_patterns=EXCLUDE,
                      commit_message="Deploy SkillPath AI")
    api.upload_file(path_or_fileobj=str(HERE / "Dockerfile"), path_in_repo="Dockerfile", repo_id=a.space, repo_type="space")
    api.upload_file(path_or_fileobj=str(HERE / "README.md"), path_in_repo="README.md", repo_id=a.space, repo_type="space")
    print(f"[hf] pushed -> https://huggingface.co/spaces/{a.space}")


if __name__ == "__main__":
    main()
