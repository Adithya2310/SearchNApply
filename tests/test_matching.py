import pytest

from matching.constants import UNKNOWN
from matching.location import score_location
from matching.salary import parse_salary_range, score_salary
from matching.scorer import score_job
from matching.skills import build_vocabulary, score_skills

RESUME_PROFILE = {
    "skills": {
        "languages": ["C#", "C", "C++", "Java", "Python", "TypeScript", "JavaScript", "SQL"],
        "technologies_tools": [
            ".NET",
            "ReactJS",
            "Playwright",
            "GitHub Actions (CI/CD)",
            "PostgreSQL",
        ],
    },
    "work_experience": [
        {
            "company": "Recent Co",
            "tech_stack": ["C#", ".NET 8", "ReactJS", "Playwright", "GitHub Actions (CI/CD)"],
        },
        {
            "company": "Older Co",
            "tech_stack": ["React", "TailwindCSS"],
        },
    ],
}


def _job(title="", description_raw="", location="", salary_range=""):
    return {
        "title": title,
        "description_raw": description_raw,
        "location": location,
        "salary_range": salary_range,
    }


def _base_config(**overrides):
    config = {
        "weight_skill": 0.60,
        "weight_salary": 0.15,
        "weight_location": 0.25,
        "skill_saturation": 4.0,
        "core_skills": "",
        "salary_floor": None,
        "salary_target": None,
        "salary_currency": "USD",
        "remote_ok": "Y",
        "target_locations": "",
        "user_country": "",
        "ai_provider": "none",
    }
    config.update(overrides)
    return config


# ---- skill vocabulary / core-skill derivation ----


def test_build_vocabulary_marks_core_skills_from_recent_job_and_top_languages():
    vocab = build_vocabulary(RESUME_PROFILE, _base_config())

    assert vocab["c#"] == 2.0  # in most-recent tech_stack AND top-3 languages
    assert vocab["react"] == 2.0  # "ReactJS" canonicalizes to "react"
    assert vocab["playwright"] == 2.0
    assert vocab["github actions"] == 2.0  # trailing "(CI/CD)" stripped by clean_skill_name
    assert vocab["postgres"] == 1.0  # only in technologies_tools, not most-recent tech_stack
    assert vocab["python"] == 1.0  # language but not in top-3


def test_build_vocabulary_respects_core_skills_override():
    vocab = build_vocabulary(RESUME_PROFILE, _base_config(core_skills="python"))

    assert vocab["python"] == 2.0
    assert vocab["c#"] == 1.0  # no longer core once override is set


# ---- skill matching: symbolic boundaries ----


def test_symbolic_skills_do_not_false_match_substrings():
    vocab = {"c++": 1.0, "c#": 1.0, ".net": 1.0}
    job = _job(description_raw="We use ObjectiveCpp tooling and dotnetcore internals sometimes")
    result = score_skills(job, vocab)
    assert result.matched == []


def test_c_plus_plus_and_c_sharp_match_with_proper_symbol_boundaries():
    vocab = {"c++": 1.0, "c#": 1.0}
    job = _job(description_raw="Looking for a C++ engineer, C# experience is a plus.")
    result = score_skills(job, vocab)
    assert set(result.matched) == {"c++", "c#"}


def test_bare_next_does_not_false_match_ordinary_english():
    # found live: "our next phase of growth" inflated ~9% of real scanned
    # jobs with no genuine Next.js mention.
    vocab = {"next": 1.0}
    result = score_skills(
        _job(description_raw="Financial strategy for our next phase of growth."), vocab
    )
    assert result.matched == []


def test_next_still_matches_via_its_unambiguous_compound_variants():
    vocab = {"next": 1.0}
    for text in ["built with Next.js", "experience with nextjs"]:
        result = score_skills(_job(description_raw=text), vocab)
        assert result.matched == ["next"], text


def test_bare_js_and_ts_do_not_false_match_inside_dotted_library_names():
    # found live: bare "js"/"ts" satisfied the plain boundary check inside
    # "next.js, typescript, ..." and "node.js, typescript, react/next.js"
    # purely from the '.' being non-alnum on both sides.
    vocab = {"js": 1.0, "ts": 1.0}
    text = "modern stack (python, node.js, typescript, react/next.js, or similar)"
    result = score_skills(_job(description_raw=text), vocab)
    # "ts" still matches — via the full word "typescript", not the bare
    # fragment — that's a real, intended match, not the bug.
    assert result.matched == ["ts"]


def test_bare_js_still_matches_standalone_mentions():
    vocab = {"js": 1.0}
    result = score_skills(_job(description_raw="3+ years of JS experience required"), vocab)
    assert result.matched == ["js"]


def test_dotnet_matches_common_variants():
    vocab = {".net": 1.0}
    for text in [".NET developer needed", "solid ASP.NET background", "experience with dotnet"]:
        result = score_skills(_job(description_raw=text), vocab)
        assert result.matched == [".net"], text


def test_ambiguous_bare_c_requires_list_delimiter_context():
    vocab = {"c": 1.0}

    matches = score_skills(_job(description_raw="Languages: C, C++, Java"), vocab).matched
    assert matches == ["c"]

    # a leading comma-space before "C" is NOT enough on its own — ordinary
    # prose has commas everywhere ("skills, C level stakeholders" looks
    # identical from the left); only a trailing delimiter counts.
    no_match = score_skills(
        _job(description_raw="This role requires strong communication skills, C level stakeholders."),
        vocab,
    ).matched
    assert no_match == []

    prose_no_match = score_skills(
        _job(description_raw="This role requires strong C communication skills"), vocab
    ).matched
    assert prose_no_match == []


def test_ambiguous_bare_go_requires_list_delimiter_context():
    vocab = {"go": 1.0}

    listed = score_skills(_job(description_raw="Skills: Go, Python, C#"), vocab).matched
    assert listed == ["go"]

    prose = score_skills(_job(description_raw="Skilled in Go and Python"), vocab).matched
    assert prose == []

    substring = score_skills(_job(description_raw="Golang microservices experience"), vocab).matched
    assert substring == []  # base non-alnum boundary already rejects this, regardless of delimiter rule


def test_ambiguous_bare_r_requires_list_delimiter_context():
    vocab = {"r": 1.0}

    listed = score_skills(_job(description_raw="Languages: Python, R, SQL"), vocab).matched
    assert listed == ["r"]

    substring = score_skills(_job(description_raw="Recruiter will reach out"), vocab).matched
    assert substring == []


def test_bare_c_does_not_false_match_a_middle_initial():
    # found live: "Chief Audit Officer" scored well above threshold purely
    # because its description quoted "Arthur C. Clarke" — the period after
    # a middle initial looks identical, from the right, to a period ending
    # an enumerated list ("...Python, and R.").
    vocab = {"c": 1.0}
    result = score_skills(
        _job(
            description_raw=(
                'Arthur C. Clarke famously said that "any sufficiently advanced '
                'technology is indistinguishable from magic."'
            )
        ),
        vocab,
    )
    assert result.matched == []


# ---- title weighting + saturation ----


def test_title_match_weighted_higher_than_description_match():
    vocab = {"python": 1.0}
    in_title = score_skills(_job(title="Python Engineer", description_raw="great team"), vocab)
    in_desc = score_skills(_job(title="Engineer", description_raw="some python helpful"), vocab)
    assert in_title.score > in_desc.score


def test_skill_score_saturates_and_does_not_exceed_one():
    vocab = {"python": 2.0, "sql": 2.0, "react": 2.0, "typescript": 2.0, "aws": 2.0}
    job = _job(description_raw="python, sql, react, typescript, aws all required")
    result = score_skills(job, vocab, saturation=4.0)
    assert result.score == 1.0


def test_skill_score_unknown_only_when_no_text_at_all():
    vocab = {"python": 1.0}
    assert score_skills(_job(), vocab).score is UNKNOWN
    assert score_skills(_job(title="Engineer"), vocab).score is not UNKNOWN


def test_skill_score_is_zero_not_unknown_when_text_present_but_no_overlap():
    vocab = {"python": 1.0}
    result = score_skills(_job(title="Chef", description_raw="cooking and baking"), vocab)
    assert result.score == 0.0


# ---- salary dimension ----


def test_parse_salary_range_adzuna_point_estimate():
    assert parse_salary_range("104099.3-104099.3") == (104099.3, 104099.3)


def test_parse_salary_range_human_string_with_k_suffix():
    assert parse_salary_range("$120K-$150K a year") == (120000.0, 150000.0)


def test_parse_salary_range_empty_is_none():
    assert parse_salary_range("") is None
    assert parse_salary_range(None) is None


def test_parse_salary_range_handles_int_from_sheets_auto_typing():
    # Google Sheets stores a manually-typed plain number as a numeric cell,
    # so gspread's get_all_records() hands back an int/float here, not a
    # str, even though every writer in job_sources always writes a string.
    assert parse_salary_range(150000) == (150000.0, 150000.0)
    assert parse_salary_range(150000.5) == (150000.5, 150000.5)


def test_score_salary_handles_int_salary_range_from_sheets():
    job = _job(salary_range=150000)
    assert score_salary(job, _base_config(salary_floor=100000)) == 1.0


def test_salary_unknown_when_no_floor_configured():
    job = _job(salary_range="150000-150000")
    assert score_salary(job, _base_config(salary_floor=None)) is UNKNOWN


def test_salary_unknown_when_job_has_no_salary():
    job = _job(salary_range="")
    assert score_salary(job, _base_config(salary_floor=100000)) is UNKNOWN


def test_salary_below_floor_decays_instead_of_zeroing():
    job = _job(salary_range="50000-50000")
    score = score_salary(job, _base_config(salary_floor=100000))
    assert 0.0 < score < 0.5


def test_salary_at_or_above_floor_with_no_target_is_full_score():
    job = _job(salary_range="150000-150000")
    assert score_salary(job, _base_config(salary_floor=100000)) == 1.0


def test_salary_ramps_between_floor_and_target():
    job = _job(salary_range="150000-150000")
    score = score_salary(job, _base_config(salary_floor=100000, salary_target=200000))
    assert 0.5 < score < 1.0


def test_salary_at_or_above_target_is_full_score():
    job = _job(salary_range="250000-250000")
    score = score_salary(job, _base_config(salary_floor=100000, salary_target=200000))
    assert score == 1.0


# ---- location dimension ----


def test_location_unknown_when_no_targets_configured():
    job = _job(location="Bangalore, Karnataka")
    assert score_location(job, _base_config(target_locations="")) is UNKNOWN


def test_location_unknown_when_job_has_no_location():
    job = _job(location="")
    assert score_location(job, _base_config(target_locations="Bangalore")) is UNKNOWN


def test_location_matches_target_directly():
    job = _job(location="Bangalore, Karnataka")
    assert score_location(job, _base_config(target_locations="Bangalore,Pune")) == 1.0


def test_location_no_match_gets_low_but_nonzero_score():
    job = _job(location="Berlin, Germany")
    score = score_location(job, _base_config(target_locations="Bangalore,Pune"))
    assert 0.0 < score < 0.6


def test_remote_job_matches_when_remote_ok():
    job = _job(location="Anywhere", title="Remote Software Engineer")
    assert score_location(job, _base_config(target_locations="Bangalore")) == 1.0


def test_remote_job_not_auto_matched_when_remote_ok_is_n():
    job = _job(location="Remote")
    score = score_location(job, _base_config(target_locations="Bangalore", remote_ok="N"))
    assert score < 1.0


def test_geo_restricted_remote_excluding_user_country_does_not_get_full_credit():
    # found live: a Mercury listing's location field literally said
    # "...or Remote within United States" — that's remote, but not for
    # someone in India, and was still scoring a full 1.0 location match.
    job = _job(
        location="San Francisco, CA, New York, NY, Portland, OR, or Remote within United States"
    )
    score = score_location(
        job, _base_config(target_locations="Bangalore,Pune,Hyderabad,Mumbai,Remote", user_country="India")
    )
    assert score < 1.0


def test_geo_restricted_remote_including_user_country_still_gets_full_credit():
    job = _job(location="Remote within India, US, or Canada")
    score = score_location(
        job, _base_config(target_locations="Bangalore,Remote", user_country="India")
    )
    assert score == 1.0


def test_unrestricted_remote_still_gets_full_credit_when_user_country_is_set():
    job = _job(location="Remote")
    score = score_location(
        job, _base_config(target_locations="Bangalore,Remote", user_country="India")
    )
    assert score == 1.0


def test_geo_restricted_remote_unaffected_when_user_country_not_configured():
    # can't judge without knowing where the user is -> don't penalize;
    # preserves the pre-fix behavior when user_country is left unset.
    job = _job(location="Remote within United States")
    score = score_location(
        job, _base_config(target_locations="Bangalore,Remote", user_country="")
    )
    assert score == 1.0


# ---- combined score_job: dynamic reweighting ----


def test_score_job_degrades_to_skill_only_when_config_is_empty():
    vocab = {"python": 1.0}
    job = _job(title="Python Engineer", description_raw="python role", location="", salary_range="")
    result = score_job(job, vocab, _base_config())
    assert result["salary_score"] is UNKNOWN
    assert result["location_score"] is UNKNOWN
    # with only skill present, match_score is exactly the skill score * 100
    skill_only = score_skills(job, vocab).score
    assert result["match_score"] == round(100 * skill_only)


def test_score_job_combines_all_three_dimensions_when_present():
    vocab = {"python": 2.0, "sql": 2.0}
    job = _job(
        title="Python Engineer",
        description_raw="python and sql required",
        location="Bangalore",
        salary_range="150000-150000",
    )
    config = _base_config(salary_floor=100000, target_locations="Bangalore")
    result = score_job(job, vocab, config)
    assert result["skill_score"] is not UNKNOWN
    assert result["salary_score"] == 1.0
    assert result["location_score"] == 1.0
    assert 0 <= result["match_score"] <= 100


def test_score_job_below_threshold_would_be_ignored_by_engine():
    vocab = {"python": 1.0}
    job = _job(title="Chef", description_raw="cooking only, no tech")
    result = score_job(job, vocab, _base_config())
    assert result["match_score"] < 40  # below default match_threshold
