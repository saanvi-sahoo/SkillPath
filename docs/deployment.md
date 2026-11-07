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
Access: **SagarSwain05** is a collaborator. This machine authenticates with an SSH key (`~/.ssh/id_ed25519`, public key added at https://github.com/settings/keys).
```bash
ssh -T git@github.com                     # "Hi SagarSwain05! You've successfully authenticated"
git remote add origin git@github.com:saanvi-sahoo/SkillPath.git
git push -u origin main
```
Day-to-day: create a branch per feature (`git checkout -b feature/<name>`), push, and open a Pull Request for team review.

## 3. Hugging Face Space (Docker)
The files are in `deploy/huggingface/`:
- `Dockerfile`: Python 3.12 + Chromium for the Selenium scraper, with MiniLM baked into the image.
- `start.sh`: FastAPI on :8000 (internal) and Streamlit on :7860 (public).
- `README.md`: the Space front-matter.

Steps:
1. Create the Space: https://huggingface.co/new-space → SDK **Docker** → visibility **Private** (recommended until reviewed).
2. Space **Settings → Variables and secrets**: add `GROQ_API_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY`, `MONGODB_URI`. In Atlas, Network Access must include `0.0.0.0/0`, because Space IPs change.
3. Push. The Space builds the root `Dockerfile` and reads its config from the root `README.md`, so a deploy step copies those in:
   ```bash
   python deploy/huggingface/push_space.py --space <hf-user>/skillpath-ai   # uses HF_TOKEN from .env
   ```
4. Watch the build logs on the Space page. First build takes about 10 minutes; cold start about 30 s.

Without `MONGODB_URI`, the container builds a local vector store at start-up (about 20 s). User profile data then lives only in the container and is lost on restart.

## 4. Tokens and rotation
- Keep tokens only in `.env` or Space secrets. Rotate any token that was ever pasted into chat or email.
- HF token: https://huggingface.co/settings/tokens. GitHub SSH keys: https://github.com/settings/keys. Atlas database users: Atlas → Database Access.
