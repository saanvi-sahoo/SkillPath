"""
LinkedIn Job Search Scraper Module
===================================

Scrapes public LinkedIn job search results using LinkedIn's guest API.
No login or API key required.

Main entry-point: :func:`scrape_linkedin_pro`.

Rate-limiting
-------------
A 3-second delay is inserted between pages to avoid being blocked.
"""

import json
import time
from typing import Any

import requests
from bs4 import BeautifulSoup


def scrape_linkedin_pro(
    keywords: str,
    location: str,
    num_pages: int = 1,
    **filters: Any,
) -> list[dict[str, str]]:
    """Scrape public LinkedIn job listings matching the given criteria.

    Parameters
    ----------
    keywords : str
        Search query (job title or skill).  Example: ``"Software Engineer"``
    location : str
        Geographic filter.  Example: ``"India"``
    num_pages : int, optional
        Result pages to fetch (each ~10 jobs). Defaults to ``1``.
    **filters : Any
        Additional LinkedIn URL parameters:

        - ``f_E``   – Experience: 1=Intern, 2=Entry, 3=Associate, 4=Mid-Senior, 5=Director, 6=Exec
        - ``f_JT``  – Job type: F=Full, P=Part, C=Contract, T=Temp, I=Intern, V=Volunteer
        - ``f_TPR`` – Time posted: r86400=24h, r604800=week, r2592000=month
        - ``sortBy``– DD=Date, R=Relevance

    Returns
    -------
    list[dict[str, str]]
        Each dict: position, company, location, date, agoTime, salary, jobUrl.
    """
    all_jobs: list[dict[str, str]] = []
    base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    for page in range(num_pages):
        params: dict[str, Any] = {
            "keywords": keywords,
            "location": location,
            "start": page * 10,
        }
        params.update(filters)

        response = requests.get(base_url, params=params, headers=headers)

        if response.status_code != 200:
            break

        soup = BeautifulSoup(response.text, "html.parser")
        job_cards = soup.find_all("li")

        if not job_cards:
            break

        for job in job_cards:
            try:
                title = job.find("h3", class_="base-search-card__title").text.strip()
                company = job.find("h4", class_="base-search-card__subtitle").text.strip()
                job_location = job.find("span", class_="job-search-card__location").text.strip()
                raw_link = job.find("a", class_="base-card__full-link")["href"].split("?")[0]
                job_id = raw_link.split("-")[-1]
                link = f"https://www.linkedin.com/jobs/view/{job_id}/"
                time_tag = job.find("time")
                date_posted = time_tag.get("datetime", "") if time_tag else ""
                ago_time = time_tag.text.strip() if time_tag else ""

                salary_tag = job.find("span", class_="job-search-card__salary-info")
                salary = salary_tag.text.strip() if salary_tag else "Not Listed"

                all_jobs.append({
                    "position": title,
                    "company": company,
                    "location": job_location,
                    "date": date_posted,
                    "agoTime": ago_time,
                    "salary": salary,
                    "jobUrl": link,
                })

            except AttributeError:
                continue

        if page < num_pages - 1:
            time.sleep(3)

    return all_jobs


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    my_jobs = scrape_linkedin_pro(
        keywords="Software Engineer",
        location="India",
        num_pages=2,
        f_TPR="r2592000",  # Past Month
    )

    with open("jobs.json", "w", encoding="utf-8") as f:
        print(" Dumping the json ")
        json.dump(my_jobs, f, indent=8)
        print(" Done Dumping ")