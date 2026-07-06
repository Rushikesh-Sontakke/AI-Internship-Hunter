from __future__ import annotations

import re
from pathlib import Path

from .config import CandidateProfile
from .models import JobPosting, MatchResult


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


class ReviewPacketGenerator:
    def __init__(self, profile: CandidateProfile, output_dir: Path):
        self.profile = profile
        self.output_dir = output_dir

    def generate(
        self, job: JobPosting, match: MatchResult, cover_letter: str | None = None
    ) -> Path:
        if not match.qualified:
            raise ValueError("Only qualified jobs can receive an application packet")
        packet_dir = self.output_dir / f"{job.id}-{_slug(job.company)}-{_slug(job.title)}"
        packet_dir.mkdir(parents=True, exist_ok=True)
        packet = packet_dir / "REVIEW.md"
        packet.write_text(self._render(job, match, cover_letter), encoding="utf-8")
        return packet

    def _default_cover_letter(self, job: JobPosting, match: MatchResult) -> str:
        skills = ", ".join(match.matched_skills) or "relevant skills"
        return (
            "Dear Hiring Team,\n\n"
            f"I am applying for the {job.title} role at {job.company}. I am an EECS "
            "undergraduate at National Tsing Hua University with hands-on experience "
            f"relevant to this role through {skills}.\n\n"
            f"Sincerely,\n{self.profile.name}"
        )

    def _render(
        self, job: JobPosting, match: MatchResult, cover_letter: str | None = None
    ) -> str:
        skills = ", ".join(match.matched_skills) or "No direct skills detected"
        evidence = "\n".join(f"- {item}" for item in self.profile.evidence)
        reasons = "\n".join(f"- {item}" for item in match.reasons)
        letter = cover_letter or self._default_cover_letter(job, match)
        return f"""# Human review packet: {job.title}

## Job

- Company: {job.company}
- Location: {job.location}
- Application URL: {job.url}
- Match score: {match.score}%
- Matched skills: {skills}

## Match rationale

{reasons}

## Resume-tailoring plan

Prioritize these existing skills: {skills}.

Use only this verified evidence:

{evidence}

## Cover-letter draft

{letter}

## Final review checklist

- [ ] Confirm the role is paid and still open.
- [ ] Remove any unsupported inference.
- [ ] Edit for company-specific motivation.
- [ ] Generate and visually inspect the tailored PDF.
- [ ] Verify all fields and uploads.
- [ ] Manually click Submit; this tool never submits.
"""
