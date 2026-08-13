import json

import pytest

from profile_updater import apply, extract, log

PROFILE = {
    "skills": {"languages": ["Python"], "technologies_tools": []},
    "work_experience": [{"company": "Acme", "bullets": ["Did a thing."]}],
    "projects": [{"name": "Karna", "description": "A crowdfunding platform."}],
}


def test_extract_update_returns_parsed_proposal(monkeypatch):
    monkeypatch.setattr(
        extract,
        "generate",
        lambda *a, **k: json.dumps(
            {"skills": ["Kafka"], "bullet": "Built a Kafka pipeline.", "suggested_target_type": "work_experience", "suggested_target_name": "Acme"}
        ),
    )

    result = extract.extract_update("I built a Kafka pipeline at work", PROFILE, config={})

    assert result["skills"] == ["Kafka"]
    assert result["suggested_target_type"] == "work_experience"
    assert result["suggested_target_name"] == "Acme"


def test_extract_update_raises_on_invalid_json(monkeypatch):
    monkeypatch.setattr(extract, "generate", lambda *a, **k: "not json")

    with pytest.raises(ValueError, match="did not return valid JSON"):
        extract.extract_update("text", PROFILE, config={})


def test_extract_update_raises_when_missing_keys(monkeypatch):
    monkeypatch.setattr(extract, "generate", lambda *a, **k: json.dumps({"skills": []}))

    with pytest.raises(ValueError, match="missing required keys"):
        extract.extract_update("text", PROFILE, config={})


def test_add_bullet_to_work_experience_appends_and_is_case_insensitive():
    profile = {"work_experience": [{"company": "Acme", "bullets": ["Did a thing."]}]}

    apply.add_bullet_to_work_experience(profile, "acme", "Did another thing.")

    assert profile["work_experience"][0]["bullets"] == ["Did a thing.", "Did another thing."]


def test_add_bullet_to_work_experience_raises_when_company_not_found():
    profile = {"work_experience": []}

    with pytest.raises(ValueError, match="No work_experience entry"):
        apply.add_bullet_to_work_experience(profile, "Nonexistent", "bullet")


def test_add_bullet_to_project_appends_to_description():
    profile = {"projects": [{"name": "Karna", "description": "A crowdfunding platform."}]}

    apply.add_bullet_to_project(profile, "Karna", "Now supports multi-chain deployment.")

    assert profile["projects"][0]["description"] == "A crowdfunding platform. Now supports multi-chain deployment."


def test_add_bullet_to_project_raises_when_project_not_found():
    profile = {"projects": []}

    with pytest.raises(ValueError, match="No project entry"):
        apply.add_bullet_to_project(profile, "Nonexistent", "bullet")


def test_add_new_project_creates_entry():
    profile = {}

    apply.add_new_project(profile, "SideQuest", "A new side project.")

    assert profile["projects"] == [{"name": "SideQuest", "description": "A new side project.", "links": {}}]


def test_append_log_entry_writes_one_json_line(tmp_path):
    log_path = tmp_path / "profile_updates_log.jsonl"

    entry = log.append_log_entry(
        raw_input="I built a Kafka pipeline",
        proposed={"skills": ["Kafka"]},
        decision="approved",
        applied={"skills": ["Kafka"]},
        log_path=str(log_path),
    )

    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    written = json.loads(lines[0])
    assert written["decision"] == "approved"
    assert written["raw_input"] == "I built a Kafka pipeline"
    assert written == entry


def test_append_log_entry_appends_not_overwrites(tmp_path):
    log_path = tmp_path / "profile_updates_log.jsonl"

    log.append_log_entry("first", {}, "rejected", log_path=str(log_path))
    log.append_log_entry("second", {}, "approved", log_path=str(log_path))

    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 2
