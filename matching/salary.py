import re

from .constants import UNKNOWN

_RANGE_RE = re.compile(r"^\s*([\d.,]+)\s*-\s*([\d.,]+)\s*$")
_NUMBER_RE = re.compile(r"[\d,]+(?:\.\d+)?\s*[kKmM]?")


def _parse_number(token):
    m = re.match(r"([\d,]+(?:\.\d+)?)\s*([kKmM])?", token.strip())
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    suffix = (m.group(2) or "").lower()
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    return value


def parse_salary_range(raw):
    """Best-effort parse of Jobs.salary_range into (min, max) floats, or
    None if empty/unparseable. Handles Adzuna's "104099.3-104099.3" style
    (point estimates show up as min==max) and rougher human strings like
    "$120K-$150K a year" as a fallback.
    """
    raw = (raw or "").strip()
    if not raw:
        return None

    m = _RANGE_RE.match(raw)
    if m:
        lo = _parse_number(m.group(1))
        hi = _parse_number(m.group(2))
        if lo is not None and hi is not None:
            return (lo, hi)

    nums = [_parse_number(tok) for tok in _NUMBER_RE.findall(raw)]
    nums = [n for n in nums if n is not None]
    if len(nums) == 1:
        return (nums[0], nums[0])
    if len(nums) >= 2:
        return (min(nums[:2]), max(nums[:2]))
    return None


def score_salary(job_row, config):
    """UNKNOWN whenever the user hasn't set a salary_floor, or the job's
    salary can't be parsed — never filled with a neutral guess. Below the
    floor decays smoothly rather than cliffing to 0, since a job just under
    the floor is still worth seeing.
    """
    floor = config.get("salary_floor")
    if not floor or floor <= 0:
        return UNKNOWN

    parsed = parse_salary_range(job_row.get("salary_range"))
    if parsed is None:
        return UNKNOWN

    lo, hi = parsed
    figure = hi if hi else lo
    if not figure or figure <= 0:
        return UNKNOWN

    target = config.get("salary_target")
    if target and target > floor:
        if figure >= target:
            return 1.0
        if figure >= floor:
            return 0.5 + 0.5 * (figure - floor) / (target - floor)
        return max(0.0, 0.5 * figure / floor)

    if figure >= floor:
        return 1.0
    return max(0.0, 0.5 * figure / floor)
