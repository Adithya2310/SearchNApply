import requests
import logging
from job_sources.dedup import compute_job_id
from job_sources.utils import strip_html

logger = logging.getLogger(__name__)

def fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None):
    """
    Fetch job listings from Oracle's own Oracle Fusion Recruiting Careers site.
    """
    if existing_job_ids is None:
        existing_job_ids = set()

    site_domain = "eeho.fa.us2.oraclecloud.com"
    site_number = "CX_45001"
    base_url = f"https://{site_domain}/hcmRestApi/resources/latest"

    # Stage 1: Fetch job listings
    # We will fetch up to 100 jobs for demonstration, paging through if necessary.
    # In a full run, we might want to fetch more or use target_roles to filter by keyword.
    
    limit = 25
    offset = 0
    all_reqs = []
    
    # We'll fetch just one or two pages to keep it lightweight, or up to a max (e.g., 200).
    max_jobs_to_fetch = 200
    
    while offset < max_jobs_to_fetch:
        search_url = f"{base_url}/recruitingCEJobRequisitions?finder=findReqs;siteNumber={site_number}&limit={limit}&offset={offset}&expand=requisitionList"
        try:
            response = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch job list from Oracle: {e}")
            break
            
        items = data.get("items", [])
        if not items:
            break
            
        req_list = items[0].get("requisitionList", [])
        if not req_list:
            break
            
        all_reqs.extend(req_list)
        
        if len(req_list) < limit:
            break
            
        offset += limit

    jobs_found = []
    seen_urls = set()
    
    company = company_name or "Oracle"

    for req in all_reqs:
        req_id = req.get("Id")
        if not req_id:
            continue
            
        title = req.get("Title", "")
        if not title:
            continue

        location = req.get("PrimaryLocation", "")
        # Construct URL as requested by candidate experience
        url = f"https://{site_domain}/hcmUI/CandidateExperience/en/sites/jobsearch/job/{req_id}"

        if url in seen_urls:
            continue
        seen_urls.add(url)

        job_id = compute_job_id(company, title, url)

        # Skip entirely if already known (matches workday's dedup pattern)
        if job_id in existing_job_ids:
            continue

        job_data = {
            "source": f"custom_{identifier}",
            "company": company,
            "title": title,
            "url": url,
            "location": location,
            "salary_range": "", # Oracle doesn't expose this uniformly
            "description_raw": ""
        }

        # Stage 2: Fetch full description for genuinely new postings
        try:
            detail_url = f"{base_url}/recruitingCEJobRequisitionDetails?finder=ById;Id=%22{req_id}%22,siteNumber=%22{site_number}%22"
            detail_resp = requests.get(detail_url, headers={'User-Agent': 'Mozilla/5.0'})
            detail_resp.raise_for_status()
            detail_data = detail_resp.json()

            det_items = detail_data.get("items", [])
            if det_items:
                job_details = det_items[0]
                desc_parts = []

                if job_details.get("ExternalDescriptionStr"):
                    desc_parts.append(job_details["ExternalDescriptionStr"])
                if job_details.get("ExternalQualificationsStr"):
                    desc_parts.append(job_details["ExternalQualificationsStr"])
                if job_details.get("ExternalResponsibilitiesStr"):
                    desc_parts.append(job_details["ExternalResponsibilitiesStr"])

                raw_desc = " ".join(desc_parts)
                job_data["description_raw"] = strip_html(raw_desc)
        except Exception as e:
            logger.error(f"Failed to fetch details for Oracle job {req_id}: {e}")

        jobs_found.append(job_data)

    return jobs_found
