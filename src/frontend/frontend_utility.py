import requests

BASE_URL = "http://127.0.0.1:8000"


def scrape_jobs(keywords: str, location: str, num_pages: int = 1, filters: dict = None) -> list[dict]:
    """Search LinkedIn for job listings matching the given criteria.

    Hits the POST /jobs endpoint to scrape LinkedIn's public job board
    and return basic metadata for each matching listing.

    Args:
        keywords: The job title or skill to search for.
            Example: "Software Engineer", "Data Analyst".
        location: Geographic location to filter results by.
            Example: "India", "San Francisco, CA", "Remote".
        num_pages: Number of result pages to fetch. Each page contains
            approximately 10 listings. Defaults to 1. Max 10.
        filters: Optional dictionary of LinkedIn query-string filters.
            Common keys include:
                - "f_E": Experience level ("1"=Intern, "2"=Entry, etc.)
                - "f_JT": Job type ("F"=Full-time, "P"=Part-time, etc.)
                - "f_TPR": Time posted ("r86400"=24h, "r604800"=week, etc.)
                - "f_WT": Work type ("1"=On-site, "2"=Remote, "3"=Hybrid)
                - "sortBy": Sort order ("DD"=Date, "R"=Relevance)
            Defaults to None (no filters applied).

    Returns:
        A list of dictionaries, each containing:
            - "position" (str): Job title.
            - "company" (str): Hiring company name.
            - "location" (str): Job location.
            - "date" (str): ISO date of posting, or empty string.
            - "agoTime" (str): Relative time (e.g., "3 days ago").
            - "salary" (str): Salary if listed, else "Not Listed".
            - "jobUrl" (str): Direct link to the LinkedIn posting.

    Raises:
        requests.exceptions.HTTPError: If the API returns a non-2xx status
            code (e.g., 404 when no jobs are found).

    Example:
        >>> jobs = scrape_jobs("Python Developer", "India", filters={"f_TPR": "r604800"})
        >>> print(jobs[0]["position"])
        'Python Developer'
    """
    response = requests.post(f"{BASE_URL}/jobs", json={
        "keywords": keywords,
        "location": location,
        "num_pages": num_pages,
        "filters": filters or {},
    })
    response.raise_for_status()
    return response.json()


def scrape_jobs_slice(keywords: str, location: str, n: int, num_pages: int = 1, filters: dict = None) -> list[dict]:
    """Search LinkedIn for jobs and return only the first N results.

    Hits the POST /jobs/slice endpoint. Identical to scrape_jobs() but
    truncates the result list to exactly `n` entries. All requested pages
    are still scraped server-side before the slice is applied.

    Args:
        keywords: The job title or skill to search for.
        location: Geographic location to filter results by.
        n: Maximum number of job listings to return. Must be >= 1.
            This is applied after all pages are scraped, so it controls
            output size, not scraping depth.
        num_pages: Number of result pages to fetch. Defaults to 1.
        filters: Optional dictionary of LinkedIn query-string filters.
            See scrape_jobs() for the full list of supported keys.

    Returns:
        A list of at most `n` job dictionaries, each with the same
        structure as described in scrape_jobs().

    Raises:
        requests.exceptions.HTTPError: If the API returns a non-2xx status
            code (e.g., 404 when no jobs are found).

    Example:
        >>> top_3 = scrape_jobs_slice("DevOps Engineer", "Remote", n=3, num_pages=2)
        >>> len(top_3)
        3
    """
    response = requests.post(f"{BASE_URL}/jobs/slice", json={
        "keywords": keywords,
        "location": location,
        "num_pages": num_pages,
        "filters": filters or {},
    }, params={"n": n})
    response.raise_for_status()
    return response.json()


def enrich_profiles(jobs: list[dict], n: int = None) -> list[dict]:
    """Enrich a list of jobs with full descriptions and criteria.

    Hits the POST /profiles endpoint. For each job that has a "jobUrl",
    the API fetches the individual LinkedIn posting page and extracts
    the full-text description and structured criteria (seniority level,
    employment type, industry, job function).

    Args:
        jobs: A list of job dictionaries, each containing at minimum a
            "jobUrl" key. You can pass the raw output from scrape_jobs()
            or scrape_jobs_slice() directly.
        n: Optional limit on how many jobs to enrich. If None, all jobs
            in the list are enriched. Each enrichment takes ~3 seconds,
            so set this to avoid long wait times on large lists.

    Returns:
        A list of enriched job dictionaries. Each dict contains all the
        original fields plus:
            - "job_id" (str): Numeric LinkedIn job ID.
            - "description" (str): Full-text job description.
            - "criteria" (dict): Key-value pairs such as
                {"Seniority level": "Mid-Senior level",
                 "Employment type": "Full-time"}.

    Raises:
        requests.exceptions.HTTPError: If the API returns a non-2xx status
            code (e.g., 400 when the jobs list is empty).

    Example:
        >>> jobs = scrape_jobs_slice("ML Engineer", "India", n=2)
        >>> enriched = enrich_profiles(jobs, n=2)
        >>> print(enriched[0]["description"][:50])
        'We are looking for a Machine Learning Engineer...'
    """
    response = requests.post(f"{BASE_URL}/profiles", json={
        "jobs": jobs,
    }, params={"n": n} if n else {})
    response.raise_for_status()
    return response.json()


def scrape_and_enrich(keywords: str, location: str, num_pages: int = 1, filters: dict = None, n: int = None) -> list[dict]:
    """Search LinkedIn for jobs and immediately enrich them in one call.

    Hits the POST /jobs-with-profiles endpoint. This combines the scraping
    and enrichment steps into a single API call:
        1. Scrapes LinkedIn for jobs matching the query.
        2. Fetches full descriptions for the top `n` results (or all if
           `n` is not set).

    Args:
        keywords: The job title or skill to search for.
        location: Geographic location to filter results by.
        num_pages: Number of result pages to fetch. Defaults to 1.
        filters: Optional dictionary of LinkedIn query-string filters.
            See scrape_jobs() for the full list of supported keys.
        n: Optional limit on how many scraped jobs to enrich. Highly
            recommended for any scrape with num_pages > 1, since
            enriching 20+ jobs takes over 60 seconds. If None, all
            scraped jobs are enriched.

    Returns:
        A list of fully enriched job dictionaries containing both
        the basic metadata (position, company, location, etc.) and
        enrichment fields (job_id, description, criteria).

    Raises:
        requests.exceptions.HTTPError: If the API returns a non-2xx status
            code (e.g., 404 when no jobs are found).

    Example:
        >>> results = scrape_and_enrich(
        ...     "Data Scientist", "Remote",
        ...     num_pages=2, filters={"f_WT": "2"}, n=5
        ... )
        >>> print(f"Got {len(results)} enriched jobs")
        'Got 5 enriched jobs'
    """
    response = requests.post(f"{BASE_URL}/jobs-with-profiles", json={
        "keywords": keywords,
        "location": location,
        "num_pages": num_pages,
        "filters": filters or {},
        "n": n,
    })
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    jobs = scrape_jobs("Software Engineer", "India", num_pages=1, filters={"f_TPR": "r2592000"})
    print(f"Found {len(jobs)} jobs")

    sliced = scrape_jobs_slice("Software Engineer", "India", n=3)
    print(f"Sliced to {len(sliced)} jobs")

    enriched = enrich_profiles(sliced, n=2)
    print(f"Enriched {len(enriched)} jobs")

    full = scrape_and_enrich("Data Scientist", "Remote", n=2)
    print(f"Full pipeline returned {len(full)} jobs")
