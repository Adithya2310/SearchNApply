import requests

from .utils import strip_html

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"


def fetch_jobs(board_token, company_name=None):
    """No API key required — Greenhouse job boards are public."""
    resp = requests.get(
        BASE_URL.format(board_token=board_token), params={"content": "true"}, timeout=15
    )
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for job in data.get("jobs", []):
        location = (job.get("location") or {}).get("name", "")
        jobs.append(
            {
                "source": "greenhouse",
                "company": company_name or job.get("company_name") or board_token,
                "title": job.get("title", ""),
                "url": job.get("absolute_url", ""),
                "location": location,
                "salary_range": "",
                "description_raw": strip_html(job.get("content", "")),
            }
        )
    return jobs
