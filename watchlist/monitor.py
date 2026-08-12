from datetime import datetime, timezone

from job_sources import greenhouse, lever, workday
from job_sources.dedup import compute_job_id
from digest.formatter import format_digest
from digest.mailer import send_email
from matching.engine import run_matching

# Companies on Greenhouse/Lever/Workday are the "easy, queryable" tier per
# DESIGN.md. Custom scrapes are explicitly called out as more fragile,
# per-company efforts — not built yet. Unsupported careers_source values
# are skipped, not fatal, same isolation principle as M1's per-source
# error handling.
#
# Workday isn't in this dict — it needs target_roles (a search query,
# since large employers here can have thousands of postings) and
# existing_job_ids (to skip its extra per-job detail fetch for anything
# already seen) that greenhouse/lever don't need, so it's dispatched
# separately in run_watchlist_scan rather than forcing every fetcher into
# the same signature.
SOURCE_FETCHERS = {
    "greenhouse": lambda identifier, company_name: greenhouse.fetch_jobs(
        identifier, company_name=company_name
    ),
    "lever": lambda identifier, company_name: lever.fetch_jobs(
        identifier, company_name=company_name
    ),
}


def _is_active(value):
    return str(value or "").strip().upper() in {"Y", "YES", "TRUE", "1"}


def _split_csv(value):
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _existing_job_ids(client):
    return {row["job_id"] for row in client.get_rows("Jobs") if row.get("job_id")}


def run_watchlist_scan(client, resume_profile, today=None):
    """M6 — checks each active Watchlist company, adds any new listings to
    Jobs tagged source=watchlist:<company>, scores them via M4 (same
    skills/salary criteria, no separate logic), and sends an immediate
    standalone email for whichever of *this run's* new listings cleared
    the threshold — separate from M5's digest, since the point of
    watchlisting a company is not missing it.

    Non-matches still land in Jobs (via M4's normal Ignored path) so
    they're visible later even if they didn't clear the bar.
    """
    today = today or datetime.now(timezone.utc).date().isoformat()
    watchlist_rows = client.get_rows("Watchlist")
    existing_ids = _existing_job_ids(client)

    config_rows = {r["key"]: r["value"] for r in client.get_rows("Config") if r.get("key")}
    target_roles = _split_csv(config_rows.get("target_roles"))

    summary = {}
    new_job_ids_this_run = []

    for row in watchlist_rows:
        company_name = row.get("company_name", "").strip()
        if not company_name or not _is_active(row.get("active")):
            continue

        source = (row.get("careers_source") or "").strip().lower()
        identifier = (row.get("careers_identifier") or "").strip()
        label = f"watchlist:{company_name}"

        try:
            if source == "workday":
                raw_jobs = workday.fetch_jobs(
                    identifier,
                    target_roles or [""],
                    company_name=company_name,
                    existing_job_ids=existing_ids,
                )
            else:
                fetcher = SOURCE_FETCHERS.get(source)
                if fetcher is None:
                    summary[label] = f"error: unsupported careers_source '{source}'"
                    continue
                raw_jobs = fetcher(identifier, company_name)
        except Exception as e:
            summary[label] = f"error: {e}"
            continue

        new_rows = []
        for job in raw_jobs:
            job_id = compute_job_id(job["company"], job["title"], job["url"])
            if job_id in existing_ids:
                continue
            existing_ids.add(job_id)
            new_rows.append(
                {
                    **job,
                    "job_id": job_id,
                    "source": label,
                    "match_score": "",
                    "date_found": today,
                    "status": "New",
                }
            )
            new_job_ids_this_run.append(job_id)

        client.append_rows("Jobs", new_rows)
        summary[label] = len(new_rows)

        client.update_rows(
            "Watchlist",
            "company_name",
            {company_name: {"last_checked": datetime.now(timezone.utc).isoformat()}},
        )

    if new_job_ids_this_run:
        run_matching(client, resume_profile)

    alert_count = 0
    if new_job_ids_this_run:
        rows_by_id = {r["job_id"]: r for r in client.get_rows("Jobs")}
        matches = [
            rows_by_id[job_id]
            for job_id in new_job_ids_this_run
            if rows_by_id.get(job_id, {}).get("status") == "New"
        ]
        if matches:
            subject, text_body, html_body = format_digest(matches, subject_prefix="Watchlist Alert")
            send_email(subject, text_body, html_body)
            updates = {job["job_id"]: {"status": "Reviewed"} for job in matches}
            client.update_rows("Jobs", "job_id", updates)
            alert_count = len(matches)

    summary["alert_sent"] = alert_count
    return summary
