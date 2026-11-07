# Hugging Face Space (SDK: docker). Build context = repository root:
#   docker build -f deploy/huggingface/Dockerfile -t skillpath-ai .
FROM python:3.12-slim

# chromium + driver for the Selenium Naukri scraper; build tools for some wheels
RUN apt-get update && apt-get install -y --no-install-recommends chromium chromium-driver build-essential curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface CHROME_BIN=/usr/bin/chromium
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt
# bake the embedding model into the image (no download at cold start)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY --chown=user . .
EXPOSE 7860
CMD ["bash", "deploy/huggingface/start.sh"]
