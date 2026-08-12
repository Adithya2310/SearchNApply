from job_sources import workday
from job_sources.dedup import compute_job_id


class FakeResponse:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def test_search_jobs_posts_expected_payload(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse({"jobPostings": [{"title": "Software Engineer"}]})

    monkeypatch.setattr(workday.requests, "post", fake_post)

    result = workday.search_jobs("bigco/wd5/External", query="python", limit=5)

    assert captured["url"] == "https://bigco.wd5.myworkdayjobs.com/wday/cxs/bigco/External/jobs"
    assert captured["json"] == {"appliedFacets": {}, "limit": 5, "offset": 0, "searchText": "python"}
    assert result == [{"title": "Software Engineer"}]


def test_fetch_jobs_skips_detail_fetch_for_already_known_jobs(monkeypatch):
    identifier = "bigco/wd5/External"
    listing = {
        "title": "Python Engineer",
        "externalPath": "/job/remote/Python-Engineer_R1",
        "locationsText": "Remote",
    }
    known_url = "https://bigco.wd5.myworkdayjobs.com/External/job/remote/Python-Engineer_R1"
    known_id = compute_job_id("BigCo", "Python Engineer", known_url)

    monkeypatch.setattr(workday, "search_jobs", lambda identifier, query="", limit=10, offset=0: [listing])

    detail_calls = []
    monkeypatch.setattr(
        workday,
        "fetch_job_detail",
        lambda identifier, path: detail_calls.append(path) or {"jobDescription": "should not be fetched"},
    )

    jobs = workday.fetch_jobs(
        identifier, ["python"], company_name="BigCo", existing_job_ids={known_id}
    )

    assert jobs == []
    assert detail_calls == []


def test_fetch_jobs_fetches_detail_only_for_new_listings(monkeypatch):
    identifier = "bigco/wd5/External"
    listing = {
        "title": "Python Engineer",
        "externalPath": "/job/remote/Python-Engineer_R1",
        "locationsText": "Remote",
    }

    monkeypatch.setattr(workday, "search_jobs", lambda identifier, query="", limit=10, offset=0: [listing])

    detail_calls = []

    def fake_detail(identifier, path):
        detail_calls.append(path)
        return {"jobDescription": "<p>Great python role</p>", "location": "Remote"}

    monkeypatch.setattr(workday, "fetch_job_detail", fake_detail)

    jobs = workday.fetch_jobs(identifier, ["python"], company_name="BigCo", existing_job_ids=set())

    assert len(jobs) == 1
    assert detail_calls == ["/job/remote/Python-Engineer_R1"]
    job = jobs[0]
    assert job["source"] == "workday"
    assert job["company"] == "BigCo"
    assert job["title"] == "Python Engineer"
    assert job["url"] == "https://bigco.wd5.myworkdayjobs.com/External/job/remote/Python-Engineer_R1"
    assert job["description_raw"] == "Great python role"


def test_fetch_jobs_dedupes_across_multiple_queries_within_one_run(monkeypatch):
    identifier = "bigco/wd5/External"
    listing = {
        "title": "Python Engineer",
        "externalPath": "/job/remote/Python-Engineer_R1",
        "locationsText": "Remote",
    }

    call_count = []

    def fake_search(identifier, query="", limit=10, offset=0):
        call_count.append(query)
        return [listing]  # same job returned for every query

    monkeypatch.setattr(workday, "search_jobs", fake_search)
    monkeypatch.setattr(workday, "fetch_job_detail", lambda identifier, path: {"jobDescription": ""})

    jobs = workday.fetch_jobs(
        identifier, ["python", "engineer"], company_name="BigCo", existing_job_ids=set()
    )

    assert call_count == ["python", "engineer"]
    assert len(jobs) == 1  # same url across both queries -> only counted once
