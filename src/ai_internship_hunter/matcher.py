from __future__ import annotations

import re

from .config import CandidateProfile, SearchPreferences
from .models import JobPosting, MatchResult
from .semantic import HybridConceptSimilarity, SimilarityEngine


ALIASES = {
    "yolov8": ("yolov8", "yolo", "object detection"),
    "pytorch": ("pytorch", "deep learning"),
    "opencv": ("opencv", "computer vision", "image processing"),
    "openocr": ("openocr", "ocr", "optical character recognition"),
    "scikit-learn": ("scikit-learn", "sklearn", "machine learning"),
    "xgboost": ("xgboost", "gradient boosting"),
    "flask": ("flask", "rest api", "backend api"),
    "docker": ("docker", "container", "containerization"),
    "sql": ("sql", "database"),
    "pandas": ("pandas", "data analysis", "data pipeline"),
    "shap": ("shap", "explainable ai", "model interpretability"),
    "firebase": ("firebase", "firestore"),
}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", text.casefold()).strip()


def _contains_term(haystack: str, term: str) -> bool:
    normalized = _normalize(term)
    if normalized in {"c", "c++"}:
        return re.search(rf"(?<![a-z0-9+]){re.escape(normalized)}(?![a-z0-9+])", haystack) is not None
    return normalized in haystack


class JobMatcher:
    def __init__(
        self,
        profile: CandidateProfile,
        preferences: SearchPreferences,
        similarity: SimilarityEngine | None = None,
    ):
        self.profile = profile
        self.preferences = preferences
        self.similarity = similarity or HybridConceptSimilarity(profile)

    def score(self, job: JobPosting) -> MatchResult:
        if job.id is None:
            raise ValueError("Job must be persisted before scoring")
        haystack = _normalize(f"{job.title} {job.description}")
        matched = self._matched_skills(haystack)
        requested = self._requested_signals(haystack)

        # Hybrid score: explicit evidence stays dominant while semantic similarity
        # recognizes related concepts such as object detection and image processing.
        skills_score = min(40.0, len(matched) * 5.0)
        semantic_similarity = self.similarity.similarity(f"{job.title} {job.description}")
        semantic_score = semantic_similarity * 20.0
        title_score = self._title_score(job.title)
        location_ok = any(place.casefold() in job.location.casefold() for place in self.preferences.locations)
        location_score = 10.0 if location_ok else 0.0
        language_ok = job.language.casefold() in {x.casefold() for x in self.preferences.languages}
        language_score = 5.0 if language_ok else 0.0
        paid_ok = not self.preferences.paid_only or job.is_paid is True
        paid_score = 5.0 if paid_ok else 0.0
        normalized_title = _normalize(job.title)
        is_internship = any(
            signal in normalized_title
            for signal in ("intern", "internship", "co op", "student")
        )
        internship_score = 5.0 if is_internship else 0.0

        total = round(
            skills_score + semantic_score + title_score + location_score
            + language_score + paid_score + internship_score
        )
        total = max(0, min(100, total))
        missing = tuple(sorted(signal for signal in requested if signal not in {x.casefold() for x in matched}))
        reasons = (
            f"Matched {len(matched)} relevant skills or semantic signals.",
            f"Semantic similarity is {semantic_similarity:.0%} using {self.similarity.name}.",
            f"Role alignment contributed {round(title_score)} of 15 points.",
            f"Title {'passes' if is_internship else 'fails'} the internship eligibility gate.",
            f"Location {'matches' if location_ok else 'does not match'} configured preferences.",
            f"Language {'matches' if language_ok else 'does not match'} English-only preference.",
            f"Paid requirement {'is satisfied' if paid_ok else 'is not confirmed'}.",
        )
        return MatchResult(
            job_id=job.id,
            score=total,
            qualified=is_internship and total >= self.preferences.minimum_match_score,
            matched_skills=tuple(matched),
            missing_signals=missing,
            reasons=reasons,
        )

    def _matched_skills(self, haystack: str) -> list[str]:
        matches: list[str] = []
        for skill in self.profile.skills:
            normalized = skill.casefold()
            terms = ALIASES.get(normalized, (normalized,))
            if any(_contains_term(haystack, term) for term in terms):
                matches.append(skill)
        return sorted(set(matches), key=str.casefold)

    def _requested_signals(self, haystack: str) -> set[str]:
        return {canonical for canonical, terms in ALIASES.items() if any(_contains_term(haystack, term) for term in terms)}

    def _title_score(self, title: str) -> float:
        normalized = _normalize(title)
        if any(_normalize(role) in normalized for role in self.profile.role_interests):
            return 15.0
        role_terms = (
            "machine learning", "artificial intelligence", "computer vision", "data science",
            "data scientist", "data analyst", "analytics", "backend", "mlops", "applied ai",
        )
        if any(term in normalized for term in role_terms) or re.search(r"\bai\b", normalized):
            return 15.0
        return 0.0
