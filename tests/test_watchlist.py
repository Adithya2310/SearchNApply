import pytest

from watchlist import monitor
from sheets.client import SheetsClient
from tests.fake_gspread import FakeGspreadClient, FakeSpreadsheet
from tests.test_digest import FakeSMTP

RESUME_PROFILE = {
    "skills": {"languages": ["Python"], "technologies_tools": []},
    "work_experience": [{"company": "Co", "tech_stack": ["Python"]}],
}


def _job(company, title, url, description_raw=""):
    return {
        "source": "greenhouse",
        "company": company,
        "title": title,
        "url": url,
        "location": "",
        "salary_range": "",
        "description_raw": description_raw,
    }


@pytest.fixture(autouse=True)
def reset_fake_smtp(monkeypatch):
    FakeSMTP.sent = []
    FakeSMTP.logins = []
    monkeypatch.setenv("GMAIL_ADDRESS", "me@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "abcd")
    monkeypatch.setattr("digest.mailer.smtplib.SMTP", FakeSMTP)


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


def test_skips_inactive_and_blank_active_watchlist_rows(client, monkeypatch):
    client.append_rows(
        "Watchlist",
        [
            {"company_name": "Inactive Co", "careers_source": "greenhouse", "careers_identifier": "x", "active": "N"},
            {"company_name": "Blank Active Co", "careers_source": "greenhouse", "careers_identifier": "y", "active": ""},
        ],
    )
    called = []
    monkeypatch.setattr(monitor.greenhouse, "fetch_jobs", lambda identifier, company_name: called.append(identifier) or [])

    summary = monitor.run_watchlist_scan(client, RESUME_PROFILE)

    assert called == []
    assert summary == {"alert_sent": 0}


def test_new_matching_listing_is_added_scored_and_alerted(client, monkeypatch):
    client.append_row(
        "Watchlist",
        {"company_name": "Acme", "careers_source": "greenhouse", "careers_identifier": "acme", "active": "Y"},
    )
    monkeypatch.setattr(
        monitor.greenhouse,
        "fetch_jobs",
        lambda identifier, company_name: [_job("Acme", "Python Engineer", "https://acme/1", "python role")],
    )

    summary = monitor.run_watchlist_scan(client, RESUME_PROFILE, today="2026-08-12")

    assert summary["watchlist:Acme"] == 1
    assert summary["alert_sent"] == 1
    assert len(FakeSMTP.sent) == 1
    subject = FakeSMTP.sent[0][2]
    assert "Watchlist Alert" in subject

    rows = client.get_rows("Jobs")
    assert len(rows) == 1
    assert rows[0]["source"] == "watchlist:Acme"
    assert rows[0]["status"] == "Reviewed"  # alerted -> marked Reviewed
    assert int(rows[0]["match_score"]) > 0

    watchlist_rows = client.get_rows("Watchlist")
    assert watchlist_rows[0]["last_checked"] != ""


def test_non_matching_listing_is_logged_but_not_alerted(client, monkeypatch):
    client.append_row(
        "Watchlist",
        {"company_name": "Acme", "careers_source": "greenhouse", "careers_identifier": "acme", "active": "Y"},
    )
    monkeypatch.setattr(
        monitor.greenhouse,
        "fetch_jobs",
        lambda identifier, company_name: [_job("Acme", "Chef", "https://acme/2", "cooking only")],
    )

    summary = monitor.run_watchlist_scan(client, RESUME_PROFILE, today="2026-08-12")

    assert summary["watchlist:Acme"] == 1
    assert summary["alert_sent"] == 0
    assert FakeSMTP.sent == []

    rows = client.get_rows("Jobs")
    assert len(rows) == 1
    assert rows[0]["status"] == "Ignored"  # logged silently, per DESIGN.md


def test_dedupes_against_existing_jobs_rows(client, monkeypatch):
    client.append_row(
        "Watchlist",
        {"company_name": "Acme", "careers_source": "greenhouse", "careers_identifier": "acme", "active": "Y"},
    )
    from job_sources.dedup import compute_job_id

    existing = _job("Acme", "Python Engineer", "https://acme/1", "python role")
    existing_id = compute_job_id(existing["company"], existing["title"], existing["url"])
    client.append_row(
        "Jobs",
        {**existing, "job_id": existing_id, "match_score": 80, "date_found": "2026-08-01", "status": "Reviewed"},
    )
    monkeypatch.setattr(monitor.greenhouse, "fetch_jobs", lambda identifier, company_name: [existing])

    summary = monitor.run_watchlist_scan(client, RESUME_PROFILE, today="2026-08-12")

    assert summary["watchlist:Acme"] == 0
    assert summary["alert_sent"] == 0
    assert len(client.get_rows("Jobs")) == 1  # not duplicated


def test_one_company_fetch_error_does_not_block_others(client, monkeypatch):
    client.append_rows(
        "Watchlist",
        [
            {"company_name": "Broken Co", "careers_source": "greenhouse", "careers_identifier": "broken", "active": "Y"},
            {"company_name": "Acme", "careers_source": "lever", "careers_identifier": "acme", "active": "Y"},
        ],
    )

    def broken_fetch(identifier, company_name):
        raise RuntimeError("404")

    monkeypatch.setattr(monitor.greenhouse, "fetch_jobs", broken_fetch)
    monkeypatch.setattr(
        monitor.lever,
        "fetch_jobs",
        lambda identifier, company_name: [_job("Acme", "Python Engineer", "https://acme/1", "python role")],
    )

    summary = monitor.run_watchlist_scan(client, RESUME_PROFILE, today="2026-08-12")

    assert summary["watchlist:Broken Co"] == "error: 404"
    assert summary["watchlist:Acme"] == 1


def test_unsupported_careers_source_is_skipped_not_fatal(client, monkeypatch):
    client.append_row(
        "Watchlist",
        {"company_name": "BigCo", "careers_source": "workday", "careers_identifier": "bigco", "active": "Y"},
    )

    summary = monitor.run_watchlist_scan(client, RESUME_PROFILE)

    assert "unsupported careers_source" in summary["watchlist:BigCo"]
