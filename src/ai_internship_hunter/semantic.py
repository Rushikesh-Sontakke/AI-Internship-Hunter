from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol

from .config import CandidateProfile


TOKEN_RE = re.compile(r"[a-z0-9+#.]{2,}")
CONCEPTS = {
    "machine_learning": (
        "machine learning", "deep learning", "pytorch", "tensorflow", "scikit-learn",
        "xgboost", "model training", "neural network", "predictive modeling",
    ),
    "computer_vision": (
        "computer vision", "image processing", "object detection", "yolo", "opencv",
        "ocr", "optical character recognition", "cnn", "visual recognition",
    ),
    "data_science": (
        "data science", "data analysis", "pandas", "numpy", "sql", "statistics",
        "feature engineering", "model evaluation", "shap", "analytics",
    ),
    "backend": (
        "backend", "flask", "fastapi", "rest api", "api server", "microservice",
        "database", "mysql", "firebase",
    ),
    "mlops": (
        "mlops", "docker", "kubernetes", "deployment", "model monitoring", "mlflow",
        "kubeflow", "ci cd", "cloud", "inference pipeline",
    ),
    "software_engineering": (
        "python", "c++", "javascript", "typescript", "git", "data structures",
        "algorithms", "software engineering",
    ),
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def token_cosine(left: str, right: str) -> float:
    left_counts = Counter(TOKEN_RE.findall(normalize(left)))
    right_counts = Counter(TOKEN_RE.findall(normalize(right)))
    if not left_counts or not right_counts:
        return 0.0
    dot = sum(value * right_counts[token] for token, value in left_counts.items())
    left_norm = math.sqrt(sum(value * value for value in left_counts.values()))
    right_norm = math.sqrt(sum(value * value for value in right_counts.values()))
    return dot / (left_norm * right_norm)


def detected_concepts(text: str) -> set[str]:
    normalized = normalize(text)
    return {
        concept
        for concept, phrases in CONCEPTS.items()
        if any(phrase in normalized for phrase in phrases)
    }


class SimilarityEngine(Protocol):
    name: str

    def similarity(self, job_text: str) -> float: ...


class HybridConceptSimilarity:
    """Dependency-free semantic approximation using concepts plus lexical cosine."""

    name = "hybrid-concept"

    def __init__(self, profile: CandidateProfile):
        self.profile_text = " ".join(
            (profile.summary, *profile.skills, *profile.role_interests, *profile.evidence)
        )
        self.profile_concepts = detected_concepts(self.profile_text)

    def similarity(self, job_text: str) -> float:
        job_concepts = detected_concepts(job_text)
        if job_concepts:
            concept_coverage = len(job_concepts & self.profile_concepts) / len(job_concepts)
        else:
            concept_coverage = 0.0
        lexical = min(1.0, token_cosine(self.profile_text, job_text) * 3.0)
        return max(0.0, min(1.0, 0.75 * concept_coverage + 0.25 * lexical))


class SentenceTransformerSimilarity:
    """Optional local embedding engine; install the project's `semantic` extra."""

    name = "sentence-transformer"

    def __init__(self, profile: CandidateProfile, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                "Sentence Transformers is not installed. Run: pip install -e .[semantic]"
            ) from error
        self.model = SentenceTransformer(model_name)
        profile_text = " ".join(
            (profile.summary, *profile.skills, *profile.role_interests, *profile.evidence)
        )
        self.profile_vector = self.model.encode(profile_text, normalize_embeddings=True)

    def similarity(self, job_text: str) -> float:
        job_vector = self.model.encode(job_text, normalize_embeddings=True)
        score = float(self.profile_vector @ job_vector)
        return max(0.0, min(1.0, score))

