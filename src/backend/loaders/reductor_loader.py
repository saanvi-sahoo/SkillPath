"""
resume_loader.py
================
Extracts structured information from a resume PDF using the Reducto API.

What it does:
-------------
1. Uploads the resume PDF to Reducto's cloud service.
2. Sends an extraction schema (name, email, phone, skills, education,
   projects, experience) along with a system prompt.
3. Receives a structured JSON response.
4. Prints the result in a readable bullet-point format.
5. Saves the output to resume_data.json for use by other modules.

Module location (per project structure):
    src/backend/loaders/resume_loader.py

Dependencies:
    See requirements.txt or install manually:
        pip install reducto

    Reducto API key must be set in the .env file:
        REDUCTO_API_KEY=your_key_here

    Or hardcoded below for development (do NOT commit the key to Git).

Usage (standalone):
    python resume_loader.py

Usage (as module):
    from src.backend.loaders.resume_loader import load_resume

    data = load_resume("path/to/resume.pdf")
    skills = data.get("skills", [])

Output:
    - Printed bullet-point summary to stdout
    - resume_data.json saved to the current working directory

Author: Rhythm Kamra
"""

import json
import os
from pathlib import Path

from reducto import Reducto


# ──────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

# Load from environment variable (recommended) or fall back to hardcoded value.
# To set the env variable:
#     export REDUCTO_API_KEY="your_key_here"      (Linux/macOS)
#     set REDUCTO_API_KEY=your_key_here           (Windows)
# Or add it to your .env file and load with python-dotenv.
from dotenv import load_dotenv

load_dotenv(override=True)                        # reads your .env file
API_KEY = os.getenv("REDUCTO_API_KEY")

if not API_KEY:
    raise EnvironmentError("REDUCTO_API_KEY is not set! ...")
DEFAULT_RESUME_PATH = "resume.pdf"
OUTPUT_JSON = "resume_data.json"

# ──────────────────────────────────────────────────────────────────────────────
#  EXTRACTION SCHEMA
#  Tells Reducto what fields to extract and what type each field should be.
#  Follows JSON Schema format.
# ──────────────────────────────────────────────────────────────────────────────

RESUME_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "Full name of the candidate."
        },
        "email": {
            "type": "string",
            "description": "Contact email address."
        },
        "phone": {
            "type": "string",
            "description": "Contact phone number."
        },
        "skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of technical and soft skills mentioned."
        },
        "education": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of educational qualifications."
        },
        "projects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of project titles or descriptions."
        },
        "experience": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of work/internship experiences."
        },
    }
}


# ──────────────────────────────────────────────────────────────────────────────
#  FORMATTER
# ──────────────────────────────────────────────────────────────────────────────

def format_as_bullets(data: dict | list | str, indent: int = 0) -> None:
    """
    Recursively prints a nested data structure (dict/list/scalar) as
    a human-readable indented bullet-point list.

    Dict keys are printed as section headers (uppercased).
    List items are printed as '- item' bullets.
    Scalar values are printed directly.

    Args:
        data   (dict | list | str): The data to format and print.
        indent (int): Current indentation level (used in recursion).

    Example output:
        NAME:
          Rhythm Kamra
        SKILLS:
          - Python
          - Django
          - React
    """
    pad = "  " * indent

    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{pad}{key.upper()}:")
            format_as_bullets(value, indent + 1)

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                format_as_bullets(item, indent + 1)
            else:
                print(f"{pad}- {item}")

    else:
        print(f"{pad}{data}")


# ──────────────────────────────────────────────────────────────────────────────
#  CORE LOADER FUNCTION — importable by other modules
# ──────────────────────────────────────────────────────────────────────────────

def load_resume(resume_path: str = DEFAULT_RESUME_PATH) -> dict:
    """
    Uploads a resume PDF to Reducto and extracts structured data from it.

    Process:
        1. Validates that the PDF file exists at the given path.
        2. Initialises the Reducto API client with the configured API key.
        3. Uploads the PDF — Reducto returns a file_id for this upload.
        4. Calls extract.run() with the schema and a student-resume
           system prompt to guide the extraction model.
        5. Parses the result and saves it to OUTPUT_JSON.

    Args:
        resume_path (str): Path to the resume PDF file.
                           Default: 'resume.pdf' in the current directory.

    Returns:
        dict: Extracted resume data matching RESUME_SCHEMA keys.
              Returns an empty dict if extraction fails.

    Raises:
        FileNotFoundError: If the PDF does not exist at resume_path.

    Example:
        >>> data = load_resume("resumes/rhythm_kamra.pdf")
        >>> print(data["skills"])
        ['Python', 'Django', 'React', 'MySQL', ...]
    """
    pdf_path = Path(resume_path)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"Resume PDF not found at: '{pdf_path.resolve()}'\n"
            f"Place your resume in the same directory and update DEFAULT_RESUME_PATH."
        )

    print(f"  Loading resume: {pdf_path.resolve()}")

    # Initialise Reducto client
    client = Reducto(api_key=API_KEY)

    # Step 1 — Upload the PDF
    print("  Uploading to Reducto...")
    upload = client.upload(file=pdf_path)
    print(f"  Upload successful. File ID: {upload.file_id}")

    # Step 2 — Run structured extraction
    print("  Extracting structured data...")
    result = client.extract.run(
        input=upload.file_id,
        instructions={
            "schema": RESUME_SCHEMA,
            "system_prompt": (
                "This is a student resume. Extract all structured information "
                "accurately. For skills, include every technology, language, "
                "framework, and tool mentioned anywhere in the document."
            ),
        },
        settings={
            "array_extract": True   # Ensures list fields return arrays
        }
    )

    # Step 3 — Parse the result
    if not result.result:
        print("  [WARN] Reducto returned an empty result.")
        return {}

    extracted: dict = result.result[0]

    # Step 4 — Persist to JSON for downstream use
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)
    print(f"  Saved extracted data → '{OUTPUT_JSON}'")

    return extracted


# ──────────────────────────────────────────────────────────────────────────────
#  STANDALONE RUN
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  RESUME LOADER (Reducto PDF Extractor)")
    print("=" * 55)

    data = load_resume(DEFAULT_RESUME_PATH)

    print("\n  EXTRACTED DATA (bullet format):\n")
    format_as_bullets(data)