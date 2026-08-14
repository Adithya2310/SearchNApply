from datetime import datetime, timezone

from resume_tailor import output


def test_safe_filename_part_strips_non_alnum():
    assert output.safe_filename_part("Acme Corp!") == "Acme_Corp"


def test_safe_filename_part_handles_blank():
    assert output.safe_filename_part("") == ""
    assert output.safe_filename_part(None) == ""


def test_save_tailored_resume_writes_expected_filename_and_content(tmp_path):
    out_dir = str(tmp_path / "tailored_resumes")

    filename = output.save_tailored_resume(
        "DRAFT TEXT",
        company="Acme Corp",
        role="Backend Engineer",
        today=datetime(2026, 8, 14, tzinfo=timezone.utc),
        output_dir=out_dir,
    )

    assert filename == f"{out_dir}/Acme_Corp_Backend_Engineer_20260814.txt"
    with open(filename) as f:
        assert f.read() == "DRAFT TEXT"


def test_save_tailored_resume_falls_back_to_generic_names_when_blank(tmp_path):
    out_dir = str(tmp_path / "tailored_resumes")

    filename = output.save_tailored_resume(
        "text", company="", role="", today=datetime(2026, 8, 14, tzinfo=timezone.utc), output_dir=out_dir
    )

    assert filename == f"{out_dir}/company_role_20260814.txt"
