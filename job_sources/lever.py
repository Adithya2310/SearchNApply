import requests

from .utils import strip_html

BASE_URL = "https://api.lever.co/v0/postings/{company}"


def fetch_jobs(company, company_name=None):
    """No API key required — Lever job postings are public."""
    resp = requests.get(BASE_URL.format(company=company), params={"mode": "json"}, timeout=15)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, dict):
        # defensive: {"ok": false, ...} shape seen on some empty/misconfigured boards
        return []

    jobs = []
    for job in data:
        categories = job.get("categories") or {}
        jobs.append(
            {
                "source": "lever",
                "company": company_name or company,
                "title": job.get("text", ""),
                "url": job.get("hostedUrl", ""),
                "location": categories.get("location", ""),
                "salary_range": "",
                "description_raw": strip_html(job.get("description", "")),
            }
        )
    return jobs
