import os
from datetime import datetime, timedelta, timezone

from . import adzuna, greenhouse, jsearch, lever
from .dedup import compute_job_id

JSEARCH_LAST_RUN_KEY = "jsearch_last_run"


def _config_map(client):
    return {row["key"]: row["value"] for row in client.get_rows("Config") if row.get("key")}


def _split_csv(value):
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _set_config_value(client, key, value):
    if client.find_row_index("Config", "key", key) is None:
        client.append_row("Config", {"key": key, "value": value})
    else:
        client.update_row("Config", "key", key, {"value": value})


def _existing_job_ids(client):
    return {row["job_id"] for row in client.get_rows("Jobs") if row.get("job_id")}


def _append_new_jobs(client, raw_jobs, existing_ids, today):
    """Dedupes against existing_ids (mutated in place) and writes all new
    rows for this source in one batched API call.
    """
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
                "match_score": "",
                "date_found": today,
                "status": "New",
            }
        )
    client.append_rows("Jobs", new_rows)
    return len(new_rows)


def _jsearch_due(config):
    interval_hours = float(os.environ.get("JSEARCH_SCAN_INTERVAL_HOURS", 12))
    last_run = config.get(JSEARCH_LAST_RUN_KEY)
    if not last_run:
        return True
    last_run_dt = datetime.fromisoformat(last_run)
    return datetime.now(timezone.utc) - last_run_dt >= timedelta(hours=interval_hours)


def run_scan(client, today=None):
    """M1 — reads scan targets from the Config sheet, fetches from every
    source, dedupes against Jobs' existing job_ids, appends the rest.

    Greenhouse/Lever/Adzuna always run. JSearch only runs once its own
    JSEARCH_SCAN_INTERVAL_HOURS has elapsed (free tier: 200 req/month).
    Returns a dict of source -> jobs added (or "error: ..."/"skipped ...").
    """
    today = today or datetime.now(timezone.utc).date().isoformat()
    config = _config_map(client)
    existing_ids = _existing_job_ids(client)
    summary = {}

    for board in _split_csv(config.get("greenhouse_boards")):
        label = f"greenhouse:{board}"
        try:
            jobs = greenhouse.fetch_jobs(board)
            summary[label] = _append_new_jobs(client, jobs, existing_ids, today)
        except Exception as e:
            summary[label] = f"error: {e}"

    for company in _split_csv(config.get("lever_companies")):
        label = f"lever:{company}"
        try:
            jobs = lever.fetch_jobs(company)
            summary[label] = _append_new_jobs(client, jobs, existing_ids, today)
        except Exception as e:
            summary[label] = f"error: {e}"

    target_roles = _split_csv(config.get("target_roles"))
    target_locations = _split_csv(config.get("target_locations")) or [None]
    adzuna_country = config.get("adzuna_country") or "us"
    for role in target_roles:
        for location in target_locations:
            label = f"adzuna:{role}@{location or 'any'}"
            try:
                jobs = adzuna.fetch_jobs(role, where=location, country=adzuna_country)
                summary[label] = _append_new_jobs(client, jobs, existing_ids, today)
            except Exception as e:
                summary[label] = f"error: {e}"

    if target_roles and _jsearch_due(config):
        query = " ".join(target_roles[:1] + (target_locations[:1] if target_locations[0] else []))
        label = f"jsearch:{query}"
        try:
            jobs = jsearch.fetch_jobs(query)
            summary[label] = _append_new_jobs(client, jobs, existing_ids, today)
            _set_config_value(client, JSEARCH_LAST_RUN_KEY, datetime.now(timezone.utc).isoformat())
        except Exception as e:
            summary[label] = f"error: {e}"
    elif target_roles:
        summary["jsearch"] = "skipped (JSEARCH_SCAN_INTERVAL_HOURS not elapsed)"

    return summary
