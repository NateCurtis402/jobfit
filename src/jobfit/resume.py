"""Resume -> text chunks. No LLM: the resume is embedded directly, so scoring is
deterministic and a bad match is a bug you can reproduce, not a model's mood.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

SECTION_RE = re.compile(
    r"^(experience|work experience|employment|education|skills|projects|"
    r"certifications|certificates|summary|professional summary|profile)\b",
    re.IGNORECASE,
)
BULLET_RE = re.compile(r"^\s*[•\-\*\u2022]\s*")
CHUNK_CHARS = 700  # ~1 short section per chunk; small enough to match one posting aspect


class ResumeParseError(ValueError):
    pass


@dataclass(frozen=True)
class Resume:
    text: str
    chunks: tuple[str, ...]
    sections: tuple[str, ...]
    keywords: tuple[str, ...]

    @property
    def is_thin(self) -> bool:
        """Guard against a 3-line resume silently scoring everything at zero."""
        return len(self.text.strip()) < 200


def pdf_to_text(data: bytes) -> str:
    """PDF support is optional: pypdf is a small extra, not a hard dependency."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - exercised only without pypdf
        raise ResumeParseError(
            "PDF upload needs pypdf. Install it (pip install 'jobfit[pdf]') "
            "or POST plain text as {\"resume_text\": \"...\"}."
        ) from exc
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sections(text: str) -> list[str]:
    """Split on resume section headers; returns the body of each section."""
    lines = text.split("\n")
    sections: list[list[str]] = [[]]
    for line in lines:
        if SECTION_RE.match(line.strip()) and len(line.strip()) < 60:
            sections.append([line.strip()])
        else:
            sections[-1].append(BULLET_RE.sub("", line))
    return ["\n".join(s).strip() for s in sections if "\n".join(s).strip()]


def chunk(text: str, max_chars: int = CHUNK_CHARS) -> tuple[str, ...]:
    """Section-aware chunking: keep a section whole if it fits, otherwise split it."""
    out: list[str] = []
    for section in split_sections(text):
        if len(section) <= max_chars:
            out.append(section)
            continue
        words, buf = section.split(), ""
        for word in words:
            if len(buf) + len(word) + 1 > max_chars:
                out.append(buf.strip())
                buf = ""
            buf += word + " "
        if buf.strip():
            out.append(buf.strip())
    return tuple(out) or (text[:max_chars],)


# Terms worth matching explicitly, because they are what postings filter on.
KEYWORD_TERMS = (
    "python", "sql", "postgres", "postgresql", "fastapi", "docker", "kubernetes",
    "aws", "gcp", "azure", "terraform", "linux", "git", "ci/cd", "rest", "api",
    "etl", "airflow", "dbt", "spark", "pandas", "numpy", "pytorch", "tensorflow",
    "machine learning", "llm", "rag", "vector", "embeddings", "nlp", "java",
    "javascript", "typescript", "react", "go", "rust", "agile", "scrum", "excel",
    "tableau", "power bi", "logistics", "inventory", "supply chain", "erp", "gcms",
    "gcss", "data analysis", "reporting",
)


def extract_keywords(text: str) -> tuple[str, ...]:
    low = text.lower()
    return tuple(term for term in KEYWORD_TERMS if re.search(rf"\b{re.escape(term)}\b", low))


def parse(text: str) -> Resume:
    cleaned = clean(text)
    if not cleaned:
        raise ResumeParseError("resume text is empty")
    return Resume(
        text=cleaned,
        chunks=chunk(cleaned),
        sections=tuple(s.split("\n")[0][:60] for s in split_sections(cleaned)),
        keywords=extract_keywords(cleaned),
    )
