from html import escape


def _score(job):
    try:
        return int(job.get("match_score") or 0)
    except (TypeError, ValueError):
        return 0


def format_digest(jobs):
    """jobs: Jobs rows already filtered to status=New and match_score above
    threshold. Returns (subject, text_body, html_body), sorted best match
    first.
    """
    jobs_sorted = sorted(jobs, key=_score, reverse=True)
    n = len(jobs_sorted)
    subject = f"Job Digest: {n} new match{'es' if n != 1 else ''}"

    text_lines = []
    html_rows = []
    for job in jobs_sorted:
        location = job.get("location") or "—"
        salary = job.get("salary_range") or ""
        salary_part = f" | {salary}" if salary else ""
        text_lines.append(
            f"[{_score(job)}] {job.get('title', '')} at {job.get('company', '')} "
            f"({location}){salary_part}\n    {job.get('url', '')}"
        )
        html_rows.append(
            "<tr>"
            f"<td style='padding:4px 8px'>{_score(job)}</td>"
            f"<td style='padding:4px 8px'>{escape(job.get('title', ''))}</td>"
            f"<td style='padding:4px 8px'>{escape(job.get('company', ''))}</td>"
            f"<td style='padding:4px 8px'>{escape(location)}</td>"
            f"<td style='padding:4px 8px'>{escape(salary)}</td>"
            f"<td style='padding:4px 8px'><a href='{escape(job.get('url', ''), quote=True)}'>Apply</a></td>"
            "</tr>"
        )

    text_body = f"{n} new job match{'es' if n != 1 else ''} above your threshold:\n\n" + "\n\n".join(
        text_lines
    )
    html_body = (
        "<html><body>"
        f"<p>{n} new job match{'es' if n != 1 else ''} above your threshold:</p>"
        "<table style='border-collapse:collapse'>"
        "<tr><th align='left'>Score</th><th align='left'>Title</th><th align='left'>Company</th>"
        "<th align='left'>Location</th><th align='left'>Salary</th><th align='left'></th></tr>"
        + "".join(html_rows)
        + "</table></body></html>"
    )
    return subject, text_body, html_body
