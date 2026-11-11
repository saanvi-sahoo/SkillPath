<h1 align="center">SkillPath AI</h1>
<p align="center"><em>AI-powered career upskilling: resume ↔ JD analysis, a career-only RAG advisor over MongoDB Atlas, and validated 30-day roadmaps</em></p>

Sabudh Foundation internship project (team: Saanvi Sahoo, Amrit Singh, Isa Ahmed Khan; mentor: Ms. Suparna Dutta), built on the previous batch's **UpskillxAI** (its original README is kept below).

<p align="center">
  <a href="https://saanvi-sahoo-skillpath-srcfrontendfrontend-qwxzcn.streamlit.app"><img alt="Open the live app" src="https://static.streamlit.io/badges/streamlit_badge_black_white.svg"></a>
  &nbsp;<a href="reports/SkillPath_AI_Implementation_Report.pdf"><img alt="Full report (PDF)" src="https://img.shields.io/badge/Report-PDF-1D4ED8.svg"></a>
  &nbsp;<a href="docs/README.md"><img alt="Documentation" src="https://img.shields.io/badge/Docs-17_guides-334E68.svg"></a>
</p>

## Live app and links

| What | Link | Notes |
|---|---|---|
| **Live app** (Streamlit Community Cloud) | **https://saanvi-sahoo-skillpath-srcfrontendfrontend-qwxzcn.streamlit.app** | Works with no keys (retrieval-only answers). For AI-written answers, open the sidebar → *AI engine & your own API key* (Groq / Gemini / OpenAI / OpenRouter). If the app was idle it shows "wake up": click it and wait about 30 s |
| Full implementation report (PDF, 57 pages) | [reports/SkillPath_AI_Implementation_Report.pdf](reports/SkillPath_AI_Implementation_Report.pdf) | Summary, results and every document in one file. Rebuild: `python docs/build_pdf_report.py` |
| Documentation index | [docs/README.md](docs/README.md) | Runbook, scenarios, embeddings, RAG, Atlas, chatbot, prompt training, experiment log |
| Source code | https://github.com/saanvi-sahoo/SkillPath | Branch `main`; app entry point `src/frontend/frontend.py` |
| **Career dataset** (source of truth) | [view](https://github.com/saanvi-sahoo/SkillPath/blob/main/docs/emerging_tech_career_dataset_cleaned.csv) · [raw CSV](https://github.com/saanvi-sahoo/SkillPath/raw/main/docs/emerging_tech_career_dataset_cleaned.csv) | 2,900 × 13; quality audit: [reports/data_quality/career_dataset_report.md](reports/data_quality/career_dataset_report.md) |
| Knowledge base (curated guides) | [src/data/knowledge_base/](src/data/knowledge_base/) | 9 guides, 37 sections embedded for the chatbot |
| Retrieval benchmarks | [reports/embeddings/](reports/embeddings/) · [reports/heldout/](reports/heldout/) | Career P@5 (by query type), guide Hit@k, Atlas checks, held-out results tables |
| Prompt evaluation results | [reports/prompt_eval/](reports/prompt_eval/) · [docs/experiment_log.md](docs/experiment_log.md) | Prompt v1–v6 A/B tests (E0–E35) |
| Vector database | [MongoDB Atlas, project "SkillPath AI"](https://cloud.mongodb.com/v2/6aef8bc9b64186873a8b7606#/overview) | Team login needed. Cluster `skillpath-cluster` → *Browse Collections* → database `skillpath_ai`. Setup: [docs/mongodb_atlas_setup.md](docs/mongodb_atlas_setup.md) |
| App settings, logs, secrets | [share.streamlit.io](https://share.streamlit.io) | App owner only: ⋮ → *Settings → Secrets*, *Manage app* for logs and reboot. See [docs/deployment.md](docs/deployment.md) |

### REST API

The deployed app is Streamlit only (Streamlit Cloud doesn't host a separate API server); the cloud app runs the pipeline in-process. The FastAPI backend runs locally with `./run_local.sh` (or the `uvicorn` command below):

| Check | Link |
|---|---|
| Interactive API docs (try every endpoint) | http://localhost:8000/docs |
| OpenAPI schema | http://localhost:8000/openapi.json |
| Endpoints | `POST /pipeline/run` (analyse resume + JD) · `POST /chat` (Career Advisor) · `POST /roadmap` (30-day plan) · `POST /skills/compare` (exact skill gaps) · `POST /jobs`, `/jobs/slice`, `/profiles`, `/jobs-with-profiles` |

Example: `curl -X POST localhost:8000/skills/compare -H 'Content-Type: application/json' -d '{"candidate_skills":["Python","MySQL"],"required_skills":["SQL","Power BI"]}'`

## What's built

| What | How | Status |
|---|---|---|
| Resume/JD parsing + skill analysis | LangGraph pipeline; LLM structured output, or rule-based when keyless | ✅ verified end to end |
| Career knowledge base (source of truth) | `docs/emerging_tech_career_dataset_cleaned.csv` → 2,899 × 384 MiniLM vectors | ✅ |
| Vector database | **MongoDB Atlas Vector Search** (`skillpath_ai`: careers, knowledge + jobs, private profiles, feedback) | ✅ live, verified |
| RAG precision | Cross-encoder re-ranking: career P@5 0.767 → 0.858, guide Hit@3 0.90 → 0.967 | ✅ |
| Career Advisor chatbot | Career/study-only guardrail, question profiler, cited RAG answers, question queue | ✅ |
| Prompt script training | Versioned prompts v1–v8 tested on frozen unseen sets (120 + 40 cases), intent routing, claim-level citation checks; **v7 live** (0.95 vs v6 0.90) with the **E38 real-world pipeline** (conversation memory, career-change search 0.825→0.895, adaptive roadmap, failure handling); v8 candidate. [Final validation](docs/final_validation.md): fresh journeys 8/8, smoke tests 8/9, ready for demonstration, not yet for public release. [Report](https://claude.ai/artifact/Ah127g8yDze1b9DKfmYedZ) · [method](docs/evaluation.md) | ✅ |
| Feedback learning | 👍/👎 feedback stored in Atlas and reused on similar questions | ✅ |
| Skill gaps + 30-day roadmap | Exact canonical comparison, prioritised + validated plan, role-specific capstone | ✅ |
| Runs without paid keys | Keyless mode, local Mistral (Ollama), or the visitor's own API key | ✅ |

## Run locally

**One command:** `./run_local.sh` → http://localhost:8501 (or `./run_local.sh --keyless` → http://localhost:8502, same as the deployed app).

```bash
python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env                               # add keys + MONGODB_URI
python -m src.rag.ingest --sources all             # embeddings -> Atlas (or local fallback)
uvicorn src.backend.fastapi_ends.api_endpoint:app --port 8000
streamlit run src/frontend/frontend.py
python -m pytest -q tests                          # 40 offline tests
```

---

# Inherited README (UpskillxAI, previous batch)

<h1 align="center">
  UpskillxAI
</h1>
<p align="center">
  <em>An Intelligent, Agentic Career Orchestration Platform</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue.svg">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.100%2B-00a393.svg">
  <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B.svg">
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-Agentic_AI-orange.svg">
  <img alt="Selenium" src="https://img.shields.io/badge/Selenium-Web_Scraping-43B02A.svg">
</p>

---

## <img src="https://raw.githubusercontent.com/feathericons/feather/master/icons/list.svg" width="24" height="24" align="center" alt="TOC"/> Table of Contents
- [Overview](#overview)
- [The Problem](#the-problem)
- [Our Solution](#our-solution)
- [System Architecture](#system-architecture)
- [Performance Benchmarks](#performance-benchmarks)
- [Key Features](#key-features)
- [Installation & Usage](#installation--usage)

---

## <img src="https://raw.githubusercontent.com/feathericons/feather/master/icons/book-open.svg" width="24" height="24" align="center" alt="Overview"/> Overview

**UpskillxAI** is an end-to-end, multi-agent AI pipeline designed to stop candidates from applying to jobs blindly. 

By taking a user's Resume and a target Job Description (JD), the system autonomously calculates a deterministic ATS match score, identifies exact semantic skill gaps, and aggressively scrapes the web for live job listings and curated learning paths—all orchestrated via a highly parallelized **LangGraph Directed Acyclic Graph (DAG)**.

---

## <img src="https://raw.githubusercontent.com/feathericons/feather/master/icons/alert-triangle.svg" width="24" height="24" align="center" alt="Problem"/> The Problem

1. **The Black Box of ATS:** Candidates apply to hundreds of jobs without understanding why they are automatically rejected by Applicant Tracking Systems.
2. **Keyword vs. Semantic Matching:** Traditional resume analyzers look for exact keyword matches. They fail to understand that a "Frontend Developer" applying for "DevOps" lacks deep architectural skills.
3. **Fragmented Workflow:** Discovering what skills you lack, finding high-quality resources to learn them, and finding jobs that fit your newly acquired skills currently takes hours of manual searching across multiple platforms.

---

## <img src="https://raw.githubusercontent.com/feathericons/feather/master/icons/check-circle.svg" width="24" height="24" align="center" alt="Solution"/> Our Solution

We engineered a centralized orchestration platform that handles the entire pipeline in under 60 seconds:
1. **Document Ingestion:** Uses Reducto API and PyMuPDF to extract text from any format cleanly.
2. **Resilient AI Brain:** Utilizes a fallback chain (`Gemini 2.5` → `Groq Llama 3.3`) strictly bound to Pydantic schemas to output deterministic JSON skill gap analysis.
3. **Parallel I/O Processing:** Instead of sequential loading, LangGraph executes headless Selenium web scrapers (Naukri/LinkedIn) and Tavily API searches at the *exact same time*.
4. **Contextual Memory:** All parsed data is serialized to a persistent state, empowering a localized Chatbot Agent to converse with the user about their specific profile.

---

## <img src="https://raw.githubusercontent.com/feathericons/feather/master/icons/layers.svg" width="24" height="24" align="center" alt="Architecture"/> System Architecture

![System Architecture](assets/image.png)

The platform is divided into three distinct layers:
* **Frontend:** A responsive Streamlit dashboard with Session State memory to prevent data-wiping on refresh.
* **Backend:** A FastAPI server invoking the LangGraph orchestrator.
* **Persistence:** A localized JSON memory store bridging the gap between the heavy background pipeline and the lightweight conversational agent.

---

## <img src="https://raw.githubusercontent.com/feathericons/feather/master/icons/zap.svg" width="24" height="24" align="center" alt="Performance"/> Performance Benchmarks

![Performance Benchmarks](assets/fig5_1_node_times.png)

By architecting the pipeline as a LangGraph DAG, we separated Compute-bound tasks (LLM Inference) from I/O-bound tasks (Web Scraping). 

* **Sequential Execution Wait Time:** ~67 Seconds
* **Our Parallel DAG Wait Time:** ~49 Seconds
* **Net Latency Reduction:** **~35%**

---

## <img src="https://raw.githubusercontent.com/feathericons/feather/master/icons/star.svg" width="24" height="24" align="center" alt="Features"/> Key Features

- **Multi-Model LLM Fallback:** Zero-downtime inference with automatic routing to secondary models if the primary API hits rate limits.
- **Dynamic DOM Scrapers:** Custom Selenium-based headless browsers with explicit `WebDriverWait` states to extract React-based Job Portals bypassing anti-bot blockers.
- **Strict JSON Enforcement:** Regex sanitization combined with Langchain structured outputs ensures the UI never crashes due to markdown hallucinations.
- **"Ghost Link" Extraction:** Cleanly scrapes LinkedIn job details without triggering CAPTCHAs or requiring authentication.
- **Memory-Injected Agent:** A specialized Chatbot tool (`query_career_memory`) allows the LLM to access the user's hard drive state securely, ensuring 0% hallucination on ATS scores.

---

## <img src="https://raw.githubusercontent.com/feathericons/feather/master/icons/terminal.svg" width="24" height="24" align="center" alt="Installation"/> Installation & Usage

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/AI_FOR_EDU_NEW.git
cd AI_FOR_EDU_NEW
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup Environment Variables
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_google_key
GROQ_API_KEY=your_groq_key
TAVILY_API_KEY=your_tavily_key
```

### 4. Run the Backend & Frontend
Boot up the FastAPI server and Streamlit dashboard:
```bash
# Run the FastAPI Backend (if running decoupled)
fastapi dev src/backend/fastapi_ends/api_endpoint.py

# Run the Streamlit Dashboard
streamlit run src/frontend/frontend.py
```