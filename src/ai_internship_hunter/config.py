from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CandidateProfile:
    name: str
    email: str
    phone: str
    location: str
    graduation: str
    work_authorized_in_taiwan: bool
    summary: str
    skills: tuple[str, ...]
    role_interests: tuple[str, ...]
    evidence: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> "CandidateProfile":
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("skills", "role_interests", "evidence"):
            data[key] = tuple(data[key])
        return cls(**data)


@dataclass(frozen=True)
class SearchPreferences:
    languages: tuple[str, ...]
    locations: tuple[str, ...]
    paid_only: bool
    minimum_match_score: int
    application_limit: int | None
    human_review_required: bool

    @classmethod
    def load(cls, path: Path) -> "SearchPreferences":
        data = json.loads(path.read_text(encoding="utf-8"))
        data["languages"] = tuple(data["languages"])
        data["locations"] = tuple(data["locations"])
        return cls(**data)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_defaults() -> tuple[CandidateProfile, SearchPreferences]:
    root = project_root()
    return (
        CandidateProfile.load(root / "config" / "candidate.json"),
        SearchPreferences.load(root / "config" / "preferences.json"),
    )

