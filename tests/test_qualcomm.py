import pytest
from job_sources.custom import qualcomm
from job_sources.dedup import compute_job_id


class FakeResponse:
    def __init__(self, content="", text=""):
        self.content = content.encode("utf-8") if isinstance(content, str) else content
        self.text = text

    def raise_for_status(self):
        pass


def test_fetch_jobs_fetches_sitemap_and_skips_landing_page(monkeypatch):
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://careers.qualcomm.com/careers</loc>
    </url>
    <url>
        <loc>https://careers.qualcomm.com/careers/job/123-software-engineer--remote?domain=qualcomm.com</loc>
    </url>
</urlset>
"""
    
    def fake_get(url, timeout=None):
        if "sitemap.xml" in url:
            return FakeResponse(content=sitemap_xml)
        else:
            return FakeResponse(text='<script type="application/ld+json">{"@type": "JobPosting", "title": "Software Engineer", "description": "<p>C++</p>", "jobLocation": {"address": {"addressLocality": "San Diego", "addressRegion": "CA", "addressCountry": "US"}}}</script>')
            
    monkeypatch.setattr(qualcomm.requests, "get", fake_get)
    
    jobs = qualcomm.fetch_jobs("qualcomm")
    
    assert len(jobs) == 1
    job = jobs[0]
    assert job["source"] == "qualcomm"
    assert job["company"] == "Qualcomm"
    assert job["title"] == "Software Engineer"
    assert job["url"] == "https://careers.qualcomm.com/careers/job/123-software-engineer--remote?domain=qualcomm.com"
    assert job["location"] == "San Diego, CA, US"
    assert job["description_raw"] == "C++"


def test_fetch_jobs_skips_known_job_ids(monkeypatch):
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://careers.qualcomm.com/careers</loc>
    </url>
    <url>
        <loc>https://careers.qualcomm.com/careers/job/123-software-engineer--remote?domain=qualcomm.com</loc>
    </url>
</urlset>
"""
    known_url = "https://careers.qualcomm.com/careers/job/123-software-engineer--remote?domain=qualcomm.com"
    known_id = compute_job_id("Qualcomm", "Software Engineer", known_url)
    
    detail_calls = []
    
    def fake_get(url, timeout=None):
        if "sitemap.xml" in url:
            return FakeResponse(content=sitemap_xml)
        detail_calls.append(url)
        return FakeResponse(text='<script type="application/ld+json">{"@type": "JobPosting"}</script>')
        
    monkeypatch.setattr(qualcomm.requests, "get", fake_get)
    
    jobs = qualcomm.fetch_jobs("qualcomm", existing_job_ids={known_id})
    assert len(jobs) == 0
    assert len(detail_calls) == 0


def test_target_roles_filtering(monkeypatch):
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://careers.qualcomm.com/careers</loc>
    </url>
    <url>
        <loc>https://careers.qualcomm.com/careers/job/123-software-engineer--remote</loc>
    </url>
    <url>
        <loc>https://careers.qualcomm.com/careers/job/456-data-scientist--remote</loc>
    </url>
</urlset>
"""
    detail_calls = []
    
    def fake_get(url, timeout=None):
        if "sitemap.xml" in url:
            return FakeResponse(content=sitemap_xml)
        detail_calls.append(url)
        if "software-engineer" in url:
            return FakeResponse(text='<script type="application/ld+json">{"@type": "JobPosting", "title": "Software Engineer", "description": ""}</script>')
        return FakeResponse(text='<script type="application/ld+json">{"@type": "JobPosting", "title": "Data Scientist", "description": ""}</script>')
        
    monkeypatch.setattr(qualcomm.requests, "get", fake_get)
    
    jobs = qualcomm.fetch_jobs("qualcomm", target_roles=["data"])
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Data Scientist"
    
    # ensure it only fetched details for the matching one
    assert len(detail_calls) == 1
    assert "456-data-scientist" in detail_calls[0]
