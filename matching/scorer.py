from .constants import UNKNOWN
from .location import score_location
from .salary import score_salary
from ai_provider import provider
from .skills import score_skills, SkillResult, _is_technical_role, _requires_senior_experience

import logging

_log = logging.getLogger(__name__)


def _watchlist_regex_fallback(title, desc):
    """Rule-based fallback for when AI is unavailable or disabled."""
    title_lower = title.lower()
    combined = f"{title_lower} {desc.lower()}"
    if _is_technical_role(title_lower) and not _requires_senior_experience(combined):
        return SkillResult(1.0, ["Technical Role (1-3 yrs)"])
    return SkillResult(0.0, [])


def score_skills_dispatch(job_row, vocabulary, config):
    """AI hook point (M14) — scoped to the skill dimension only; salary and
    location stay deterministic in every mode, there's no value in spending
    tokens on numeric/string comparisons.

    For watchlist jobs (workday / custom-scrape), we use Gemini to decide
    whether the role is technical and suitable for 1-3 years of experience,
    falling back to a regex heuristic if AI is disabled or errors out.
    """
    source = str(job_row.get("source") or "").strip().lower()
    is_watchlist = source in ("workday", "custom-scrape")

    if is_watchlist:
        title = (job_row.get("title") or "").strip()
        desc = (job_row.get("description_raw") or "").strip()

        if config.get("ai_provider") in ("gemini", "claude"):
            prompt = (
                f"Analyze this job posting:\n\nTitle: {title}\n\n"
                f"Description: {desc[:2000]}\n\n"
                "Question 1: Is this a technical role (e.g. software engineer, data, AI, cloud)?\n"
                "Question 2: Is the experience requirement suitable for a candidate with 1-3 years of experience? "
                "(i.e. it does NOT explicitly require 4+ years of senior experience).\n"
                "If the answer to BOTH questions is yes, output EXACTLY the word 'YES'. Otherwise, output 'NO'."
            )
            try:
                answer = provider.generate(
                    prompt, system="You are an expert technical recruiter.", config=config
                ).strip().lower()
                if "yes" in answer:
                    return SkillResult(1.0, ["Technical Role (1-3 yrs) via AI"])
                else:
                    return SkillResult(0.0, [])
            except Exception as exc:
                _log.warning("AI skill scoring failed, falling back to rule-based: %s", exc)

        # AI disabled or failed — use regex fallback
        return _watchlist_regex_fallback(title, desc)

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
