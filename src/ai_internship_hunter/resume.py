from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .models import JobPosting, MatchResult


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", value.casefold()).strip()


@dataclass(frozen=True)
class Education:
    school: str
    degree: str
    location: str
    dates: str
    details: tuple[str, ...]


@dataclass(frozen=True)
class SkillGroup:
    label: str
    skills: tuple[str, ...]


@dataclass(frozen=True)
class Project:
    title: str
    dates: str
    skills: tuple[str, ...]
    links: dict[str, str]
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class Experience:
    title: str
    organization: str
    location: str
    dates: str
    skills: tuple[str, ...]
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class ResumeSource:
    name: str
    email: str
    phone: str
    location: str
    github: str
    linkedin: str
    base_summary: str
    education: Education
    skill_groups: tuple[SkillGroup, ...]
    projects: tuple[Project, ...]
    experience: tuple[Experience, ...]

    @classmethod
    def load(cls, path: Path) -> "ResumeSource":
        data = json.loads(path.read_text(encoding="utf-8"))
        education_data = data.pop("education")
        education = Education(**{**education_data, "details": tuple(education_data["details"])})
        skill_groups = tuple(
            SkillGroup(label=item["label"], skills=tuple(item["skills"]))
            for item in data.pop("skill_groups")
        )
        projects = tuple(
            Project(
                title=item["title"], dates=item["dates"], skills=tuple(item["skills"]),
                links=dict(item["links"]), bullets=tuple(item["bullets"]),
            )
            for item in data.pop("projects")
        )
        experience = tuple(
            Experience(
                title=item["title"], organization=item["organization"],
                location=item["location"], dates=item["dates"],
                skills=tuple(item["skills"]), bullets=tuple(item["bullets"]),
            )
            for item in data.pop("experience")
        )
        return cls(
            **data,
            education=education,
            skill_groups=skill_groups,
            projects=projects,
            experience=experience,
        )


@dataclass(frozen=True)
class TailoredResume:
    source: ResumeSource
    target_title: str
    target_company: str
    headline: str
    summary: str
    matched_skills: tuple[str, ...]
    skill_groups: tuple[SkillGroup, ...]
    projects: tuple[Project, ...]
    experience: tuple[Experience, ...]


class ResumeTailor:
    """Reorders verified evidence without inventing or exaggerating claims."""

    def __init__(self, source: ResumeSource):
        self.source = source

    def tailor(self, job: JobPosting, match: MatchResult) -> TailoredResume:
        matched = tuple(match.matched_skills)
        matched_keys = {_normalize(skill) for skill in matched}
        job_text = _normalize(f"{job.title} {job.description}")
        role = re.sub(r"\s*\(?\b(?:intern|internship)\b\)?\s*", " ", job.title, flags=re.I)
        role = re.sub(r"\s+", " ", role).strip(" ,-()")
        headline = f"{role} Candidate" if role else "AI Engineering Candidate"

        focus = ", ".join(matched[:6])
        summary = self.source.base_summary
        if focus:
            summary = (
                "EECS undergraduate at National Tsing Hua University specializing in machine "
                f"learning and computer vision, with hands-on experience in {focus}. Built and "
                "deployed deep learning, data, and full-stack systems."
            )

        skill_groups = tuple(
            SkillGroup(
                label=group.label,
                skills=tuple(sorted(
                    group.skills,
                    key=lambda skill: (0 if _normalize(skill) in matched_keys else 1, group.skills.index(skill)),
                )),
            )
            for group in self.source.skill_groups
        )

        projects = tuple(sorted(
            self.source.projects,
            key=lambda item: self._item_score(item.skills, item.bullets, job_text, matched_keys),
            reverse=True,
        ))
        experience = tuple(sorted(
            self.source.experience,
            key=lambda item: self._item_score(item.skills, item.bullets, job_text, matched_keys),
            reverse=True,
        ))
        return TailoredResume(
            source=self.source,
            target_title=job.title,
            target_company=job.company,
            headline=headline,
            summary=summary,
            matched_skills=matched,
            skill_groups=skill_groups,
            projects=projects,
            experience=experience,
        )

    @staticmethod
    def _item_score(
        skills: tuple[str, ...], bullets: tuple[str, ...], job_text: str, matched: set[str]
    ) -> int:
        skill_keys = {_normalize(skill) for skill in skills}
        matched_score = 4 * len(skill_keys & matched)
        job_score = sum(1 for skill in skill_keys if skill and skill in job_text)
        bullet_score = sum(1 for bullet in bullets if any(term in _normalize(bullet) for term in matched))
        return matched_score + job_score + bullet_score
