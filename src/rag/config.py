"""
Central configuration for the UpskillxAI embedding + RAG layer.

Every tunable that affects embeddings or retrieval lives here so experiments
are reproducible: if you change a value, log it in docs/experiment_log.md.
All values can be overridden with environment variables (see .env.example).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

from src.utilities.env import load_env; load_env()

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ── Embedding model ──────────────────────────────────────────────────────────
# all-MiniLM-L6-v2 (384-dim). E11: on the 24 labelled career queries it beat bge-small
# (strict P@5 0.767 vs 0.733) and it is the model of the team's embedding starter kit, so
# vectors in careers_embeddings_v1 stay compatible across team scripts.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))
# L2-normalised vectors => cosine similarity == dot product.
NORMALIZE_EMBEDDINGS = True
# Asymmetric retrieval models want an instruction on the QUERY side only (never on documents).
_QUERY_INSTRUCTIONS = {"BAAI/bge-small-en-v1.5": "Represent this sentence for searching relevant passages: "}
QUERY_INSTRUCTION = os.getenv("EMBEDDING_QUERY_INSTRUCTION", _QUERY_INSTRUCTIONS.get(EMBEDDING_MODEL, ""))

# ── Chunking ─────────────────────────────────────────────────────────────────
# MiniLM truncates at 256 tokens, bge-small at 512. 150 words ~ 200 tokens fits both.
CHUNK_MAX_WORDS = int(os.getenv("CHUNK_MAX_WORDS", "150"))
CHUNK_OVERLAP_WORDS = int(os.getenv("CHUNK_OVERLAP_WORDS", "30"))

# ── Vector store ─────────────────────────────────────────────────────────────
# "mongo"  -> MongoDB Atlas Vector Search (requires MONGODB_URI)
# "local"  -> numpy file store under data/vector_store (offline dev / CI)
# "auto"   -> mongo if MONGODB_URI is set, else local
VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "auto").lower()
MONGODB_URI = os.getenv("MONGODB_URI", "")
# Names follow docs/SkillPath_AI_End_to_End_Project_Documentation.pdf section 8.2.
MONGODB_DB = os.getenv("MONGODB_DB", "skillpath_ai")
# One collection per data class so private resume data never sits in the shared career KB
# (project doc section 12: "never place sensitive resume contents in the shared career collection").
COLLECTIONS = {
    #  source      (collection,                                         vector index name)
    "careers":   (os.getenv("MONGODB_CAREERS_COLLECTION", "careers_embeddings_v1"), "career_vector_index"),
    "knowledge": (os.getenv("MONGODB_KNOWLEDGE_COLLECTION", "knowledge_chunks_v1"), "knowledge_vector_index"),
    # Atlas M0 allows max 3 search indexes per cluster (E19): jobs share the knowledge collection,
    # separated by the indexed `source` field.
    "jobs":      (os.getenv("MONGODB_JOBS_COLLECTION", "knowledge_chunks_v1"), "knowledge_vector_index"),
    "profile":   (os.getenv("MONGODB_PROFILE_COLLECTION", "user_profile_chunks_v1"), "profile_vector_index"),
}
LOCAL_STORE_DIR = Path(os.getenv("LOCAL_STORE_DIR", PROJECT_ROOT / "src" / "data" / "vector_store"))

# ── Retrieval ────────────────────────────────────────────────────────────────
TOP_K = int(os.getenv("RAG_TOP_K", "6"))
# Atlas ANN: candidates scanned per result. 15-20x limit is Atlas' recommendation.
NUM_CANDIDATES_MULTIPLIER = int(os.getenv("RAG_NUM_CANDIDATES_MULTIPLIER", "20"))
# Chunks below this cosine score are dropped as irrelevant noise. MODEL-SPECIFIC:
# MiniLM: 0.30 (E12 calibration). bge-small would need ~0.60 (scores compressed high).
MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.30"))
# Career results below this are flagged weak_match (ask a clarifying question instead).
CAREER_MIN_SCORE = float(os.getenv("CAREER_MIN_SCORE", "0.40"))

# ── Data sources ─────────────────────────────────────────────────────────────
# Source of truth for the Career Advisor (Kaggle "Emerging Tech Career Path Dataset with Skills", cleaned, 13 cols).
CAREERS_CSV = Path(os.getenv("CAREERS_CSV", PROJECT_ROOT / "docs" / "emerging_tech_career_dataset_cleaned.csv"))
# 2,848/2,900 rows carry the same placeholder salary/growth; only other values are shown to users.
PLACEHOLDER_SALARY = 140100.0
PLACEHOLDER_GROWTH = 0.05
# Feature flag for the career-retrieval adapter (project doc section 12, phase C).
CAREER_RAG_ENABLED = os.getenv("CAREER_RAG_ENABLED", "true").lower() == "true"
MEMORY_JSON = PROJECT_ROOT / "src" / "backend" / "memory.json"
LINKEDIN_JOBS_JSON = PROJECT_ROOT / "master_jobs_detailed.json"
NAUKRI_JOBS_JSON = PROJECT_ROOT / "src" / "backend" / "scraper" / "jobs.json"
KNOWLEDGE_DIR = PROJECT_ROOT / "src" / "data" / "knowledge_base"

# Default user id. The Streamlit UI gives every browser session its own id (E26) so profiles of
# different visitors never mix (memory file + private profile chunks are both keyed by user_id).
DEFAULT_USER_ID = os.getenv("UPSKILL_USER_ID", "default")
USER_MEMORY_DIR = PROJECT_ROOT / "src" / "backend" / "user_memory"


def memory_path(user_id: str = None) -> Path:
    """Analysed-profile file for a user: memory.json for the local default user, else user_memory/<id>.json."""
    import re as _re
    if not user_id or user_id == DEFAULT_USER_ID:
        return MEMORY_JSON
    return USER_MEMORY_DIR / (_re.sub(r"[^A-Za-z0-9_-]", "", user_id)[:64] + ".json")

REPORTS_DIR = PROJECT_ROOT / "reports" / "embeddings"
