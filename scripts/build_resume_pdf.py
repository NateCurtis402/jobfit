"""Render the plain-text resume to a one-page ATS-friendly PDF.

Needs reportlab (pip install reportlab) — deliberately not a jobfit dependency,
because the app never renders resumes.

Usage: python scripts/build_resume_pdf.py data/private/resume-tech.md out.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate

SECTION_NAMES = {
    "SUMMARY", "TECHNICAL SKILLS", "PROJECTS", "EXPERIENCE", "EDUCATION",
    "CERTIFICATIONS", "TRAINING", "CORE COMPETENCIES",
}
ROLE_PREFIXES = (
    "JobFit —", "Personal infrastructure", "Telecommunications Operations",
    "Technical Logistics", "Administrative Officer",
)


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle(
            "name", parent=base["Title"], fontName="Helvetica-Bold", fontSize=15.5,
            leading=18, alignment=TA_CENTER, spaceAfter=1,
        ),
        "contact": ParagraphStyle(
            "contact", parent=base["Normal"], fontName="Helvetica", fontSize=8,
            leading=9.6, alignment=TA_CENTER, textColor="#222222",
        ),
        "section": ParagraphStyle(
            "section", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=9,
            leading=10.6, spaceBefore=4, spaceAfter=1, textColor="#111111",
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Helvetica", fontSize=8.2, leading=10.1,
        ),
        "role": ParagraphStyle(
            "role", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8.5,
            leading=10.4, spaceBefore=2,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Helvetica", fontSize=8.1, leading=9.9,
        ),
    }


def split_header(lines: list[str]) -> tuple[list[str], list[str]]:
    header: list[str] = []
    for idx, line in enumerate(lines):
        if not line.strip():
            return header, lines[idx + 1:]
        header.append(line.strip())
    return header, []


def build(md_path: Path, out_path: Path) -> None:
    st = styles()
    header, body_lines = split_header(md_path.read_text().splitlines())
    story: list = [Paragraph(header[0], st["name"])]
    for line in header[1:]:
        story.append(Paragraph(line.replace(" | ", " &nbsp;|&nbsp; "), st["contact"]))

    bullets: list[str] = []

    def flush() -> None:
        if not bullets:
            return
        items = [ListItem(Paragraph(b, st["bullet"]), leftIndent=9) for b in bullets]
        story.append(
            ListFlowable(items, bulletType="bullet", start="•", leftIndent=11,
                         bulletFontSize=6.5, bulletOffsetY=-1)
        )
        bullets.clear()

    for raw in body_lines:
        text = raw.strip()
        if not text:
            continue
        if text.startswith("•"):
            bullets.append(text.lstrip("• ").strip())
            continue
        flush()
        if text in SECTION_NAMES:
            story.append(Paragraph(text, st["section"]))
            story.append(HRFlowable(width="100%", thickness=0.5, color="#999999", spaceAfter=2))
        elif text.startswith(ROLE_PREFIXES):
            story.append(Paragraph(text, st["role"]))
        else:
            story.append(Paragraph(text, st["body"]))
    flush()

    SimpleDocTemplate(
        str(out_path), pagesize=LETTER,
        leftMargin=0.55 * inch, rightMargin=0.55 * inch,
        topMargin=0.42 * inch, bottomMargin=0.36 * inch,
        title="Nathaniel Curtis — Resume", author="Nathaniel Curtis",
    ).build(story)


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    build(src, dst)
    print(f"wrote {dst}")
