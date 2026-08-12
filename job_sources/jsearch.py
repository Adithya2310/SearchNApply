import os

import requests

from .utils import strip_html

URL = "https://jsearch.p.rapidapi.com/search-v2"


def fetch_jobs(query, num_pages=1, country="us", api_key=None):
    """Free tier: 200 requests/month total — callers must gate calls via
    JSEARCH_SCAN_INTERVAL_HOURS, not call this on every scan tick.
    """
    api_key = api_key or os.environ["RAPIDAPI_JSEARCH_KEY"]

    resp = requests.get(
        URL,
        headers={
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        },
        params={"query": query, "num_pages": num_pages, "country": country, "date_posted": "all"},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for job in data.get("data", {}).get("jobs", []):
        salary_min = job.get("job_min_salary")
        salary_max = job.get("job_max_salary")
        if job.get("job_salary_string"):
            salary_range = job["job_salary_string"]
        elif salary_min or salary_max:
            salary_range = f"{salary_min or ''}-{salary_max or ''}"
        else:
            salary_range = ""
        jobs.append(
            {
                "source": "jsearch",
                "company": job.get("employer_name", ""),
                "title": job.get("job_title", ""),
                "url": job.get("job_apply_link", ""),
                "location": job.get("job_location", ""),
                "salary_range": salary_range,
                "description_raw": strip_html(job.get("job_description", "")),
            }
        )
    return jobs
