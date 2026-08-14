import requests
import re
import logging
from xml.etree import ElementTree
import json

from job_sources.dedup import compute_job_id
from job_sources.utils import strip_html

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://careers.qualcomm.com/careers/sitemap.xml?domain=qualcomm.com"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None):
    if not company_name:
        company_name = "Qualcomm"
    if existing_job_ids is None:
        existing_job_ids = set()

    try:
        resp = requests.get(SITEMAP_URL, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch qualcomm sitemap: {e}")
        return []

    root = ElementTree.fromstring(resp.content)
    urls = root.findall("s:url/s:loc", NS)

    jobs = []

    # Skip the first url which is the careers landing page
    for loc in urls[1:]:
        url = loc.text.strip()
        if not url:
            continue

        match = re.search(r'/job/([^?]+)', url)
        if not match:
            continue

        slug = match.group(1)

        id_match = re.match(r'^\d+-(.*)$', slug)
        if id_match:
            rest = id_match.group(1)
        else:
            rest = slug

        if '--' in rest:
            title_slug, _ = rest.split('--', 1)
        else:
            title_slug = rest

        title = title_slug.replace('-', ' ').title()

        if target_roles:
            title_lower = title.lower()
            if not any(role.lower() in title_lower for role in target_roles):
                continue

        job_id = compute_job_id(company_name, title, url)
        if job_id in existing_job_ids:
            continue

        detail = fetch_job_detail(url)
        if not detail:
            continue

        jobs.append({
            "source": "qualcomm",
            "company": company_name,
            "title": title,
            "url": url,
            "location": detail.get("location", ""),
            "salary_range": "",
            "description_raw": detail.get("description", ""),
        })

    return jobs


def fetch_job_detail(url):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', resp.text, re.DOTALL)
    if not match:
        return None

    try:
        data = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return None

    if data.get("@type") != "JobPosting":
        return None

    title = data.get("title", "")
    description = strip_html(data.get("description", ""))

    loc_data = data.get("jobLocation", {})
    address = loc_data.get("address", {})

    loc_parts = []
    if isinstance(address, dict):
        if address.get("addressLocality"):
            loc_parts.append(address["addressLocality"])
        if address.get("addressRegion"):
            loc_parts.append(address["addressRegion"])
        if address.get("addressCountry"):
            loc_parts.append(address["addressCountry"])

    location = ", ".join(loc_parts)

    return {
        "title": title,
        "description": description,
        "location": location,
    }
