import pytest
from job_sources.custom.fm_global import fetch_jobs
from job_sources.dedup import compute_job_id

class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception("HTTP Error")

def test_fetch_jobs_success(monkeypatch):
    mock_data = {
        "jobs": [
            {
                "data": {
                    "title": "Software Engineer",
                    "meta_data": {"canonical_url": "https://careers.fm.com/jobs/123"},
                    "full_location": "Boston, MA",
                    "description": "<p>Great job</p>",
                    "salary_min_value": 100000,
                    "salary_max_value": 150000
                }
            },
            {
                "data": {
                    "title": "Data Scientist",
                    "meta_data": {"canonical_url": "https://careers.fm.com/jobs/456"},
                    "full_location": "Remote",
                    "description": "<b>Awesome job</b>"
                }
            }
        ]
    }

    call_count = 0
    def mock_get(url, headers=None, params=None, timeout=None):
        nonlocal call_count
        call_count += 1
        return FakeResponse(mock_data)

    monkeypatch.setattr("requests.get", mock_get)

    jobs = fetch_jobs("fm_global")
    assert len(jobs) == 2
    assert jobs[0]["title"] == "Software Engineer"
    assert jobs[0]["url"] == "https://careers.fm.com/jobs/123"
    assert jobs[0]["location"] == "Boston, MA"
    assert jobs[0]["salary_range"] == "$100000 - $150000"
    assert "Great job" in jobs[0]["description_raw"]
    
    assert jobs[1]["title"] == "Data Scientist"
    assert jobs[1]["url"] == "https://careers.fm.com/jobs/456"
    assert "Awesome job" in jobs[1]["description_raw"]
    assert jobs[1]["salary_range"] == ""

def test_fetch_jobs_existing_job_ids(monkeypatch):
    mock_data = {
        "jobs": [
            {
                "data": {
                    "title": "Existing Job",
                    "meta_data": {"canonical_url": "https://careers.fm.com/jobs/789"},
                    "full_location": "NY",
                    "description": "<p>Secret description</p>"
                }
            }
        ]
    }

    def mock_get(url, headers=None, params=None, timeout=None):
        return FakeResponse(mock_data)

    monkeypatch.setattr("requests.get", mock_get)

    company = "FM Global"
    job_id = compute_job_id(company, "Existing Job", "https://careers.fm.com/jobs/789")
    existing_ids = {job_id}

    jobs = fetch_jobs("fm_global", company_name=company, existing_job_ids=existing_ids)
    assert len(jobs) == 0  # Known jobs are skipped entirely

def test_fetch_jobs_dedup_queries(monkeypatch):
    mock_data_1 = {
        "jobs": [
            {
                "data": {
                    "title": "Engineer",
                    "meta_data": {"canonical_url": "https://careers.fm.com/jobs/999"},
                    "full_location": "NY"
                }
            }
        ]
    }
    
    # Second query returns the SAME job + one new one
    mock_data_2 = {
        "jobs": [
            {
                "data": {
                    "title": "Engineer",
                    "meta_data": {"canonical_url": "https://careers.fm.com/jobs/999"},
                    "full_location": "NY"
                }
            },
            {
                "data": {
                    "title": "Manager",
                    "meta_data": {"canonical_url": "https://careers.fm.com/jobs/1000"},
                    "full_location": "NY"
                }
            }
        ]
    }

    call_count = 0
    def mock_get(url, headers=None, params=None, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return FakeResponse(mock_data_1)
        else:
            return FakeResponse(mock_data_2)

    monkeypatch.setattr("requests.get", mock_get)

    jobs = fetch_jobs("fm_global", target_roles=["engineer", "manager"])
    assert len(jobs) == 2
    titles = [j["title"] for j in jobs]
    assert "Engineer" in titles
    assert "Manager" in titles
