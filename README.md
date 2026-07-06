# AI Internship Hunter

A local-first assistant that imports internship postings, ranks them against a candidate profile, and prepares truthful, job-specific application materials for human review.

The application does **not** scrape protected job boards, log into accounts, or submit applications. It reads public job data from documented ATS endpoints and authorized JSON exports. The workflow always stops before submission.

## Current capabilities

- Structured candidate profile based on `Resume_July.pdf`
- Preferences for English-only paid internships in Hsinchu, Taipei, or remote
- SQLite storage with deduplication by source URL
- Public Greenhouse and Lever discovery connectors
- Hybrid concept/lexical matching with an 80% qualification threshold
- Optional local Sentence Transformers embeddings
- Ranked top-10 Markdown report
- Evidence-only resume tailoring that never invents qualifications
- One-page DOCX and PDF resume generation
- Responsive local review dashboard
- Deterministic resume-tailoring plan and cover-letter draft
- Review queue; no submit action exists
- CLI and unit tests using only the Python standard library

## Quick start

```powershell
python -m ai_internship_hunter --db data/hunter.db init
python -m ai_internship_hunter --db data/hunter.db import-jobs examples/jobs.json
python -m ai_internship_hunter --db data/hunter.db score
python -m ai_internship_hunter --db data/hunter.db prepare --job-id 1
python -m ai_internship_hunter --db data/hunter.db build-resume --job-id 1
```

Discover current jobs from the configured public ATS boards and write the top matches:

```powershell
python -m ai_internship_hunter --db data/jobs.db discover
```

The default providers in `config/providers.json` target public Taiwan career boards using [Greenhouse's Job Board API](https://developers.greenhouse.io/job-board.html) and [Lever's Postings API](https://github.com/lever/postings-api). Edit that file to add or disable companies.

Open the local review dashboard after discovery:

```powershell
python -m ai_internship_hunter --db data/jobs.db dashboard
```

Then visit `http://127.0.0.1:8765`. The dashboard is read-only: it displays rankings, evidence, review status, and links to original job pages. It does not submit applications.

To use local neural embeddings instead of the dependency-free hybrid engine:

```powershell
pip install -e ".[semantic]"
python -m ai_internship_hunter --embedding-model all-MiniLM-L6-v2 --db data/jobs.db discover
```

When running from a source checkout without installing the package:

```powershell
$env:PYTHONPATH = "src"
python -m ai_internship_hunter --db data/hunter.db init
```

Generated review packets are written under `generated/`. Read and edit them before opening the application URL yourself.

## Architecture

- `config/`: candidate and search preferences
- `src/ai_internship_hunter/repository.py`: SQLite persistence
- `matcher.py`: transparent scoring rules
- `semantic.py`: hybrid concept similarity and optional local embeddings
- `materials.py`: truthful draft generation from known resume evidence
- `resume.py`: structured resume source and deterministic evidence ordering
- `resume_documents.py`: ATS-friendly DOCX and PDF generation
- `dashboard.py`: local read-only review interface
- `providers.py`: JSON, Greenhouse, and Lever discovery adapters
- `reports.py`: ranked top-match reports
- `cli.py`: end-to-end local workflow

## Next milestone

Add opt-in browser-assisted form filling that stops at the final review page, plus interview-preparation packets for submitted roles.
