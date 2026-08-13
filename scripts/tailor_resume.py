"""M9 entrypoint — tailor a resume against a job description.

    python scripts/tailor_resume.py --job-id <Jobs.job_id>
    python scripts/tailor_resume.py --jd-file path/to/description.txt

Runs skill-gap resolution interactively before generating the tailored
resume — see resume_tailor/gaps.py and DESIGN.md M9.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from matching.config import load_config
from resume_tailor.gaps import find_skill_gaps
from resume_tailor.profile_updates import add_confirmed_skills
from resume_tailor.tailor import tailor_resume
from sheets.client import SheetsClient

OUTPUT_DIR = "tailored_resumes"


def _load_resume_profile(path):
    with open(path) as f:
        return json.load(f)


def _save_resume_profile(path, profile):
    with open(path, "w") as f:
        json.dump(profile, f, indent=2)
        f.write("\n")


def _prompt_skill_gap(skill):
    print(f"\nThis job asks for '{skill}', which isn't in your profile.")
    while True:
        answer = input(
            "  [1] I know this already  [2] I'll learn it (project planned)  [3] skip > "
        ).strip()
        if answer in ("1", "2", "3"):
            return answer
        print("  Please enter 1, 2, or 3.")


def _safe_filename_part(value):
    return "".join(c if c.isalnum() else "_" for c in value).strip("_")


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="M9 — Resume Tailoring Engine")
    parser.add_argument("--job-id", help="Jobs.job_id to tailor against")
    parser.add_argument("--jd-file", help="Path to a local job description text file")
    args = parser.parse_args()

    if not args.job_id and not args.jd_file:
        sys.exit("Provide --job-id (a Jobs sheet row) or --jd-file (a local text file)")

    client = SheetsClient()
    config = load_config(client)

    if args.job_id:
        rows = client.get_rows("Jobs")
        job_row = next((r for r in rows if r.get("job_id") == args.job_id), None)
        if job_row is None:
            sys.exit(f"No Jobs row with job_id={args.job_id}")
        job_description = f"{job_row.get('title', '')}\n\n{job_row.get('description_raw', '')}"
        company, title = job_row.get("company", ""), job_row.get("title", "")
    else:
        with open(args.jd_file) as f:
            job_description = f.read()
        company, title = "unknown", "unknown"

    # load_config() only exposes M4's scoring-related keys — resume_profile_path
    # isn't one of them (same reason run_matching.py/run_watchlist.py read it
    # from a raw Config dict instead of load_config()'s typed one).
    config_rows = {r["key"]: r["value"] for r in client.get_rows("Config") if r.get("key")}
    resume_profile_path = config_rows.get("resume_profile_path") or "resume_profile.json"
    resume_profile = _load_resume_profile(resume_profile_path)

    print("Checking for skill gaps against this job description...")
    gaps = find_skill_gaps(job_description, resume_profile, config)

    confirmed_skills = []
    learning_skills = []
    for skill in gaps:
        answer = _prompt_skill_gap(skill)
        if answer == "1":
            confirmed_skills.append(skill)
        elif answer == "2":
            learning_skills.append(skill)

    if confirmed_skills:
        add_confirmed_skills(resume_profile, confirmed_skills)
        _save_resume_profile(resume_profile_path, resume_profile)
        print(f"Added to your profile: {', '.join(confirmed_skills)}")

    if learning_skills:
        print(f"Noted as learning goals (not added to the resume yet): {', '.join(learning_skills)}")

    print("\nGenerating tailored, ATS-friendly resume...")
    skipped = [s for s in gaps if s not in confirmed_skills and s not in learning_skills]
    keywords = confirmed_skills + skipped
    draft = tailor_resume(resume_profile, job_description, keywords, config)

    print("\n" + "=" * 70)
    print(draft)
    print("=" * 70)

    save = input("\nSave this as the final tailored resume? [y/n] ").strip().lower()
    if save != "y":
        print("Discarded — nothing written.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_company = _safe_filename_part(company) or "company"
    safe_title = _safe_filename_part(title) or "role"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"{OUTPUT_DIR}/{safe_company}_{safe_title}_{timestamp}.txt"
    with open(filename, "w") as f:
        f.write(draft)
    print(f"Saved: {filename}")

    if args.job_id:
        app_rows = client.get_rows("Applications")
        match = next((r for r in app_rows if r.get("linked_job_id") == args.job_id), None)
        if match:
            client.update_row("Applications", "app_id", match["app_id"], {"resume_version_used": filename})
            print(f"Updated Applications row {match['app_id']}.resume_version_used")
        else:
            print(
                "No Applications row is linked to this job yet — log it manually "
                "(or via the dashboard once M7 exists) and record this filename "
                "as resume_version_used."
            )


if __name__ == "__main__":
    main()
