"""Live (non-mocked) verification of all 5 tabs against the real Sheet.

For each tab: confirm the header matches schema.py (== DESIGN.md Section 2)
exactly, append a marked test row, read it back, then delete it.

    python scripts/verify_all_sheets.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sheets import SheetsClient
from sheets.schema import SHEETS

MARKER = "verify-all-sheets-smoke-test"

TEST_ROWS = {
    "Jobs": {"job_id": MARKER, "source": "greenhouse", "company": "Acme", "status": "New"},
    "Applications": {"app_id": MARKER, "source_type": "manual", "company": "Acme", "status": "Applied"},
    "Contacts": {"contact_id": MARKER, "name": "Jane Recruiter", "company": "Acme"},
    "Config": {"key": MARKER, "value": "test"},
    "Watchlist": {"company_name": MARKER, "careers_source": "greenhouse", "active": "Y"},
}

ID_COLUMNS = {
    "Jobs": "job_id",
    "Applications": "app_id",
    "Contacts": "contact_id",
    "Config": "key",
    "Watchlist": "company_name",
}


def main():
    client = SheetsClient()
    client.ensure_schema()

    results = {}
    for sheet_name, columns in SHEETS.items():
        ws = client._worksheet(sheet_name)
        header = ws.row_values(1)
        header_ok = header == columns
        print(f"[{sheet_name}] header matches DESIGN.md: {header_ok}")
        if not header_ok:
            print(f"  expected: {columns}")
            print(f"  actual:   {header}")
        results[sheet_name] = {"header_ok": header_ok}

    for sheet_name, row in TEST_ROWS.items():
        id_col = ID_COLUMNS[sheet_name]
        client.append_row(sheet_name, row)
        read_back = [r for r in client.get_rows(sheet_name) if r[id_col] == MARKER]
        write_read_ok = len(read_back) == 1 and all(
            read_back[0][k] == v for k, v in row.items()
        )
        print(f"[{sheet_name}] write+read-back ok: {write_read_ok}")
        results[sheet_name]["write_read_ok"] = write_read_ok

        idx = client.find_row_index(sheet_name, id_col, MARKER)
        client._worksheet(sheet_name).delete_rows(idx)
        still_there = client.find_row_index(sheet_name, id_col, MARKER) is not None
        print(f"[{sheet_name}] cleanup ok: {not still_there}")
        results[sheet_name]["cleanup_ok"] = not still_there

    print()
    overall = all(all(v.values()) for v in results.values())
    print("OVERALL:", "PASS" if overall else "FAIL")
    if not overall:
        sys.exit(1)


if __name__ == "__main__":
    main()
