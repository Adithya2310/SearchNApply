import pytest

import dashboard
from sheets.client import SheetsClient
from tests.fake_gspread import FakeGspreadClient, FakeSpreadsheet


@pytest.fixture
def client(monkeypatch):
    spreadsheet = FakeSpreadsheet()
    monkeypatch.setattr("sheets.client.Credentials.from_service_account_file", lambda path, scopes: object())
    monkeypatch.setattr("sheets.client.gspread.authorize", lambda creds: FakeGspreadClient(spreadsheet))
    c = SheetsClient(spreadsheet_id="fake-id", credentials_path="fake-path.json")
    c.ensure_schema()
    return c


def _job(job_id="job1", **overrides):
    row = {
        "job_id": job_id,
        "source": "greenhouse",
        "company": "Acme",
        "title": "Software Engineer",
        "url": "https://acme.example/jobs/1",
        "match_score": 80,
        "status": "New",
    }
    row.update(overrides)
    return row


def test_mark_interested_creates_applications_row_and_moves_job(client):
    client.append_row("Jobs", _job())

    dashboard.mark_interested(client, _job())

    app_rows = client.get_rows("Applications")
    assert len(app_rows) == 1
    assert app_rows[0]["linked_job_id"] == "job1"
    assert app_rows[0]["source_type"] == "auto-discovered"
    assert app_rows[0]["company"] == "Acme"
    assert app_rows[0]["role"] == "Software Engineer"
    assert app_rows[0]["status"] == "Interested"

    job_rows = client.get_rows("Jobs")
    assert job_rows[0]["status"] == "Moved to Applications"


def test_mark_interested_is_idempotent_not_duplicated(client):
    client.append_row("Jobs", _job())

    dashboard.mark_interested(client, _job())
    dashboard.mark_interested(client, _job())

    assert len(client.get_rows("Applications")) == 1


def test_mark_ignored_only_updates_jobs_status(client):
    client.append_row("Jobs", _job())

    dashboard.mark_ignored(client, _job())

    assert client.get_rows("Jobs")[0]["status"] == "Ignored"
    assert client.get_rows("Applications") == []
