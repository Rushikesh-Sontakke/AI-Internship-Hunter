"""Read a user's public GitHub repositories and suggest resume updates.

The analyzer is grounded and non-fabricating: it reports repository *metadata*
(name, language, topics, description, timestamps) and derives structural
suggestions from it. Draft resume bullets are explicit templates with a
placeholder for impact — it never invents a metric or an achievement.

The core (`parse_repos`, `analyze`, `render_report`) is pure and unit tested.
HTTP access reuses the injectable `JsonHttpClient` from `providers.py`, so tests
run with a fake client and no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

from .providers import JsonHttpClient, UrllibJsonClient
from .resume import ResumeSource


def _tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.casefold()) if len(token) >= 2}


def _skill_keys(skills: tuple[str, ...]) -> set[str]:
    """Normalized skill set, expanding compound skills like ``C/C++``."""

    keys: set[str] = set()
    for skill in skills:
        casefolded = skill.casefold().strip()
        keys.add(casefolded)
        for part in re.split(r"[/,]", casefolded):
            part = part.strip()
            if part:
                keys.add(part)
    return keys


@dataclass(frozen=True)
class Repo:
    name: str
    description: str
    language: str
    topics: tuple[str, ...]
    stars: int
    fork: bool
    archived: bool
    html_url: str
    homepage: str
    pushed_at: str


def username_from_url(url: str) -> str:
    """Extract a GitHub username from a profile URL or return the input unchanged."""

    match = re.search(r"github\.com/([^/?#]+)", url.strip(), flags=re.I)
    return match.group(1) if match else url.strip().strip("/")


def parse_repos(payload: object) -> list[Repo]:
    if not isinstance(payload, list):
        raise ValueError("GitHub repos response must be a JSON array")
    repos: list[Repo] = []
    for item in payload:
        repos.append(
            Repo(
                name=str(item.get("name", "")),
                description=str(item.get("description") or ""),
                language=str(item.get("language") or ""),
                topics=tuple(item.get("topics") or ()),
                stars=int(item.get("stargazers_count") or 0),
                fork=bool(item.get("fork")),
                archived=bool(item.get("archived")),
                html_url=str(item.get("html_url") or ""),
                homepage=str(item.get("homepage") or ""),
                pushed_at=str(item.get("pushed_at") or ""),
            )
        )
    return repos


def fetch_repos(username: str, client: JsonHttpClient | None = None) -> list[Repo]:
    client = client or UrllibJsonClient()
    user = quote(username, safe="")
    payload = client.get_json(
        f"https://api.github.com/users/{user}/repos?per_page=100&sort=pushed"
    )
    return parse_repos(payload)


@dataclass(frozen=True)
class RepoFinding:
    repo: Repo
    on_resume: bool
    issues: tuple[str, ...]
    draft_bullet: str | None


@dataclass(frozen=True)
class AnalysisReport:
    username: str
    new_projects: tuple[RepoFinding, ...]
    hygiene: tuple[RepoFinding, ...]
    skill_signals: tuple[str, ...]


def _is_on_resume(repo: Repo, source: ResumeSource) -> bool:
    urls = {
        url.casefold()
        for project in source.projects
        for url in project.links.values()
    }
    if repo.html_url and repo.html_url.casefold() in urls:
        return True
    name_tokens = _tokens(repo.name)
    if not name_tokens:
        return False
    for project in source.projects:
        if name_tokens & _tokens(project.title):
            return True
    return False


def _issues_for(repo: Repo) -> tuple[str, ...]:
    issues: list[str] = []
    if not repo.description.strip():
        issues.append("No description set — add a one-line summary on GitHub.")
    if not repo.topics:
        issues.append("No topics/tags — add them on GitHub for discoverability.")
    return tuple(issues)


def _draft_bullet(repo: Repo) -> str:
    language = f" using {repo.language}" if repo.language else ""
    topics = f" ({', '.join(repo.topics)})" if repo.topics else ""
    seed = repo.description.strip()
    seed_part = f" {seed}" if seed else ""
    return (
        f"Built {repo.name}{language}{topics}:{seed_part} "
        "<add one concrete impact or metric>. "
        f"Code: {repo.html_url}"
    )


def analyze(
    repos: list[Repo],
    source: ResumeSource,
    known_skills: tuple[str, ...],
    *,
    include_forks: bool = False,
) -> AnalysisReport:
    username = username_from_url(source.github) if source.github else ""
    considered = [
        repo
        for repo in repos
        if not repo.archived and (include_forks or not repo.fork)
    ]
    considered.sort(key=lambda repo: repo.pushed_at, reverse=True)

    new_projects: list[RepoFinding] = []
    hygiene: list[RepoFinding] = []
    skill_keys = _skill_keys(known_skills)
    signals: dict[str, None] = {}  # ordered de-dup

    for repo in considered:
        on_resume = _is_on_resume(repo, source)
        issues = _issues_for(repo)
        if not on_resume:
            new_projects.append(
                RepoFinding(repo=repo, on_resume=False, issues=issues, draft_bullet=_draft_bullet(repo))
            )
        elif issues:
            hygiene.append(RepoFinding(repo=repo, on_resume=True, issues=issues, draft_bullet=None))

        for candidate in (repo.language, *repo.topics):
            candidate = candidate.strip()
            if candidate and candidate.casefold() not in skill_keys:
                signals.setdefault(candidate, None)

    return AnalysisReport(
        username=username,
        new_projects=tuple(new_projects),
        hygiene=tuple(hygiene),
        skill_signals=tuple(signals),
    )


def render_report(report: AnalysisReport) -> str:
    lines: list[str] = [
        f"# GitHub review: {report.username or 'unknown user'}",
        "",
        "> Grounded in your public repository metadata. Draft bullets are templates "
        "with a placeholder for impact — fill in real numbers; nothing is invented.",
        "",
        "## New projects not on your resume",
        "",
    ]
    if report.new_projects:
        for finding in report.new_projects:
            repo = finding.repo
            meta = " · ".join(
                part for part in (
                    repo.language or "",
                    f"{repo.stars}★" if repo.stars else "",
                    f"pushed {repo.pushed_at[:10]}" if repo.pushed_at else "",
                ) if part
            )
            lines.append(f"### {repo.name}")
            if meta:
                lines.append(f"_{meta}_")
            lines.append("")
            lines.append(f"- Suggested resume bullet: {finding.draft_bullet}")
            for issue in finding.issues:
                lines.append(f"- Hygiene: {issue}")
            lines.append("")
    else:
        lines.append("- Every source repository is already represented on your resume.")
        lines.append("")

    lines.append("## Description hygiene for repos already on your resume")
    lines.append("")
    if report.hygiene:
        for finding in report.hygiene:
            lines.append(f"- **{finding.repo.name}**")
            for issue in finding.issues:
                lines.append(f"  - {issue}")
    else:
        lines.append("- No description/topic gaps found on tracked repositories.")
    lines.append("")

    lines.append("## Skill signals from your repos")
    lines.append("")
    if report.skill_signals:
        lines.append(
            "These languages/topics appear in your repositories but are not on your "
            "skills list — consider adding the ones you can defend:"
        )
        lines.append("")
        for signal in report.skill_signals:
            lines.append(f"- {signal}")
    else:
        lines.append("- Your repositories introduce no skills beyond those already listed.")
    lines.append("")
    return "\n".join(lines)
