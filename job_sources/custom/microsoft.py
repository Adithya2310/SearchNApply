import requests
import re
import json
import logging
from xml.etree import ElementTree
from urllib.parse import urlparse, unquote

from job_sources.dedup import compute_job_id
from job_sources.utils import strip_html

logger = logging.getLogger(__name__)

def extract_title_from_url(url):
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if not path.startswith('/careers/job/'):
        return None
    
    slug = path.replace('/careers/job/', '').strip('/')
    match = re.match(r'^\d+-(.+)$', slug)
    if match:
        title_slug = match.group(1).strip('-')
        title = title_slug.replace('-', ' ').title()
        return title
    return None

def fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None):
    if company_name is None:
        company_name = "Microsoft"
    if existing_job_ids is None:
        existing_job_ids = set()
        
    sitemap_url = "https://apply.careers.microsoft.com/careers/sitemap.xml?domain=microsoft.com"
    
    logger.info(f"Fetching sitemap from {sitemap_url}")
    try:
        response = requests.get(sitemap_url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch sitemap for {identifier}: {e}")
        return []
        
    try:
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError as e:
        logger.error(f"Failed to parse sitemap XML: {e}")
        return []

    namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls = root.findall('ns:url/ns:loc', namespace)
    
    if not urls:
        logger.warning("No URLs found in sitemap.")
        return []
        
    job_urls = [loc.text for loc in urls[1:] if '/careers/job/' in loc.text]
    
    jobs = []
    
    for url in job_urls:
        title = extract_title_from_url(url)
        if not title:
            continue
            
        if target_roles:
            title_lower = title.lower()
            if not any(role.lower() in title_lower for role in target_roles):
                continue
                
        # Compute early job_id to skip details fetch
        job_id = compute_job_id(company_name, title, url)
        
        if job_id in existing_job_ids:
            continue
            
        try:
            detail_resp = requests.get(url, timeout=15)
            detail_resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch job page {url}: {e}")
            continue
            
        match = re.search(r'<script type="application/ld\+json">(.*?)</script>', detail_resp.text, re.DOTALL)
        if not match:
            logger.warning(f"No JSON-LD found in {url}")
            continue
            
        try:
            ld_data = json.loads(match.group(1).strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON-LD in {url}: {e}")
            continue
            
        if ld_data.get('@type') != 'JobPosting':
            continue
            
        real_title = ld_data.get('title', title)
        desc_raw = ld_data.get('description', '')
        desc = strip_html(desc_raw)
        
        location = "Unknown"
        job_loc = ld_data.get('jobLocation', {})
        if isinstance(job_loc, dict):
            addr = job_loc.get('address', {})
            if isinstance(addr, dict):
                parts = []
                for k in ['addressLocality', 'addressRegion', 'addressCountry']:
                    val = addr.get(k)
                    if val:
                        if isinstance(val, dict):
                            val = val.get('name', '')
                        if val:
                            parts.append(str(val))
                if parts:
                    location = ", ".join(parts)
        elif isinstance(job_loc, list) and len(job_loc) > 0:
            addr = job_loc[0].get('address', {})
            if isinstance(addr, dict):
                parts = []
                for k in ['addressLocality', 'addressRegion', 'addressCountry']:
                    val = addr.get(k)
                    if val:
                        if isinstance(val, dict):
                            val = val.get('name', '')
                        if val:
                            parts.append(str(val))
                if parts:
                    location = ", ".join(parts)

        # Compute final job_id with real title
        final_job_id = compute_job_id(company_name, real_title, url)
        if final_job_id in existing_job_ids:
            continue
            
        jobs.append({
            'source': identifier,
            'company': company_name,
            'title': real_title,
            'url': url,
            'location': location,
            'salary_range': '',
            'description_raw': desc
        })
        
        existing_job_ids.add(final_job_id)
        existing_job_ids.add(job_id)

    return jobs
