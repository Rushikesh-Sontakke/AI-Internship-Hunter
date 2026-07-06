import unittest

from ai_internship_hunter.providers import GreenhouseProvider, LeverProvider, detect_paid


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def get_json(self, url):
        self.urls.append(url)
        return self.payload


class ProviderTests(unittest.TestCase):
    def test_greenhouse_maps_public_job(self):
        client = FakeClient({"jobs": [{
            "id": 123,
            "title": "Machine Learning Intern",
            "absolute_url": "https://example.test/jobs/123",
            "location": {"name": "Taipei, Taiwan"},
            "content": "<p>Paid internship using Python and PyTorch for machine learning.</p> " * 8,
        }]})
        jobs = GreenhouseProvider("example", "Example", client).discover()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].external_id, "123")
        self.assertEqual(jobs[0].location, "Taipei, Taiwan")
        self.assertEqual(jobs[0].language, "English")
        self.assertTrue(jobs[0].is_paid)

    def test_lever_maps_public_job(self):
        client = FakeClient([{
            "id": "abc",
            "text": "AI Engineer Intern",
            "descriptionPlain": "Build machine learning systems with Python. " * 10,
            "additionalPlain": "Compensation is provided.",
            "categories": {"location": "Remote", "commitment": "Intern"},
            "hostedUrl": "https://jobs.lever.co/example/abc",
        }])
        jobs = LeverProvider("example", "Example", client).discover()
        self.assertEqual(jobs[0].title, "AI Engineer Intern")
        self.assertEqual(jobs[0].source, "lever:example")
        self.assertTrue(jobs[0].is_paid)

    def test_unpaid_takes_precedence(self):
        self.assertFalse(detect_paid("This is an unpaid internship without compensation."))


if __name__ == "__main__":
    unittest.main()

