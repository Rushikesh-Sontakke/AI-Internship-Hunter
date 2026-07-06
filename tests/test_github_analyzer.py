from ai_internship_hunter.github_analyzer import (
    Repo,
    analyze,
    fetch_repos,
    parse_repos,
    render_report,
    username_from_url,
)
from ai_internship_hunter.resume import Project, ResumeSource


def _source() -> ResumeSource:
    # Minimal ResumeSource with only the fields the analyzer reads (projects + github).
    return ResumeSource(
        name="Rushikesh Sontakke",
        email="me@example.com",
        phone="+886",
        location="Hsinchu",
        github="https://github.com/Rushikesh-Sontakke",
        linkedin="",
        base_summary="",
        education=None,
        skill_groups=(),
        projects=(
            Project(
                title="Deep Learning Pill Recognition System",
                dates="",
                skills=("Python",),
                links={"Code": "https://github.com/Rushikesh-Sontakke/Pill_Identification_Deep_Learning"},
                bullets=(),
            ),
        ),
        experience=(),
    )


def _repo(name, **kw) -> Repo:
    base = dict(
        description="", language="", topics=(), stars=0, fork=False,
        archived=False, html_url=f"https://github.com/Rushikesh-Sontakke/{name}",
        homepage="", pushed_at="2026-01-01T00:00:00Z",
    )
    base.update(kw)
    return Repo(name=name, **base)


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.url = None

    def get_json(self, url):
        self.url = url
        return self.payload


def test_username_from_url_variants():
    assert username_from_url("https://github.com/Rushikesh-Sontakke") == "Rushikesh-Sontakke"
    assert username_from_url("https://github.com/foo/bar") == "foo"
    assert username_from_url("plainname") == "plainname"


def test_parse_repos_handles_missing_and_null_fields():
    repos = parse_repos([
        {"name": "a", "description": None, "language": None, "topics": None},
        {"name": "b", "stargazers_count": 5, "fork": True, "topics": ["cv", "ml"]},
    ])
    assert repos[0].description == "" and repos[0].language == ""
    assert repos[0].topics == ()
    assert repos[1].stars == 5 and repos[1].fork is True
    assert repos[1].topics == ("cv", "ml")


def test_fetch_repos_builds_correct_url_and_parses():
    client = FakeClient([{"name": "x"}])
    repos = fetch_repos("Rushikesh-Sontakke", client=client)
    assert client.url == "https://api.github.com/users/Rushikesh-Sontakke/repos?per_page=100&sort=pushed"
    assert repos[0].name == "x"


def test_repo_on_resume_by_url_is_not_flagged_new():
    repos = [_repo("Pill_Identification_Deep_Learning", language="Python")]
    report = analyze(repos, _source(), ("Python",))
    assert report.new_projects == ()


def test_new_repo_gets_draft_bullet_and_hygiene_flags():
    repos = [_repo("edge-inference-benchmark", language="Go")]  # no description, no topics
    report = analyze(repos, _source(), ("Python",))
    assert len(report.new_projects) == 1
    finding = report.new_projects[0]
    assert "edge-inference-benchmark" in finding.draft_bullet
    assert "<add one concrete impact or metric>" in finding.draft_bullet  # never invents
    assert any("description" in issue.lower() for issue in finding.issues)
    assert any("topics" in issue.lower() for issue in finding.issues)


def test_forks_and_archived_excluded_by_default():
    repos = [
        _repo("forked-thing", fork=True),
        _repo("archived-thing", archived=True),
        _repo("real-thing"),
    ]
    report = analyze(repos, _source(), ("Python",))
    names = {finding.repo.name for finding in report.new_projects}
    assert names == {"real-thing"}


def test_skill_signals_exclude_known_and_expand_compounds():
    repos = [_repo("svc", language="Go", topics=("kubernetes", "c++"))]
    # Known skills include C/C++ -> "c++" must NOT appear as a gap; Go and kubernetes should.
    report = analyze(repos, _source(), ("Python", "C/C++"))
    assert "Go" in report.skill_signals
    assert "kubernetes" in report.skill_signals
    assert "c++" not in [s.casefold() for s in report.skill_signals]


def test_new_projects_sorted_by_pushed_desc():
    repos = [
        _repo("older", pushed_at="2025-01-01T00:00:00Z"),
        _repo("newer", pushed_at="2026-06-01T00:00:00Z"),
    ]
    report = analyze(repos, _source(), ())
    assert [f.repo.name for f in report.new_projects] == ["newer", "older"]


def test_render_report_contains_sections():
    repos = [_repo("newthing", language="Rust")]
    text = render_report(analyze(repos, _source(), ("Python",)))
    assert "# GitHub review: Rushikesh-Sontakke" in text
    assert "New projects not on your resume" in text
    assert "Skill signals" in text
    assert "newthing" in text
