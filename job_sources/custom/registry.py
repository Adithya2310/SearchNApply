import importlib


def get_fetcher(company_slug):
    """Dynamically loads job_sources/custom/<company_slug>.py's fetch_jobs.

    This is what makes the custom-scrape tier scalable: adding a new
    custom-scrape company is "drop one file here implementing
    fetch_jobs(identifier, company_name=None, target_roles=None,
    existing_job_ids=None), then add a Watchlist row with
    careers_source=custom-scrape and careers_identifier=<company_slug>" —
    watchlist/monitor.py's dispatch never needs to change to support it.

    Returns None only when no file matches the slug, so a not-yet-built
    scraper is just another per-company error in the watchlist run, not
    fatal to the rest of it. A module that exists but is genuinely broken
    (e.g. a missing dependency inside it) re-raises instead of being
    silently treated as "not found" — distinguished via the
    ModuleNotFoundError's `.name`, since both cases raise the same
    exception type.
    """
    module_name = f"job_sources.custom.{company_slug}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name == module_name:
            return None
        raise

    fetcher = getattr(module, "fetch_jobs", None)
    if fetcher is None:
        raise AttributeError(f"{module_name} has no fetch_jobs()")
    return fetcher
