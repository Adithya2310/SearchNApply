from matching.config import load_config

from .formatter import format_digest
from .mailer import send_email


def run_digest(client):
    """M5 — emails whatever is currently status=New with match_score above
    Config.match_threshold, then marks those rows Reviewed.

    Naturally idempotent across runs without any extra state: once a job
    is emailed it's marked Reviewed, so the next run (however frequent)
    only ever picks up genuinely new matches since the last send. Sends
    nothing (and touches nothing) when there's nothing to report.
    """
    threshold = load_config(client)["match_threshold"]

    rows = client.get_rows("Jobs")
    candidates = [
        r
        for r in rows
        if r.get("status") == "New" and str(r.get("match_score", "")).strip() and int(r["match_score"]) >= threshold
    ]

    if not candidates:
        return {"sent": False, "count": 0}

    subject, text_body, html_body = format_digest(candidates)
    send_email(subject, text_body, html_body)

    updates = {r["job_id"]: {"status": "Reviewed"} for r in candidates}
    client.update_rows("Jobs", "job_id", updates)

    return {"sent": True, "count": len(candidates)}
