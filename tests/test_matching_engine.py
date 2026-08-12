import pytest

from matching.engine import run_matching
from sheets.client import SheetsClient
from tests.fake_gspread import FakeGspreadClient, FakeSpreadsheet

RESUME_PROFILE = {
    "skills": {"languages": ["Python"], "technologies_tools": []},
    "work_experience": [{"company": "Co", "tech_stack": ["Python"]}],
}


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


def _job_row(job_id, title, description_raw="", status="New"):
    return {
        "job_id": job_id,
        "source": "greenhouse",
        "company": "Acme",
        "title": title,
        "url": f"https://example.com/{job_id}",
        "location": "",
        "salary_range": "",
        "description_raw": description_raw,
        "match_score": "",
        "date_found": "2026-08-12",
        "status": status,
    }


def test_run_matching_scores_new_rows_and_ignores_below_threshold(client):
    client.append_rows(
        "Jobs",
        [
            _job_row("job1", "Python Engineer", "python role, great fit"),
            _job_row("job2", "Chef", "cooking only, no tech at all"),
        ],
    )

    result = run_matching(client, RESUME_PROFILE)

    rows = {r["job_id"]: r for r in client.get_rows("Jobs")}
    assert result["scored"] == 2
    assert rows["job1"]["match_score"] != ""
    assert int(rows["job1"]["match_score"]) > 0
    assert rows["job1"]["status"] == "New"  # above threshold, left alone

    assert int(rows["job2"]["match_score"]) < 40
    assert rows["job2"]["status"] == "Ignored"
    assert result["ignored"] == 1


def test_run_matching_is_idempotent_and_never_rescoresor_unignores(client):
    client.append_rows("Jobs", [_job_row("job1", "Python Engineer", "python role")])
    run_matching(client, RESUME_PROFILE)

    rows = client.get_rows("Jobs")
    first_score = rows[0]["match_score"]

    # user manually reviewed it in the dashboard after scoring
    client.update_row("Jobs", "job_id", "job1", {"status": "Interested"})

    result_again = run_matching(client, RESUME_PROFILE)

    rows_again = client.get_rows("Jobs")
    assert result_again["scored"] == 0  # already-scored row untouched
    assert rows_again[0]["match_score"] == first_score
    assert rows_again[0]["status"] == "Interested"  # not clobbered back to New/Ignored


def test_run_matching_no_op_when_nothing_to_score(client):
    result = run_matching(client, RESUME_PROFILE)
    assert result == {"scored": 0, "ignored": 0}
