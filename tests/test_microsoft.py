import pytest
from unittest.mock import patch, MagicMock
from job_sources.custom.microsoft import fetch_jobs, extract_title_from_url
from job_sources.dedup import compute_job_id

def test_extract_title_from_url():
    url = "https://apply.careers.microsoft.com/careers/job/1970393556959696-senior-software-engineer-?domain=microsoft.com"
    title = extract_title_from_url(url)
    assert title == "Senior Software Engineer"
    
    url2 = "https://apply.careers.microsoft.com/careers/job/1970393556955022-supply-chain-program-manager-united-states-washington-redmond?domain=microsoft.com"
    title2 = extract_title_from_url(url2)
    assert title2 == "Supply Chain Program Manager United States Washington Redmond"

@patch('requests.get')
def test_fetch_jobs_basic(mock_get):
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://apply.careers.microsoft.com/careers?domain=microsoft.com</loc></url>
        <url><loc>https://apply.careers.microsoft.com/careers/job/123-software-engineer?domain=microsoft.com</loc></url>
    </urlset>"""
    
    job_html = """
    <html>
        <body>
            <script type="application/ld+json">
            {
                "@type": "JobPosting",
                "title": "Software Engineer",
                "description": "We are looking for a Software Engineer.",
                "jobLocation": {
                    "address": {
                        "addressLocality": "Redmond",
                        "addressRegion": "WA",
                        "addressCountry": "US"
                    }
                }
            }
            </script>
        </body>
    </html>
    """
    
    def side_effect(url, timeout=None):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        if 'sitemap.xml' in url:
            mock_resp.content = sitemap_xml.encode('utf-8')
            mock_resp.text = sitemap_xml
        else:
            mock_resp.content = job_html.encode('utf-8')
            mock_resp.text = job_html
        return mock_resp
        
    mock_get.side_effect = side_effect
    
    jobs = fetch_jobs('microsoft', target_roles=['software'])
    assert len(jobs) == 1
    job = jobs[0]
    assert job['title'] == "Software Engineer"
    assert job['location'] == "Redmond, WA, US"
    assert "We are looking for a Software Engineer." in job['description_raw']
    assert job['company'] == "Microsoft"

@patch('requests.get')
def test_fetch_jobs_dedup(mock_get):
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://apply.careers.microsoft.com/careers?domain=microsoft.com</loc></url>
        <url><loc>https://apply.careers.microsoft.com/careers/job/123-software-engineer?domain=microsoft.com</loc></url>
    </urlset>"""
    
    def side_effect(url, timeout=None):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.content = sitemap_xml.encode('utf-8')
        return mock_resp
        
    mock_get.side_effect = side_effect
    
    url = "https://apply.careers.microsoft.com/careers/job/123-software-engineer?domain=microsoft.com"
    existing_id = compute_job_id("Microsoft", "Software Engineer", url)
    
    jobs = fetch_jobs('microsoft', existing_job_ids={existing_id})
    assert len(jobs) == 0
    assert mock_get.call_count == 1 # only sitemap
