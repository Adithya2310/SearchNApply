from job_sources.custom import amd
from job_sources.dedup import compute_job_id


class FakeResponse:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def test_fetch_jobs_paginates_and_returns_jobs(monkeypatch):
    captured_urls = []

    def fake_get(url, timeout=None):
        captured_urls.append(url)
        if "page=1" in url:
            return FakeResponse({
                "totalCount": 150,
                "jobs": [
                    {
                        "data": {
                            "title": "Software Engineer",
                            "meta_data": {"canonical_url": "https://careers.amd.com/jobs/1"},
                            "description": "<p>Great role 1</p>",
                            "full_location": "Austin, Texas",
                        }
                    }
                ]
            })
        else:
            return FakeResponse({
                "totalCount": 150,
                "jobs": [
                    {
                        "data": {
                            "title": "Hardware Engineer",
                            "apply_url": "https://global-external-amd.icims.com/jobs/2/login",
                            "description": "<p>Great role 2</p>",
                            "full_location": "Santa Clara, California",
                            "salary_min_value": "100000",
                            "salary_max_value": "150000"
                        }
                    }
                ]
            })

    monkeypatch.setattr(amd.requests, "get", fake_get)

    jobs = amd.fetch_jobs("amd", company_name="AMD")
    
    assert len(captured_urls) == 2
    assert "limit=100&page=1" in captured_urls[0]
    assert "limit=100&page=2" in captured_urls[1]
    
    assert len(jobs) == 2
    assert jobs[0]["title"] == "Software Engineer"
    assert jobs[0]["url"] == "https://careers.amd.com/jobs/1"
    assert jobs[0]["description_raw"] == "Great role 1"
    assert jobs[0]["location"] == "Austin, Texas"
    
    assert jobs[1]["title"] == "Hardware Engineer"
    assert jobs[1]["url"] == "https://global-external-amd.icims.com/jobs/2/login"
    assert jobs[1]["description_raw"] == "Great role 2"
    assert jobs[1]["location"] == "Santa Clara, California"
    assert jobs[1]["salary_range"] == "$100000 - $150000"


def test_fetch_jobs_filters_by_target_roles(monkeypatch):
    def fake_get(url, timeout=None):
        return FakeResponse({
            "totalCount": 2,
            "jobs": [
                {
                    "data": {
                        "title": "Software Engineer",
                        "meta_data": {"canonical_url": "https://careers.amd.com/jobs/1"},
                    }
                },
                {
                    "data": {
                        "title": "Sales Manager",
                        "meta_data": {"canonical_url": "https://careers.amd.com/jobs/2"},
                    }
                }
            ]
        })

    monkeypatch.setattr(amd.requests, "get", fake_get)

    jobs = amd.fetch_jobs("amd", target_roles=["engineer"])
    
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Software Engineer"


def test_fetch_jobs_skips_existing_jobs(monkeypatch):
    known_url = "https://careers.amd.com/jobs/1"
    known_id = compute_job_id("AMD", "Software Engineer", known_url)

    def fake_get(url, timeout=None):
        return FakeResponse({
            "totalCount": 1,
            "jobs": [
                {
                    "data": {
                        "title": "Software Engineer",
                        "meta_data": {"canonical_url": known_url},
                    }
                }
            ]
        })

    monkeypatch.setattr(amd.requests, "get", fake_get)

    jobs = amd.fetch_jobs("amd", company_name="AMD", existing_job_ids={known_id})
    assert jobs == []
