"""One-time live check that Sheets credentials/schema are wired up correctly.

Run after filling in GOOGLE_APPLICATION_CREDENTIALS and
GOOGLE_SHEETS_SPREADSHEET_ID in .env:

    python scripts/verify_sheets_setup.py

Creates any missing tabs/headers on the real Sheet, writes one throwaway
row to Jobs, reads it back, then updates it — exits non-zero on failure.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from sheets import SheetsClient

load_dotenv()


def main():
    client = SheetsClient()
    client.ensure_schema()
    print("Schema OK: all 5 tabs present with correct headers.")

    client.append_row(
        "Jobs",
        {
            "job_id": "verify-sheets-setup-smoke-test",
            "company": "Smoke Test Co",
            "title": "Setup Verification",
            "status": "New",
        },
    )
    print("Append OK.")

    rows = client.get_rows("Jobs")
    match = next(r for r in rows if r["job_id"] == "verify-sheets-setup-smoke-test")
    assert match["company"] == "Smoke Test Co"
    print("Read OK.")

    client.update_row(
        "Jobs", "job_id", "verify-sheets-setup-smoke-test", {"status": "Ignored"}
    )
    rows = client.get_rows("Jobs")
    match = next(r for r in rows if r["job_id"] == "verify-sheets-setup-smoke-test")
    assert match["status"] == "Ignored"
    print("Update OK.")

    print(
        "\nAll checks passed. Delete the 'verify-sheets-setup-smoke-test' row "
        "from the Jobs tab before moving on."
    )


if __name__ == "__main__":
    main()
