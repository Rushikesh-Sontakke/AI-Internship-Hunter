import unittest

from ai_internship_hunter.config import CandidateProfile, SearchPreferences
from ai_internship_hunter.matcher import JobMatcher
from ai_internship_hunter.models import JobPosting


def profile() -> CandidateProfile:
    return CandidateProfile(
        name="Candidate", email="candidate@example.com", phone="1", location="Hsinchu",
        graduation="January 2027", work_authorized_in_taiwan=True, summary="ML student",
        skills=("Python", "PyTorch", "YOLOv8", "OpenCV", "OpenOCR", "Flask", "Docker", "SQL"),
        role_interests=("computer vision engineer",), evidence=("Built a CV pipeline.",),
    )


def preferences() -> SearchPreferences:
    return SearchPreferences(
        languages=("English",), locations=("Hsinchu", "Taipei", "Remote"), paid_only=True,
        minimum_match_score=80, application_limit=None, human_review_required=True,
    )


class MatcherTests(unittest.TestCase):
    def test_strong_job_qualifies(self):
        job = JobPosting(
            id=1, source="test", external_id="1", title="Computer Vision Engineer Intern",
            company="Vision", location="Taipei", language="English", is_paid=True,
            description="Python PyTorch YOLO OpenCV OCR Flask Docker SQL internship",
            url="https://example.test/1",
        )
        result = JobMatcher(profile(), preferences()).score(job)
        self.assertGreaterEqual(result.score, 95)
        self.assertTrue(result.qualified)

    def test_unrelated_job_is_rejected(self):
        job = JobPosting(
            id=2, source="test", external_id="2", title="Graphic Design Intern",
            company="Design", location="Kaohsiung", language="Chinese", is_paid=False,
            description="Figma illustration typography", url="https://example.test/2",
        )
        result = JobMatcher(profile(), preferences()).score(job)
        self.assertLess(result.score, 80)
        self.assertFalse(result.qualified)

    def test_high_scoring_senior_role_is_not_an_internship_match(self):
        job = JobPosting(
            id=3, source="test", external_id="3", title="Senior Computer Vision Engineer",
            company="Vision", location="Taipei", language="English", is_paid=True,
            description="Python PyTorch YOLO OpenCV OCR Flask Docker SQL",
            url="https://example.test/3",
        )
        result = JobMatcher(profile(), preferences()).score(job)
        self.assertGreaterEqual(result.score, 80)
        self.assertFalse(result.qualified)


if __name__ == "__main__":
    unittest.main()
