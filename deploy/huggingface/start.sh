#!/usr/bin/env bash
# Starts FastAPI (internal :8000) + Streamlit (public :7860, the HF Spaces port).
set -euo pipefail
cd "$(dirname "$0")/../.."
# Secrets (GROQ_API_KEY, GEMINI_API_KEY, TAVILY_API_KEY, MONGODB_URI) come from Space settings -> Secrets.
if [ -z "${MONGODB_URI:-}" ]; then
  echo "[start] MONGODB_URI not set -> building local vector store"
  python -m src.rag.ingest --sources careers knowledge jobs --backend local || echo "[start] ingest failed (continuing)"
fi
uvicorn src.backend.fastapi_ends.api_endpoint:app --host 127.0.0.1 --port 8000 &
exec streamlit run src/frontend/frontend.py --server.port 7860 --server.address 0.0.0.0 --server.headless true
