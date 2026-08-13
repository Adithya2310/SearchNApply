import json

import pytest

from outreach import generate

PROFILE = {"name": "Adithya NG", "skills": {"languages": ["Python"]}}


def test_generate_email_draft_returns_subject_and_body(monkeypatch):
    monkeypatch.setattr(
        generate, "generate", lambda *a, **k: json.dumps({"subject": "Re: Backend Engineer", "body": "Hi there,..."})
    )

    result = generate.generate_email_draft(PROFILE, "job description", "Acme", "Backend Engineer", None, config={})

    assert result == {"subject": "Re: Backend Engineer", "body": "Hi there,..."}


def test_generate_email_draft_includes_company_role_and_contact_in_prompt(monkeypatch):
    captured = {}

    def fake_generate(prompt, system=None, config=None):
        captured["prompt"] = prompt
        captured["system"] = system
        return json.dumps({"subject": "s", "body": "b"})

    monkeypatch.setattr(generate, "generate", fake_generate)

    generate.generate_email_draft(PROFILE, "job description text", "Acme", "Backend Engineer", "Jane", config={})

    assert "Acme" in captured["prompt"]
    assert "Backend Engineer" in captured["prompt"]
    assert "Jane" in captured["prompt"]
    assert "job description text" in captured["prompt"]


def test_generate_email_draft_marks_contact_unknown_when_none_given(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        generate,
        "generate",
        lambda prompt, system=None, config=None: captured.setdefault("prompt", prompt) and json.dumps({"subject": "s", "body": "b"}),
    )

    generate.generate_email_draft(PROFILE, "jd", "Acme", "Role", None, config={})

    assert "(unknown)" in captured["prompt"]


def test_generate_email_draft_raises_on_invalid_json(monkeypatch):
    monkeypatch.setattr(generate, "generate", lambda *a, **k: "not json")

    with pytest.raises(ValueError, match="did not return valid JSON"):
        generate.generate_email_draft(PROFILE, "jd", "Acme", "Role", None, config={})


def test_generate_email_draft_raises_when_missing_fields(monkeypatch):
    monkeypatch.setattr(generate, "generate", lambda *a, **k: json.dumps({"subject": "s"}))

    with pytest.raises(ValueError, match="missing subject/body"):
        generate.generate_email_draft(PROFILE, "jd", "Acme", "Role", None, config={})


def test_enforce_linkedin_length_leaves_short_notes_untouched():
    note = "Short note."
    assert generate._enforce_linkedin_length(note) == note


def test_enforce_linkedin_length_truncates_at_word_boundary():
    note = "word " * 100  # way over 300 chars
    result = generate._enforce_linkedin_length(note)
    assert len(result) <= 300
    assert result.endswith("…")
    assert not result[:-1].endswith(" ")  # truncated at a word boundary, no trailing space before the ellipsis


def test_generate_linkedin_note_enforces_length(monkeypatch):
    monkeypatch.setattr(generate, "generate", lambda *a, **k: "x " * 500)

    result = generate.generate_linkedin_note(PROFILE, "jd", "Acme", "Role", "Jane", config={})

    assert len(result) <= 300
