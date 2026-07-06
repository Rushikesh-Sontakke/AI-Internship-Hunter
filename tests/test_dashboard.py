import tempfile
import unittest
from pathlib import Path

from ai_internship_hunter.dashboard import render_dashboard, render_job
from ai_internship_hunter.models import JobPosting, MatchResult
from ai_internship_hunter.repository import Repository


class DashboardTests(unittest.TestCase):
    def test_dashboard_renders_qualified_job_and_escapes_content(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Repository(Path(directory) / "hunter.db")
            repository.initialize()
            job_id = repository.upsert_job(JobPosting(
                source="test", external_id="1", title="ML <Intern>", company="Example",
                location="Taipei", description="Python & ML", url="https://example.test/1",
                language="English", is_paid=True,
            ))
            repository.save_match(MatchResult(
                job_id=job_id, score=88, qualified=True, matched_skills=("Python",),
                missing_signals=(), reasons=("Strong fit",),
            ))
            dashboard = render_dashboard(repository)
            detail = render_job(repository, job_id)
            self.assertIn("88%", dashboard)
            self.assertIn("ML &lt;Intern&gt;", dashboard)
            self.assertNotIn("ML <Intern>", dashboard)
            self.assertIn("Python &amp; ML", detail)


if __name__ == "__main__":
    unittest.main()

