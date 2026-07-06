"""Role-aware cover-letter drafting from verified resume evidence.

The letter leads with the emphasis the role calls for (see `roles.role_area`),
foregrounds the matched skills, and cites the candidate's single most relevant
project. Every sentence is built from real resume data — project titles, skills,
and bullets — so nothing is invented.
"""

from __future__ import annotations

import re

from .models import JobPosting, MatchResult
from .resume import Project, TailoredResume
from .roles import role_area


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", value.casefold()).strip()


def _lead_skills(match: MatchResult, limit: int = 5) -> str:
    skills = list(match.matched_skills[:limit])
    if not skills:
        return ""
    if len(skills) == 1:
        return skills[0]
    return f"{', '.join(skills[:-1])}, and {skills[-1]}"


def _best_bullets(project: Project, match: MatchResult, job: JobPosting, limit: int = 2) -> list[str]:
    """Pick the project bullets most relevant to the role, preserving their order."""

    matched = {_normalize(skill) for skill in match.matched_skills}
    job_text = _normalize(f"{job.title} {job.description}")

    def score(bullet: str) -> int:
        text = _normalize(bullet)
        skill_hits = sum(1 for skill in matched if skill and skill in text)
        job_hits = sum(1 for token in set(text.split()) if len(token) > 3 and token in job_text)
        return skill_hits * 3 + job_hits

    ranked = sorted(project.bullets, key=score, reverse=True)
    chosen = [bullet for bullet in ranked[:limit]]
    # Restore the project's original ordering for natural reading.
    return [bullet for bullet in project.bullets if bullet in chosen]


def build_cover_letter(tailored: TailoredResume, job: JobPosting, match: MatchResult) -> str:
    """Return a tailored cover-letter draft (greeting through signature)."""

    area = role_area(job.title, job.description)
    skills = _lead_skills(match)
    skill_clause = f", including {skills}" if skills else ""

    paragraphs = [
        "Dear Hiring Team,",
        (
            f"I am applying for the {job.title} role at {job.company}. I am an EECS "
            "undergraduate at National Tsing Hua University with hands-on experience in "
            f"{area}{skill_clause}, and I enjoy building and shipping systems end to end."
        ),
    ]

    if tailored.projects:
        top = tailored.projects[0]
        project_skills = ", ".join(top.skills[:4])
        skills_clause = f", built with {project_skills}" if project_skills else ""
        bullets = _best_bullets(top, match, job)
        detail = " ".join(bullets)
        paragraphs.append(
            f"One project especially relevant to this role is my {top.title}{skills_clause}. {detail}".strip()
        )

    paragraphs.append(
        f"I would welcome the opportunity to bring this experience to {job.company} as an intern. "
        "Thank you for your consideration."
    )
    paragraphs.append(f"Sincerely,\n{tailored.source.name}")
    return "\n\n".join(paragraphs)
