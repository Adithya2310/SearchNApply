from datetime import datetime, timedelta, timezone

import pytest

from job_sources import aggregator
from sheets.client import SheetsClient
from tests.fake_gspread import FakeGspreadClient, FakeSpreadsheet


@pytest.fixture
def client(monkeypatch):
    spreadsheet = FakeSpreadsheet()
    monkeypatch.setattr(
        "sheets.client.Credentials.from_service_account_file",
        lambda path, scopes: object(),
    )
    monkeypatch.setattr(
        "sheets.client.gspread.authorize",
        lambda creds: FakeGspreadClient(spreadsheet),
    )
    c = SheetsClient(spreadsheet_id="fake-id", credentials_path="fake-path.json")
    c.ensure_schema()
    return c


def _job(company, title, url, **extra):
    return {
        "source": "greenhouse",
        "company": company,
        "title": title,
        "url": url,
        "location": "",
        "salary_range": "",
        "description_raw": "",
        **extra,
    }


def test_run_scan_dedupes_across_sources_and_runs(client, monkeypatch):
    client.append_row("Config", {"key": "greenhouse_boards", "value": "acme"})
    client.append_row("Config", {"key": "lever_companies", "value": "acme"})

    same_job = _job("Acme", "Backend Engineer", "https://acme.example/jobs/1")
    monkeypatch.setattr(aggregator.greenhouse, "fetch_jobs", lambda board: [same_job])
    monkeypatch.setattr(aggregator.lever, "fetch_jobs", lambda company: [same_job])

    summary = aggregator.run_scan(client, today="2026-08-12")

    assert summary["greenhouse:acme"] == 1
    assert summary["lever:acme"] == 0  # same company+title+url -> same job_id, deduped
    assert len(client.get_rows("Jobs")) == 1

    # running again with the same source data adds nothing new
    summary2 = aggregator.run_scan(client, today="2026-08-12")
    assert summary2["greenhouse:acme"] == 0
    assert len(client.get_rows("Jobs")) == 1


def test_run_scan_continues_after_one_source_errors(client, monkeypatch):
    client.append_row("Config", {"key": "greenhouse_boards", "value": "broken,ok"})

    def fetch_jobs(board):
        if board == "broken":
            raise RuntimeError("404")
        return [_job("OkCo", "SWE", "https://ok.example/1")]

    monkeypatch.setattr(aggregator.greenhouse, "fetch_jobs", fetch_jobs)

    summary = aggregator.run_scan(client, today="2026-08-12")

    assert summary["greenhouse:broken"] == "error: 404"
    assert summary["greenhouse:ok"] == 1
    assert len(client.get_rows("Jobs")) == 1


def test_jsearch_skipped_when_interval_not_elapsed(client, monkeypatch):
    client.append_row("Config", {"key": "target_roles", "value": "software engineer"})
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    client.append_row("Config", {"key": "jsearch_last_run", "value": recent})
    monkeypatch.setenv("JSEARCH_SCAN_INTERVAL_HOURS", "12")

    called = []
    monkeypatch.setattr(
        aggregator.jsearch, "fetch_jobs", lambda query: called.append(query) or []
    )

    summary = aggregator.run_scan(client, today="2026-08-12")

    assert called == []
    assert summary["jsearch"] == "skipped (JSEARCH_SCAN_INTERVAL_HOURS not elapsed)"


def test_jsearch_runs_when_interval_elapsed_and_updates_last_run(client, monkeypatch):
    client.append_row("Config", {"key": "target_roles", "value": "software engineer"})
    stale = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    client.append_row("Config", {"key": "jsearch_last_run", "value": stale})
    monkeypatch.setenv("JSEARCH_SCAN_INTERVAL_HOURS", "12")

    called = []

    def fake_fetch(query):
        called.append(query)
        return [_job("JSCo", "SWE", "https://js.example/1", source="jsearch")]

    monkeypatch.setattr(aggregator.jsearch, "fetch_jobs", fake_fetch)

    summary = aggregator.run_scan(client, today="2026-08-12")

    assert called == ["software engineer"]
    assert summary["jsearch:software engineer"] == 1
    config = {r["key"]: r["value"] for r in client.get_rows("Config")}
    assert config["jsearch_last_run"] != stale
