---
title: SkillPath AI
emoji: 🎓
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# SkillPath AI: Hugging Face Space deployment

This file is the Space's README (the front-matter above configures the Space). To deploy:

1. Create a Space at https://huggingface.co/new-space: **SDK = Docker**, blank template.
2. Settings → **Variables and secrets** → add `GROQ_API_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY`, and `MONGODB_URI` (Atlas Network Access must allow `0.0.0.0/0`, because Space IPs are dynamic).
3. Push the repository with a Hugging Face **access token** (Settings → Access Tokens → *write*). Passwords are not accepted for git:
   ```bash
   cp deploy/huggingface/Dockerfile Dockerfile        # Spaces build ./Dockerfile
   cp deploy/huggingface/README.md README_SPACE.md    # the Space needs this front-matter in README.md
   git remote add space https://huggingface.co/spaces/<user>/skillpath-ai
   git push space main                                # username = HF user, password = the token
   ```
Notes: the free CPU Space has 16 GB RAM, which is plenty for MiniLM. The Selenium scraper uses the bundled Chromium. Without `MONGODB_URI`, the container builds a local vector store at start-up (about 20 s).
