"""
naukri_scraper.py
=================
Scrapes job listings from Naukri.com using Selenium (headless Chrome)
and BeautifulSoup for HTML parsing.

Why Selenium?
-------------
Naukri.com is a React single-page application. Job cards are injected
into the DOM by JavaScript after the initial page load. A plain HTTP
request (requests.get) only retrieves the empty HTML shell, so
Selenium is used to drive a real Chrome browser, wait for the JS to
render the page, and then hand the fully-rendered HTML to
BeautifulSoup for extraction.

Module location (per project structure):
    src/backend/scrapers/naukri_scraper.py

Dependencies:
    See requirements.txt or install manually:
        pip install selenium webdriver-manager beautifulsoup4 lxml

    System dependency (Linux):
        wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
        sudo apt install ./google-chrome-stable_current_amd64.deb -y

Usage (standalone):
    python naukri_scraper.py

Usage (as module):
    from src.backend.scrapers.naukri_scraper import scrape_naukri_jobs

    jobs = scrape_naukri_jobs(
        keyword="python developer",
        location="delhi",
        pages=2
    )

Output:
    - jobs.csv   (appended, not overwritten on re-runs)
    - jobs.json  (merged with existing data on re-runs)

Author: Rhythm Kamra
"""

import csv
import json
import os
import time
import random

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# ──────────────────────────────────────────────────────────────────────────────
#  DEFAULT CONFIG — override by calling scrape_naukri_jobs() with arguments
#  or by editing these constants for standalone runs.
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_KEYWORD  = "data analyst"
DEFAULT_LOCATION = ""          # e.g. "delhi" — leave empty for all India
DEFAULT_PAGES    = 3
OUTPUT_CSV       = "jobs.csv"
OUTPUT_JSON      = "jobs.json"
HEADLESS         = True        # False = visible browser window (good for debugging)


# ──────────────────────────────────────────────────────────────────────────────
#  URL BUILDER
# ──────────────────────────────────────────────────────────────────────────────

def build_naukri_url(keyword: str, location: str, page: int) -> str:
    """
    Constructs a Naukri.com search URL from keyword, location, and page number.

    Naukri URL format:
        https://www.naukri.com/<keyword-slug>-jobs-in-<location-slug>-<page>
        https://www.naukri.com/<keyword-slug>-jobs-<page>   (no location)

    Args:
        keyword  (str): Job title / role to search for.
        location (str): City or region. Pass empty string for all-India search.
        page     (int): Page number (1-indexed).

    Returns:
        str: Fully formed Naukri search URL.

    Example:
        >>> build_naukri_url("data analyst", "delhi", 2)
        'https://www.naukri.com/data-analyst-jobs-in-delhi-2'
    """
    keyword_slug = keyword.strip().lower().replace(" ", "-")
    if location.strip():
        location_slug = location.strip().lower().replace(" ", "-")
        return f"https://www.naukri.com/{keyword_slug}-jobs-in-{location_slug}-{page}"
    return f"https://www.naukri.com/{keyword_slug}-jobs-{page}"


# ──────────────────────────────────────────────────────────────────────────────
#  SELENIUM DRIVER SETUP
# ──────────────────────────────────────────────────────────────────────────────

def create_chrome_driver() -> webdriver.Chrome:
    """
    Initialises and returns a Selenium Chrome WebDriver instance.

    Uses webdriver-manager to automatically download the correct
    ChromeDriver binary that matches the installed Chrome version,
    so no manual ChromeDriver setup is needed.

    Chrome flags used:
        --headless=new          Run without a visible window.
        --no-sandbox            Required for Linux/Docker environments.
        --disable-dev-shm-usage Prevents crashes in low-memory containers.
        --disable-gpu           Avoids GPU rendering in headless mode.
        --window-size=1920,1080 Ensures full-width layout so all elements render.
        user-agent              Spoofs a real desktop browser to avoid bot blocks.
        excludeSwitches         Removes the "Chrome is being controlled" banner
                                that can interfere with automation detection.

    Returns:
        webdriver.Chrome: A configured, ready-to-use Chrome WebDriver instance.
    """
    options = Options()

    if HEADLESS:
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


# ──────────────────────────────────────────────────────────────────────────────
#  PAGE SCRAPER
# ──────────────────────────────────────────────────────────────────────────────

def scrape_page(driver: webdriver.Chrome, url: str) -> list[dict]:
    """
    Navigates to a single Naukri search results page, waits for job
    cards to be rendered by JavaScript, then extracts all job listings.

    The function uses an explicit WebDriverWait (up to 15 seconds) for
    the CSS selector 'div.srp-jobtuple-wrapper' to appear in the DOM
    before attempting to parse — this ensures JS has finished rendering.

    Args:
        driver (webdriver.Chrome): Active Selenium Chrome driver.
        url    (str): The Naukri search page URL to visit.

    Returns:
        list[dict]: A list of job dictionaries extracted from the page.
                    Returns an empty list if no jobs are found or the
                    page times out.
    """
    print(f"\n  Fetching: {url}")
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.srp-jobtuple-wrapper"))
        )
        print("    Jobs loaded successfully.")
    except Exception:
        print("    Timed out waiting for jobs — page may be empty or blocked.")

    # Extra buffer for lazy-loaded skill tags and descriptions
    time.sleep(random.uniform(2, 4))

    soup = BeautifulSoup(driver.page_source, "lxml")
    return parse_job_cards(soup)


# ──────────────────────────────────────────────────────────────────────────────
#  HTML PARSERS
# ──────────────────────────────────────────────────────────────────────────────

def parse_job_cards(soup: BeautifulSoup) -> list[dict]:
    """
    Finds all job card wrapper elements on a parsed Naukri page and
    extracts structured data from each one.

    Naukri's current HTML layout (2024-2025) wraps each job in:
        <div class="srp-jobtuple-wrapper">
            <article class="jobTuple ..."> ... </article>
        </div>

    A fallback selector targets the <article> directly in case
    Naukri removes the outer wrapper in a future layout change.

    Args:
        soup (BeautifulSoup): Parsed HTML of a Naukri search results page.

    Returns:
        list[dict]: Extracted job records. Cards that fail to parse are
                    skipped (logged to stdout) rather than crashing the run.
    """
    wrappers = soup.find_all("div", class_="srp-jobtuple-wrapper")
    if not wrappers:
        # Fallback: target article tags directly
        wrappers = soup.find_all("article", class_=lambda c: c and "jobTuple" in c)

    print(f"    Found {len(wrappers)} job cards.")
    return [job for w in wrappers if (job := extract_job_data(w))]


def safe_text(tag) -> str:
    """
    Safely extracts and strips inner text from a BeautifulSoup tag.

    Args:
        tag: A BeautifulSoup Tag object, or None.

    Returns:
        str: Stripped text content, or 'N/A' if the tag is None.
    """
    return tag.get_text(strip=True) if tag else "N/A"


def extract_skills(card) -> str:
    """
    Extracts the required skills list from a job card element.

    Naukri has changed their skills HTML structure multiple times.
    This function tries several known selectors in priority order so
    that it remains functional across layout changes:

        1. ul.tags-gt          — Primary skills container (2024-2025 layout)
        2. li.tag-li           — Individual skill pill (direct fallback)
        3. div.skills-section  — Older layout wrapper
        4. .key-skill          — Legacy class name
        5. li.tag / span.tag   — Generic tag elements (pre-2023 layout)
        6. Heuristic <ul> scan — Any <ul> containing ≥2 short list items
                                 (items < 40 chars each are likely skills,
                                  not descriptions)

    Args:
        card (bs4.element.Tag): A single job card element.

    Returns:
        str: Comma-separated skill names, or 'N/A' if none are found.
    """
    skills = []

    # Method 1 — current primary layout
    container = card.find("ul", class_="tags-gt") or card.find("div", class_="tags-gt")
    if container:
        items = container.find_all("li") or container.find_all("a")
        skills = [i.get_text(strip=True) for i in items if i.get_text(strip=True)]

    # Method 2 — individual pill class
    if not skills:
        items = card.find_all("li", class_="tag-li")
        skills = [i.get_text(strip=True) for i in items if i.get_text(strip=True)]

    # Method 3 — older wrapper
    if not skills:
        section = card.find("div", class_="skills-section")
        if section:
            skills = [i.get_text(strip=True) for i in section.find_all(["li", "a", "span"])]

    # Method 4 — legacy class
    if not skills:
        skills = [i.get_text(strip=True) for i in card.find_all(class_="key-skill")]

    # Method 5 — generic tag elements
    if not skills:
        items = card.find_all("li", class_="tag") or card.find_all("span", class_="tag")
        skills = [i.get_text(strip=True) for i in items]

    # Method 6 — heuristic scan of all <ul> elements
    if not skills:
        for ul in card.find_all("ul"):
            candidates = [li.get_text(strip=True) for li in ul.find_all("li")]
            short = [c for c in candidates if c and len(c) < 40]
            if len(short) >= 2:
                skills = short
                break

    # Deduplicate and remove overly long strings
    seen, cleaned = set(), []
    for s in skills:
        s = s.strip()
        if s and s not in seen and len(s) < 50:
            seen.add(s)
            cleaned.append(s)

    return ", ".join(cleaned) if cleaned else "N/A"


def extract_job_data(card) -> dict | None:
    """
    Extracts all available fields from a single Naukri job card element.

    Fields extracted:
        Title       — Job title (linked text of the apply anchor)
        Company     — Employer name
        Experience  — Required years of experience
        Salary      — Advertised salary (often 'Not Disclosed')
        Location    — Job location(s)
        Skills      — Required skills (see extract_skills for strategy)
        Description — Short description snippet shown in the card
        Link        — Direct URL to the full job posting

    Args:
        card (bs4.element.Tag): A single job card wrapper element.

    Returns:
        dict | None: Structured job data, or None if a critical error
                     occurs during parsing (card is skipped silently).
    """
    try:
        title_tag = card.find("a", class_="title")
        title = safe_text(title_tag)
        link  = title_tag.get("href", "N/A") if title_tag else "N/A"

        company_tag = (
            card.find("a", class_="comp-name") or
            card.find("a", class_="comp-dtls-wrap")
        )
        company = safe_text(company_tag)

        exp_tag = (
            card.find("span", class_="expwdth") or
            card.find("li",   class_="experience")
        )
        experience = safe_text(exp_tag)

        salary_tag = (
            card.find("span", class_="sal") or
            card.find("li",   class_="salary")
        )
        salary = safe_text(salary_tag) if salary_tag else "Not Disclosed"

        loc_tag = (
            card.find("span", class_="locWdth") or
            card.find("li",   class_="location")
        )
        location = safe_text(loc_tag)

        skills = extract_skills(card)

        desc_tag = (
            card.find("span", class_="job-desc") or
            card.find("div",  class_="job-desc")
        )
        description = safe_text(desc_tag)

        return {
            "Title":       title,
            "Company":     company,
            "Experience":  experience,
            "Salary":      salary,
            "Location":    location,
            "Skills":      skills,
            "Description": description,
            "Link":        link,
        }

    except Exception as e:
        print(f"    [WARN] Could not parse a job card: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
#  OUTPUT WRITERS
# ──────────────────────────────────────────────────────────────────────────────

def save_to_csv(jobs: list[dict], filename: str) -> None:
    """
    Appends job records to a CSV file, writing the header only if the
    file does not already exist (safe for repeated runs).

    Args:
        jobs     (list[dict]): Job records to write.
        filename (str): Target CSV file path.
    """
    if not jobs:
        print("\n  [INFO] No jobs to save to CSV.")
        return

    fields = ["Title", "Company", "Experience", "Salary",
              "Location", "Skills", "Description", "Link"]
    file_exists = os.path.isfile(filename)

    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not file_exists:
            writer.writeheader()
        writer.writerows(jobs)

    print(f"\n  Saved {len(jobs)} jobs → '{filename}'")


def save_to_json(jobs: list[dict], filename: str) -> None:
    """
    Merges new job records into an existing JSON file, or creates a
    new one. Existing records are preserved across runs.

    Args:
        jobs     (list[dict]): New job records to add.
        filename (str): Target JSON file path.
    """
    if not jobs:
        print("\n  [INFO] No jobs to save to JSON.")
        return

    existing = []
    if os.path.isfile(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []

    combined = existing + jobs
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"  Saved {len(combined)} total jobs → '{filename}' ({len(jobs)} new)")


# ──────────────────────────────────────────────────────────────────────────────
#  PUBLIC API — importable function for use by other modules
# ──────────────────────────────────────────────────────────────────────────────

def scrape_naukri_jobs(
    keyword:  str = DEFAULT_KEYWORD,
    location: str = DEFAULT_LOCATION,
    pages:    int = DEFAULT_PAGES,
    save_csv:  bool = True,
    save_json: bool = True,
) -> list[dict]:
    """
    Main entry point for the Naukri scraper. Launches Chrome, iterates
    over the requested number of search result pages, and collects all
    job listings.

    Args:
        keyword   (str):  Job title / role to search. Default: 'data analyst'.
        location  (str):  City or region. Empty string = all India.
        pages     (int):  Number of result pages to scrape (≈20 jobs/page).
        save_csv  (bool): If True, appends results to OUTPUT_CSV.
        save_json (bool): If True, merges results into OUTPUT_JSON.

    Returns:
        list[dict]: All collected job records across all pages.

    Example:
        >>> jobs = scrape_naukri_jobs("react developer", "bangalore", pages=2)
        >>> print(jobs[0]["Skills"])
        'React, TypeScript, Redux, Node.js'
    """
    print("=" * 65)
    print("  NAUKRI SCRAPER")
    print("=" * 65)
    print(f"  Keyword  : {keyword}")
    print(f"  Location : {location or 'All India'}")
    print(f"  Pages    : {pages}")
    print("=" * 65)

    driver = create_chrome_driver()
    all_jobs: list[dict] = []

    try:
        for page_num in range(1, pages + 1):
            print(f"\n--- Page {page_num} / {pages} ---")
            url  = build_naukri_url(keyword, location, page_num)
            jobs = scrape_page(driver, url)
            all_jobs.extend(jobs)

            if page_num < pages:
                delay = random.uniform(3, 6)
                print(f"  Waiting {delay:.1f}s before next page...")
                time.sleep(delay)
    finally:
        driver.quit()
        print("\n  Browser closed.")

    if save_csv:
        save_to_csv(all_jobs, OUTPUT_CSV)
    if save_json:
        save_to_json(all_jobs, OUTPUT_JSON)

    print(f"\n  Done — {len(all_jobs)} jobs scraped total.")
    return all_jobs


# ──────────────────────────────────────────────────────────────────────────────
#  STANDALONE RUN
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    scrape_naukri_jobs(
        keyword=DEFAULT_KEYWORD,
        location=DEFAULT_LOCATION,
        pages=DEFAULT_PAGES,
    )