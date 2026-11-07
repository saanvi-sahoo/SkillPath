"""
Job Profile Enrichment Module
=============================

This module provides functionality to scrape **full job descriptions** and
metadata from individual LinkedIn job posting pages.

It is used by the FastAPI layer (``api_endpoint.py``) to *enrich* basic job
listings that were discovered by ``linkdin.py`` with detailed descriptions,
seniority level, employment type, and other criteria.

Typical workflow
----------------
1. ``linkdin.py`` discovers jobs and returns a list with ``jobUrl`` fields.
2. Each ``jobUrl`` is passed to :func:`get_full_job_profile` which fetches
   the posting page and parses out the full description + criteria.

Dependencies
------------
- ``requests`` – HTTP client for fetching LinkedIn pages.
- ``beautifulsoup4`` – HTML parser for extracting structured data.

Note
----
LinkedIn may rate-limit aggressive scraping.  The companion CLI
(``if __name__ == "__main__"`` block) sleeps **3 seconds** between requests
to reduce the risk of being blocked.
"""

from pyasn1.debug import Debug
import json
import sys
import time
from typing import Any
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from loguru import logger

LOG_DIR = Path(__file__).parent / "logs"

# 1. Clear the default setup
logger.remove()

# 2. Define the exact colors for EVERY piece of data
custom_format = (
    # TIME: Bright Yellow
    "<fg #F4D03F>{time:YYYY-MM-DD HH:mm:ss.SSS}</> | "
    
    # LEVEL: Dynamic (Changes based on INFO, ERROR, etc.)
    "<level>{level: <8}</level> | "
    
    # PROCESS ID: Hot Pink
    "<fg #FF69B4>Proc-{process.id}</>:"
    
    # THREAD ID: Bright Orange
    "<fg #FF8C00>Thread-{thread.id}</> | "
    
    # MODULE/FILE: Lime Green
    "<fg #00FF00>{module}</>:"
    
    # FUNCTION: Bright Cyan
    "<fg #00FFFF>{function}</>:"
    
    # LINE NUMBER: Coral/Red
    "<fg #FF7F50>{line}</> - "
    
    # MESSAGE: Dynamic (Matches the level color)
    "<level>{message}</level>"
)

# 3. Apply the format to the Terminal
logger.add(sys.stdout, colorize=True, format=custom_format, level="DEBUG")

# 4. Apply the format to the specific log file (Fixes KeyError: 'name')
logger.add(
    str(LOG_DIR / "jobs_profile.log"),  
    filter=lambda record: record["file"].name == "jobs_profile.py",
    colorize=True,         
    format=custom_format,
    rotation="10 MB"       
)


def get_full_job_profile(job_url: str) -> dict[str, Any]:
    """Fetch and parse the full description of a single LinkedIn job posting.

    Given a public LinkedIn job URL, this function:

    1. Extracts the numeric **job ID** from the URL.
    2. Hits LinkedIn's guest job-posting API to retrieve the HTML page.
    3. Parses the HTML to extract:
       - The full-text **job description**.
       - A dictionary of **job criteria** (e.g. Seniority level,
         Employment type, Industry, Job function).

    Parameters
    ----------
    job_url : str
        A public LinkedIn job URL.
        Example: ``"https://www.linkedin.com/jobs/view/1234567890"``

    Returns
    -------
    dict[str, Any]
        On **success**, a dict with the following keys:

        - ``job_id`` (*str*) – The numeric LinkedIn job ID.
        - ``description`` (*str*) – Full-text job description
          (whitespace-trimmed).
        - ``criteria`` (*dict[str, str]*) – Key/value pairs of job
          criteria headers and their values. Example::

              {
                  "Seniority level": "Entry level",
                  "Employment type": "Full-time",
                  "Job function": "Engineering",
                  "Industries": "Software Development"
              }

        On **failure** (non-200 HTTP response):

        - ``error`` (*str*) – A human-readable error message.

    Raises
    ------
    This function does **not** raise exceptions.  Network or parsing
    errors are caught and returned as ``{"error": "..."}`` dicts so
    that batch callers can continue processing remaining jobs.

    Examples
    --------
    >>> profile = get_full_job_profile(
    ...     "https://www.linkedin.com/jobs/view/3948576210"
    ... )
    >>> profile["job_id"]
    '3948576210'
    >>> "description" in profile
    True
    """

    job_id: str = job_url.split("?")[0].split("-")[-1]
    logger.info(f"Fetching job profile | job_id={job_id}")

    api_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        ),
    }

    response = requests.get(api_url, headers=headers)

    if response.status_code != 200:
        logger.error(f"Failed to fetch job_id={job_id} | HTTP {response.status_code}")
        return {"error": f"Failed to fetch profile (HTTP {response.status_code})"}

    soup = BeautifulSoup(response.text, "html.parser")

    description_div = soup.find("div", class_="description__text")
    full_description: str = (
        description_div.text.strip() if description_div else "No description found"
    )

    criteria_dict: dict[str, str] = {}
    criteria_list = soup.find("ul", class_="description__job-criteria-list")

    if criteria_list:
        items = criteria_list.find_all("li")
        for item in items:
            header = item.find(
                "h3", class_="description__job-criteria-subheader"
            ).text.strip()
            value = item.find(
                "span", class_="description__job-criteria-text"
            ).text.strip()
            criteria_dict[header] = value

    logger.success(f"Profile parsed | job_id={job_id} | criteria_count={len(criteria_dict)}")

    return {
        "job_id": job_id,
        "description": full_description,
        "criteria": criteria_dict,
    }


if __name__ == "__main__":

    logger.info("Opening jobs.json")

    try:
        with open("jobs.json", "r", encoding="utf-8") as file:
            basic_jobs = json.load(file)
    except FileNotFoundError:
        logger.error("Could not find jobs.json — did you run the first script?")
        exit()

    logger.info(f"Found {len(basic_jobs)} jobs — starting deep scrape (~3s per job)")

    detailed_jobs = []

    for index, job in enumerate(basic_jobs):
        logger.info(
            f"[{index + 1}/{len(basic_jobs)}] {job['position']} at {job['company']}"
        )

        job_url = job.get("jobUrl")

        if job_url:
            profile_details = get_full_job_profile(job_url)
            job.update(profile_details)
            detailed_jobs.append(job)
            time.sleep(3)

    output_filename = "master_jobs_detailed.json"
    logger.info(f"Saving {len(detailed_jobs)} enriched jobs to {output_filename}")

    with open(output_filename, "w", encoding="utf-8") as file:
        json.dump(detailed_jobs, file, indent=4)

    logger.success("Done — all enriched job data saved successfully.")