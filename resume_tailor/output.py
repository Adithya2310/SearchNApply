import os
from datetime import datetime, timezone

OUTPUT_DIR = "tailored_resumes"


def safe_filename_part(value):
    return "".join(c if c.isalnum() else "_" for c in (value or "")).strip("_")


def save_tailored_resume(draft, company, role, today=None, output_dir=None):
    """Writes the draft to <output_dir>/<company>_<role>_<date>.txt and
    returns the filename. Shared by scripts/tailor_resume.py and the
    dashboard's Apply Kit tab so both produce identically-named files.
    """
    output_dir = output_dir or OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    safe_company = safe_filename_part(company) or "company"
    safe_role = safe_filename_part(role) or "role"
    timestamp = (today or datetime.now(timezone.utc)).strftime("%Y%m%d")
    filename = f"{output_dir}/{safe_company}_{safe_role}_{timestamp}.txt"
    with open(filename, "w") as f:
        f.write(draft)
    return filename
