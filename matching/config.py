DEFAULTS = {
    "match_threshold": 40.0,
    "weight_skill": 0.60,
    "weight_salary": 0.15,
    "weight_location": 0.25,
    "skill_saturation": 4.0,
}


def _num(raw, default=None):
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def load_config(client):
    """Read the Config sheet into a typed dict with M4's defaults filled
    in for anything unset — the whole point of Config is tuning the
    system without touching code.
    """
    raw = {row["key"]: row["value"] for row in client.get_rows("Config") if row.get("key")}
    return {
        "ai_provider": (str(raw.get("ai_provider", "none")).strip().lower() or "none"),
        "match_threshold": _num(raw.get("match_threshold"), DEFAULTS["match_threshold"]),
        "weight_skill": _num(raw.get("weight_skill"), DEFAULTS["weight_skill"]),
        "weight_salary": _num(raw.get("weight_salary"), DEFAULTS["weight_salary"]),
        "weight_location": _num(raw.get("weight_location"), DEFAULTS["weight_location"]),
        "skill_saturation": _num(raw.get("skill_saturation"), DEFAULTS["skill_saturation"]),
        "core_skills": raw.get("core_skills", ""),
        "salary_floor": _num(raw.get("salary_floor")),
        "salary_target": _num(raw.get("salary_target")),
        "salary_currency": (str(raw.get("salary_currency", "USD")).strip().upper() or "USD"),
        "remote_ok": raw.get("remote_ok", "Y"),
        "target_locations": raw.get("target_locations", ""),
        # Where the user actually is, so "Remote within United States" can
        # be recognized as excluding them rather than getting full remote
        # credit. Blank means we can't judge, so no restriction is applied.
        "user_country": raw.get("user_country", ""),
    }
