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
1. Sign in at https://share.streamlit.io with GitHub (an account with access to `saanvi-sahoo/SkillPath`).
2. Open the **prefilled deploy form**:
   https://share.streamlit.io/deploy?repository=saanvi-sahoo/SkillPath&branch=main&mainModule=src/frontend/frontend.py
   (or **Create app → Deploy a public app from GitHub** → repo `saanvi-sahoo/SkillPath`, branch `main`, main file `src/frontend/frontend.py`). Pick an App URL, e.g. `skillpath-ai`.
3. **Advanced settings** → Python **3.12** (required: the CPU torch wheel in `requirements.txt` is pinned for cp312 x86_64). Paste the **Secrets** (TOML; root-level keys become environment variables). Choose one variant:

   **Variant A: works immediately, no Atlas network change.** The app builds its career/guide/job index locally on the first chat (~15–20 s, then cached for the container's life). Profile chunks live in the container and are lost on restart.
   ```toml
   GROQ_API_KEY = "..."
   GEMINI_API_KEY = "..."
   TAVILY_API_KEY = "..."
   PIPELINE_MODE = "inprocess"
   VECTOR_BACKEND = "local"
   ```
   **Variant B: shared MongoDB Atlas.** The same keys plus `MONGODB_URI` and `MONGODB_DB = "skillpath_ai"`, without `VECTOR_BACKEND`. This needs Atlas Network Access to allow `0.0.0.0/0`, because **Streamlit Cloud has no stable outbound IPs** (its fixed-IP allowlist was retired; see the Streamlit forum threads "IP addresses of Streamlit community cloud servers" and "What IP address range can I whitelist for my DB connection?"). The database stays protected by the 32-character database-user password, but anyone who obtains the URI could connect from anywhere, so keep it only in Streamlit secrets and rotate it if it ever leaks:
   ```bash
   atlas accessLists create 0.0.0.0/0 --comment "Streamlit Community Cloud" --projectId 6aef8bc9b64186873a8b7606
   ```
   Or in the UI: Atlas → Security → Network Access → Add IP Address → *Allow access from anywhere*.
4. Click **Deploy**. The first build takes about 5–10 minutes (uv installs the requirements; the torch CPU wheel is 210 MB).
5. **Verify:** open the app, then go to the Career Advisor tab → "Which career fits Python, SQL and dashboards?" → it answers with cited `career_XXXX` records. Then upload a resume/JD → Analyze Profile.
6. Known limits on Streamlit Cloud: no Chrome, so the Naukri scraper is skipped (LinkedIn still works); the container sleeps after inactivity, and the first request after waking takes about 30 s.

The build was **pre-tested locally** in a `linux/amd64` `python:3.12-slim` container with uv (the same installer Streamlit Cloud uses). Log: `reports/streamlit_cloud_sim.log`.

### 3b. Hugging Face Space (if a PRO account is available)
1. `python deploy/huggingface/push_space.py --space <hf-user>/skillpath-ai` (uses `HF_TOKEN` from `.env`). It creates a private Docker Space, sets the API keys as Space secrets, and uploads the code (personal data and `.env` excluded).
2. Atlas Network Access must include `0.0.0.0/0`.
3. The image: Python 3.12, Chromium (Selenium), CPU torch, MiniLM baked in. FastAPI runs on :8000 internally and Streamlit on :7860.

## 4. Tokens and rotation
- Keep tokens only in `.env` or Space secrets. Rotate any token that was ever pasted into chat or email.
- HF token: https://huggingface.co/settings/tokens. GitHub SSH keys: https://github.com/settings/keys. Atlas database users: Atlas → Database Access.
