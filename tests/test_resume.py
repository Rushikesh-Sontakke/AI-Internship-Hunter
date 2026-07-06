import tempfile
import unittest
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from ai_internship_hunter.models import JobPosting, MatchResult
from ai_internship_hunter.resume import ResumeSource, ResumeTailor
from ai_internship_hunter.resume_documents import ResumeDocumentGenerator


ROOT = Path(__file__).resolve().parents[1]


class ResumeTests(unittest.TestCase):
    def test_tailoring_reorders_verified_evidence_and_generates_documents(self):
        source = ResumeSource.load(ROOT / "config" / "resume.json")
        job = JobPosting(
            id=7, source="test", external_id="7", title="Backend Software Engineer Intern",
            company="Example", location="Taipei", language="English", is_paid=True,
            description="Python Flask Docker SQL backend APIs", url="https://example.test/7",
        )
        match = MatchResult(
            job_id=7, score=90, qualified=True,
            matched_skills=("Python", "Flask", "Docker", "SQL"),
            missing_signals=(), reasons=("Strong match",),
        )
        tailored = ResumeTailor(source).tailor(job, match)
        self.assertEqual(tailored.projects[0].title, "Deep Learning Pill Recognition System")
        self.assertIn("Flask", tailored.summary)

        with tempfile.TemporaryDirectory() as directory:
            docx_path, pdf_path = ResumeDocumentGenerator(Path(directory)).generate(tailored, 7)
            self.assertGreater(docx_path.stat().st_size, 1000)
            self.assertGreater(pdf_path.stat().st_size, 1000)
            self.assertEqual(len(PdfReader(pdf_path).pages), 1)
            text = "\n".join(p.text for p in Document(docx_path).paragraphs)
            self.assertIn(source.name, text)
            self.assertIn("Deep Learning Pill Recognition System", text)


if __name__ == "__main__":
    unittest.main()

