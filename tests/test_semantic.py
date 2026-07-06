import unittest

from ai_internship_hunter.config import CandidateProfile
from ai_internship_hunter.semantic import HybridConceptSimilarity


class SemanticTests(unittest.TestCase):
    def test_related_concepts_score_above_unrelated_role(self):
        profile = CandidateProfile(
            name="Candidate", email="x@example.com", phone="1", location="Taipei",
            graduation="January 2027", work_authorized_in_taiwan=True,
            summary="Machine learning and computer vision student",
            skills=("Python", "PyTorch", "YOLOv8", "OpenCV", "Docker"),
            role_interests=("computer vision engineer",),
            evidence=("Deployed an object detection pipeline.",),
        )
        engine = HybridConceptSimilarity(profile)
        related = engine.similarity("Image processing and visual recognition model internship")
        unrelated = engine.similarity("Brand illustration and typography marketing role")
        self.assertGreater(related, unrelated)
        self.assertGreater(related, 0.5)


if __name__ == "__main__":
    unittest.main()

