from datetime import datetime, timezone


def _parse_year_month(value):
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m")
    except ValueError:
        return None


def _years_of_experience(work_experience, today=None):
    """Career span from the earliest start_date to the latest end_date (or
    today, for a role with no end_date — i.e. still ongoing), not a literal
    sum of each role's duration — matches how "years of experience" is
    normally read on an application form.
    """
    today = today or datetime.now(timezone.utc)
    starts, ends = [], []
    for exp in work_experience or []:
        start = _parse_year_month(exp.get("start_date"))
        if start:
            starts.append(start)
            ends.append(_parse_year_month(exp.get("end_date")) or today)
    if not starts:
        return None
    span_months = (max(ends).year - min(starts).year) * 12 + (max(ends).month - min(starts).month)
    return round(span_months / 12, 1)


def _format_education(education_entry):
    degree = (education_entry.get("degree") or "").strip()
    institution = (education_entry.get("institution") or "").strip()
    return ", ".join(p for p in (degree, institution) if p)


def _format_number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return ""
    return str(int(value)) if value.is_integer() else str(value)


def _format_desired_salary(config):
    config = config or {}
    currency = (config.get("salary_currency") or "").strip()
    floor = _format_number(config.get("salary_floor"))
    target = _format_number(config.get("salary_target"))
    if not floor and not target:
        return ""
    if target and floor and target != floor:
        return f"{currency} {floor}-{target}".strip()
    return f"{currency} {floor or target}".strip()


def build_fields(resume_profile, job_info, config=None, resume_filename=None, today=None):
    """Deterministic, no AI — every value here already lives in
    resume_profile.json/Config, the same data M4/M9 use. `job_info` is a
    normalized dict with company/title/url keys, since the caller may be
    working from either a Jobs row or an Applications row.
    """
    config = config or {}
    job_info = job_info or {}
    contact = resume_profile.get("contact", {}) or {}
    work_experience = resume_profile.get("work_experience", []) or []
    education = resume_profile.get("education", []) or []
    current_job = work_experience[0] if work_experience else {}
    latest_edu = education[0] if education else {}
    years = _years_of_experience(work_experience, today=today)

    return [
        ("Full Name", resume_profile.get("name", "")),
        ("Email", contact.get("email", "")),
        ("Phone", contact.get("phone", "")),
        ("LinkedIn", contact.get("linkedin", "")),
        ("GitHub", contact.get("github", "")),
        ("Current/Most Recent Employer", current_job.get("company", "")),
        ("Current/Most Recent Title", current_job.get("title", "")),
        ("Years of Experience", str(years) if years is not None else ""),
        ("Highest Education", _format_education(latest_edu)),
        ("Desired Salary", _format_desired_salary(config)),
        ("Resume File to Attach", resume_filename or "(no tailored resume yet - run M9 first)"),
        ("Company Applying To", job_info.get("company", "")),
        ("Role Applying For", job_info.get("title", "")),
        ("Job Posting URL", job_info.get("url", "")),
    ]
