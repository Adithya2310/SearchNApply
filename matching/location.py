from .constants import UNKNOWN

REMOTE_KEYWORDS = ("remote", "anywhere", "distributed", "work from home", "wfh")
NO_MATCH_SCORE = 0.2
SAME_COUNTRY_SCORE = 0.6


def _split_csv(value):
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _is_remote(job_row):
    haystack = " ".join(
        [
            job_row.get("location", "") or "",
            job_row.get("title", "") or "",
            job_row.get("description_raw", "") or "",
        ]
    ).lower()
    return any(kw in haystack for kw in REMOTE_KEYWORDS)


def score_location(job_row, config):
    """UNKNOWN when the user hasn't set target_locations, or the job has no
    location string — never filled with a neutral guess.
    """
    targets = _split_csv(config.get("target_locations"))
    location = (job_row.get("location") or "").strip()
    if not targets or not location:
        return UNKNOWN

    remote_ok = str(config.get("remote_ok", "Y")).strip().upper() != "N"
    if remote_ok and _is_remote(job_row):
        return 1.0

    location_lower = location.lower()
    targets_lower = [t.lower() for t in targets]

    if any(t in location_lower or location_lower in t for t in targets_lower):
        return 1.0

    loc_parts = [p.strip() for p in location_lower.split(",")]
    loc_country_ish = loc_parts[-1] if loc_parts else ""
    for t in targets_lower:
        t_parts = [p.strip() for p in t.split(",")]
        t_country_ish = t_parts[-1] if t_parts else ""
        if t_country_ish and t_country_ish == loc_country_ish:
            return SAME_COUNTRY_SCORE

    return NO_MATCH_SCORE
