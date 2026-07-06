from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .browser_bot import (
    ApplicantProfile,
    ApplicationAssistant,
    build_field_plan,
    extract_cover_letter,
    packet_dir_for,
)
from .config import load_defaults, project_root
from .cover_letter import build_cover_letter
from .dashboard import serve_dashboard
from .github_analyzer import (
    analyze as analyze_github,
    fetch_repos,
    render_report,
    username_from_url,
)
from .interview_prep import InterviewPrepGenerator
from .matcher import JobMatcher
from .materials import ReviewPacketGenerator
from .providers import JsonFileProvider, load_configured_providers
from .reports import write_top_matches
from .repository import Repository
from .resume import ResumeSource, ResumeTailor
from .resume_documents import (
    ResumeDocumentGenerator,
    build_cover_letter_pdf,
    cover_letter_file_stem,
)
from .semantic import SentenceTransformerSimilarity


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="internship-hunter")
    parser.add_argument("--db", type=Path, default=Path("data/hunter.db"))
    parser.add_argument(
        "--embedding-model",
        help="Optional Sentence Transformers model; default uses dependency-free hybrid concepts",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create the local database")
    importer = commands.add_parser("import-jobs", help="Import an authorized JSON export")
    importer.add_argument("path", type=Path)
    commands.add_parser("score", help="Score every stored job")
    discover = commands.add_parser("discover", help="Fetch, score, and report public ATS jobs")
    discover.add_argument("--providers", type=Path, default=Path("config/providers.json"))
    discover.add_argument("--limit", type=int, default=10)
    discover.add_argument("--report", type=Path, default=Path("generated/top-10.md"))
    top = commands.add_parser("top", help="Write a report from the current ranking")
    top.add_argument("--limit", type=int, default=10)
    top.add_argument("--report", type=Path, default=Path("generated/top-10.md"))
    prepare = commands.add_parser("prepare", help="Create a human-review packet")
    prepare.add_argument("--job-id", type=int, required=True)
    prepare.add_argument("--output", type=Path, default=Path("generated"))
    build_resume = commands.add_parser(
        "build-resume", help="Generate tailored DOCX/PDF materials for a qualified job"
    )
    build_resume.add_argument("--job-id", type=int, required=True)
    build_resume.add_argument("--output", type=Path, default=Path("generated"))
    dashboard = commands.add_parser("dashboard", help="Start the local read-only review dashboard")
    dashboard.add_argument("--host", default="127.0.0.1")
    dashboard.add_argument("--port", type=int, default=8765)
    interview = commands.add_parser(
        "interview", help="Generate an interview-prep packet for a qualified job"
    )
    interview.add_argument("--job-id", type=int, required=True)
    interview.add_argument("--output", type=Path, default=Path("generated"))
    github = commands.add_parser(
        "github-review",
        help="Analyze public GitHub repos and suggest resume updates",
    )
    github.add_argument("--user", help="GitHub username (defaults to the resume profile)")
    github.add_argument("--output", type=Path, default=Path("generated/github-review.md"))
    github.add_argument("--include-forks", action="store_true", help="Include forked repos")
    apply = commands.add_parser(
        "apply",
        help="Open the application form in a browser, fill it, and stop at Submit",
    )
    apply.add_argument("--job-id", type=int, required=True)
    apply.add_argument("--output", type=Path, default=Path("generated"))
    apply.add_argument(
        "--headless",
        action="store_true",
        help="Run without a visible window (for testing only; you cannot click Submit)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    repository = Repository(args.db)
    repository.initialize()
    profile, preferences = load_defaults()
    similarity = (
        SentenceTransformerSimilarity(profile, args.embedding_model)
        if args.embedding_model
        else None
    )
    matcher = JobMatcher(profile, preferences, similarity=similarity)

    if args.command == "init":
        print(f"Initialized {args.db}")
        return 0
    if args.command == "import-jobs":
        jobs = JsonFileProvider(args.path).discover()
        for job in jobs:
            repository.upsert_job(job)
        print(f"Imported {len(jobs)} jobs")
        return 0
    if args.command == "score":
        for job in repository.list_jobs():
            result = matcher.score(job)
            repository.save_match(result)
        for job, result in repository.list_ranked(limit=10000, qualified_only=False):
            label = "QUALIFIED" if result.qualified else "skip"
            print(f"{job.id:>3}  {result.score:>3}%  {label:<9}  {job.company} - {job.title}")
        return 0
    if args.command == "discover":
        providers = load_configured_providers(args.providers)
        discovered = 0
        successful = 0
        for provider in providers:
            try:
                jobs = provider.discover()
            except Exception as error:
                print(f"Provider {provider.name} failed: {error}")
                continue
            successful += 1
            discovered += len(jobs)
            for job in jobs:
                repository.upsert_job(job)
            print(f"{provider.name}: {len(jobs)} jobs")
        if providers and successful == 0:
            raise SystemExit("All configured providers failed")
        for job in repository.list_jobs():
            repository.save_match(matcher.score(job))
        ranked = repository.list_ranked(limit=args.limit, qualified_only=True)
        report = write_top_matches(ranked, args.report)
        print(f"Discovered {discovered} jobs; {len(ranked)} qualified matches in {report}")
        return 0
    if args.command == "top":
        ranked = repository.list_ranked(limit=args.limit, qualified_only=True)
        report = write_top_matches(ranked, args.report)
        print(f"Wrote {len(ranked)} qualified matches to {report}")
        return 0
    if args.command == "prepare":
        job = repository.get_job(args.job_id)
        if job is None:
            raise SystemExit(f"Job {args.job_id} does not exist")
        result = matcher.score(job)
        repository.save_match(result)
        if not result.qualified:
            raise SystemExit(
                f"Job {job.id} scored {result.score}%; minimum is {preferences.minimum_match_score}%"
            )
        source = ResumeSource.load(project_root() / "config" / "resume.json")
        tailored = ResumeTailor(source).tailor(job, result)
        cover_text = build_cover_letter(tailored, job, result)
        packet = ReviewPacketGenerator(profile, args.output).generate(job, result, cover_text)
        repository.mark_ready_for_review(job.id, packet)
        print(f"Review packet: {packet}")
        return 0
    if args.command == "build-resume":
        job = repository.get_job(args.job_id)
        if job is None:
            raise SystemExit(f"Job {args.job_id} does not exist")
        result = matcher.score(job)
        repository.save_match(result)
        if not result.qualified:
            raise SystemExit(
                f"Job {job.id} scored {result.score}%; minimum is {preferences.minimum_match_score}%"
            )
        source = ResumeSource.load(project_root() / "config" / "resume.json")
        tailored = ResumeTailor(source).tailor(job, result)
        cover_text = build_cover_letter(tailored, job, result)
        packet = ReviewPacketGenerator(profile, args.output).generate(job, result, cover_text)
        docx_path, pdf_path = ResumeDocumentGenerator(args.output).generate(tailored, job.id)
        cover_pdf = pdf_path.parent / f"{cover_letter_file_stem(source.name)}.pdf"
        build_cover_letter_pdf(source, cover_text, cover_pdf)
        repository.mark_ready_for_review(job.id, packet)
        print(f"Review packet: {packet}")
        print(f"Tailored DOCX: {docx_path}")
        print(f"Tailored PDF: {pdf_path}")
        print(f"Cover letter PDF: {cover_pdf}")
        return 0
    if args.command == "dashboard":
        serve_dashboard(repository, host=args.host, port=args.port)
        return 0
    if args.command == "interview":
        job = repository.get_job(args.job_id)
        if job is None:
            raise SystemExit(f"Job {args.job_id} does not exist")
        result = matcher.score(job)
        repository.save_match(result)
        if not result.qualified:
            raise SystemExit(
                f"Job {job.id} scored {result.score}%; minimum is {preferences.minimum_match_score}%"
            )
        path = InterviewPrepGenerator(profile, args.output).generate(job, result)
        print(f"Interview prep: {path}")
        return 0
    if args.command == "github-review":
        source = ResumeSource.load(project_root() / "config" / "resume.json")
        username = args.user or username_from_url(source.github)
        if not username:
            raise SystemExit("No GitHub username provided and none found in resume.json")
        try:
            repos = fetch_repos(username)
        except Exception as error:
            raise SystemExit(f"Could not fetch repositories for {username}: {error}")
        report = analyze_github(
            repos, source, profile.skills, include_forks=args.include_forks
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_report(report), encoding="utf-8")
        print(
            f"Analyzed {len(repos)} repos for {username}: "
            f"{len(report.new_projects)} new project(s), "
            f"{len(report.hygiene)} hygiene note(s). Report: {args.output}"
        )
        return 0
    if args.command == "apply":
        job = repository.get_job(args.job_id)
        if job is None:
            raise SystemExit(f"Job {args.job_id} does not exist")
        if not job.url:
            raise SystemExit(f"Job {job.id} has no application URL")
        packet_dir = packet_dir_for(args.output, job.id, job.company, job.title)
        review_md = packet_dir / "REVIEW.md"
        resume_pdfs = sorted(packet_dir.glob("*_Resume.pdf"))
        if not resume_pdfs or not review_md.exists():
            raise SystemExit(
                f"Missing materials for job {job.id}. Run: "
                f"build-resume --job-id {job.id} first"
            )
        resume_pdf = resume_pdfs[0]
        cover_pdfs = sorted(packet_dir.glob("*_Cover_Letter.pdf"))
        cover_pdf = cover_pdfs[0].resolve() if cover_pdfs else None
        applicant = ApplicantProfile.load(
            project_root() / "config" / "candidate.json",
            project_root() / "config" / "resume.json",
        )
        cover_letter = extract_cover_letter(review_md.read_text(encoding="utf-8"))
        plan = build_field_plan(
            applicant, resume_pdf.resolve(), cover_letter, cover_letter_pdf=cover_pdf
        )
        print(f"Opening application for: {job.company} - {job.title}")
        print(f"URL: {job.url}")
        try:
            ApplicationAssistant(headless=args.headless).apply(job.url, plan)
        except RuntimeError as error:
            raise SystemExit(str(error))
        return 0
    return 1
