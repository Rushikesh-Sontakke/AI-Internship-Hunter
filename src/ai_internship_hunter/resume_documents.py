from __future__ import annotations

from html import escape
from pathlib import Path

from .resume import Experience, Project, TailoredResume


# compact_reference_guide with named resume overrides:
# Letter portrait; 0.55-inch margins for a one-page application resume;
# Calibri/Helvetica 9.2-point body; restrained navy section hierarchy;
# proposal_centerpiece title block adapted to name, target headline, and contacts.
NAVY = "17365D"
BLUE = "1F4D78"
GRAY = "555555"


def _slug(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


class ResumeDocumentGenerator:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def generate(self, resume: TailoredResume, job_id: int) -> tuple[Path, Path]:
        target = self.output_dir / f"{job_id}-{_slug(resume.target_company)}-{_slug(resume.target_title)}"
        target.mkdir(parents=True, exist_ok=True)
        docx_path = target / "tailored-resume.docx"
        pdf_path = target / "tailored-resume.pdf"
        self._build_docx(resume, docx_path)
        self._build_pdf(resume, pdf_path)
        return docx_path, pdf_path

    def _build_docx(self, resume: TailoredResume, path: Path) -> None:
        from docx import Document
        from docx.enum.section import WD_SECTION
        from docx.enum.style import WD_STYLE_TYPE
        from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Inches, Pt, RGBColor

        doc = Document()
        section = doc.sections[0]
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.top_margin = Inches(0.48)
        section.bottom_margin = Inches(0.48)
        section.left_margin = Inches(0.58)
        section.right_margin = Inches(0.58)
        section.header_distance = Inches(0.25)
        section.footer_distance = Inches(0.25)

        styles = doc.styles
        normal = styles["Normal"]
        normal.font.name = "Calibri"
        normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        normal.font.size = Pt(8.9)
        normal.paragraph_format.space_before = Pt(0)
        normal.paragraph_format.space_after = Pt(0.6)
        normal.paragraph_format.line_spacing = 1.0

        heading = styles["Heading 1"]
        heading.font.name = "Calibri"
        heading._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        heading._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        heading.font.size = Pt(10.2)
        heading.font.bold = True
        heading.font.color.rgb = RGBColor.from_string(BLUE)
        heading.paragraph_format.space_before = Pt(3.2)
        heading.paragraph_format.space_after = Pt(1.4)
        heading.paragraph_format.keep_with_next = True

        bullet = styles["List Bullet"]
        bullet.font.name = "Calibri"
        bullet._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        bullet._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        bullet.font.size = Pt(8.6)
        bullet.paragraph_format.left_indent = Inches(0.18)
        bullet.paragraph_format.first_line_indent = Inches(-0.13)
        bullet.paragraph_format.space_before = Pt(0)
        bullet.paragraph_format.space_after = Pt(0.35)
        bullet.paragraph_format.line_spacing = 1.0

        if "Entry" not in styles:
            entry = styles.add_style("Entry", WD_STYLE_TYPE.PARAGRAPH)
        else:
            entry = styles["Entry"]
        entry.base_style = normal
        entry.paragraph_format.space_before = Pt(0.6)
        entry.paragraph_format.space_after = Pt(0)
        entry.paragraph_format.keep_with_next = True

        def set_run(run, *, size=None, bold=None, italic=None, color=None):
            run.font.name = "Calibri"
            run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Calibri")
            run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Calibri")
            if size is not None:
                run.font.size = Pt(size)
            if bold is not None:
                run.bold = bold
            if italic is not None:
                run.italic = italic
            if color is not None:
                run.font.color.rgb = RGBColor.from_string(color)

        def add_hyperlink(paragraph, label: str, url: str):
            part = paragraph.part
            relationship_id = part.relate_to(
                url,
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                is_external=True,
            )
            hyperlink = OxmlElement("w:hyperlink")
            hyperlink.set(qn("r:id"), relationship_id)
            run = OxmlElement("w:r")
            properties = OxmlElement("w:rPr")
            color = OxmlElement("w:color")
            color.set(qn("w:val"), BLUE)
            properties.append(color)
            run.append(properties)
            text = OxmlElement("w:t")
            text.text = label
            run.append(text)
            hyperlink.append(run)
            paragraph._p.append(hyperlink)

        def add_heading(text: str):
            paragraph = doc.add_paragraph(style="Heading 1")
            paragraph.add_run(text.upper())
            return paragraph

        def set_right_tab(paragraph):
            paragraph.paragraph_format.tab_stops.add_tab_stop(
                Inches(7.25), alignment=WD_TAB_ALIGNMENT.RIGHT
            )

        # Adapted proposal_centerpiece title block.
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        set_run(p.add_run(resume.source.name), size=19.5, bold=True, color=NAVY)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(1.2)
        set_run(p.add_run(resume.headline), size=9.4, italic=True, color=GRAY)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2.4)
        add_hyperlink(p, "GitHub", resume.source.github)
        set_run(p.add_run("  |  "), size=8.4, color=GRAY)
        add_hyperlink(p, "LinkedIn", resume.source.linkedin)
        set_run(p.add_run(f"  |  {resume.source.email}  |  {resume.source.phone}"), size=8.4)

        add_heading("Summary")
        p = doc.add_paragraph(resume.summary)
        p.paragraph_format.space_after = Pt(0.8)

        add_heading("Education")
        p = doc.add_paragraph(style="Entry")
        set_right_tab(p)
        set_run(p.add_run(resume.source.education.school), bold=True)
        p.add_run("\t")
        set_run(p.add_run(resume.source.education.location), italic=True)
        p = doc.add_paragraph(style="Entry")
        set_right_tab(p)
        set_run(p.add_run(resume.source.education.degree), italic=True)
        p.add_run("\t")
        set_run(p.add_run(resume.source.education.dates), italic=True)
        for detail in resume.source.education.details:
            doc.add_paragraph(detail, style="List Bullet")

        add_heading("Technical Skills")
        for group in resume.skill_groups:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0.25)
            set_run(p.add_run(f"{group.label}: "), bold=True)
            p.add_run(", ".join(group.skills))

        add_heading("Projects")
        for project in resume.projects:
            self._add_docx_project(doc, project, set_run, add_hyperlink, set_right_tab)

        add_heading("Experience")
        for item in resume.experience:
            p = doc.add_paragraph(style="Entry")
            set_right_tab(p)
            set_run(p.add_run(item.title), bold=True)
            p.add_run("\t")
            set_run(p.add_run(item.dates), italic=True)
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            set_run(p.add_run(f"{item.organization} | {item.location}"), italic=True, color=GRAY)
            for bullet_text in item.bullets:
                doc.add_paragraph(bullet_text, style="List Bullet")

        doc.core_properties.author = resume.source.name
        doc.core_properties.title = f"Resume - {resume.target_title} - {resume.target_company}"
        doc.save(path)

    @staticmethod
    def _add_docx_project(doc, project: Project, set_run, add_hyperlink, set_right_tab) -> None:
        from docx.shared import Pt

        p = doc.add_paragraph(style="Entry")
        set_right_tab(p)
        set_run(p.add_run(project.title), bold=True)
        for label, url in project.links.items():
            set_run(p.add_run("  |  "), size=8.2, color=GRAY)
            add_hyperlink(p, label, url)
        p.add_run("\t")
        set_run(p.add_run(project.dates), italic=True)
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        set_run(p.add_run(", ".join(project.skills)), italic=True, color=GRAY)
        for bullet_text in project.bullets:
            doc.add_paragraph(bullet_text, style="List Bullet")

    def _build_pdf(self, resume: TailoredResume, path: Path) -> None:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer,
        )

        document = SimpleDocTemplate(
            str(path), pagesize=letter,
            leftMargin=0.58 * inch, rightMargin=0.58 * inch,
            topMargin=0.42 * inch, bottomMargin=0.42 * inch,
            title=f"Resume - {resume.target_title} - {resume.target_company}",
            author=resume.source.name,
        )
        styles = getSampleStyleSheet()
        body = ParagraphStyle(
            "ResumeBody", parent=styles["Normal"], fontName="Helvetica", fontSize=9.0,
            leading=10.1, spaceAfter=0.9, textColor=colors.HexColor("#111111"),
        )
        heading = ParagraphStyle(
            "ResumeHeading", parent=body, fontName="Helvetica-Bold", fontSize=10.4,
            leading=11.2, spaceBefore=3.8, spaceAfter=1.5,
            textColor=colors.HexColor(f"#{BLUE}"), keepWithNext=True,
        )
        entry = ParagraphStyle(
            "ResumeEntry", parent=body, fontName="Helvetica", fontSize=9.0,
            leading=9.9, spaceBefore=0.5, spaceAfter=0, keepWithNext=True,
        )
        bullet_style = ParagraphStyle(
            "ResumeBullet", parent=body, fontSize=8.8, leading=9.7, spaceAfter=0,
            leftIndent=0,
        )
        name_style = ParagraphStyle(
            "ResumeName", parent=body, alignment=TA_CENTER, fontName="Helvetica-Bold",
            fontSize=19.5, leading=20, textColor=colors.HexColor(f"#{NAVY}"), spaceAfter=0,
        )
        center = ParagraphStyle(
            "ResumeCenter", parent=body, alignment=TA_CENTER, fontSize=8.8,
            leading=9.6, textColor=colors.HexColor(f"#{GRAY}"), spaceAfter=1.2,
        )

        def p(value: str, style=body):
            return Paragraph(value, style)

        def bullets(items: tuple[str, ...]):
            return ListFlowable(
                [ListItem(p(escape(item), bullet_style), leftIndent=0) for item in items],
                bulletType="bullet", start="-", leftIndent=12, bulletFontName="Helvetica",
                bulletFontSize=8, bulletOffsetY=1.1, spaceAfter=0,
            )

        story = [
            p(escape(resume.source.name), name_style),
            p(escape(resume.headline), center),
            p(
                f'<link href="{escape(resume.source.github, quote=True)}">GitHub</link> | '
                f'<link href="{escape(resume.source.linkedin, quote=True)}">LinkedIn</link> | '
                f'{escape(resume.source.email)} | {escape(resume.source.phone)}',
                center,
            ),
            p("SUMMARY", heading),
            p(escape(resume.summary)),
            p("EDUCATION", heading),
            p(
                f'<b>{escape(resume.source.education.school)}</b> - '
                f'{escape(resume.source.education.location)} <font color="#{GRAY}">| '
                f'{escape(resume.source.education.dates)}</font>', entry,
            ),
            p(f'<i>{escape(resume.source.education.degree)}</i>', entry),
            bullets(resume.source.education.details),
            p("TECHNICAL SKILLS", heading),
        ]
        for group in resume.skill_groups:
            story.append(p(f'<b>{escape(group.label)}:</b> {escape(", ".join(group.skills))}'))

        story.append(p("PROJECTS", heading))
        for project in resume.projects:
            links = "".join(
                f' | <link href="{escape(url, quote=True)}">{escape(label)}</link>'
                for label, url in project.links.items()
            )
            block = [
                p(f'<b>{escape(project.title)}</b>{links} <font color="#{GRAY}">| {escape(project.dates)}</font>', entry),
                p(f'<i>{escape(", ".join(project.skills))}</i>', entry),
                bullets(project.bullets),
            ]
            story.append(KeepTogether(block))

        story.append(p("EXPERIENCE", heading))
        for item in resume.experience:
            block = [
                p(f'<b>{escape(item.title)}</b> <font color="#{GRAY}">| {escape(item.dates)}</font>', entry),
                p(f'<i>{escape(item.organization)} | {escape(item.location)}</i>', entry),
                bullets(item.bullets),
            ]
            story.append(KeepTogether(block))
        document.build(story)
