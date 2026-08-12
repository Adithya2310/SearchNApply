"""Seed starter Config rows so M1 has something to scan.

Idempotent — safe to re-run; only fills in keys that don't already exist.
Edit these values directly in the Config tab afterwards, no code changes
needed (that's the whole point of the Config sheet).

    python scripts/seed_config.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sheets import SheetsClient

DEFAULTS = {
    "target_roles": {
        "value": "software engineer, backend engineer, full stack developer",
        "notes": "comma-separated search terms used by Adzuna + JSearch",
    },
    "target_locations": {
        "value": "",
        "notes": "comma-separated locations for Adzuna/JSearch, blank = no location filter",
    },
    "adzuna_country": {
        "value": "us",
        "notes": "Adzuna country code, e.g. us / gb / in",
    },
    "greenhouse_boards": {
        "value": "greenhouse",
        "notes": "comma-separated Greenhouse board tokens to scan broadly (edit to real target companies)",
    },
    "lever_companies": {
        "value": "palantir",
        "notes": "comma-separated Lever company slugs to scan broadly (edit to real target companies)",
    },
    "resume_profile_path": {
        "value": "resume_profile.json",
        "notes": "used by M4/M9",
    },
    "ai_provider": {
        "value": "none",
        "notes": "claude / gemini / none — read by M3, M4, M9, M10",
    },
}


def main():
    client = SheetsClient()
    client.ensure_schema()
    existing_keys = {row["key"] for row in client.get_rows("Config")}

    for key, spec in DEFAULTS.items():
        if key in existing_keys:
            print(f"skip (already set): {key}")
            continue
        client.append_row("Config", {"key": key, "value": spec["value"], "notes": spec["notes"]})
        print(f"seeded: {key} = {spec['value']!r}")


if __name__ == "__main__":
    main()
