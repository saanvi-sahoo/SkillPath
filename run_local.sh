#!/usr/bin/env bash
# SkillPath AI: start everything locally with one command (docs/runbook.md §0).
#
#   ./run_local.sh            # full local app: Mistral (Ollama) + MongoDB Atlas -> http://localhost:8501
#   ./run_local.sh --keyless  # same as the deployed app: no .env, no keys        -> http://localhost:8502
#   Ctrl+C stops everything this script started.
set -uo pipefail
cd "$(dirname "$0")"

MODE="full"; [ "${1:-}" = "--keyless" ] && MODE="keyless"
PORT=8501; [ "$MODE" = "keyless" ] && PORT=8502
mkdir -p logs

say() { printf "\033[1;34m[skillpath]\033[0m %s\n" "$*"; }
free_port() { local pids; pids=$(lsof -ti tcp:"$1" 2>/dev/null); [ -n "$pids" ] && { say "freeing port $1"; kill $pids 2>/dev/null; sleep 1; }; }

# 1. Python environment (created once, reused afterwards)
if [ ! -x .venv/bin/python ]; then
  say "creating .venv (first run only, ~5 min)"
  python3.12 -m venv .venv && .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -r requirements.txt || { say "dependency install failed"; exit 1; }
fi
PY=.venv/bin/python

# 2. Local LLM (full mode): make sure Ollama is serving and the model exists
if [ "$MODE" = "full" ]; then
  if ! curl -s -m 2 http://127.0.0.1:11434/api/tags >/dev/null; then
    if command -v ollama >/dev/null; then
      say "starting Ollama"; (ollama serve > logs/ollama.log 2>&1 &)
      for _ in $(seq 1 20); do curl -s -m 2 http://127.0.0.1:11434/api/tags >/dev/null && break; sleep 1; done
    else
      say "Ollama not installed -> app will answer in retrieval-only mode (install: brew install ollama)"
    fi
  fi
  if command -v ollama >/dev/null && ! ollama list 2>/dev/null | grep -q '^mistral'; then
    say "downloading mistral (one time, ~4 GB)"; ollama pull mistral
  fi
fi

# 3. Start services
free_port "$PORT"
if [ "$MODE" = "full" ]; then
  free_port 8000
  say "starting API on http://127.0.0.1:8000 (log: logs/api.log)"
  $PY -m uvicorn src.backend.fastapi_ends.api_endpoint:app --port 8000 > logs/api.log 2>&1 &
  API_PID=$!
  trap 'say "stopping"; kill $API_PID 2>/dev/null; exit 0' INT TERM
  ENVV=()
else
  # identical to the Streamlit Cloud deployment: ignore .env, local vectors, in-process pipeline
  ENVV=(env SKILLPATH_NO_DOTENV=1 VECTOR_BACKEND=local PIPELINE_MODE=inprocess OLLAMA_BASE_URL=http://127.0.0.1:9)
fi

say "starting app on http://localhost:$PORT  (Ctrl+C to stop)"
( for _ in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:$PORT/_stcore/health && { open "http://localhost:$PORT" 2>/dev/null; break; }; sleep 1; done ) &
${ENVV[@]+"${ENVV[@]}"} $PY -m streamlit run src/frontend/frontend.py --server.headless true --server.port "$PORT" --browser.gatherUsageStats false
kill ${API_PID:-} 2>/dev/null
