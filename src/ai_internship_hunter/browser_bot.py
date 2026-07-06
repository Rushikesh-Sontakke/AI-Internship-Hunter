"""Browser-assisted application filling that always stops before submission.

The driver opens a job's public application page in a *visible* browser, fills the
fields it can confidently identify on Greenhouse- and Lever-hosted forms, uploads
the tailored resume, and pastes the cover-letter draft. It then scrolls to the
submit button, highlights it, and hands control back to the human. It never clicks
submit and never logs into an account.

The field-planning core (`ApplicantProfile`, `build_field_plan`) is pure and unit
tested. Playwright is imported lazily inside the driver so the rest of the package
and its tests do not depend on it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


@dataclass(frozen=True)
class ApplicantProfile:
    """Contact details used to fill application forms, drawn from local config."""

    first_name: str
    last_name: str
    email: str
    phone: str
    location: str
    github: str
    linkedin: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @classmethod
    def load(cls, candidate_path: Path, resume_path: Path) -> "ApplicantProfile":
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        resume = json.loads(resume_path.read_text(encoding="utf-8"))
        name = str(candidate.get("name") or resume.get("name") or "").strip()
        first, _, last = name.partition(" ")
        return cls(
            first_name=first,
            last_name=last,
            email=str(candidate.get("email") or resume.get("email") or ""),
            phone=str(candidate.get("phone") or resume.get("phone") or ""),
            location=str(candidate.get("location") or resume.get("location") or ""),
            github=str(resume.get("github") or ""),
            linkedin=str(resume.get("linkedin") or ""),
        )


@dataclass(frozen=True)
class FieldTarget:
    """One logical form field: the value plus resilient ways to locate it.

    `selectors` are CSS selectors tried in order (covers Greenhouse and Lever).
    `label_keywords` drive a fallback that finds an input associated with a label
    containing one of the keywords, for ATS custom questions with unstable ids.
    `kind` is "text", "textarea", or "file".
    """

    name: str
    value: str
    selectors: tuple[str, ...]
    label_keywords: tuple[str, ...] = ()
    kind: str = "text"


def build_field_plan(
    profile: ApplicantProfile, resume_pdf: Path, cover_letter: str
) -> list[FieldTarget]:
    """Build the ordered fill plan. Pure: no browser, no I/O. Unit tested.

    Only fields with a non-empty value are included, so a form that lacks a given
    field simply has nothing to fill for it.
    """

    candidates = [
        FieldTarget(
            name="first_name",
            value=profile.first_name,
            selectors=(
                "#first_name",
                'input[name="first_name"]',
                'input[autocomplete="given-name"]',
            ),
            label_keywords=("first name",),
        ),
        FieldTarget(
            name="last_name",
            value=profile.last_name,
            selectors=(
                "#last_name",
                'input[name="last_name"]',
                'input[autocomplete="family-name"]',
            ),
            label_keywords=("last name", "surname", "family name"),
        ),
        FieldTarget(
            name="full_name",
            value=profile.full_name,
            selectors=('input[name="name"]', "#name", 'input[autocomplete="name"]'),
            label_keywords=("full name",),
        ),
        FieldTarget(
            name="email",
            value=profile.email,
            selectors=(
                "#email",
                'input[name="email"]',
                'input[type="email"]',
                'input[autocomplete="email"]',
            ),
            label_keywords=("email",),
        ),
        FieldTarget(
            name="phone",
            value=profile.phone,
            selectors=(
                "#phone",
                'input[name="phone"]',
                'input[type="tel"]',
                'input[autocomplete="tel"]',
            ),
            label_keywords=("phone", "mobile"),
        ),
        FieldTarget(
            name="location",
            value=profile.location,
            selectors=('input[name="location"]', "#location", 'input[autocomplete="address-level2"]'),
            label_keywords=("location", "city"),
        ),
        FieldTarget(
            name="linkedin",
            value=profile.linkedin,
            selectors=('input[name="urls[LinkedIn]"]', "#linkedin"),
            label_keywords=("linkedin",),
        ),
        FieldTarget(
            name="github",
            value=profile.github,
            selectors=('input[name="urls[GitHub]"]', "#github"),
            label_keywords=("github",),
        ),
        FieldTarget(
            name="resume",
            value=str(resume_pdf),
            selectors=(
                'input[type="file"][name="resume"]',
                "#resume",
                'input[type="file"]',
            ),
            label_keywords=("resume", "cv"),
            kind="file",
        ),
        FieldTarget(
            name="cover_letter",
            value=cover_letter,
            selectors=(
                'textarea[name="comments"]',
                "#cover_letter_text",
                "textarea",
            ),
            label_keywords=("cover letter", "additional information", "comments"),
            kind="textarea",
        ),
    ]
    return [target for target in candidates if target.value.strip()]


def packet_dir_for(output_dir: Path, job_id: int, company: str, title: str) -> Path:
    """Locate the review-packet directory produced by `build-resume`/`prepare`."""

    return output_dir / f"{job_id}-{_slug(company)}-{_slug(title)}"


def extract_cover_letter(review_markdown: str) -> str:
    """Pull the drafted cover letter out of a generated REVIEW.md."""

    match = re.search(
        r"## Cover-letter draft\s*(.*?)\s*## Final review checklist",
        review_markdown,
        flags=re.S,
    )
    return match.group(1).strip() if match else ""


# The submit controls we deliberately locate only to *highlight and avoid*.
SUBMIT_SELECTORS = (
    'button[type="submit"]',
    'input[type="submit"]',
    "button#submit_app",
    'button:has-text("Submit Application")',
    'button:has-text("Submit application")',
    'button:has-text("Submit")',
)


@dataclass
class ApplicationAssistant:
    """Drives a visible browser to fill a form, then stops at the submit step.

    This class never clicks a submit control. It is intentionally kept thin so the
    filling logic in `build_field_plan` can be verified without a browser.
    """

    headless: bool = False
    filled: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def apply(self, url: str, plan: list[FieldTarget]) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "Playwright is not installed. Run:\n"
                '  pip install -e ".[browser]"\n'
                "  playwright install chromium"
            ) from error

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded")
            for target in plan:
                if self._fill_target(page, target):
                    self.filled.append(target.name)
                else:
                    self.skipped.append(target.name)
            self._highlight_submit_without_clicking(page)
            print(f"Filled: {', '.join(self.filled) or 'nothing'}")
            print(f"Not found on this form: {', '.join(self.skipped) or 'none'}")
            print(
                "\nReview every field in the browser, then click Submit yourself.\n"
                "This tool never submits."
            )
            input("Press Enter here to close the browser once you are done... ")
            browser.close()

    def _fill_target(self, page, target: FieldTarget) -> bool:  # pragma: no cover - browser
        locator = self._first_visible(page, target)
        if locator is None:
            return False
        if target.kind == "file":
            locator.set_input_files(target.value)
        else:
            locator.fill(target.value)
        return True

    def _first_visible(self, page, target: FieldTarget):  # pragma: no cover - browser
        for selector in target.selectors:
            locator = page.locator(selector).first
            try:
                if locator.count() and locator.is_visible():
                    return locator
            except Exception:
                continue
        for keyword in target.label_keywords:
            locator = page.get_by_label(re.compile(keyword, re.I)).first
            try:
                if locator.count() and locator.is_visible():
                    return locator
            except Exception:
                continue
        return None

    def _highlight_submit_without_clicking(self, page) -> None:  # pragma: no cover - browser
        for selector in SUBMIT_SELECTORS:
            locator = page.locator(selector).first
            try:
                if locator.count():
                    locator.scroll_into_view_if_needed()
                    locator.evaluate(
                        "el => { el.style.outline = '3px solid #d33'; "
                        "el.style.outlineOffset = '2px'; }"
                    )
                    return
            except Exception:
                continue
