from pathlib import Path

from ai_internship_hunter.config import CandidateProfile
from ai_internship_hunter.interview_prep import InterviewPrepGenerator
from ai_internship_hunter.models import JobPosting, MatchResult


def _profile() -> CandidateProfile:
    return CandidateProfile(
        name="Rushikesh Sontakke",
        email="me@example.com",
        phone="+886",
        location="Hsinchu, Taiwan",
        graduation="January 2027",
        work_authorized_in_taiwan=True,
        summary="EECS undergrad.",
        skills=("Python", "YOLOv8", "OpenCV"),
        role_interests=("computer vision engineer",),
        evidence=("Improved OCR accuracy from 63% to 79.6%.",),
    )


def _cv_job() -> JobPosting:
    return JobPosting(
        source="greenhouse:x",
        external_id="1",
        title="Computer Vision Engineer Intern",
        company="Vision Labs",
        location="Taipei, Taiwan",
        description="Work on object detection, YOLO, OpenCV, and OCR pipelines.",
        url="https://example.com/job",
        id=1,
    )


def _match() -> MatchResult:
    return MatchResult(
        job_id=1,
        score=93,
        qualified=True,
        matched_skills=("OpenCV", "Python", "YOLOv8"),
        missing_signals=("tensorflow",),
        reasons=(),
    )


def test_packet_written_to_expected_path(tmp_path):
    path = InterviewPrepGenerator(_profile(), tmp_path).generate(_cv_job(), _match())
    assert path == tmp_path / "1-vision-labs-computer-vision-engineer-intern" / "INTERVIEW.md"
    assert path.exists()


def test_packet_contains_concept_specific_questions(tmp_path):
    path = InterviewPrepGenerator(_profile(), tmp_path).generate(_cv_job(), _match())
    text = path.read_text(encoding="utf-8")
    # Concept detected from posting -> computer-vision section present
    assert "Computer Vision" in text
    assert "Intersection-over-Union" in text  # a CV coding topic
    # Should not pull in an unrelated concept the posting never mentions
    assert "Backend Engineering" not in text


def test_packet_surfaces_gaps_and_evidence(tmp_path):
    path = InterviewPrepGenerator(_profile(), tmp_path).generate(_cv_job(), _match())
    text = path.read_text(encoding="utf-8")
    assert "tensorflow" in text  # missing signal surfaced as a gap
    assert "Improved OCR accuracy" in text  # candidate evidence as STAR anchor
    assert "OpenCV" in text  # matched strength listed


def test_no_invented_company_facts_only_a_checklist(tmp_path):
    path = InterviewPrepGenerator(_profile(), tmp_path).generate(_cv_job(), _match())
    text = path.read_text(encoding="utf-8")
    assert "Company research checklist" in text
    assert "[ ]" in text  # research left as unchecked tasks, not fabricated answers


def test_job_with_no_known_concepts_falls_back(tmp_path):
    job = JobPosting(
        source="x", external_id="9", title="Generalist Intern", company="Acme",
        location="Remote", description="A little of everything.", url="", id=9,
    )
    match = MatchResult(
        job_id=9, score=80, qualified=True, matched_skills=(), missing_signals=(), reasons=(),
    )
    text = InterviewPrepGenerator(_profile(), tmp_path).generate(job, match).read_text("utf-8")
    # Falls back to software-engineering prompts rather than emitting nothing.
    assert "Software Engineering" in text
