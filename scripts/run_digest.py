"""M5 entrypoint — email a digest of New jobs above match_threshold.

    python scripts/run_digest.py

Intended to run right after scripts/run_matching.py in the same
GitHub Actions job — by the time this runs, M4 has already scored
everything new from this scan.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sheets import SheetsClient
from digest import run_digest


def main():
    client = SheetsClient()
    client.ensure_schema()
    result = run_digest(client)
    if result["sent"]:
        print(f"sent digest: {result['count']} jobs")
    else:
        print("no new matches above threshold, nothing sent")


if __name__ == "__main__":
    main()
