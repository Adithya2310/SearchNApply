import pytest

from digest.engine import run_digest
from digest.formatter import format_digest
from digest.mailer import send_email
from sheets.client import SheetsClient
from tests.fake_gspread import FakeGspreadClient, FakeSpreadsheet


class FakeSMTP:
    sent = []
    logins = []

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, addr, password):
        FakeSMTP.logins.append((addr, password))

    def sendmail(self, from_addr, to_addrs, message):
        FakeSMTP.sent.append((from_addr, to_addrs, message))


@pytest.fixture(autouse=True)
def reset_fake_smtp(monkeypatch):
    FakeSMTP.sent = []
    FakeSMTP.logins = []
    monkeypatch.setenv("GMAIL_ADDRESS", "me@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")


def _job_row(job_id, title, match_score, status="New", company="Acme", url="https://x/1", location="Remote", salary_range=""):
    return {
        "job_id": job_id,
        "source": "greenhouse",
        "company": company,
        "title": title,
        "url": url,
        "location": location,
        "salary_range": salary_range,
        "description_raw": "",
        "match_score": match_score,
        "date_found": "2026-08-12",
        "status": status,
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
    c.append_row("Config", {"key": "match_threshold", "value": 40})
    return c


# ---- mailer ----


def test_send_email_strips_spaces_from_app_password(monkeypatch):
    monkeypatch.setattr("digest.mailer.smtplib.SMTP", FakeSMTP)
    send_email(
        "subject",
        "body",
        to_addr="me@example.com",
        from_addr="me@example.com",
        app_password="abcd efgh ijkl mnop",
    )
    assert FakeSMTP.logins == [("me@example.com", "abcdefghijklmnop")]
    assert len(FakeSMTP.sent) == 1


def test_send_email_defaults_recipient_to_sender(monkeypatch):
    monkeypatch.setattr("digest.mailer.smtplib.SMTP", FakeSMTP)
    send_email("s", "b", from_addr="me@example.com", app_password="x")
    from_addr, to_addrs, _ = FakeSMTP.sent[0]
    assert to_addrs == ["me@example.com"]


# ---- formatter ----


def test_format_digest_sorts_best_match_first():
    jobs = [
        _job_row("j1", "Low Match", 50),
        _job_row("j2", "High Match", 90),
    ]
    subject, text_body, html_body = format_digest(jobs)
    assert "2 new matches" in subject
    assert text_body.index("High Match") < text_body.index("Low Match")
    assert html_body.index("High Match") < html_body.index("Low Match")


def test_format_digest_escapes_html_special_characters():
    jobs = [_job_row("j1", "C++ <Senior> Engineer", 80, company="R&D Corp")]
    _, _, html_body = format_digest(jobs)
    assert "<Senior>" not in html_body
    assert "&lt;Senior&gt;" in html_body
    assert "R&amp;D Corp" in html_body


def test_format_digest_singular_wording_for_one_job():
    subject, text_body, _ = format_digest([_job_row("j1", "Solo Match", 80)])
    assert "1 new match" in subject
    assert "matches" not in subject


# ---- engine ----


def test_run_digest_sends_and_marks_reviewed(client, monkeypatch):
    monkeypatch.setattr("digest.mailer.smtplib.SMTP", FakeSMTP)
    client.append_rows(
        "Jobs",
        [
            _job_row("j1", "Good Match", 80, status="New"),
            _job_row("j2", "Below Threshold", 10, status="New"),
            _job_row("j3", "Already Reviewed", 90, status="Reviewed"),
        ],
    )

    result = run_digest(client)

    assert result == {"sent": True, "count": 1}
    assert len(FakeSMTP.sent) == 1
    rows = {r["job_id"]: r for r in client.get_rows("Jobs")}
    assert rows["j1"]["status"] == "Reviewed"
    assert rows["j2"]["status"] == "New"  # below threshold, untouched
    assert rows["j3"]["status"] == "Reviewed"  # was already Reviewed, untouched


def test_run_digest_no_op_when_nothing_qualifies(client, monkeypatch):
    monkeypatch.setattr("digest.mailer.smtplib.SMTP", FakeSMTP)
    client.append_rows("Jobs", [_job_row("j1", "Below Threshold", 10, status="New")])

    result = run_digest(client)

    assert result == {"sent": False, "count": 0}
    assert FakeSMTP.sent == []


def test_run_digest_second_run_only_sends_genuinely_new_matches(client, monkeypatch):
    monkeypatch.setattr("digest.mailer.smtplib.SMTP", FakeSMTP)
    client.append_rows("Jobs", [_job_row("j1", "First Batch", 80, status="New")])
    run_digest(client)
    assert len(FakeSMTP.sent) == 1

    client.append_rows("Jobs", [_job_row("j2", "Second Batch", 85, status="New")])
    result = run_digest(client)

    assert result == {"sent": True, "count": 1}  # only j2, j1 already Reviewed
    assert len(FakeSMTP.sent) == 2
