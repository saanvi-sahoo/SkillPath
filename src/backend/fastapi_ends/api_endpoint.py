"""
LinkedIn Job Scraper - FastAPI Application
==========================================

This module is the main entry point for the LinkedIn Job Scraper REST API.
It defines all HTTP endpoints, request/response schemas (via Pydantic models),
and wires them to the underlying scraper functions in ``linkdin.py`` and
``jobs_profile.py``.

Running the server
------------------
From the ``fastapi_ends/`` directory, run:

    uvicorn api_endpoint:app --reload

The interactive Swagger UI will be available at:
    http://127.0.0.1:8000/docs

The alternative ReDoc documentation will be available at:
    http://127.0.0.1:8000/redoc
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

# --- MONKEY PATCH FOR LANGCHAIN VERSION BUG ---
import langchain_core.exceptions
if not hasattr(langchain_core.exceptions, "ContextOverflowError"):
    class ContextOverflowError(Exception): pass
    langchain_core.exceptions.ContextOverflowError = ContextOverflowError
# ----------------------------------------------
import asyncio
from concurrent.futures import ThreadPoolExecutor
from src.backend.fastapi_ends.linkdin import scrape_linkedin_pro
from src.backend.fastapi_ends.jobs_profile import get_full_job_profile


# ---------------------------------------------------------------------------
# App Initialization & Global Metadata
# ---------------------------------------------------------------------------

app = FastAPI(
    title="LinkedIn Job Scraper API",
    description="""
## Overview

This API provides programmatic access to **publicly available LinkedIn job listings**
without requiring authentication or an API key. It uses LinkedIn's guest-facing
search and job-posting endpoints and parses the HTML responses to return
clean, structured JSON data.

The API is organized into three logical groups:

- **Scraping** — Search for jobs by keyword, location, and optional filters.
  Returns basic metadata (title, company, location, salary, URL).
- **Enrichment** — Given a list of job URLs, fetch each posting's full text
  description and structured criteria (Seniority, Employment Type, Industry, etc.).
- **Combined Flow** — Perform both operations in one call.

### What a basic job listing looks like

Every job returned by the `/jobs` endpoint has this structure:

```json
{
  "position": "Software Engineer",
  "company": "Google",
  "location": "Bangalore, Karnataka, India",
  "date": "2026-04-15",
  "agoTime": "5 days ago",
  "salary": "Not Listed",
  "jobUrl": "https://www.linkedin.com/jobs/view/3948576210"
}
```

### What an enriched job listing looks like

After passing a `jobUrl` through `/profiles`, three extra fields are added:

```json
{
  "position": "Software Engineer",
  "company": "Google",
  "location": "Bangalore, Karnataka, India",
  "date": "2026-04-15",
  "agoTime": "5 days ago",
  "salary": "Not Listed",
  "jobUrl": "https://www.linkedin.com/jobs/view/3948576210",
  "job_id": "3948576210",
  "description": "We are looking for a skilled Software Engineer to join our team...",
  "criteria": {
    "Seniority level": "Mid-Senior level",
    "Employment type": "Full-time",
    "Job function": "Engineering and Information Technology",
    "Industries": "Software Development"
  }
}
```

---

## Authentication

None required. This API consumes LinkedIn's public (guest) endpoints.
No API key, OAuth token, or login session is needed.

> **Note:** Because this API scrapes public pages, its reliability depends on
> LinkedIn's page structure remaining unchanged. If LinkedIn updates their HTML
> layout, some fields may temporarily return empty strings until the parser is updated.

---

## Rate Limiting

LinkedIn's servers will temporarily block IP addresses that make requests
too quickly. To mitigate this, the scraper inserts a **3-second delay**:

- Between paginated search requests (when `num_pages > 1`).
- Between full profile fetches (when enriching multiple jobs).

**Practical time estimates:**

| Operation                        | Approximate time |
|----------------------------------|-----------------|
| 1-page scrape (~10 jobs)         | 1–2 seconds      |
| 2-page scrape (~20 jobs)         | ~5 seconds       |
| Enriching 5 profiles             | ~15 seconds      |
| Enriching 10 profiles            | ~30 seconds      |
| Enriching 20 profiles            | ~60 seconds      |

**If you receive empty results or errors mid-scrape**, it is likely that LinkedIn
has temporarily rate-limited your IP. Wait a few minutes before retrying.
Always use the `n` parameter to limit enrichment to only what you actually need.

---

## Recommended Workflow

### Two-step (recommended for most use cases)

**Step 1** — Search for jobs:

```json
POST /jobs
{
  "keywords": "Data Scientist",
  "location": "India",
  "num_pages": 2,
  "filters": { "f_E": "2,3", "f_JT": "F", "f_TPR": "r604800" }
}
```

This returns a list of jobs, each with a `jobUrl`. Pick the ones you want.

**Step 2** — Enrich only the jobs you care about:

```json
POST /profiles?n=5
{
  "jobs": [
    { "jobUrl": "https://www.linkedin.com/jobs/view/3948576210" },
    { "jobUrl": "https://www.linkedin.com/jobs/view/3948576211" }
  ]
}
```

### One-shot (convenient for small scrapes)

```json
POST /jobs-with-profiles
{
  "keywords": "Machine Learning Engineer",
  "location": "Remote",
  "num_pages": 1,
  "filters": { "f_WT": "2" },
  "n": 5
}
```

> **Tip:** Always set `n` in the one-shot endpoint to avoid waiting for
> 20+ profile fetches. Setting `n=5` scrapes all pages but only enriches the top 5.

---

## Master Filter Reference

The `filters` field accepts any combination of the LinkedIn query parameters below.
Multiple values for a single filter can be combined with commas — e.g., `"f_E": "2,3"` returns
both Entry Level and Associate roles simultaneously.

---

### Core Search & Sorting

| Parameter  | Type   | Description                                                                                  |
|------------|--------|----------------------------------------------------------------------------------------------|
| `keywords` | string | The job title or skill to search. Example: `"Python Developer"`                             |
| `location` | string | City, region, or country. Example: `"Amritsar, Punjab, India"`                              |
| `geoId`    | string | LinkedIn internal Geographic ID. Overrides `location` for strict geo matching. Example: `"102713980"` for India |
| `sortBy`   | string | `"R"` = Most Recent (best for scraping fresh data), `"DD"` = Most Relevant (LinkedIn default) |
| `distance` | string | Radius in miles from the location. Example: `"25"`, `"50"`, `"100"`                        |

---

### Work Type (`f_WT`)

| Value | Meaning  |
|-------|----------|
| `"1"` | On-site  |
| `"2"` | Remote   |
| `"3"` | Hybrid   |

---

### Experience Level (`f_E`)

| Value | Meaning         |
|-------|-----------------|
| `"1"` | Internship      |
| `"2"` | Entry level     |
| `"3"` | Associate       |
| `"4"` | Mid-Senior level|
| `"5"` | Director        |
| `"6"` | Executive       |

---

### Job Type (`f_JT`)

| Value | Meaning     |
|-------|-------------|
| `"F"` | Full-time   |
| `"P"` | Part-time   |
| `"C"` | Contract    |
| `"T"` | Temporary   |
| `"V"` | Volunteer   |
| `"I"` | Internship  |
| `"O"` | Other       |

---

### Timing & Competition

| Parameter  | Value      | Meaning                                                                          |
|------------|------------|----------------------------------------------------------------------------------|
| `f_TPR`    | `"r86400"` | Past 24 hours                                                                    |
| `f_TPR`    | `"r604800"`| Past 1 week                                                                      |
| `f_TPR`    | `"r2592000"`| Past 1 month                                                                    |
| `f_JIYN`   | `"true"`   | Limits results to jobs with fewer than 10 applicants ("Just In / Few Applicants")|
| `f_AL`     | `"true"`   | Limits results to LinkedIn Easy Apply jobs only (no external redirect)           |

---

### Minimum Salary (`f_SB2`)

Note: Only returns jobs where the employer explicitly listed a salary range.

| Value | Minimum Salary |
|-------|---------------|
| `"1"` | $40,000+      |
| `"2"` | $60,000+      |
| `"3"` | $80,000+      |
| `"4"` | $100,000+     |
| `"5"` | $120,000+     |
| `"6"` | $140,000+     |
| `"7"` | $160,000+     |
| `"8"` | $180,000+     |
| `"9"` | $200,000+     |

---

### Company (`f_C`)

Must use LinkedIn's internal numeric Company ID. Multiple IDs can be comma-separated.

| Example Value | Company   |
|---------------|-----------|
| `"1441"`      | Google    |
| `"1035"`      | Microsoft |
| `"1586"`      | Amazon    |
| `"162479"`    | Apple     |

---

### Industry (`f_I`)

Must use LinkedIn's internal numeric Industry ID. Multiple IDs can be comma-separated.

| Example Value | Industry              |
|---------------|-----------------------|
| `"4"`         | Software Development  |
| `"96"`        | IT Services           |
| `"43"`        | Financial Services    |
| `"27"`        | Retail                |
| `"3"`         | Higher Education      |
| `"11"`        | Management Consulting |

---

### Job Function / Department (`f_F`)

| Value       | Department          |
|-------------|---------------------|
| `"eng"`     | Engineering         |
| `"it"`      | Information Technology |
| `"art"`     | Art / Creative / Design |
| `"hr"`      | Human Resources     |
| `"mkt"`     | Marketing           |
| `"fin"`     | Finance             |
| `"sal"`     | Sales               |
| `"prdm"`    | Product Management  |
| `"mgmt"`    | Management          |
| `"consult"` | Consulting          |

---

## Error Reference

| Status Code | Meaning                                                                  |
|-------------|--------------------------------------------------------------------------|
| `200`       | Request succeeded. Response body contains the job data.                  |
| `400`       | Bad request. The input payload is missing required fields or is malformed.|
| `404`       | No results found for the given search criteria.                          |
| `422`       | Validation error. A request field failed Pydantic type/constraint checks. |
| `500`       | Unexpected server error. Check server logs for details.                  |
""",
    version="1.0.0",
    contact={
        "name": "API Support",
    },
)

executor = ThreadPoolExecutor(max_workers=5)



# ---------------------------------------------------------------------------
# Pydantic Models — Request & Response Schemas
# ---------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    """
    Request body for job search endpoints.

    Defines the search query (keywords + location), pagination depth,
    and any optional LinkedIn-specific filters.
    """
    keywords: str = Field(
        ...,
        description=(
            "The job title, role, or skill to search for on LinkedIn. "
            "This maps directly to the search bar on LinkedIn's Jobs page. "
            "Be as specific or as broad as needed. "
            "Examples: 'Software Engineer', 'Data Analyst', 'Product Manager'."
        ),
        example="Software Engineer",
    )
    location: str = Field(
        ...,
        description=(
            "The geographic location to filter results by. "
            "Can be a country, city, or region as recognised by LinkedIn. "
            "Examples: 'India', 'Bangalore, Karnataka', 'San Francisco, CA', 'Remote'."
        ),
        example="India",
    )
    num_pages: int = Field(
        default=1,
        description=(
            "The number of search result pages to fetch. "
            "Each page contains approximately 10 job listings. "
            "For example, `num_pages=3` will attempt to return up to 30 jobs. "
            "A 3-second delay is inserted between pages to avoid rate limiting. "
            "Minimum: 1. Maximum: 10."
        ),
        ge=1,
        le=10,
        example=2,
    )
    filters: dict = Field(
        default={},
        description=(
            "A dictionary of optional LinkedIn query-string filters. "
            "Pass an empty dict `{}` to apply no filters. "
            "Multiple values for a single filter are combined with commas — e.g., `{\"f_E\": \"2,3\"}` "
            "returns both Entry Level and Associate roles. "
            "See the **Master Filter Reference** in the API overview at the top of this page "
            "for the full list of supported parameters, including: "
            "`f_WT` (work type), `f_E` (experience level), `f_JT` (job type), "
            "`f_TPR` (time posted), `f_JIYN` (few applicants), `f_AL` (Easy Apply only), "
            "`f_SB2` (minimum salary), `f_C` (company ID), `f_I` (industry ID), "
            "`f_F` (job function), `geoId` (geographic ID), `distance`, and `sortBy`."
        ),
        example={"f_TPR": "r2592000", "f_JT": "F"},
    )


class JobResponse(BaseModel):
    """
    Response schema for a single basic job listing.

    Returned by the /jobs and /jobs/slice endpoints. Contains surface-level
    metadata about the job — enough to identify the posting and decide whether
    to enrich it further.
    """
    position: str = Field(
        ...,
        description="The advertised job title as it appears on LinkedIn.",
        example="Senior Software Engineer",
    )
    company: str = Field(
        ...,
        description="The name of the company that posted the job.",
        example="Google",
    )
    location: str = Field(
        ...,
        description="The location of the role as listed on LinkedIn (city, country, or 'Remote').",
        example="Bangalore, Karnataka, India",
    )
    date: str = Field(
        ...,
        description=(
            "The ISO 8601 date string indicating when the job was posted "
            "(e.g., '2026-04-15'). Returns an empty string if unavailable."
        ),
        example="2026-04-15",
    )
    agoTime: str = Field(
        ...,
        description=(
            "Human-readable relative posting time (e.g., '3 days ago', '1 week ago'). "
            "Returns an empty string if unavailable."
        ),
        example="5 days ago",
    )
    salary: str = Field(
        ...,
        description=(
            "Salary information if the employer provided it. "
            "Returns 'Not Listed' if no salary was shown."
        ),
        example="Not Listed",
    )
    jobUrl: str = Field(
        ...,
        description=(
            "The direct, clean URL to the LinkedIn job posting. "
            "Query parameters are stripped. Use this URL with the /profiles endpoint."
        ),
        example="https://www.linkedin.com/jobs/view/3948576210",
    )


class ProfileRequestItem(BaseModel):
    """A single job entry submitted for enrichment. Must contain a valid LinkedIn job URL."""
    jobUrl: str = Field(
        ...,
        description=(
            "A public LinkedIn job posting URL. "
            "Must point to a valid job listing that is still active. "
            "The numeric job ID is extracted from the URL automatically. "
            "Example: 'https://www.linkedin.com/jobs/view/3948576210'."
        ),
        example="https://www.linkedin.com/jobs/view/3948576210",
    )


class ProfileRequest(BaseModel):
    """
    Request body for the /profiles enrichment endpoint.

    Accepts a list of job objects. Each must contain at minimum a `jobUrl`
    field. Additional fields (company, position, etc.) are preserved and
    returned alongside the enriched data.
    """
    jobs: List[ProfileRequestItem] = Field(
        ...,
        description=(
            "A list of job objects to enrich. Each object must contain a `jobUrl`. "
            "You can pass the raw output from /jobs directly into this field."
        ),
    )


class EnrichedJobResponse(JobResponse):
    """
    Response schema for a job that has been enriched with full posting details.

    Extends the basic JobResponse with additional fields scraped from the
    individual job posting page: the full description and structured criteria.
    """
    job_id: Optional[str] = Field(
        None,
        description=(
            "The unique numeric LinkedIn Job ID extracted from the job URL. "
            "Useful for de-duplication and direct API lookups."
        ),
        example="3948576210",
    )
    description: Optional[str] = Field(
        None,
        description=(
            "The complete, full-text job description as posted by the employer. "
            "Includes responsibilities, qualifications, about-the-company sections, etc. "
            "Returns 'No description found' if the div was not present in the page HTML."
        ),
    )
    criteria: Optional[Dict[str, str]] = Field(
        None,
        description=(
            "A dictionary of structured job criteria scraped from the criteria list "
            "on the posting page. Keys and values vary by posting, but commonly include: "
            "'Seniority level', 'Employment type', 'Job function', 'Industries'. "
            "Returns an empty dict if no criteria section is found."
        ),
        example={
            "Seniority level": "Mid-Senior level",
            "Employment type": "Full-time",
            "Job function": "Engineering and Information Technology",
            "Industries": "Software Development",
        },
    )


class FullRequest(ScrapeRequest):
    """
    Request body for the combined scrape + enrich endpoint.

    Inherits all fields from ScrapeRequest and adds an optional `n` parameter
    to control how many jobs are enriched after scraping.
    """
    n: Optional[int] = Field(
        None,
        description=(
            "Maximum number of scraped jobs to enrich with full descriptions. "
            "If omitted, all scraped jobs will be enriched (not recommended for large scrapes "
            "due to the time cost — approximately 3 seconds per job). "
            "For example, if `num_pages=2` yields 20 jobs and `n=5`, only the first "
            "5 jobs will be enriched. The other 15 are discarded."
        ),
        ge=1,
        example=5,
    )


# ---------------------------------------------------------------------------
# Internal Helper Functions
# ---------------------------------------------------------------------------

def run_scrape(req: ScrapeRequest) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper around scrape_linkedin_pro.
    Executed in a thread-pool executor to avoid blocking the async event loop.
    """
    return scrape_linkedin_pro(
        keywords=req.keywords,
        location=req.location,
        num_pages=req.num_pages,
        **req.filters,
    )


def enrich_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper that iterates over a list of jobs and calls
    get_full_job_profile for each one that has a jobUrl.
    Executed in a thread-pool executor to avoid blocking the async event loop.
    Jobs without a jobUrl are passed through unchanged.
    """
    detailed = []
    for job in jobs:
        url = job.get("jobUrl")
        if url:
            profile = get_full_job_profile(url)
            job.update(profile)
        detailed.append(job)
    return detailed


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/jobs",
    summary="Search LinkedIn for Job Listings",
    description="""
Performs a search against LinkedIn's public job board and returns a list of
basic job listings matching the provided keywords, location, and filters.

### What is returned

Each result contains surface-level metadata only:
- Job title, company name, location
- Posting date (ISO) and relative age (e.g., "3 days ago")
- Salary (if advertised)
- The direct LinkedIn job URL

The full job description and criteria are **not** fetched by this endpoint.
To retrieve those, pass the returned `jobUrl` values to the `/profiles` endpoint.

### Pagination

Set `num_pages` to fetch multiple pages of results. Each page returns approximately
10 listings. A 3-second inter-page delay is applied automatically.

### Errors

- `404` is returned if LinkedIn returns no results for the given query.
- If LinkedIn rate-limits the request mid-scrape, partial results may be returned
  (the scraper stops at the first non-200 response).
""",
    response_model=List[JobResponse],
    responses={
        200: {"description": "A list of job listings matching the search criteria."},
        404: {"description": "No jobs were found for the provided keywords and location."},
    },
    tags=["Scraping"],
)
async def get_jobs(req: ScrapeRequest):
    loop = asyncio.get_event_loop()
    jobs = await loop.run_in_executor(executor, lambda: run_scrape(req))
    if not jobs:
        raise HTTPException(status_code=404, detail="No jobs found matching the provided criteria.")
    return jobs


@app.post(
    "/jobs/slice",
    summary="Search LinkedIn for Jobs and Return First N Results",
    description="""
Identical to the `POST /jobs` endpoint in every way, but the final result list
is truncated to return only the first `n` results.

### When to use this endpoint

Use this endpoint when you need a predictable, fixed number of results regardless
of how many pages you scrape. For example:

- You want to scrape 3 pages (potentially 30 results) but only need the top 5.
- You are testing your integration and want to limit the output size.

The `n` value is applied **after** scraping all requested pages, so all pages
are still fetched. If you want to avoid scraping extra pages, reduce `num_pages`
in the request body instead.

### Query Parameter

| Parameter | Type    | Required | Description                            |
|-----------|---------|----------|----------------------------------------|
| `n`       | integer | Yes      | Number of results to return. Must be >= 1. |

### Errors

- `404` is returned if no jobs were found before the slice was applied.
""",
    response_model=List[JobResponse],
    responses={
        200: {"description": "A truncated list of the first N job listings found."},
        404: {"description": "No jobs were found for the provided keywords and location."},
    },
    tags=["Scraping"],
)
async def get_jobs_slice(
    req: ScrapeRequest,
    n: int = Query(..., ge=1, description="The maximum number of job results to return. Applied after all pages are scraped."),
):
    loop = asyncio.get_event_loop()
    jobs = await loop.run_in_executor(executor, lambda: run_scrape(req))
    if not jobs:
        raise HTTPException(status_code=404, detail="No jobs found matching the provided criteria.")
    return jobs[:n]


@app.post(
    "/profiles",
    summary="Enrich a List of Jobs with Full Descriptions and Criteria",
    description="""
Takes a list of job objects (each containing a `jobUrl`) and fetches the **complete
job description** and **structured criteria** from each individual LinkedIn job posting page.

### What enrichment adds

For each job, the following additional fields are returned on top of the basic metadata:

- `job_id` — The numeric LinkedIn job ID (extracted from the URL).
- `description` — The complete full-text job description as written by the employer.
- `criteria` — A key-value dictionary of structured criteria from the posting page,
  such as Seniority level, Employment type, Job function, and Industries.

### Time cost

Each profile fetch takes approximately 3 seconds (rate-limit delay). Plan accordingly:

| Jobs to enrich | Approximate time |
|----------------|-----------------|
| 1              | ~1 second        |
| 5              | ~15 seconds      |
| 10             | ~30 seconds      |
| 20             | ~60 seconds      |

Use the `n` query parameter to limit the number of profiles fetched in one call.

### Input format

You can pass the raw output from `POST /jobs` directly as the `jobs` field.
At minimum, each item must have a `jobUrl` field.

### Errors

- `400` is returned if the `jobs` list is empty.
- Individual jobs with a missing or invalid `jobUrl` are silently skipped (they
  are included in the response without enrichment).
""",
    response_model=List[EnrichedJobResponse],
    responses={
        200: {"description": "A list of jobs with full descriptions and criteria appended."},
        400: {"description": "The jobs list in the request body was empty."},
    },
    tags=["Enrichment"],
)
async def get_profiles(
    req: ProfileRequest,
    n: Optional[int] = Query(
        None,
        ge=1,
        description=(
            "Limit enrichment to only the first N jobs in the submitted list. "
            "Highly recommended for large lists to avoid long response times. "
            "If omitted, all submitted jobs are enriched."
        ),
    ),
):
    if not req.jobs:
        raise HTTPException(status_code=400, detail="The jobs list cannot be empty.")

    # Convert Pydantic models to plain dicts for the helper function
    jobs_to_process = [item.dict() for item in req.jobs]
    if n is not None:
        jobs_to_process = jobs_to_process[:n]

    loop = asyncio.get_event_loop()
    detailed = await loop.run_in_executor(executor, lambda: enrich_jobs(jobs_to_process))
    return detailed


@app.post(
    "/jobs-with-profiles",
    summary="Scrape and Enrich Jobs in a Single Request",
    description="""
Combines the full search and enrichment pipeline into a single API call.
This endpoint is the most convenient option when you want enriched results
without making two separate requests.

### How it works

1. **Scrape** — LinkedIn is queried using the provided keywords, location,
   pagination, and filters. This produces a list of basic job listings.
2. **Slice** (optional) — If `n` is provided, only the first `n` jobs from
   the scraped list are carried forward into the enrichment step.
3. **Enrich** — Each selected job is fetched individually to retrieve the
   full description and criteria.

### Performance guidance

Because this endpoint performs both scraping and enrichment sequentially,
the total response time can be significant. Always provide a value for `n`
unless you intentionally want all scraped jobs enriched.

| `num_pages` | Jobs scraped | `n` | Jobs enriched | Approx. time |
|-------------|--------------|-----|---------------|--------------|
| 1           | ~10          | 5   | 5             | ~20 seconds  |
| 2           | ~20          | 5   | 5             | ~23 seconds  |
| 2           | ~20          | 20  | 20            | ~66 seconds  |
| 3           | ~30          | None| 30            | ~96 seconds  |

### Errors

- `404` is returned if the initial scrape returned no jobs.
""",
    response_model=List[EnrichedJobResponse],
    responses={
        200: {"description": "A list of fully enriched job listings."},
        404: {"description": "No jobs were found for the provided search criteria."},
    },
    tags=["Combined Flow"],
)
async def get_jobs_with_profiles(req: FullRequest):
    loop = asyncio.get_event_loop()

    # Step 1 — Scrape job listings
    scrape_req = ScrapeRequest(
        keywords=req.keywords,
        location=req.location,
        num_pages=req.num_pages,
        filters=req.filters,
    )
    jobs = await loop.run_in_executor(executor, lambda: run_scrape(scrape_req))

    if not jobs:
        raise HTTPException(status_code=404, detail="No jobs found matching the provided criteria.")

    # Step 2 — Optionally limit how many are enriched
    if req.n is not None:
        jobs = jobs[:req.n]

    # Step 3 — Enrich with full descriptions
    detailed = await loop.run_in_executor(executor, lambda: enrich_jobs(jobs))
    return detailed


# ---------------------------------------------------------------------------
# Full UpskillxAI Pipeline Endpoint
# ---------------------------------------------------------------------------
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from src.backend.main_runner import build_main_graph

class PipelineRequest(BaseModel):
    resume_input: str = Field(..., description="Resume text, URL, or local path.")
    jd_input: str = Field(..., description="Job description text, URL, or local path.")
    target_role: str = Field(default="software engineer", description="Target role for scraping.")
    location: str = Field(default="", description="Location for scraping.")
    user_id: str = Field(default="default", description="Owner of the analysed profile (keeps visitors' data separate).")

@app.post(
    "/pipeline/run",
    summary="Run Full UpskillxAI Pipeline",
    description="Runs the full LangGraph pipeline: extraction, brain analysis, scraping, and net surfing. Returns the final state.",
    tags=["Pipeline"],
)
async def run_pipeline(req: PipelineRequest):
    # shared with the Streamlit in-process mode: run graph -> save memory.json -> re-embed profile
    from src.backend.pipeline_service import run_and_persist
    return await run_and_persist(req.resume_input, req.jd_input, req.target_role, req.location, req.user_id)
#uv run uvicorn api_endpoint.py:app --reload


class ChatRequest(BaseModel):
    messages: List[dict] = Field(..., description="Chat history: [{'role': 'user'|'assistant', 'content': str}]")
    debug: bool = Field(default=False, description="Include routing + retrieved chunks in the response.")
    user_id: str = Field(default="default", description="Whose analysed profile to use.")


@app.post(
    "/chat",
    summary="Career Advisor Chat (RAG)",
    description="Career/study-only advisor. Routes the message, retrieves context from the vector store and answers.",
    tags=["Chatbot"],
)
async def chat(req: ChatRequest):
    import asyncio
    from src.backend.chatbot import answer
    res = await asyncio.to_thread(lambda: answer(req.messages, user_id=req.user_id))
    if not req.debug:
        return {"reply": res["text"]}
    hits = [{k: v for k, v in h.items() if k != "embedding"} for h in res.get("hits", [])]
    return {"reply": res["text"], "route": res["route"], "hits": hits, "latency_ms": res.get("latency_ms")}
#uv run uvicorn api_endpoint.py:app --reload

class RoadmapRequest(BaseModel):
    target_role: str = Field(default="", description="Target role, e.g. 'data analyst'.")
    candidate_skills: List[str] = Field(default_factory=list)
    required_skills: Optional[List[str]] = Field(default=None, description="If given, gaps = exact canonical comparison.")
    gaps: Optional[List[str]] = Field(default=None, description="Use these gaps directly instead of comparing.")
    daily_minutes: int = Field(default=90, ge=15, le=480)
    level: str = Field(default="beginner")
    from_profile: bool = Field(default=False, description="Ignore the fields above and use the latest analysed profile.")
    user_id: str = Field(default="default")


@app.post("/roadmap", summary="Personalised 30-day roadmap", tags=["Roadmap"],
          description="Prioritised, validated 30-day plan (src/roadmap/generator.py).")
async def roadmap(req: RoadmapRequest):
    import asyncio
    from src.roadmap.generator import generate_roadmap, roadmap_from_profile
    if req.from_profile:
        return await asyncio.to_thread(lambda: roadmap_from_profile(req.daily_minutes, req.level, user_id=req.user_id))
    return await asyncio.to_thread(lambda: generate_roadmap(req.target_role, req.candidate_skills, req.required_skills,
                                   req.gaps, req.daily_minutes, req.level, user_id=req.user_id))


@app.post("/skills/compare", summary="Exact skill-gap comparison", tags=["Roadmap"])
async def skills_compare(candidate_skills: List[str], required_skills: List[str]):
    from src.skills.normalizer import compare
    return compare(candidate_skills, required_skills)
