import tempfile
import unittest
from pathlib import Path

from ai_internship_hunter.models import JobPosting, MatchResult
from ai_internship_hunter.repository import Repository


class RepositoryTests(unittest.TestCase):
    def test_upsert_deduplicates_source_job(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Repository(Path(directory) / "hunter.db")
            repository.initialize()
            job = JobPosting(
                source="test", external_id="abc", title="ML Intern", company="Example",
                location="Remote", description="Python", url="https://example.test/abc",
                language="English", is_paid=True,
            )
            first_id = repository.upsert_job(job)
            second_id = repository.upsert_job(job)
            self.assertEqual(first_id, second_id)
            self.assertEqual(len(repository.list_jobs()), 1)

            repository.save_match(MatchResult(
                job_id=first_id, score=88, qualified=True,
                matched_skills=("Python",), missing_signals=(), reasons=("Strong fit",),
            ))
            ranked = repository.list_ranked(limit=10)
            self.assertEqual(len(ranked), 1)
            self.assertEqual(ranked[0][1].score, 88)


if __name__ == "__main__":
    unittest.main()
