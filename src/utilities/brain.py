"""
brain.py
========
LangGraph state machine — the AI brain of the project.

What it does:
    1. Takes resume_text + job_description from state
    2. Calls Gemini to extract skills, find gaps, score ATS, generate learning path
    3. Dumps everything back into state for teammates to consume


Install dependencies:
    pip install langgraph langchain-google-genai python-dotenv

Input formats supported
-----------------------
resume_text:
    • str  — raw text, passed through as-is
    • dict — output of reducto_loader.load_resume(); the dict MUST contain at
             least one of these keys (checked in order):
               "text"        → used directly
               "raw_text"    → used directly
               "skills"      → list/str joined into a skills block
             Any extra keys (name, email, experience, education …) that are
             present in the dict are also serialised and appended so Gemini
             sees the full picture.

job_description:
    • str  — raw text OR Jina markdown → passed through as-is
    • dict — Naukri scraper output; expected keys (all optional):
               "Skills"      → list or str
               "Description" → str
             Falls back to str(dict) if neither key is found.

How teammates consume the state:
    from brain import run_brain, SkillBrainState

    result = run_brain(
        resume_text=load_resume("resume.pdf"),   # dict OK
        job_description=get_job_description(url) # markdown str OK
    )

    result["skill_gaps"]       # list[str]  — missing skills
    result["learning_path"]    # list[dict] — {skill, search_queries: [3 strings]}
    result["ats_score"]        # int 0-100
    result["candidate_skills"] # list[str]
    result["required_skills"]  # list[str]

Author: [Your Name]
"""

import os
from langfuse import observe
import json
import re
from typing import TypedDict, Union
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

load_dotenv(override=True)


# ─────────────────────────────────────────────────────────────────────────────
#  INPUT NORMALISATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _normalise_resume(raw: Union[str, dict]) -> str:
    """
    Accept either a plain string or the dict returned by reducto_loader.load_resume().

    reducto_loader typically returns something like:
        {
            "text": "...",          # full extracted text  (preferred)
            "raw_text": "...",      # alternative full text key
            "skills": [...],        # list of skill strings
            "name": "...",
            "email": "...",
            "experience": [...],
            "education": [...],
            ...
        }

    Strategy (checked in order):
      1. If "text" key exists and is non-empty → use it directly.
      2. If "raw_text" key exists and is non-empty → use it directly.
      3. Otherwise, reconstruct a readable block from every known key so
         Gemini still gets as much signal as possible.
    """
    if isinstance(raw, str):
        return raw.strip()

    if not isinstance(raw, dict):
        # Fallback: coerce anything else to string
        return str(raw).strip()

    # Preferred: full pre-extracted text
    for full_text_key in ("text", "raw_text"):
        value = raw.get(full_text_key, "")
        if isinstance(value, str) and value.strip():
            return value.strip()

    # Reconstruct from individual keys
    parts: list[str] = []

    # Personal info
    for info_key in ("name", "email", "phone", "location", "linkedin", "github"):
        val = raw.get(info_key)
        if val:
            parts.append(f"{info_key.capitalize()}: {val}")

    # Skills — may be a list or a string
    skills = raw.get("skills")
    if skills:
        if isinstance(skills, list):
            parts.append("Skills: " + ", ".join(str(s) for s in skills))
        else:
            parts.append(f"Skills: {skills}")

    # Experience — may be a list of dicts or strings
    experience = raw.get("experience")
    if experience:
        parts.append("Experience:")
        if isinstance(experience, list):
            for item in experience:
                parts.append(f"  - {item}" if not isinstance(item, dict) else
                             f"  - {item.get('title', '')} at {item.get('company', '')}: "
                             f"{item.get('description', '')}")
        else:
            parts.append(f"  {experience}")

    # Education
    education = raw.get("education")
    if education:
        parts.append("Education:")
        if isinstance(education, list):
            for item in education:
                parts.append(f"  - {item}" if not isinstance(item, dict) else
                             f"  - {item.get('degree', '')} from {item.get('institution', '')}")
        else:
            parts.append(f"  {education}")

    # Any remaining keys we haven't handled above
    handled = {"text", "raw_text", "name", "email", "phone", "location",
                "linkedin", "github", "skills", "experience", "education"}
    for key, val in raw.items():
        if key not in handled and val:
            parts.append(f"{key.replace('_', ' ').capitalize()}: {val}")

    return "\n".join(parts).strip() or str(raw)


def _normalise_jd(raw: Union[str, dict]) -> str:
    """
    Accept either:
      • A plain string (raw text or Jina markdown) → returned as-is.
      • A dict from the Naukri scraper with keys "Skills" and/or "Description".

    Naukri scraper example output:
        {
            "Skills": ["Python", "Docker", "Kubernetes"],   # or a plain string
            "Description": "We are looking for a ..."
        }
    """
    if isinstance(raw, str):
        return raw.strip()

    if not isinstance(raw, dict):
        return str(raw).strip()

    parts: list[str] = []

    skills = raw.get("Skills") or raw.get("skills")
    if skills:
        if isinstance(skills, list):
            parts.append("Required Skills: " + ", ".join(str(s) for s in skills))
        else:
            parts.append(f"Required Skills: {skills}")

    description = raw.get("Description") or raw.get("description")
    if description:
        parts.append(f"Job Description:\n{description}")

    # Catch-all: serialise any remaining keys
    handled = {"Skills", "skills", "Description", "description"}
    for key, val in raw.items():
        if key not in handled and val:
            parts.append(f"{key}: {val}")

    return "\n\n".join(parts).strip() or str(raw)


# ─────────────────────────────────────────────────────────────────────────────
#  STATE DEFINITION
# ─────────────────────────────────────────────────────────────────────────────

class SkillBrainState(TypedDict):
    # ── INPUTS (set before running) ──────────────────────────────────────────
    # Accepts str OR dict (see _normalise_resume / _normalise_jd above)
    resume_text:       Union[str, dict]
    job_description:   Union[str, dict]

    # ── EXTRACTED (set by analyse_node) ──────────────────────────────────────
    candidate_skills:  list[str]
    required_skills:   list[str]

    # ── COMPUTED (set by analyse_node) ───────────────────────────────────────
    skill_gaps:        list[str]
    ats_score:         int

    # ── OUTPUT FOR TEAMMATES ─────────────────────────────────────────────────
    # Each item: {"skill": str, "search_queries": [str, str, str]}
    learning_path:     list[dict]

    # ── META ─────────────────────────────────────────────────────────────────
    error:             str


# ─────────────────────────────────────────────────────────────────────────────
#  GEMINI CLIENT
# ─────────────────────────────────────────────────────────────────────────────

from langchain_groq import ChatGroq

# gemini-2.5-flash was retired by Google (404 "no longer available", found 2026-11-08).
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# Free-tier models tried in order when a quota error occurs.
_FREE_TIER_MODELS = [
     "groq:openai/gpt-oss-20b",
    "groq:qwen/qwen3.8-27b",
    GEMINI_MODEL
    ]

def get_base_llm(model: str = GEMINI_MODEL, temperature: float = 0.2, **kwargs):
    """Return a base LLM client (Groq or Gemini) pinned to *model*."""
    # Force max_retries to 0 so we fail instantly to the next model in the fallback chain instead of waiting
    kwargs.setdefault("max_retries", 0)
    
    if model.startswith("groq:"):
        actual_model = model.replace("groq:", "")
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY not found in .env")
        return ChatGroq(
            model=actual_model,
            api_key=api_key,
            temperature=temperature,
            **kwargs
        )
    else:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY not found in .env")
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            **kwargs
        )

def get_robust_llm(primary_model: str = GEMINI_MODEL, temperature: float = 0.2, **kwargs):
    """
    Returns an LLM bound with a multi-model fallback chain.
    If primary_model hits a quota exhaustion, it seamlessly falls back to the next models.
    """
    primary_llm = get_base_llm(primary_model, temperature=temperature, **kwargs)
    
    fallback_llms = []
    for fallback_model in _FREE_TIER_MODELS:
        if fallback_model != primary_model:
            fallback_llms.append(get_base_llm(fallback_model, temperature=temperature, **kwargs))
            
    if fallback_llms:
        return primary_llm.with_fallbacks(fallback_llms)
    return primary_llm

def get_robust_structured_llm(schema, primary_model: str = GEMINI_MODEL, temperature: float = 0.2, **kwargs):
    """
    Returns an LLM bound with structured output and a multi-model fallback chain.
    """
    primary_llm = get_base_llm(primary_model, temperature=temperature, **kwargs).with_structured_output(schema)
    
    fallback_llms = []
    for fallback_model in _FREE_TIER_MODELS:
        if fallback_model != primary_model:
            fallback_llms.append(get_base_llm(fallback_model, temperature=temperature, **kwargs).with_structured_output(schema))
            
    if fallback_llms:
        return primary_llm.with_fallbacks(fallback_llms)
    return primary_llm

# ─────────────────────────────────────────────────────────────────────────────
#  PROMPT
# ─────────────────────────────────────────────────────────────────────────────

ANALYSIS_PROMPT = """
You are an expert resume analyst and career coach.

Analyze the resume and job description below. Return ONLY a valid JSON object — no markdown, no backticks, no explanation.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

Return this exact JSON structure:
{{
  "candidate_skills": ["Languages: Python", "Frameworks: Django"],
  "required_skills": ["Languages: Python", "Tools: Docker"],
  "skill_gaps": ["Tools: Docker", "Tools: Kubernetes"],
  "ats_score": 72,
  "learning_path": [
    {{
      "skill": "Docker",
      "search_queries": [
        "best free course for Docker beginners",
        "Docker tutorial project based learning",
        "Docker roadmap 2024 how to learn"
      ]
    }}
  ]
}}

Rules:
- candidate_skills: every technical skill, tool, language, framework found in the resume. Format each string strictly as "Category: Skill" (e.g., "Languages: Python", "Tools: Git"). Use broad categories like Languages, Frameworks, Tools, Soft Skills.
- required_skills: every skill explicitly or implicitly required by the JD. Format each string as "Category: Skill".
- skill_gaps: skills in required_skills that are missing or not mentioned in the resume. Format each string as "Category: Skill".
- ats_score: integer 0-100. Score based on keyword overlap, experience match, and formatting signals
- learning_path: one entry per skill_gap (use just the skill name without the category prefix here), each with exactly 3 search_queries a person can paste into Google
- search_queries must be specific and actionable — not generic like "learn python"
- Return ONLY the JSON. No other text.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  NODE
# ─────────────────────────────────────────────────────────────────────────────

@observe()
def analyse_node(state: SkillBrainState) -> SkillBrainState:
    """
    Core LangGraph node.

    Reads:  state["resume_text"]    (str OR dict from reducto_loader)
            state["job_description"] (str OR dict from Naukri scraper)
    Writes: all output fields into state.
    """

    # ── Normalise inputs regardless of source ────────────────────────────────
    resume = _normalise_resume(state.get("resume_text", ""))
    jd     = _normalise_jd(state.get("job_description", ""))

    if not resume or not jd:
        return {
            **state,
            "error": "resume_text and job_description are both required (got empty after normalisation).",
            "candidate_skills": [],
            "required_skills":  [],
            "skill_gaps":       [],
            "ats_score":        0,
            "learning_path":    [],
        }

    import time

    prompt = ANALYSIS_PROMPT.format(resume=resume, jd=jd)
    raw    = ""
    last_error: str = ""

    for model in _FREE_TIER_MODELS:
        # Each model gets up to 2 attempts (handles transient 429 bursts)
        for attempt in range(2):
            try:
                print(f"  [brain] trying model={model} attempt={attempt + 1}")
                llm      = get_base_llm(model)
                response = llm.invoke([HumanMessage(content=prompt)])
                raw      = response.text.strip()  # .text: Gemini 3.x returns content as a list of parts

                # Strip markdown code fences if Gemini wraps the JSON anyway
                raw = re.sub(r"^```(?:json)?", "", raw).strip()
                raw = re.sub(r"```$",          "", raw).strip()

                data = json.loads(raw)

                return {
                    **state,
                    "candidate_skills": data.get("candidate_skills", []),
                    "required_skills":  data.get("required_skills",  []),
                    "skill_gaps":       data.get("skill_gaps",       []),
                    "ats_score":        int(data.get("ats_score",    0)),
                    "learning_path":    data.get("learning_path",    []),
                    "error":            "",
                }

            except json.JSONDecodeError as e:
                # Bad JSON from this model — no point retrying same model
                last_error = f"Model {model} returned invalid JSON: {e}\nRaw: {raw[:300]}"
                print(f"  [brain] JSON error with {model}: {e}")
                break  # try next model

            except Exception as e:
                err_str = str(e)
                last_error = err_str

                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    # Quota hit — wait once then retry the same model
                    if attempt == 0:
                        wait = 15
                        match = re.search(r"retryDelay.*?(\d+)s", err_str)
                        if match:
                            wait = min(int(match.group(1)), 60)
                        print(f"  [brain] 429 on {model}, waiting {wait}s then retrying…")
                        time.sleep(wait)
                        continue  # retry same model
                    # Second attempt also hit quota → fall through to next model
                    print(f"  [brain] 429 again on {model}, moving to next model…")

                else:
                    # 404 NOT_FOUND, 400, or any other error →
                    # log it and try the next model (don't bail out)
                    print(f"  [brain] {model} failed ({err_str[:120]}), trying next model…")

                break  # move to next model in _FREE_TIER_MODELS

    # All models exhausted
    return {
        **state,
        "error": (
            f"All free-tier models exhausted or failed.\n"
            f"Last error: {last_error}\n\n"
            "Fix options:\n"
            "  1. Wait a few minutes and retry (per-minute quota resets)\n"
            "  2. Create a new API key at https://aistudio.google.com\n"
            "  3. Enable billing on your Google Cloud project for higher quotas"
        ),
        "candidate_skills": [],
        "required_skills":  [],
        "skill_gaps":       [],
        "ats_score":        0,
        "learning_path":    [],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  GRAPH ASSEMBLY
# ─────────────────────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(SkillBrainState)
    graph.add_node("analyse", analyse_node)
    graph.add_edge(START, "analyse")
    graph.add_edge("analyse", END)
    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
#  PUBLIC FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def run_brain(
    resume_text:     Union[str, dict],
    job_description: Union[str, dict],
) -> SkillBrainState:
    """
    Main entry point. Accepts all three input formats out of the box:

        # 1. reducto_loader dict
        result = run_brain(
            resume_text=load_resume("resume.pdf"),
            job_description=get_job_description(url)
        )

        # 2. Plain text / Jina markdown
        result = run_brain(
            resume_text="John Doe | Python, Django ...",
            job_description="We need a backend engineer with ..."
        )

        # 3. Naukri scraper dict
        result = run_brain(
            resume_text=load_resume("resume.pdf"),
            job_description={"Skills": ["Python", "Docker"], "Description": "..."}
        )

    Returns SkillBrainState with all fields populated.
    """
    graph = build_graph()

    initial_state: SkillBrainState = {
        "resume_text":      resume_text,      # normalised inside analyse_node
        "job_description":  job_description,  # normalised inside analyse_node
        "candidate_skills": [],
        "required_skills":  [],
        "skill_gaps":       [],
        "ats_score":        0,
        "learning_path":    [],
        "error":            "",
    }

    return graph.invoke(initial_state)


# ─────────────────────────────────────────────────────────────────────────────
#  STANDALONE TEST — python brain.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # ── Test 1: reducto_loader-style dict resume + plain-text JD ─────────────
    SAMPLE_RESUME_DICT = {
        "name":  "Rhythm Kamra",
        "email": "itsmerhythmmk@gmail.com",
        "phone": "+91-6284185832",
        "skills": [
            "Python", "Django", "JavaScript", "React", "Next.js",
            "Node.js", "MySQL", "MongoDB", "Git/GitHub", "HTML5",
            "CSS3", "SQL", "Firebase",
        ],
        "experience": [
            {
                "title":       "Full Stack Developer Intern",
                "company":     "XYZ Corp",
                "description": "Built a full-stack web application using Django and React. "
                               "Implemented LDAP authentication for enterprise login system. "
                               "Developed REST APIs consumed by React Native mobile app.",
            }
        ],
        "education": [
            {"degree": "B.Tech Computer Science", "institution": "Punjab University", "year": "2024"}
        ],
    }

    # ── Test 2: Naukri scraper-style dict JD ─────────────────────────────────
    SAMPLE_JD_DICT = {
        "Skills": ["Python", "AWS", "Docker", "Kubernetes", "scikit-learn",
                   "TensorFlow", "Apache Spark", "Airflow", "GitHub Actions"],
        "Description": (
            "Software Engineer — Data & AI Platform\n\n"
            "We are looking for a backend engineer with 2+ years of experience "
            "in Python and cloud platforms (AWS or Azure). You will build and "
            "maintain ML pipelines using scikit-learn and TensorFlow, containerise "
            "services with Docker/Kubernetes, and automate workflows with Airflow "
            "and GitHub Actions."
        ),
    }

    print("=" * 60)
    print("  SKILL BRAIN — Running analysis (dict inputs)...")
    print("=" * 60)

    result = run_brain(
        resume_text=SAMPLE_RESUME_DICT,
        job_description=SAMPLE_JD_DICT,
    )

    if result["error"]:
        print(f"\n❌ Error: {result['error']}")
    else:
        print(f"\n✅ ATS Score: {result['ats_score']} / 100")

        print(f"\n📋 Candidate Skills ({len(result['candidate_skills'])}):")
        for s in result["candidate_skills"]:
            print(f"   • {s}")

        print(f"\n📌 Required Skills ({len(result['required_skills'])}):")
        for s in result["required_skills"]:
            print(f"   • {s}")

        print(f"\n🚨 Skill Gaps ({len(result['skill_gaps'])}):")
        for s in result["skill_gaps"]:
            print(f"   ✗ {s}")

        print(f"\n📚 Learning Path:")
        for item in result["learning_path"]:
            print(f"\n   [{item['skill']}]")
            for i, q in enumerate(item["search_queries"], 1):
                print(f"   {i}. {q}")

    print("\n" + "=" * 60)
    print("  State keys available to teammates:")
    print("  result['skill_gaps']       →", type(result["skill_gaps"]))
    print("  result['learning_path']    →", type(result["learning_path"]))
    print("  result['ats_score']        →", type(result["ats_score"]))
    print("  result['candidate_skills'] →", type(result["candidate_skills"]))
    print("  result['required_skills']  →", type(result["required_skills"]))
    print("=" * 60)