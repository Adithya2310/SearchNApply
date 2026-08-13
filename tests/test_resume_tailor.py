import json

import pytest

from resume_tailor import gaps, tailor
from resume_tailor.profile_updates import add_confirmed_skills

PROFILE = {
    "skills": {"languages": ["Python"], "technologies_tools": ["React"]},
    "work_experience": [{"company": "Co", "tech_stack": ["PostgreSQL"]}],
}


def test_candidate_skill_set_canonicalizes_across_the_whole_profile():
    result = gaps.candidate_skill_set(PROFILE)
    assert result == {"python", "react", "postgres"}


def test_find_skill_gaps_excludes_known_skills_even_by_alias(monkeypatch):
    monkeypatch.setattr(gaps, "generate", lambda *a, **k: json.dumps(["ReactJS", "Kubernetes", "Python"]))

    result = gaps.find_skill_gaps("some JD text", PROFILE, config={})

    assert result == ["Kubernetes"]  # ReactJS -> known "react"; Python already known


def test_find_skill_gaps_returns_all_when_profile_has_nothing(monkeypatch):
    monkeypatch.setattr(gaps, "generate", lambda *a, **k: json.dumps(["Go", "Rust"]))

    result = gaps.find_skill_gaps("JD text", {"skills": {}, "work_experience": []}, config={})

    assert result == ["Go", "Rust"]


def test_extract_required_skills_raises_on_invalid_json(monkeypatch):
    monkeypatch.setattr(gaps, "generate", lambda *a, **k: "not json")

    with pytest.raises(ValueError, match="did not return valid JSON"):
        gaps.extract_required_skills("JD text", config={})


def test_extract_required_skills_raises_when_not_a_list(monkeypatch):
    monkeypatch.setattr(gaps, "generate", lambda *a, **k: json.dumps({"skills": ["Go"]}))

    with pytest.raises(ValueError, match="isn't a list"):
        gaps.extract_required_skills("JD text", config={})


def test_add_confirmed_skills_dedupes_by_canonical_name():
    profile = {"skills": {"technologies_tools": ["React"]}}

    add_confirmed_skills(profile, ["ReactJS", "Kubernetes"])

    assert profile["skills"]["technologies_tools"] == ["React", "Kubernetes"]


def test_add_confirmed_skills_initializes_missing_skills_block():
    profile = {}

    add_confirmed_skills(profile, ["Kubernetes"])

    assert profile["skills"]["technologies_tools"] == ["Kubernetes"]


def test_tailor_resume_passes_profile_jd_and_keywords_to_ai(monkeypatch):
    captured = {}

    def fake_generate(prompt, system=None, config=None):
        captured["prompt"] = prompt
        captured["system"] = system
        captured["config"] = config
        return "TAILORED RESUME TEXT"

    monkeypatch.setattr(tailor, "generate", fake_generate)

    result = tailor.tailor_resume(PROFILE, "job description here", ["Kubernetes", "Go"], config={"ai_provider": "gemini"})

    assert result == "TAILORED RESUME TEXT"
    assert "job description here" in captured["prompt"]
    assert '"languages"' in captured["prompt"]  # profile JSON is embedded
    assert "Kubernetes, Go" in captured["system"]
    assert captured["config"] == {"ai_provider": "gemini"}


def test_tailor_resume_handles_no_keywords(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        tailor, "generate", lambda prompt, system=None, config=None: captured.setdefault("system", system) or ""
    )

    tailor.tailor_resume(PROFILE, "job description", [], config={})

    assert "(none)" in captured["system"]


def test_format_date_range_uses_present_only_when_end_date_missing():
    assert tailor._format_date_range("2024-02", "") == "2024-02 - Present"
    assert tailor._format_date_range("2024-02", None) == "2024-02 - Present"


def test_format_date_range_uses_the_literal_end_date_when_present():
    # Regression: live-tested output once rendered a job with a real,
    # already-past end_date as "Present" — the model inferred an ongoing
    # role instead of using the profile's actual data. This must be
    # computed here, in code, never left to the model to reason about.
    assert tailor._format_date_range("2024-02", "2026-07") == "2024-02 - 2026-07"


def test_tailor_resume_embeds_precomputed_date_ranges_not_raw_dates(monkeypatch):
    profile = {
        "skills": {},
        "work_experience": [{"company": "Co", "start_date": "2024-02", "end_date": "2026-07"}],
    }
    captured = {}
    monkeypatch.setattr(
        tailor, "generate", lambda prompt, system=None, config=None: captured.setdefault("prompt", prompt) or ""
    )

    tailor.tailor_resume(profile, "job description", [], config={})

    assert '"date_range": "2024-02 - 2026-07"' in captured["prompt"]


def test_tailor_resume_does_not_mutate_the_caller_s_profile(monkeypatch):
    profile = {
        "skills": {},
        "work_experience": [{"company": "Co", "start_date": "2024-02", "end_date": "2026-07"}],
    }
    monkeypatch.setattr(tailor, "generate", lambda prompt, system=None, config=None: "")

    tailor.tailor_resume(profile, "job description", [], config={})

    assert "date_range" not in profile["work_experience"][0]
