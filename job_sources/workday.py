import requests

from .dedup import compute_job_id
from .utils import strip_html

DEFAULT_LIMIT = 10


def _split_identifier(identifier):
    # "<subdomain>/<wd-instance>/<site>", e.g. "lnw/wd5/LightWonderExternalCareers".
    # Assumes subdomain == the tenant name in the API path, true for every
    # real tenant checked so far (Light & Wonder, Walmart).
    subdomain, wd_instance, site = identifier.split("/")
    return subdomain, wd_instance, site


def _public_base_url(identifier):
    subdomain, wd_instance, site = _split_identifier(identifier)
    return f"https://{subdomain}.{wd_instance}.myworkdayjobs.com/{site}"


def _api_base_url(identifier):
    subdomain, wd_instance, site = _split_identifier(identifier)
    return f"https://{subdomain}.{wd_instance}.myworkdayjobs.com/wday/cxs/{subdomain}/{site}"


def search_jobs(identifier, query="", limit=DEFAULT_LIMIT, offset=0):
    """Lightweight listing search — no description, but enough (title,
    location, path) to compute a job_id and dedupe before paying for the
    more expensive detail fetch.
    """
    resp = requests.post(
        f"{_api_base_url(identifier)}/jobs",
        json={"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": query},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("jobPostings", [])


def fetch_job_detail(identifier, external_path):
    resp = requests.get(f"{_api_base_url(identifier)}{external_path}", timeout=20)
    resp.raise_for_status()
    return resp.json().get("jobPostingInfo", {})


def fetch_jobs(identifier, queries, company_name=None, existing_job_ids=None, limit=DEFAULT_LIMIT):
    """queries: search terms to run (reuses Config.target_roles — same
    pattern as the Adzuna/JSearch integrations). Workday's search API
    doesn't return full descriptions the way Greenhouse/Lever's does, and
    large employers here can have thousands of postings — fetching full
    detail for every result on every scan would be a real N+1. Skipping
    the detail fetch for anything already in existing_job_ids (computable
    from listing data alone: company+title+url) keeps steady-state cost
    down to just genuinely new postings.
    """
    existing_job_ids = existing_job_ids or set()
    company_label = company_name or identifier.split("/")[0]
    base_url = _public_base_url(identifier)

    seen_urls = set()
    jobs = []
    for query in queries:
        for posting in search_jobs(identifier, query=query, limit=limit):
            external_path = posting.get("externalPath", "")
            url = f"{base_url}{external_path}"
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = posting.get("title", "")
            job_id = compute_job_id(company_label, title, url)
            if job_id in existing_job_ids:
                continue

            detail = fetch_job_detail(identifier, external_path)
            jobs.append(
                {
                    "source": "workday",
                    "company": company_label,
                    "title": title,
                    "url": url,
                    "location": detail.get("location") or posting.get("locationsText", ""),
                    "salary_range": "",
                    "description_raw": strip_html(detail.get("jobDescription", "")),
                }
            )
    return jobs
