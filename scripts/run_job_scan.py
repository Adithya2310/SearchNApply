"""M1 entrypoint — run one aggregator pass and print a per-source summary.

    python scripts/run_job_scan.py

Reads scan targets (target_roles, target_locations, greenhouse_boards,
lever_companies) from the Config sheet. Intended to be invoked on a
schedule (every JOB_SCAN_INTERVAL_MINUTES) by GitHub Actions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sheets import SheetsClient
from job_sources.aggregator import run_scan


def main():
    client = SheetsClient()
    client.ensure_schema()
    summary = run_scan(client)
    for label, result in summary.items():
        print(f"{label}: {result}")


if __name__ == "__main__":
    main()
