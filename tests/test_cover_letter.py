from ai_internship_hunter.cover_letter import build_cover_letter
from ai_internship_hunter.models import JobPosting, MatchResult
from ai_internship_hunter.resume import Project, ResumeSource, TailoredResume
from ai_internship_hunter.roles import role_area


def _tailored(projects) -> TailoredResume:
    source = ResumeSource(
        name="Rushikesh Sontakke", email="me@example.com", phone="+886",
        location="Hsinchu", github="", linkedin="", base_summary="",
        education=None, skill_groups=(), projects=projects, experience=(),
    )
    return TailoredResume(
        source=source, target_title="", target_company="", headline="",
        summary="", matched_skills=(), skill_groups=(), projects=projects, experience=(),
    )


_BACKEND = Project(
    title="Deep Learning Pill Recognition System", dates="", skills=("Flask", "Docker", "Python"),
    links={}, bullets=("Built a scalable Flask backend deployed on Docker.",
                       "Improved OCR accuracy from 63% to 79.6%."),
)
_CHAT = Project(
    title="ChatSphere", dates="", skills=("React", "Firebase"), links={},
    bullets=("Built a real-time chat app.",),
)


def test_role_area_backend_vs_ml():
    assert "backend" in role_area("Backend Software Engineer Intern", "")
    assert role_area("Machine Learning Scientist Intern", "pytorch models") == "machine learning"
    assert role_area("Data Analyst Intern", "sql analytics") == "data science"


def test_cover_letter_leads_with_role_area_and_skills():
    job = JobPosting(
        source="x", external_id="1", title="Backend Software Engineer Intern",
        company="Appier", location="Taipei", description="Flask Docker SQL APIs",
        url="", id=1,
    )
    match = MatchResult(
        job_id=1, score=88, qualified=True,
        matched_skills=("Docker", "Flask", "Python", "SQL"), missing_signals=(), reasons=(),
    )
    letter = build_cover_letter(_tailored((_BACKEND, _CHAT)), job, match)
    assert "backend" in letter                       # role-aware framing
    assert "Backend Software Engineer Intern" in letter
    assert "Appier" in letter
    assert "Docker" in letter and "Flask" in letter  # matched skills foregrounded
    assert letter.startswith("Dear Hiring Team,")
    assert letter.rstrip().endswith("Rushikesh Sontakke")


def test_cover_letter_cites_top_ranked_project_only():
    job = JobPosting(
        source="x", external_id="1", title="Backend Intern", company="Appier",
        location="Taipei", description="Flask Docker", url="", id=1,
    )
    match = MatchResult(
        job_id=1, score=85, qualified=True, matched_skills=("Flask", "Docker"),
        missing_signals=(), reasons=(),
    )
    # Tailoring already ordered projects; the letter must cite projects[0].
    letter = build_cover_letter(_tailored((_BACKEND, _CHAT)), job, match)
    assert "Deep Learning Pill Recognition System" in letter
    assert "ChatSphere" not in letter


def test_cover_letter_only_uses_real_bullets():
    job = JobPosting(
        source="x", external_id="1", title="Backend Intern", company="Appier",
        location="Taipei", description="Flask Docker", url="", id=1,
    )
    match = MatchResult(
        job_id=1, score=85, qualified=True, matched_skills=("Flask", "Docker"),
        missing_signals=(), reasons=(),
    )
    letter = build_cover_letter(_tailored((_BACKEND,)), job, match)
    # The backend bullet (skill-relevant) must be chosen over the OCR one.
    assert "scalable Flask backend" in letter
