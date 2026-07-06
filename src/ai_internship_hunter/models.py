from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobPosting:
    source: str
    external_id: str
    title: str
    company: str
    location: str
    description: str
    url: str
    language: str = "English"
    is_paid: bool | None = None
    id: int | None = None


@dataclass(frozen=True)
class MatchResult:
    job_id: int
    score: int
    qualified: bool
    matched_skills: tuple[str, ...]
    missing_signals: tuple[str, ...]
    reasons: tuple[str, ...]

