import json
import sys

import pytest

import scripts.tailor_resume as tailor_resume
from sheets.client import SheetsClient
from tests.fake_gspread import FakeGspreadClient, FakeSpreadsheet

PROFILE = {"skills": {"languages": ["Python"], "technologies_tools": []}, "work_experience": []}


@pytest.fixture
def client(monkeypatch):
    spreadsheet = FakeSpreadsheet()
    monkeypatch.setattr("sheets.client.Credentials.from_service_account_file", lambda path, scopes: object())
    monkeypatch.setattr("sheets.client.gspread.authorize", lambda creds: FakeGspreadClient(spreadsheet))
    monkeypatch.setattr(tailor_resume, "SheetsClient", lambda: SheetsClient(spreadsheet_id="fake-id", credentials_path="fake-path.json"))
    c = SheetsClient(spreadsheet_id="fake-id", credentials_path="fake-path.json")
    c.ensure_schema()
    return c


def test_main_reads_resume_profile_path_from_config_not_the_hardcoded_default(
    tmp_path, monkeypatch, client
):
    # Regression test: load_config() (matching/config.py) doesn't expose
    # resume_profile_path — it's not one of M4's scoring keys — so main()
    # must read it from a raw Config dict instead. An earlier version used
    # load_config()'s dict here, which silently always fell back to the
    # hardcoded "resume_profile.json" default (which exists for real, since
    # tests run from the repo root) and both read the wrong profile *and*
    # would have written real answers into it.
    marker_profile = {**PROFILE, "skills": {"languages": ["MarkerLangXYZ"], "technologies_tools": []}}
    custom_path = tmp_path / "custom_profile.json"
    custom_path.write_text(json.dumps(marker_profile))
    client.append_row("Config", {"key": "resume_profile_path", "value": str(custom_path)})
    client.append_row(
        "Jobs",
        {
            "job_id": "abc123",
            "source": "greenhouse",
            "company": "Acme",
            "title": "Engineer",
            "description_raw": "some JD text",
        },
    )

    captured = {}

    def fake_find_skill_gaps(jd, profile, config):
        captured["profile"] = profile
        return []

    monkeypatch.setattr(tailor_resume, "find_skill_gaps", fake_find_skill_gaps)
    monkeypatch.setattr(tailor_resume, "tailor_resume", lambda *a, **k: "TAILORED TEXT")
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    monkeypatch.setattr(sys, "argv", ["tailor_resume.py", "--job-id", "abc123"])

    tailor_resume.main()

    assert captured["profile"]["skills"]["languages"] == ["MarkerLangXYZ"]
