from datetime import datetime, timezone

from application_kit import fields, pitch

PROFILE = {
    "name": "Adithya NG",
    "contact": {"email": "a@example.com", "phone": "+91 123", "linkedin": "li.example/a", "github": "gh.example/a"},
    "work_experience": [
        {"company": "Insight Software", "title": "Associate Software Engineer", "start_date": "2024-02", "end_date": "2026-07"},
        {"company": "Cofount", "title": "Intern", "start_date": "2024-01", "end_date": "2024-01"},
    ],
    "education": [{"degree": "B.E. Information Science", "institution": "DSCE"}],
}

JOB_INFO = {"company": "Acme", "title": "Backend Engineer", "url": "https://acme.example/jobs/1"}


def test_years_of_experience_spans_earliest_start_to_latest_end():
    result = fields._years_of_experience(PROFILE["work_experience"])
    assert result == 2.5  # 2024-01 to 2026-07 = 30 months


def test_years_of_experience_uses_today_when_end_date_missing():
    ongoing = [{"company": "Co", "start_date": "2024-01", "end_date": ""}]
    result = fields._years_of_experience(ongoing, today=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert result == 2.0


def test_years_of_experience_none_when_no_valid_dates():
    assert fields._years_of_experience([]) is None
    assert fields._years_of_experience([{"company": "Co"}]) is None


def test_format_desired_salary_with_floor_and_target():
    config = {"salary_floor": 1200000.0, "salary_target": 2000000.0, "salary_currency": "INR"}
    assert fields._format_desired_salary(config) == "INR 1200000-2000000"


def test_format_desired_salary_with_only_floor():
    config = {"salary_floor": 1200000.0, "salary_currency": "INR"}
    assert fields._format_desired_salary(config) == "INR 1200000"


def test_format_desired_salary_blank_when_unset():
    assert fields._format_desired_salary({}) == ""


def test_build_fields_pulls_from_profile_job_and_config():
    result = dict(
        fields.build_fields(
            PROFILE,
            JOB_INFO,
            config={"salary_floor": 1200000.0, "salary_currency": "INR"},
            resume_filename="tailored_resumes/acme.txt",
            today=datetime(2026, 8, 13, tzinfo=timezone.utc),
        )
    )
    assert result["Full Name"] == "Adithya NG"
    assert result["Email"] == "a@example.com"
    assert result["Current/Most Recent Employer"] == "Insight Software"
    assert result["Highest Education"] == "B.E. Information Science, DSCE"
    assert result["Desired Salary"] == "INR 1200000"
    assert result["Resume File to Attach"] == "tailored_resumes/acme.txt"
    assert result["Company Applying To"] == "Acme"
    assert result["Role Applying For"] == "Backend Engineer"
    assert result["Job Posting URL"] == "https://acme.example/jobs/1"


def test_build_fields_placeholder_when_no_resume_generated_yet():
    result = dict(fields.build_fields(PROFILE, JOB_INFO))
    assert "run M9 first" in result["Resume File to Attach"]


def test_generate_pitch_passes_profile_and_jd_to_ai(monkeypatch):
    captured = {}

    def fake_generate(prompt, system=None, config=None):
        captured["prompt"] = prompt
        captured["system"] = system
        return "Tailored pitch text."

    monkeypatch.setattr(pitch, "generate", fake_generate)

    result = pitch.generate_pitch(PROFILE, "job description text", config={"ai_provider": "gemini"})

    assert result == "Tailored pitch text."
    assert "job description text" in captured["prompt"]
    assert '"name": "Adithya NG"' in captured["prompt"]
    assert "No Markdown" in captured["system"] or "no Markdown" in captured["system"]
