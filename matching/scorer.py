from .constants import UNKNOWN
from .location import score_location
from .salary import score_salary
from ai_provider import provider
from .skills import score_skills, SkillResult

def score_skills_dispatch(job_row, vocabulary, config):
    """AI hook point (M14) — scoped to the skill dimension only; salary and
    location stay deterministic in every mode, there's no value in spending
    tokens on numeric/string comparisons.

    ai_provider claude/gemini semantic matching isn't built yet (Phase 2).
    Any future implementation must fall back to the rule-based scorer on
    failure rather than raise — this stub already satisfies that by simply
    not having a failing path yet.
    """
    source = str(job_row.get("source") or "").strip().lower()
    is_watchlist = source in ("workday", "custom-scrape")

    if is_watchlist and config.get("ai_provider") in ("gemini", "claude"):
        title = (job_row.get("title") or "").strip()
        desc = (job_row.get("description_raw") or "").strip()
        prompt = (
            f"Analyze this job posting:\n\nTitle: {title}\n\nDescription: {desc}\n\n"
            "Question 1: Is this a technical role (e.g. software engineer, data, AI, cloud)?\n"
            "Question 2: Is the experience requirement suitable for a candidate with 1-3 years of experience? (i.e. it does NOT explicitly require 4+ years of senior experience).\n"
            "If the answer to BOTH questions is yes, output EXACTLY the word 'YES'. Otherwise, output 'NO'."
        )
        try:
            answer = provider.generate(prompt, system="You are an expert technical recruiter.", config=config).strip().lower()
            if "yes" in answer:
                return SkillResult(1.0, ["Technical Role (1-3 yrs) via AI"])
            else:
                return SkillResult(0.0, [])
        except Exception:
            pass # Fall back to rule-based

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
