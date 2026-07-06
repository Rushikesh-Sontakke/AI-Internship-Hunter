import json
from pathlib import Path

from ai_internship_hunter.browser_bot import (
    ApplicantProfile,
    build_field_plan,
    extract_cover_letter,
    packet_dir_for,
)


def _write_configs(tmp_path: Path) -> tuple[Path, Path]:
    candidate = tmp_path / "candidate.json"
    resume = tmp_path / "resume.json"
    candidate.write_text(
        json.dumps(
            {
                "name": "Rushikesh Sontakke",
                "email": "cand@example.com",
                "phone": "+886-000",
                "location": "Hsinchu, Taiwan",
            }
        ),
        encoding="utf-8",
    )
    resume.write_text(
        json.dumps(
            {
                "github": "https://github.com/x",
                "linkedin": "https://linkedin.com/in/x",
            }
        ),
        encoding="utf-8",
    )
    return candidate, resume


def test_profile_splits_name_and_merges_sources(tmp_path):
    candidate, resume = _write_configs(tmp_path)
    profile = ApplicantProfile.load(candidate, resume)
    assert profile.first_name == "Rushikesh"
    assert profile.last_name == "Sontakke"
    assert profile.full_name == "Rushikesh Sontakke"
    assert profile.github == "https://github.com/x"
    assert profile.linkedin == "https://linkedin.com/in/x"


def test_field_plan_skips_empty_values(tmp_path):
    profile = ApplicantProfile(
        first_name="Rushikesh",
        last_name="Sontakke",
        email="a@b.com",
        phone="",
        location="Hsinchu",
        github="",
        linkedin="https://linkedin.com/in/x",
    )
    plan = build_field_plan(profile, Path("resume.pdf"), "Dear team")
    names = {target.name for target in plan}
    assert "phone" not in names  # empty value dropped
    assert "github" not in names
    assert {"first_name", "last_name", "email", "linkedin", "resume", "cover_letter"} <= names


def test_resume_target_is_a_file_upload(tmp_path):
    profile = ApplicantProfile(
        first_name="A", last_name="B", email="a@b.com", phone="1",
        location="X", github="", linkedin="",
    )
    plan = build_field_plan(profile, Path("/tmp/r.pdf"), "cover")
    resume = next(target for target in plan if target.name == "resume")
    assert resume.kind == "file"
    assert resume.value == str(Path("/tmp/r.pdf"))


def test_packet_dir_matches_generator_convention():
    path = packet_dir_for(Path("generated"), 7, "Example Vision Labs", "CV Intern")
    assert path == Path("generated/7-example-vision-labs-cv-intern")


def test_extract_cover_letter_pulls_the_draft_section():
    review = (
        "# Human review packet\n\n## Cover-letter draft\n\n"
        "Dear Hiring Team,\n\nI am applying.\n\nSincerely,\nRushikesh\n\n"
        "## Final review checklist\n- [ ] Confirm\n"
    )
    letter = extract_cover_letter(review)
    assert letter.startswith("Dear Hiring Team,")
    assert "Sincerely" in letter
    assert "checklist" not in letter


def test_extract_cover_letter_missing_section_returns_empty():
    assert extract_cover_letter("no sections here") == ""
