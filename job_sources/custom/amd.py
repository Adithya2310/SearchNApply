import requests
import logging
from job_sources.dedup import compute_job_id
from job_sources.utils import strip_html

logger = logging.getLogger(__name__)

def fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None):
    if existing_job_ids is None:
        existing_job_ids = set()
    
    company = company_name if company_name else "AMD"
    source = f"custom_{identifier}"
    
    jobs = []
    seen_urls = set()
    
    limit = 100
    page = 1
    
    while True:
        url = f"https://careers.amd.com/api/jobs?limit={limit}&page={page}"
        logger.info(f"Fetching {url}")
        
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            job_listings = data.get("jobs", [])
            if not job_listings:
                break
                
            for j in job_listings:
                job_data = j.get("data", {})
                
                title = job_data.get("title", "")
                
                # Check target roles
                if target_roles:
                    title_lower = title.lower()
                    if not any(role.lower() in title_lower for role in target_roles):
                        continue
                
                # Construct URL
                job_url = ""
                meta_data = job_data.get("meta_data", {})
                if meta_data and "canonical_url" in meta_data:
                    job_url = meta_data["canonical_url"]
                else:
                    job_url = job_data.get("apply_url", "")
                    
                if not job_url or job_url in seen_urls:
                    continue
                    
                seen_urls.add(job_url)
                
                # Dedup
                job_id = compute_job_id(company, title, job_url)
                
                full_location = job_data.get("full_location", "")
                
                # Salary
                salary_min = job_data.get("salary_min_value")
                salary_max = job_data.get("salary_max_value")
                salary_range = ""
                if salary_min and salary_max:
                    salary_range = f"${salary_min} - ${salary_max}"
                elif salary_min:
                    salary_range = f"${salary_min}"
                elif salary_max:
                    salary_range = f"${salary_max}"
                
                desc_html = job_data.get("description", "")
                
                # Skip if already in database
                if job_id in existing_job_ids:
                    continue
                    
                desc_text = strip_html(desc_html)
                    
                jobs.append({
                    "source": source,
                    "company": company,
                    "title": title,
                    "url": job_url,
                    "location": full_location,
                    "salary_range": salary_range,
                    "description_raw": desc_text,
                })
                
            total_count = data.get("totalCount", 0)
            if page * limit >= total_count:
                break
                
            page += 1
            
        except Exception as e:
            logger.error(f"Error fetching from {url}: {e}")
            break
            
    return jobs
