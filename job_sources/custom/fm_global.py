import requests
import logging
from job_sources.dedup import compute_job_id
from job_sources.utils import strip_html

logger = logging.getLogger(__name__)

def fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None):
    """
    Fetch jobs from FM Global's Jibe API careers site.
    """
    if existing_job_ids is None:
        existing_job_ids = set()
    
    company = company_name if company_name else "FM Global"
    url = "https://careers.fm.com/api/jobs"
    headers = {"Accept": "application/json"}
    
    jobs = []
    seen_urls = set()
    
    queries = target_roles if target_roles else [""]
    
    for q in queries:
        page = 1
        limit = 100
        
        while True:
            params = {
                "limit": limit,
                "page": page
            }
            if q:
                params["q"] = q
                
            try:
                response = requests.get(url, headers=headers, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logger.error(f"Error fetching jobs for FM Global with query '{q}': {e}")
                break
                
            jobs_list = data.get("jobs", [])
            if not jobs_list:
                break
                
            for j in jobs_list:
                job_data = j.get("data", {})
                title = job_data.get("title", "")
                job_url = job_data.get("meta_data", {}).get("canonical_url", "")
                if not job_url:
                    job_url = f"https://careers.fm.com/jobs/{job_data.get('req_id')}?lang=en-us"
                    
                if not title or not job_url or job_url in seen_urls:
                    continue
                    
                seen_urls.add(job_url)
                
                location = job_data.get("full_location", "")
                if not location:
                    location = job_data.get("short_location", "")
                    
                salary_min = job_data.get("salary_min_value")
                salary_max = job_data.get("salary_max_value")
                salary_range = ""
                if salary_min and salary_max:
                    salary_range = f"${salary_min} - ${salary_max}"
                    
                job_id = compute_job_id(company, title, job_url)

                # Skip entirely if already known (matches workday's dedup pattern)
                if job_id in existing_job_ids:
                    continue

                raw_html = job_data.get("description", "")
                description_raw = strip_html(raw_html) if raw_html else ""

                job = {
                    "source": f"custom_{identifier}",
                    "company": company,
                    "title": title,
                    "url": job_url,
                    "location": location,
                    "salary_range": salary_range,
                    "description_raw": description_raw
                }
                jobs.append(job)
                
            if len(jobs_list) < limit:
                break
                
            page += 1

    return jobs
