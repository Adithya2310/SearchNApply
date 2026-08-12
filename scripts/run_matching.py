"""M4 entrypoint — score every unscored Jobs row against resume_profile.json.

    python scripts/run_matching.py

Reads Config for scoring weights/thresholds and resume_profile_path.
Intended to run right after scripts/run_job_scan.py in the same schedule.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sheets import SheetsClient
from matching import run_matching


def main():
    client = SheetsClient()
    client.ensure_schema()

    config_rows = {r["key"]: r["value"] for r in client.get_rows("Config") if r.get("key")}
    profile_path = config_rows.get("resume_profile_path", "resume_profile.json")
    with open(Path(__file__).resolve().parent.parent / profile_path) as f:
        resume_profile = json.load(f)

    result = run_matching(client, resume_profile)
    print(f"scored: {result['scored']}, ignored: {result['ignored']}")


if __name__ == "__main__":
    main()
