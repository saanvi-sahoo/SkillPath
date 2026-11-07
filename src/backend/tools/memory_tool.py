import os
import json
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

@tool
def query_career_memory(query: str) -> str:
    """
    Use this tool to query the user's permanent career memory.
    The memory contains the user's Resume, Job Description, Extracted Skills, 
    Scraped Job Listings (from LinkedIn and Naukri), and Recommended Learning Resources.
    Pass a highly specific query to extract exact details from the memory.
    """
    memory_path = os.path.join(os.path.dirname(__file__), "..", "memory.json")
    if not os.path.exists(memory_path):
        return "Memory is currently empty. Please ask the user to run a profile analysis first."
        
    try:
        with open(memory_path, "r", encoding="utf-8") as f:
            memory_data = json.load(f)
            
        memory_str = json.dumps(memory_data, indent=2)
        
        # Use get_robust_llm with gemma-4-26b-it for high-throughput memory reading (Unlimited TPM free tier)
        from src.utilities.brain import get_robust_llm
        llm = get_robust_llm(primary_model="gemma-4-26b-it", temperature=0.1)
        
        prompt = f"""
You are the internal Memory Engine for an AI Career Advisor.
You have access to the user's entire permanent memory, which includes their Resume, Job Description, extracted skills, scraped Job Listings, and learning Resources.

USER'S PERMANENT MEMORY:
{memory_str}

Given the above memory, answer the following query in a highly detailed, factual, and analytical manner. Extract all relevant details, company names, links, and skill gaps if relevant to the query.

QUERY:
{query}
"""
        response = llm.invoke(prompt)
        return response.content
        
    except Exception as e:
        return f"Error querying memory: {str(e)}"
