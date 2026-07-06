from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .repository import Repository


CSS = """
:root { color-scheme: light; --navy:#0f2744; --blue:#2463a2; --ink:#182230;
  --muted:#667085; --line:#dfe5ec; --panel:#ffffff; --bg:#f4f7fa; --good:#16784a; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font-family:Inter,Segoe UI,Arial,sans-serif; }
header { background:var(--navy); color:white; padding:28px max(24px,calc((100% - 1120px)/2)); }
header h1 { margin:0 0 6px; font-size:27px; letter-spacing:-.02em; }
header p { margin:0; color:#c8d6e5; }
main { width:min(1120px,calc(100% - 32px)); margin:24px auto 48px; }
.metrics { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:22px; }
.metric,.card,.detail { background:var(--panel); border:1px solid var(--line); border-radius:12px;
  box-shadow:0 4px 18px rgba(15,39,68,.05); }
.metric { padding:16px; }.metric strong { display:block; color:var(--navy); font-size:25px; }
.metric span { color:var(--muted); font-size:13px; }
.section-title { display:flex; align-items:end; justify-content:space-between; margin:0 0 12px; }
.section-title h2 { margin:0; font-size:20px; }.section-title span { color:var(--muted); font-size:13px; }
.jobs { display:grid; gap:12px; }
.card { padding:18px 20px; display:grid; grid-template-columns:76px 1fr auto; gap:16px; align-items:start; }
.score { width:64px; height:64px; border-radius:50%; display:grid; place-items:center; background:#e9f5ef;
  color:var(--good); font-weight:750; font-size:18px; border:1px solid #b9ddca; }
.card h3 { margin:0 0 4px; color:var(--navy); font-size:17px; }.meta { color:var(--muted); font-size:13px; }
.skills { display:flex; flex-wrap:wrap; gap:6px; margin-top:11px; }.skill { font-size:12px; padding:4px 8px;
  border-radius:999px; background:#eef4fa; color:#285982; }
.actions { display:flex; flex-direction:column; gap:8px; min-width:116px; }.button { text-decoration:none; text-align:center;
  padding:8px 11px; border-radius:8px; background:var(--blue); color:white; font-size:13px; font-weight:650; }
.button.secondary { background:white; color:var(--blue); border:1px solid #a9c1d8; }
.status { margin-top:8px; font-size:12px; color:var(--good); font-weight:650; }
.warning { color:#8a5a00; }.detail { padding:24px; }.detail h2 { color:var(--navy); margin-top:0; }
.description { white-space:pre-wrap; line-height:1.55; color:#344054; }.back { display:inline-block; margin-bottom:16px; color:var(--blue); }
@media (max-width:760px) { .metrics{grid-template-columns:repeat(2,1fr)} .card{grid-template-columns:64px 1fr}
  .actions{grid-column:1/-1;flex-direction:row}.actions a{flex:1} }
"""


def _page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>{CSS}</style></head><body>
<header><h1>AI Internship Hunter</h1><p>Qualified roles, tailored evidence, and human review.</p></header>
<main>{body}</main></body></html>"""


def render_dashboard(repository: Repository, limit: int = 20) -> str:
    metrics = repository.metrics()
    ranked = repository.list_ranked(limit=limit, qualified_only=True)
    metric_html = "".join(
        f'<div class="metric"><strong>{metrics[key]}</strong><span>{label}</span></div>'
        for key, label in (
            ("jobs", "Jobs discovered"), ("scored", "Jobs scored"),
            ("qualified", "Qualified at 80%+"), ("ready", "Ready for review"),
        )
    )
    cards: list[str] = []
    for job, result in ranked:
        application = repository.get_application(job.id)
        status = application[0].replace("_", " ").title() if application else "Not prepared"
        skills = "".join(
            f'<span class="skill">{escape(skill)}</span>' for skill in result.matched_skills[:8]
        )
        pay = "Paid confirmed" if job.is_paid is True else "Compensation not stated"
        pay_class = "" if job.is_paid is True else " warning"
        cards.append(f"""
<article class="card">
  <div class="score">{result.score}%</div>
  <div><h3>{escape(job.title)}</h3>
    <div class="meta">{escape(job.company)} · {escape(job.location)} · <span class="{pay_class.strip()}">{pay}</span></div>
    <div class="skills">{skills}</div><div class="status">{escape(status)}</div>
  </div>
  <div class="actions">
    <a class="button secondary" href="/job/{job.id}">Review fit</a>
    <a class="button" href="{escape(job.url, quote=True)}" target="_blank" rel="noopener">Job page</a>
  </div>
</article>""")
    jobs_html = "".join(cards) or '<div class="detail">No qualified internships yet.</div>'
    body = f"""<section class="metrics">{metric_html}</section>
<div class="section-title"><h2>Qualified internships</h2><span>Human review required before submission</span></div>
<section class="jobs">{jobs_html}</section>"""
    return _page("AI Internship Hunter", body)


def render_job(repository: Repository, job_id: int) -> str | None:
    job = repository.get_job(job_id)
    if job is None:
        return None
    ranked = {
        item.id: result
        for item, result in repository.list_ranked(limit=10000, qualified_only=False)
    }
    result = ranked.get(job_id)
    if result is None:
        return None
    reasons = "".join(f"<li>{escape(reason)}</li>" for reason in result.reasons)
    skills = ", ".join(result.matched_skills) or "None detected"
    application = repository.get_application(job_id)
    packet = escape(application[1]) if application and application[1] else "Not generated"
    body = f"""<a class="back" href="/">← Back to dashboard</a>
<article class="detail"><h2>{escape(job.title)}</h2>
<p class="meta">{escape(job.company)} · {escape(job.location)} · Score {result.score}%</p>
<p><strong>Matched evidence:</strong> {escape(skills)}</p>
<ul>{reasons}</ul>
<p><strong>Review packet:</strong> {packet}</p>
<p><a class="button" href="{escape(job.url, quote=True)}" target="_blank" rel="noopener">Open application page</a></p>
<h3>Job description</h3><div class="description">{escape(job.description)}</div></article>"""
    return _page(f"{job.title} - {job.company}", body)


def serve_dashboard(repository: Repository, host: str = "127.0.0.1", port: int = 8765) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                content = render_dashboard(repository)
                self._send(200, content)
                return
            if parsed.path.startswith("/job/"):
                try:
                    job_id = int(parsed.path.removeprefix("/job/"))
                except ValueError:
                    self._send(404, "Not found")
                    return
                content = render_job(repository, job_id)
                self._send(200 if content else 404, content or "Not found")
                return
            self._send(404, "Not found")

        def _send(self, status: int, content: str):
            body = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Dashboard: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

