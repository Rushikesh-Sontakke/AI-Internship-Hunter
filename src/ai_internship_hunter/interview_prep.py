"""Deterministic interview-preparation packets for qualified roles.

Everything here is grounded in two local sources: the job posting's own text and
the candidate's verified evidence. The generator never invents facts about the
company, its products, or its competitors. Where outside research is genuinely
needed, it emits a research *checklist* for the human to complete rather than
fabricating answers.

Technical and coding prompts are selected from concept banks keyed by the same
concept taxonomy used for matching (`semantic.detected_concepts`), so a packet
only contains questions relevant to the concepts the posting actually mentions.
"""

from __future__ import annotations

import re
from pathlib import Path

from .config import CandidateProfile
from .models import JobPosting, MatchResult
from .semantic import detected_concepts


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


CONCEPT_LABELS = {
    "machine_learning": "Machine Learning",
    "computer_vision": "Computer Vision",
    "data_science": "Data Science",
    "backend": "Backend Engineering",
    "mlops": "MLOps & Deployment",
    "software_engineering": "Software Engineering",
}


TECHNICAL_QUESTIONS: dict[str, tuple[str, ...]] = {
    "machine_learning": (
        "How do you detect and address overfitting in a model?",
        "When would you prefer gradient boosting (XGBoost) over a neural network?",
        "Explain precision, recall, and F1, and when you optimize for each.",
        "How do you handle class imbalance in a training set?",
        "What does cross-validation give you that a single train/test split does not?",
    ),
    "computer_vision": (
        "Walk through the stages of an object-detection pipeline end to end.",
        "How does non-maximum suppression work and why is it needed?",
        "What preprocessing steps improve OCR accuracy on noisy images?",
        "How would you evaluate a detection model (mAP, IoU)?",
        "How do you deal with class imbalance or small objects in detection?",
    ),
    "data_science": (
        "How do you approach feature engineering for a new tabular dataset?",
        "How do you decide which features matter (e.g., SHAP, permutation importance)?",
        "How do you detect and handle data leakage?",
        "Explain the bias-variance trade-off with an example.",
        "How would you validate that a data pipeline's output is correct?",
    ),
    "backend": (
        "How would you design a REST API for this system? What endpoints and status codes?",
        "How do you keep an API responsive under load (caching, pagination, async)?",
        "How do you design a database schema and decide on indexes?",
        "How do you handle input validation and error responses?",
        "Where would you add logging and monitoring in a service?",
    ),
    "mlops": (
        "How do you containerize and deploy a model behind an API?",
        "How do you monitor a deployed model for drift or degradation?",
        "Walk through a CI/CD flow for shipping a model update safely.",
        "How do you make model inference reproducible across environments?",
        "How do you roll back a bad deployment?",
    ),
    "software_engineering": (
        "How do you decide when to refactor versus rewrite?",
        "Describe your approach to writing testable code.",
        "How do you reason about time and space complexity of a solution?",
        "How do you use Git in a team (branches, reviews, resolving conflicts)?",
        "How do you debug a problem you cannot immediately reproduce?",
    ),
}


CODING_TOPICS: dict[str, tuple[str, ...]] = {
    "machine_learning": (
        "Implement k-fold cross-validation from scratch.",
        "Compute precision/recall/F1 from raw predictions and labels.",
    ),
    "computer_vision": (
        "Implement Intersection-over-Union (IoU) for two bounding boxes.",
        "Implement non-maximum suppression given boxes and scores.",
    ),
    "data_science": (
        "Group and aggregate records with pandas (or plain Python) to a summary table.",
        "Detect and impute missing values in a dataset.",
    ),
    "backend": (
        "Design and sketch a small REST endpoint with validation and error handling.",
        "Rate-limit requests per user with a sliding window.",
    ),
    "mlops": (
        "Write a Dockerfile that serves a model inference endpoint.",
        "Parse a stream of request logs and compute rolling latency percentiles.",
    ),
    "software_engineering": (
        "Two-pointer / sliding-window array problem (e.g., longest substring).",
        "Graph traversal: BFS/DFS on an adjacency list.",
        "Hash-map counting problem (e.g., group anagrams, top-k frequent).",
    ),
}


BEHAVIORAL_QUESTIONS = (
    "Tell me about a project you are proud of and your specific contribution.",
    "Describe a time something you built did not work as expected. What did you do?",
    "Tell me about a time you had to learn a new technology quickly.",
    "Describe a disagreement on a team and how it was resolved.",
    "How do you prioritize when you have more work than time?",
)


QUESTIONS_TO_ASK = (
    "What would my first project as an intern look like?",
    "How is success for this role measured in the first three months?",
    "What does the team's development and review workflow look like?",
    "What are the biggest technical challenges the team is facing right now?",
    "What opportunities are there to convert to a full-time role after the internship?",
)


RESEARCH_CHECKLIST = (
    "Read the company's product page and note what they actually build.",
    "Find their engineering blog or GitHub and skim recent posts/repos.",
    "Identify 2-3 competitors and how this company differentiates.",
    "Re-read the full job description and list every named tool or responsibility.",
    "Prepare a one-line reason this specific company interests you.",
)


class InterviewPrepGenerator:
    def __init__(self, profile: CandidateProfile, output_dir: Path):
        self.profile = profile
        self.output_dir = output_dir

    def generate(self, job: JobPosting, match: MatchResult) -> Path:
        packet_dir = self.output_dir / f"{job.id}-{_slug(job.company)}-{_slug(job.title)}"
        packet_dir.mkdir(parents=True, exist_ok=True)
        path = packet_dir / "INTERVIEW.md"
        path.write_text(self._render(job, match), encoding="utf-8")
        return path

    def _render(self, job: JobPosting, match: MatchResult) -> str:
        concepts = detected_concepts(f"{job.title} {job.description}")
        # Deterministic ordering by the taxonomy, not set iteration order.
        ordered = [key for key in CONCEPT_LABELS if key in concepts]

        strengths = "\n".join(f"- {skill}" for skill in match.matched_skills) or "- (none detected)"
        evidence = "\n".join(f"- {item}" for item in self.profile.evidence)
        areas = ", ".join(CONCEPT_LABELS[key] for key in ordered) or "General software engineering"

        technical = self._section_by_concept(ordered, TECHNICAL_QUESTIONS, fallback="software_engineering")
        coding = self._section_by_concept(ordered, CODING_TOPICS, fallback="software_engineering")

        gaps = "\n".join(
            f"- Be ready to discuss your exposure to **{signal}** (named in the posting, not yet on your resume)."
            for signal in match.missing_signals
        ) or "- No unmatched requirements detected in the posting."

        behavioral = "\n".join(f"- {question}" for question in BEHAVIORAL_QUESTIONS)
        ask = "\n".join(f"- {question}" for question in QUESTIONS_TO_ASK)
        research = "\n".join(f"- [ ] {item}" for item in RESEARCH_CHECKLIST)

        return f"""# Interview prep: {job.title} - {job.company}

> Grounded in the job posting and your verified evidence. Company-specific facts
> are left as a research checklist for you to complete; nothing here is invented.

## Role snapshot

- Company: {job.company}
- Location: {job.location}
- Match score: {match.score}%
- Concept areas in this posting: {areas}
- Job page: {job.url}

## Your strengths to lead with

{strengths}

Anchor answers to this verified evidence (use as STAR stories):

{evidence}

## Likely technical questions

{technical}

## Coding practice topics

{coding}

## Behavioral questions

{behavioral}

## Gaps to prepare

{gaps}

## Questions to ask them

{ask}

## Company research checklist

{research}
"""

    @staticmethod
    def _section_by_concept(
        ordered: list[str], bank: dict[str, tuple[str, ...]], fallback: str
    ) -> str:
        keys = ordered or [fallback]
        lines: list[str] = []
        for key in keys:
            questions = bank.get(key)
            if not questions:
                continue
            lines.append(f"**{CONCEPT_LABELS[key]}**")
            lines.extend(f"- {question}" for question in questions)
            lines.append("")
        return "\n".join(lines).strip() or "- (no concept-specific prompts)"
