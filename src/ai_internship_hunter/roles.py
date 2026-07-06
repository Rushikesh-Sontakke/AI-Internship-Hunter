"""Determine the emphasis a role calls for, so materials can lead with it.

Truthful framing only: this picks which of the candidate's genuine strengths to
foreground for a given posting. It never asserts a specialization the candidate
does not have — the phrases below all describe experience present in the resume.
"""

from __future__ import annotations

import re

from .semantic import detected_concepts


# Ordered by specificity. The first title cue that matches wins, because the job
# title is the most reliable signal of what the role is actually about.
_TITLE_CUES: tuple[tuple[str, str], ...] = (
    (r"back[\s-]?end", "backend and full-stack development"),
    (r"full[\s-]?stack", "full-stack development"),
    (r"\bml\s*ops\b|\bmlops\b", "ML systems and deployment"),
    (r"computer vision|\bcv\b|image", "computer vision"),
    (r"data scien|data analyst|analytics|\bdata\b", "data science"),
    (r"machine learning|\bml\b|deep learning", "machine learning"),
    (r"\bai\b|applied ai", "machine learning and AI"),
    (r"backend|api|server|infrastructure|platform", "backend development"),
)

# Fallback when the title is generic: use concepts detected in the description.
_CONCEPT_AREAS: tuple[tuple[str, str], ...] = (
    ("backend", "backend and full-stack development"),
    ("mlops", "ML systems and deployment"),
    ("computer_vision", "computer vision"),
    ("data_science", "data science"),
    ("machine_learning", "machine learning"),
    ("software_engineering", "software engineering"),
)


def role_area(title: str, description: str = "") -> str:
    """Return a short phrase for the role's emphasis, e.g. ``backend development``."""

    normalized_title = title.casefold()
    for pattern, area in _TITLE_CUES:
        if re.search(pattern, normalized_title):
            return area
    concepts = detected_concepts(f"{title} {description}")
    for key, area in _CONCEPT_AREAS:
        if key in concepts:
            return area
    return "software engineering"
