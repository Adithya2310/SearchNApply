from .constants import UNKNOWN
from .location import score_location
from .salary import score_salary
from .skills import score_skills


def score_skills_dispatch(job_row, vocabulary, config):
    """AI hook point (M14) — scoped to the skill dimension only; salary and
    location stay deterministic in every mode, there's no value in spending
    tokens on numeric/string comparisons.

    ai_provider claude/gemini semantic matching isn't built yet (Phase 2).
    Any future implementation must fall back to the rule-based scorer on
    failure rather than raise — this stub already satisfies that by simply
    not having a failing path yet.
    """
    return score_skills(job_row, vocabulary, saturation=config["skill_saturation"])


def score_job(job_row, vocabulary, config):
    """Combine the three dimensions into a single 0-100 match_score.

    UNKNOWN dimensions are dropped and the remaining weights renormalized —
    not filled with a neutral constant — so e.g. an empty Config (no
    salary_floor, no target_locations) degrades cleanly to pure
    skill-overlap ranking instead of every job clustering around a
    meaningless midpoint.
    """
    skill_result = score_skills_dispatch(job_row, vocabulary, config)
    salary_score = score_salary(job_row, config)
    location_score = score_location(job_row, config)

    dims = {
        "skill": (skill_result.score, config["weight_skill"]),
        "salary": (salary_score, config["weight_salary"]),
        "location": (location_score, config["weight_location"]),
    }
    present = [(score, weight) for score, weight in dims.values() if score is not UNKNOWN]
    weight_sum = sum(weight for _, weight in present)

    combined = sum(score * weight for score, weight in present) / weight_sum if weight_sum > 0 else 0.0
    match_score = max(0, min(100, round(100 * combined)))

    return {
        "match_score": match_score,
        "skill_score": skill_result.score,
        "salary_score": salary_score,
        "location_score": location_score,
        "matched_skills": skill_result.matched,
    }
