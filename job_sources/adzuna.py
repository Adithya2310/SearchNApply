import os

import requests

from .utils import strip_html

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


def fetch_jobs(what, where=None, country="us", results_per_page=20, app_id=None, app_key=None):
    """Free tier: 25/min, 250/day, 2500/month (developer.adzuna.com/docs/terms_of_service) —
    generous enough for the regular JOB_SCAN_INTERVAL_MINUTES schedule at one query per run,
    as long as that interval is >= 30 min.
    """
    app_id = app_id or os.environ["ADZUNA_APP_ID"]
    app_key = app_key or os.environ["ADZUNA_APP_KEY"]

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": results_per_page,
        "what": what,
    }
    if where:
        params["where"] = where

    resp = requests.get(BASE_URL.format(country=country), params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for job in data.get("results", []):
        company = (job.get("company") or {}).get("display_name", "")
        location = (job.get("location") or {}).get("display_name", "")
        salary_min = job.get("salary_min")
        salary_max = job.get("salary_max")
        salary_range = ""
        if salary_min or salary_max:
            salary_range = f"{salary_min or ''}-{salary_max or ''}"
        jobs.append(
            {
                "source": "adzuna",
                "company": company,
                "title": job.get("title", ""),
                "url": job.get("redirect_url", ""),
                "location": location,
                "salary_range": salary_range,
                "description_raw": strip_html(job.get("description", "")),
            }
        )
    return jobs
