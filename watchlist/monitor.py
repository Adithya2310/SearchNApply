from datetime import datetime, timezone

from job_sources import greenhouse, lever, workday
from job_sources.custom import registry as custom_registry
from job_sources.dedup import compute_job_id
from digest.formatter import format_digest
from digest.mailer import send_email
from matching.engine import run_matching

# Two dispatch tiers, per DESIGN.md's M6 note:
#
# 1. ATS tier (below) — one fetcher module per platform, reused across
#    every company on that platform. Adding a company here is just a new
#    Watchlist row; no code change.
# 2. Custom-scrape tier (job_sources/custom/, via custom_registry) — one
#    bespoke module per company, since a custom careers page has no shared
#    API to reuse. Adding a company here is one new file plus a Watchlist
#    row with careers_identifier = that file's module name; dispatch below
#    never changes.
#
# Every fetcher (ATS or custom) is called with the same four args —
# target_roles/existing_job_ids are ignored by fetchers that don't need
# them (Greenhouse/Lever boards are small enough to return full postings
# in one call) and used by ones that do (Workday, and any custom scraper
# for a large employer, to avoid an N+1 detail-fetch per posting).
SOURCE_FETCHERS = {
    "greenhouse": lambda identifier, company_name, target_roles, existing_job_ids: greenhouse.fetch_jobs(
        identifier, company_name=company_name
    ),
    "lever": lambda identifier, company_name, target_roles, existing_job_ids: lever.fetch_jobs(
        identifier, company_name=company_name
    ),
    "workday": lambda identifier, company_name, target_roles, existing_job_ids: workday.fetch_jobs(
        identifier, target_roles or [""], company_name=company_name, existing_job_ids=existing_job_ids
    ),
}


def _is_active(value):
    return str(value or "").strip().upper() in {"Y", "YES", "TRUE", "1"}


def _split_csv(value):
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _existing_job_ids(client):
    return {row["job_id"] for row in client.get_rows("Jobs") if row.get("job_id")}


def _fetch(source, identifier, company_name, target_roles, existing_job_ids):
    if source == "custom-scrape":
        fetcher = custom_registry.get_fetcher(identifier)
        if fetcher is None:
            raise LookupError(
                f"no custom scraper found for '{identifier}' "
                f"(expected job_sources/custom/{identifier}.py)"
            )
        return fetcher(
            identifier,
            company_name=company_name,
            target_roles=target_roles,
            existing_job_ids=existing_job_ids,
        )

    fetcher = SOURCE_FETCHERS.get(source)
    if fetcher is None:
        raise LookupError(f"unsupported careers_source '{source}'")
    return fetcher(identifier, company_name, target_roles, existing_job_ids)


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
            raw_jobs = _fetch(source, identifier, company_name, target_roles, existing_ids)
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
