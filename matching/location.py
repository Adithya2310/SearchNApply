import re

from .constants import UNKNOWN

REMOTE_KEYWORDS = ("remote", "anywhere", "distributed", "work from home", "wfh")
NO_MATCH_SCORE = 0.0
SAME_COUNTRY_SCORE = 0.6

# Confirmed against real scanned jobs: "Remote within United States" and
# "Remote within Canada or United States" both contain "remote" but are
# explicitly geo-restricted — granting them full remote credit for a user
# based elsewhere is wrong. Only the location field's own restriction
# phrasing is trustworthy here; scanning the full description for "remote"
# also catches unrelated boilerplate like "remote-first environment"
# (company culture, not a location restriction).
_REMOTE_RESTRICTION_RE = re.compile(
    r"remote\s+(?:within|in|for|based\s+in)\s+([a-z0-9,;&/\-\s]+?)(?:[.,;\n]|$)",
    re.IGNORECASE,
)


def _split_csv(value):
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _is_remote(job_row):
    haystack = " ".join(
        [
            job_row.get("location", "") or "",
            job_row.get("title", "") or "",
        ]
    ).lower()
    return any(kw in haystack for kw in REMOTE_KEYWORDS)


def _remote_restriction_excludes_user(location, user_country):
    """True if the location field names an explicit "remote within/in/for
    X" restriction that does NOT mention the user's country. False (i.e.
    treated as open/global remote) when there's no such restriction phrase
    at all, or when we don't know the user's country to check against.
    """
    if not user_country:
        return False
    match = _REMOTE_RESTRICTION_RE.search((location or "").lower())
    if not match:
        return False
    return user_country.strip().lower() not in match.group(1)


def score_location(job_row, config):
    """UNKNOWN when the user hasn't set target_locations, or the job has no
    location string — never filled with a neutral guess.
    """
    targets = _split_csv(config.get("target_locations"))
    location = (job_row.get("location") or "").strip()
    if not targets or not location:
        return UNKNOWN

    remote_ok = str(config.get("remote_ok", "Y")).strip().upper() != "N"
    if (
        remote_ok
        and _is_remote(job_row)
        and not _remote_restriction_excludes_user(location, config.get("user_country"))
    ):
        return 1.0

    location_lower = location.lower()
    # A "Remote" entry in target_locations is meant for the dedicated
    # remote-handling above, not as a literal city/region substring — if it
    # leaked in here, a geo-restricted "...or Remote within United States"
    # would substring-match "remote" and undo the restriction check just
    # applied (confirmed live: this is exactly what happened before this
    # exclusion was added).
    targets_lower = [t.lower() for t in targets if t.lower() not in REMOTE_KEYWORDS]

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
