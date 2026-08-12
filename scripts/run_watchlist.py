"""M6 entrypoint — check active Watchlist companies, score new listings,
send an immediate standalone alert for anything that clears the threshold.

    python scripts/run_watchlist.py

Meant for a separate, more frequent GitHub Actions schedule than M1
(DESIGN.md: "every 5-10 min" vs M1's 15-30 min) — it's a small, fixed
list, not a broad search.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sheets import SheetsClient
from watchlist import run_watchlist_scan


def main():
    client = SheetsClient()
    client.ensure_schema()

    config_rows = {r["key"]: r["value"] for r in client.get_rows("Config") if r.get("key")}
    profile_path = config_rows.get("resume_profile_path", "resume_profile.json")
    with open(Path(__file__).resolve().parent.parent / profile_path) as f:
        resume_profile = json.load(f)

    summary = run_watchlist_scan(client, resume_profile)
    for label, result in summary.items():
        print(f"{label}: {result}")


if __name__ == "__main__":
    main()
