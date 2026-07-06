from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import JobPosting


class JobProvider(Protocol):
    name: str

    def discover(self) -> list[JobPosting]: ...


class JsonHttpClient(Protocol):
    def get_json(self, url: str) -> Any: ...


class UrllibJsonClient:
    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    def get_json(self, url: str) -> Any:
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "AI-Internship-Hunter/0.2"},
        )
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(unescape(value or ""))
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def detect_language(text: str) -> str:
    english_words = re.findall(r"\b[a-zA-Z]{3,}\b", text)
    return "English" if len(english_words) >= 20 else "Unknown"


def detect_paid(text: str) -> bool | None:
    normalized = text.casefold()
    paid_patterns = (
        r"\bpaid internship\b", r"\bcompensation\b", r"\bsalary\b",
        r"nt\$\s*\d", r"ntd\s*\$?\s*\d", r"\$\s*\d+\s*(?:an|per)\s+hour",
    )
    unpaid_patterns = (r"\bunpaid\b", r"without compensation")
    if any(re.search(pattern, normalized) for pattern in unpaid_patterns):
        return False
    if any(re.search(pattern, normalized) for pattern in paid_patterns):
        return True
    return None


class JsonFileProvider:
    """Imports authorized exports or manually collected job descriptions."""

    name = "json-file"

    def __init__(self, path: Path):
        self.path = path

    def discover(self) -> list[JobPosting]:
        records = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("Job import must be a JSON array")
        return [JobPosting(**record) for record in records]


class GreenhouseProvider:
    def __init__(
        self, board_token: str, company: str, client: JsonHttpClient | None = None
    ):
        self.board_token = board_token
        self.company = company
        self.client = client or UrllibJsonClient()
        self.name = f"greenhouse:{board_token}"

    def discover(self) -> list[JobPosting]:
        token = quote(self.board_token, safe="")
        payload = self.client.get_json(
            f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        )
        jobs: list[JobPosting] = []
        for item in payload.get("jobs", []):
            description = html_to_text(item.get("content", ""))
            jobs.append(
                JobPosting(
                    source=self.name,
                    external_id=str(item["id"]),
                    title=item.get("title", "Untitled role"),
                    company=self.company,
                    location=item.get("location", {}).get("name", "Unknown"),
                    description=description,
                    url=item.get("absolute_url", ""),
                    language=detect_language(description),
                    is_paid=detect_paid(description),
                )
            )
        return jobs


class LeverProvider:
    def __init__(self, site: str, company: str, client: JsonHttpClient | None = None):
        self.site = site
        self.company = company
        self.client = client or UrllibJsonClient()
        self.name = f"lever:{site}"

    def discover(self) -> list[JobPosting]:
        site = quote(self.site, safe="")
        payload = self.client.get_json(
            f"https://api.lever.co/v0/postings/{site}?mode=json&limit=100"
        )
        jobs: list[JobPosting] = []
        for item in payload:
            description = " ".join(
                part for part in (
                    item.get("descriptionPlain", ""), item.get("additionalPlain", ""),
                ) if part
            )
            categories = item.get("categories", {})
            commitment = categories.get("commitment", "")
            if commitment:
                description = f"{commitment}. {description}"
            jobs.append(
                JobPosting(
                    source=self.name,
                    external_id=str(item["id"]),
                    title=item.get("text", "Untitled role"),
                    company=self.company,
                    location=categories.get("location", "Unknown"),
                    description=re.sub(r"\s+", " ", description).strip(),
                    url=item.get("hostedUrl") or item.get("applyUrl", ""),
                    language=detect_language(description),
                    is_paid=detect_paid(description),
                )
            )
        return jobs


def load_configured_providers(
    path: Path, client: JsonHttpClient | None = None
) -> list[JobProvider]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    providers: list[JobProvider] = []
    for spec in payload.get("providers", []):
        if not spec.get("enabled", True):
            continue
        provider_type = spec.get("type")
        if provider_type == "greenhouse":
            providers.append(
                GreenhouseProvider(spec["board_token"], spec["company"], client=client)
            )
        elif provider_type == "lever":
            providers.append(LeverProvider(spec["site"], spec["company"], client=client))
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")
    return providers

