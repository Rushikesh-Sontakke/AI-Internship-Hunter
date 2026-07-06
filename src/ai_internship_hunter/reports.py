from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import JobPosting, MatchResult


def write_top_matches(
    ranked: list[tuple[JobPosting, MatchResult]], output: Path
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    lines = [
        "# Top internship matches",
        "",
        f"Generated: {timestamp}",
        "",
        "Only roles meeting the configured score threshold are listed.",
        "",
    ]
    if not ranked:
        lines.append("No roles currently meet the configured threshold.")
    for index, (job, result) in enumerate(ranked, start=1):
        paid = "confirmed" if job.is_paid is True else "not stated - verify before applying"
        skills = ", ".join(result.matched_skills) or "No explicit skills detected"
        lines.extend(
            [
                f"## {index}. {job.title} - {job.company}",
                "",
                f"- Score: **{result.score}%**",
                f"- Location: {job.location}",
                f"- Paid: {paid}",
                f"- Source: {job.source}",
                f"- Matched evidence: {skills}",
                f"- Job page: {job.url}",
                "",
            ]
        )
    output.write_text("\n".join(lines), encoding="utf-8")
    return output
