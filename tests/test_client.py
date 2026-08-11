import pytest

from sheets.client import SheetsClient
from sheets.schema import SHEETS
from tests.fake_gspread import FakeGspreadClient, FakeSpreadsheet


@pytest.fixture
def fake_spreadsheet(monkeypatch):
    spreadsheet = FakeSpreadsheet()
    monkeypatch.setattr(
        "sheets.client.Credentials.from_service_account_file",
        lambda path, scopes: object(),
    )
    monkeypatch.setattr(
        "sheets.client.gspread.authorize",
        lambda creds: FakeGspreadClient(spreadsheet),
    )
    return spreadsheet


@pytest.fixture
def client(fake_spreadsheet):
    return SheetsClient(spreadsheet_id="fake-id", credentials_path="fake-path.json")


def test_ensure_schema_creates_missing_tabs(client, fake_spreadsheet):
    client.ensure_schema()

    assert set(fake_spreadsheet._worksheets.keys()) == set(SHEETS.keys())
    for sheet_name, columns in SHEETS.items():
        ws = fake_spreadsheet.worksheet(sheet_name)
        assert ws.row_values(1) == columns


def test_ensure_schema_fills_in_header_on_empty_existing_tab(client, fake_spreadsheet):
    fake_spreadsheet.add_worksheet("Jobs", rows=1000, cols=11)

    client.ensure_schema()

    assert fake_spreadsheet.worksheet("Jobs").row_values(1) == SHEETS["Jobs"]


def test_ensure_schema_raises_on_mismatched_header(client, fake_spreadsheet):
    ws = fake_spreadsheet.add_worksheet("Jobs", rows=1000, cols=11)
    ws.append_row(["job_id", "company"])  # wrong/incomplete header

    with pytest.raises(ValueError):
        client.ensure_schema()


def test_append_and_get_rows(client):
    client.ensure_schema()

    client.append_row(
        "Jobs",
        {"job_id": "abc123", "company": "Acme", "title": "SWE", "status": "New"},
    )

    rows = client.get_rows("Jobs")
    assert len(rows) == 1
    assert rows[0]["job_id"] == "abc123"
    assert rows[0]["company"] == "Acme"
    assert rows[0]["title"] == "SWE"
    assert rows[0]["status"] == "New"
    # columns not passed default to blank
    assert rows[0]["source"] == ""


def test_find_row_index(client):
    client.ensure_schema()
    client.append_row("Jobs", {"job_id": "abc123", "company": "Acme"})
    client.append_row("Jobs", {"job_id": "def456", "company": "Globex"})

    assert client.find_row_index("Jobs", "job_id", "def456") == 3
    assert client.find_row_index("Jobs", "job_id", "missing") is None


def test_update_row_merges_without_clobbering_other_columns(client):
    client.ensure_schema()
    client.append_row(
        "Jobs", {"job_id": "abc123", "company": "Acme", "title": "SWE", "status": "New"}
    )

    client.update_row("Jobs", "job_id", "abc123", {"status": "Reviewed"})

    rows = client.get_rows("Jobs")
    assert rows[0]["status"] == "Reviewed"
    assert rows[0]["company"] == "Acme"
    assert rows[0]["title"] == "SWE"


def test_update_row_raises_when_id_not_found(client):
    client.ensure_schema()

    with pytest.raises(ValueError):
        client.update_row("Jobs", "job_id", "missing", {"status": "Reviewed"})


def test_append_row_rejects_unknown_sheet(client):
    client.ensure_schema()

    with pytest.raises(ValueError):
        client.append_row("NotASheet", {"foo": "bar"})
