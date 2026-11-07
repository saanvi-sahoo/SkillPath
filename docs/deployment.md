# Deployment: GitHub and Hugging Face Spaces

## 1. What is published and what is not

| Never published (`.gitignore`) | Why |
|---|---|
| `.env` | API keys, Atlas URI, HF token |
| `src/backend/memory.json`, `src/backend/loaders/resume_data.json` | Personal resume data (doc §12) |
| `reports/chat_logs/` | User chat text |
| `src/data/vector_store/` | Rebuildable binary vectors |
| `.venv/`, `embedding_experiment/.venv/` | Local environments |

Before every push:
```bash
git status --short                      # review every file
git grep -nE "gsk_|tvly-|AIza|hf_[A-Za-z0-9]{20}|mongodb\+srv://[^<]" -- . ':!docs/deployment.md'   # must print nothing
```

## 2. GitHub (`https://github.com/saanvi-sahoo/SkillPath`)
Access: SagarSwain05 is a collaborator. This Mac pushes with the SSH key `~/.ssh/id_ed25519`, which is registered on the **saanvi-sahoo** account (agreed with the team).
```bash
ssh -T git@github.com                     # "Hi saanvi-sahoo! You've successfully authenticated"
git remote add origin git@github.com:saanvi-sahoo/SkillPath.git
git push -u origin main
```
Day-to-day: create a branch per feature (`git checkout -b feature/<name>`), push, and open a Pull Request for team review.

## 3. Hosting options (checked 2026-11-08)

| Option | Cost | Status | Notes |
|---|---|---|---|
| **Streamlit Community Cloud** | free | ✅ **Recommended**. Ready to deploy (needs one browser login) | Runs only Streamlit, so the UI runs the pipeline **in-process** (`PIPELINE_MODE=auto` falls back automatically when no API server is reachable) |
| Hugging Face Space (Docker) | **requires HF PRO** (about $9/month) | ⛔ Blocked: `402 Payment Required`, *"hosting Gradio and Docker Spaces on free cpu-basic requires a PRO subscription"* | Files are ready in `deploy/huggingface/` (Dockerfile, start.sh, README, `push_space.py`) |
| Local / college server | free | ✅ | `uvicorn` + `streamlit` (runbook §2) |

### 3a. Streamlit Community Cloud (free), step by step
1. Open https://share.streamlit.io and **Continue with GitHub** (an account with access to `saanvi-sahoo/SkillPath`). Authorise Streamlit.
2. **Create app → Deploy a public app from GitHub**:
   - Repository `saanvi-sahoo/SkillPath`, branch `main`
   - Main file path `src/frontend/frontend.py`
   - App URL e.g. `skillpath-ai`
3. **Advanced settings**: Python **3.12**. **Secrets** (TOML; root-level keys become environment variables):
   ```toml
   GROQ_API_KEY = "..."
   GROQ_API_KEY_2 = "..."
   GEMINI_API_KEY = "..."
   TAVILY_API_KEY = "..."
   MONGODB_URI = "mongodb+srv://skillpath_app:...@skillpath-cluster.fozgv6t.mongodb.net/?retryWrites=true&w=majority&appName=SkillPath"
   PIPELINE_MODE = "inprocess"
   ```
4. **Atlas network access:** Streamlit Cloud IPs are dynamic, so allow `0.0.0.0/0`. Access is still protected by the 32-character database password:
   ```bash
   atlas accessLists create 0.0.0.0/0 --comment "Streamlit Cloud"
   ```
5. **Deploy.** The first build installs the requirements (CPU torch on Linux) in about 5–10 minutes.
6. Known limit: the Naukri scraper needs Chrome, which Streamlit Cloud doesn't provide, so the job list then comes from LinkedIn only. The rest of the pipeline is unaffected.

### 3b. Hugging Face Space (if a PRO account is available)
1. `python deploy/huggingface/push_space.py --space <hf-user>/skillpath-ai` (uses `HF_TOKEN` from `.env`). It creates a private Docker Space, sets the API keys as Space secrets, and uploads the code (personal data and `.env` excluded).
2. Atlas Network Access must include `0.0.0.0/0`.
3. The image: Python 3.12, Chromium (Selenium), CPU torch, MiniLM baked in. FastAPI runs on :8000 internally and Streamlit on :7860.

## 4. Tokens and rotation
- Keep tokens only in `.env` or Space secrets. Rotate any token that was ever pasted into chat or email.
- HF token: https://huggingface.co/settings/tokens. GitHub SSH keys: https://github.com/settings/keys. Atlas database users: Atlas → Database Access.
