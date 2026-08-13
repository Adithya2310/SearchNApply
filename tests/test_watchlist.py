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
        {"company_name": "BigCo", "careers_source": "made-up-source", "careers_identifier": "bigco", "active": "Y"},
    )

    summary = monitor.run_watchlist_scan(client, RESUME_PROFILE)

    assert "unsupported careers_source" in summary["watchlist:BigCo"]


def test_custom_scrape_source_with_no_matching_module_is_skipped_not_fatal(client, monkeypatch):
    # job_sources/custom/doesnotexist.py genuinely doesn't exist — this
    # exercises the real registry, not a mock, since "no scraper built yet"
    # for a custom-scrape company must be a normal, non-fatal outcome.
    client.append_row(
        "Watchlist",
        {
            "company_name": "BigCo",
            "careers_source": "custom-scrape",
            "careers_identifier": "doesnotexist",
            "active": "Y",
        },
    )

    summary = monitor.run_watchlist_scan(client, RESUME_PROFILE)

    assert "no custom scraper found for 'doesnotexist'" in summary["watchlist:BigCo"]


def test_custom_scrape_source_is_dispatched_via_registry(client, monkeypatch):
    client.append_row("Config", {"key": "target_roles", "value": "python engineer"})
    client.append_row(
        "Watchlist",
        {"company_name": "BigCo", "careers_source": "custom-scrape", "careers_identifier": "bigco", "active": "Y"},
    )

    calls = []

    def fake_fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None):
        calls.append((identifier, company_name, list(target_roles or []), set(existing_job_ids or set())))
        return [_job("BigCo", "Python Engineer", "https://bigco/1", "python role")]

    monkeypatch.setattr(
        monitor.custom_registry,
        "get_fetcher",
        lambda slug: fake_fetch_jobs if slug == "bigco" else None,
    )

    summary = monitor.run_watchlist_scan(client, RESUME_PROFILE, today="2026-08-12")

    assert len(calls) == 1
    identifier, company_name, target_roles, existing_ids = calls[0]
    assert identifier == "bigco"
    assert company_name == "BigCo"
    assert target_roles == ["python engineer"]
    assert existing_ids == set()

    assert summary["watchlist:BigCo"] == 1
    rows = client.get_rows("Jobs")
    assert rows[0]["source"] == "watchlist:BigCo"


def test_workday_source_is_dispatched_with_target_roles_and_existing_ids(client, monkeypatch):
    client.append_row("Config", {"key": "target_roles", "value": "python engineer,data scientist"})
    client.append_row(
        "Watchlist",
        {"company_name": "BigCo", "careers_source": "workday", "careers_identifier": "bigco/wd5/External", "active": "Y"},
    )

    calls = []

    def fake_fetch_jobs(identifier, queries, company_name=None, existing_job_ids=None):
        # snapshot now — existing_job_ids is the same mutable set the caller
        # keeps mutating for the rest of the run, so capture its state at
        # call time, not a live reference to it.
        calls.append((identifier, list(queries), company_name, set(existing_job_ids or set())))
        return [_job("BigCo", "Python Engineer", "https://bigco/1", "python role")]

    monkeypatch.setattr(monitor.workday, "fetch_jobs", fake_fetch_jobs)

    summary = monitor.run_watchlist_scan(client, RESUME_PROFILE, today="2026-08-12")

    assert len(calls) == 1
    identifier, queries, company_name, existing_ids = calls[0]
    assert identifier == "bigco/wd5/External"
    assert queries == ["python engineer", "data scientist"]
    assert company_name == "BigCo"
    assert existing_ids == set()  # Jobs sheet was empty at call time

    assert summary["watchlist:BigCo"] == 1
    rows = client.get_rows("Jobs")
    assert rows[0]["source"] == "watchlist:BigCo"
