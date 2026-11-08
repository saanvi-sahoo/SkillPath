import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List

from loguru import logger
from langfuse import observe
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langchain_community.tools.tavily_search import TavilySearchResults

try:
    from src.utilities.brain import SkillBrainState
except ModuleNotFoundError:
    from brain import SkillBrainState


LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True, parents=True)

logger.remove()

custom_format = (
    "<fg #F4D03F>{time:YYYY-MM-DD HH:mm:ss.SSS}</> | "
    "<level>{level: <8}</level> | "
    "<fg #FF69B4>Proc-{process.id}</>:"
    "<fg #FF8C00>Thread-{thread.id}</> | "
    "<fg #00FF00>{module}</>:"
    "<fg #00FFFF>{function}</>:"
    "<fg #FF7F50>{line}</> - "
    "<level>{message}</level>"
)

logger.add(sys.stdout, colorize=True, format=custom_format, level="DEBUG")

logger.add(
    str(LOG_DIR / "net_surf.log"),  
    filter=lambda record: record["file"].name == "net_surf.py",
    colorize=True,         
    format=custom_format,
    rotation="10 MB"       
)


from src.utilities.env import load_env; load_env()

# E29: no import-time key requirement. Deployed keyless apps have no GEMINI key; the LLM used here comes
# from brain.get_robust_llm (server keys, the visitor's own key, local Ollama) and the node is optional.
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

from src.utilities.brain import get_robust_llm, GEMINI_MODEL
try:  # E26: unused module-level client; must not fail import in keyless mode (LLM_PROVIDER=none)
    gemini = get_robust_llm(primary_model=GEMINI_MODEL)
except Exception:  # noqa: BLE001
    gemini = None


class ResourceItem(BaseModel):
    title: str = Field(description="Type and title of resource (e.g., 'yt video: FastAPI Tutorial', 'coursera vid: Basics of FastAPI')")
    link: str = Field(description="URL link to the resource")

class SkillResource(BaseModel):
    skill: str = Field(description="Name of the skill")
    resources: List[ResourceItem] = Field(description="List of learning resources for this skill")

class SkillResourceOutput(BaseModel):
    skills: List[SkillResource]


@observe()
async def add_queries_to_state(state: SkillBrainState):
    skill_gaps = state.get("skill_gaps", [])
    learning_path = state.get("learning_path", [])
    
    queries = []
    # Extract only the top 1 search query for the top 5 skill gaps to prevent prompt overload
    for item in learning_path[:5]:
        item_queries = item.get("search_queries", [])
        if item_queries:
            queries.append(item_queries[0])
            
    # Fallback if learning_path is somehow empty
    if not queries and skill_gaps:
        for skill in skill_gaps[:5]:
            queries.append(f"best free course to learn {skill}")
            
    state["search_queries"] = queries
    logger.success(f"Extracted {len(state['search_queries'])} search queries successfully.")
    return state

@observe()
async def get_skill_resources(state: SkillBrainState):
    queries = state.get("search_queries", [])
    
    from src.utilities.llm_provider import get_secret
    tavily_key = get_secret("TAVILY_API_KEY")  # visitor's own Tavily key first, then server env
    if not tavily_key:
        raise ValueError("TAVILY_API_KEY not configured (web resources skipped)")
        
    search_tool = TavilySearchResults(max_results=3, tavily_api_key=tavily_key)
    
    logger.info(f"Firing off {len(queries)} concurrent Tavily search queries...")
    tasks = [search_tool.ainvoke({"query": q}) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    raw_search_context = ""
    for q, r in zip(queries, results):
        if isinstance(r, Exception):
            logger.error(f"Tavily search failed for query '{q}': {str(r)}")
            raw_search_context += f"Query: {q}\nError: {str(r)}\n\n"
        else:
            raw_search_context += f"Query: {q}\nResults: {r}\n\n"
            
    logger.info("Extracting and formatting resources (GEMINI_MODEL + fallbacks)...")
    prompt = f"""
    Based on the following search results, extract the best learning resources for the skills.
    
    Search Results:
    {raw_search_context}
    """
    
    from src.utilities.brain import get_robust_structured_llm
    structured_llm = get_robust_structured_llm(SkillResourceOutput, primary_model=GEMINI_MODEL)
    structured_data = await structured_llm.ainvoke([HumanMessage(content=prompt)])
    
    sd = structured_data
    out = []

    if sd and getattr(sd, "skills", None):
        for s in sd.skills:
            out.append(f"skill: {s.skill}")
            out.extend(f"resource: {r.title} : {r.link}" for r in s.resources)
            out.append("")
        logger.success("Resources successfully formatted!")
    else:
        logger.warning(f"No skills extracted. structured_data = {sd}")
        logger.debug(f"raw_search_context length = {len(raw_search_context)}")
        if "Error:" in raw_search_context:
            logger.error("Tavily API returned errors, which caused Gemini to extract no resources.")
            
    state["skill_resources"] = "\n".join(out).strip()
    return state

async def main():
    dummy_state: SkillBrainState = {
        "resume_text": "",
        "job_description": "",
        "candidate_skills": [],
        "required_skills": [],
        "skill_gaps": ["FastAPI", "PostgreSQL"],
        "ats_score": 0,
        "learning_path": [
            {"skill": "FastAPI", "search_queries": []},
            {"skill": "PostgreSQL", "search_queries": []}
        ],
        "error": ""
    }
    
    logger.info("Starting net_surf testing workflow...")
    
    state = await add_queries_to_state(dummy_state)
    state = await get_skill_resources(state)
    
    logger.info("--- Final Output Extracted from State ---")
    print(f"\n{state.get('skill_resources')}\n")

if __name__ == "__main__":
    asyncio.run(main())
