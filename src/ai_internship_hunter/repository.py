from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from .models import JobPosting, MatchResult


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT NOT NULL,
    description TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    language TEXT NOT NULL,
    is_paid INTEGER,
    discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, external_id)
);
CREATE TABLE IF NOT EXISTS matches (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
    qualified INTEGER NOT NULL,
    matched_skills TEXT NOT NULL,
    missing_signals TEXT NOT NULL,
    reasons TEXT NOT NULL,
    scored_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS applications (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('draft', 'ready_for_review', 'submitted', 'rejected', 'interview')),
    packet_path TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class Repository:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with closing(self.connect()) as connection, connection:
            connection.executescript(SCHEMA)

    def upsert_job(self, job: JobPosting) -> int:
        with closing(self.connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO jobs(source, external_id, title, company, location, description, url, language, is_paid)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, external_id) DO UPDATE SET
                  title=excluded.title, company=excluded.company, location=excluded.location,
                  description=excluded.description, url=excluded.url, language=excluded.language,
                  is_paid=excluded.is_paid
                """,
                (job.source, job.external_id, job.title, job.company, job.location,
                 job.description, job.url, job.language, job.is_paid),
            )
            row = connection.execute(
                "SELECT id FROM jobs WHERE source = ? AND external_id = ?",
                (job.source, job.external_id),
            ).fetchone()
            return int(row["id"])

    def list_jobs(self) -> list[JobPosting]:
        with closing(self.connect()) as connection:
            rows = connection.execute("SELECT * FROM jobs ORDER BY discovered_at DESC, id DESC").fetchall()
        return [self._to_job(row) for row in rows]

    def get_job(self, job_id: int) -> JobPosting | None:
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._to_job(row) if row else None

    def save_match(self, result: MatchResult) -> None:
        separator = "\u001f"
        with closing(self.connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO matches(job_id, score, qualified, matched_skills, missing_signals, reasons)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET score=excluded.score, qualified=excluded.qualified,
                  matched_skills=excluded.matched_skills, missing_signals=excluded.missing_signals,
                  reasons=excluded.reasons, scored_at=CURRENT_TIMESTAMP
                """,
                (result.job_id, result.score, result.qualified,
                 separator.join(result.matched_skills), separator.join(result.missing_signals),
                 separator.join(result.reasons)),
            )

    def list_ranked(
        self, limit: int = 10, qualified_only: bool = True
    ) -> list[tuple[JobPosting, MatchResult]]:
        where = "WHERE matches.qualified = 1" if qualified_only else ""
        query = f"""
            SELECT jobs.*, matches.score, matches.qualified, matches.matched_skills,
                   matches.missing_signals, matches.reasons
            FROM matches JOIN jobs ON jobs.id = matches.job_id
            {where}
            ORDER BY matches.score DESC, jobs.discovered_at DESC, jobs.id DESC
            LIMIT ?
        """
        with closing(self.connect()) as connection:
            rows = connection.execute(query, (limit,)).fetchall()
        separator = "\u001f"
        ranked: list[tuple[JobPosting, MatchResult]] = []
        for row in rows:
            job = self._to_job(row)
            result = MatchResult(
                job_id=int(row["id"]),
                score=int(row["score"]),
                qualified=bool(row["qualified"]),
                matched_skills=tuple(filter(None, row["matched_skills"].split(separator))),
                missing_signals=tuple(filter(None, row["missing_signals"].split(separator))),
                reasons=tuple(filter(None, row["reasons"].split(separator))),
            )
            ranked.append((job, result))
        return ranked

    def mark_ready_for_review(self, job_id: int, packet_path: Path) -> None:
        with closing(self.connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO applications(job_id, status, packet_path) VALUES (?, 'ready_for_review', ?)
                ON CONFLICT(job_id) DO UPDATE SET status='ready_for_review',
                  packet_path=excluded.packet_path, updated_at=CURRENT_TIMESTAMP
                """,
                (job_id, str(packet_path)),
            )

    def get_application(self, job_id: int) -> tuple[str, str | None] | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT status, packet_path FROM applications WHERE job_id = ?", (job_id,)
            ).fetchone()
        return (row["status"], row["packet_path"]) if row else None

    def metrics(self) -> dict[str, int]:
        with closing(self.connect()) as connection:
            jobs = int(connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])
            scored = int(connection.execute("SELECT COUNT(*) FROM matches").fetchone()[0])
            qualified = int(connection.execute(
                "SELECT COUNT(*) FROM matches WHERE qualified = 1"
            ).fetchone()[0])
            ready = int(connection.execute(
                "SELECT COUNT(*) FROM applications WHERE status = 'ready_for_review'"
            ).fetchone()[0])
        return {"jobs": jobs, "scored": scored, "qualified": qualified, "ready": ready}

    @staticmethod
    def _to_job(row: sqlite3.Row) -> JobPosting:
        paid = None if row["is_paid"] is None else bool(row["is_paid"])
        return JobPosting(
            id=int(row["id"]), source=row["source"], external_id=row["external_id"],
            title=row["title"], company=row["company"], location=row["location"],
            description=row["description"], url=row["url"], language=row["language"],
            is_paid=paid,
        )
