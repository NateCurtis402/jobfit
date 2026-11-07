"""Normalize raw job-board records into one Posting shape.

Deliberately stdlib-only: every board adapter can be unit-tested without a
database, a network, or an embedding model.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape

TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
SPACE_RE = re.compile(r"[ \t\u00a0]+")
BLANK_RE = re.compile(r"\n{3,}")

MAX_EMBED_CHARS = 4000  # keeps one posting inside the embed model's context


MOJIBAKE_RE = re.compile(r"[\u0080-\u009f]|â€|Ã[\u0080-\u00bf]|Â[\u0080-\u00bf]|â[\u0080-\u009f\u201a-\u203a]")

# One suspicious run at a time. Whole-document repair fails whenever a document
# mixes the latin-1 and cp1252 variants, which real boards do; repairing each
# run in isolation always uses the correct codec for that run.
MOJIBAKE_RUN_RE = re.compile(
    r"\u00e2[\u0080-\u009f\u2013\u2014\u2018-\u201d\u2022\u2026\u20ac\u2122\u0153\u0161]{1,2}"
    r"|[\u00c2\u00c3][\u0080-\u00bf]"
    r"|[\u0080-\u009f]+"
)


def _repair_run(match: re.Match[str]) -> str:
    run = match.group(0)
    for codec in ("latin-1", "cp1252"):
        try:
            fixed = run.encode(codec, errors="strict").decode("utf-8", errors="strict")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if not MOJIBAKE_RE.search(fixed):
            return fixed
    return ""  # an unrecoverable control run is noise, not text


def _repair_mojibake(text: str) -> str:
    """Boards serve UTF-8 that was decoded as latin-1 or cp1252 ("weâ€™re").

    Two variants show up in the wild: real cp1252 characters (â€™) and C1
    control characters (U+0080–U+009F), depending on which decoder the board
    used. Repair is applied per suspicious run and only accepted if the result
    is clean, so healthy text is never damaged.
    """
    if not MOJIBAKE_RE.search(text):
        return text
    return MOJIBAKE_RUN_RE.sub(_repair_run, text)


def html_to_text(raw: str) -> str:
    """Job descriptions arrive as HTML. Strip tags, unescape entities, squeeze blanks."""
    if not raw:
        return ""
    text = SCRIPT_RE.sub(" ", raw)
    text = TAG_RE.sub(" ", text)
    text = unescape(text)
    text = SPACE_RE.sub(" ", text)
    text = BLANK_RE.sub("\n\n", text)
    return _repair_mojibake(text).strip()


def _parse_date(value: str | None) -> date | None:
    """Boards use several date formats; unknown formats become NULL, never a guess."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()  # handles +00:00 and trailing Z
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class Posting:
    source: str
    external_id: str
    title: str
    company: str
    location: str = ""
    url: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    posted_at: date | None = None
    salary_raw: str = ""

    @property
    def content_hash(self) -> str:
        """Identity of the *job*, not the row: same role on two boards collapses to one."""
        material = f"{self.title.strip().lower()}|{self.company.strip().lower()}|{self.description[:500]}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def embedding_text(self) -> str:
        """What actually gets embedded: title/company/tags first, then a bounded body."""
        head = f"{self.title} at {self.company}. Location: {self.location or 'unspecified'}."
        if self.tags:
            head += f" Tags: {', '.join(self.tags)}."
        return f"{head}\n\n{self.description[:MAX_EMBED_CHARS]}"


def from_remotive(rec: dict) -> Posting:
    return Posting(
        source="remotive",
        external_id=str(rec["id"]),
        title=(rec.get("title") or "").strip(),
        company=(rec.get("company_name") or "").strip(),
        location=(rec.get("candidate_required_location") or "").strip(),
        url=(rec.get("url") or "").strip(),
        description=html_to_text(rec.get("description") or ""),
        tags=tuple(rec.get("tags") or ()),
        posted_at=_parse_date(rec.get("publication_date")),
        salary_raw=(rec.get("salary") or "").strip(),
    )


def from_remoteok(rec: dict) -> Posting:
    """RemoteOK's first array element is a legal notice, not a job — caller filters those."""
    salary = rec.get("salary_min")
    salary_raw = ""
    if salary and rec.get("salary_max"):
        salary_raw = f"${salary:,.0f}-${rec['salary_max']:,.0f}"
    tags = tuple(rec.get("tags") or ())
    return Posting(
        source="remoteok",
        external_id=str(rec.get("id")),
        title=(rec.get("position") or "").strip(),
        company=(rec.get("company") or "").strip(),
        location=(rec.get("location") or "").strip(),
        url=(rec.get("apply_url") or rec.get("url") or "").strip(),
        description=html_to_text(rec.get("description") or ""),
        tags=tags,
        posted_at=_parse_date(rec.get("date")),
        salary_raw=salary_raw,
    )


def from_adzuna(rec: dict) -> Posting:
    """Adzuna nests company and location, and sends a snippet rather than full text."""
    company = (rec.get("company") or {}).get("display_name") or ""
    location = (rec.get("location") or {}).get("display_name") or ""
    category = (rec.get("category") or {}).get("tag") or ""
    salary_min, salary_max = rec.get("salary_min"), rec.get("salary_max")
    salary_raw = ""
    if salary_min and salary_max:
        salary_raw = f"${salary_min:,.0f}-${salary_max:,.0f}"
    return Posting(
        source="adzuna",
        external_id=str(rec.get("id") or ""),
        title=(rec.get("title") or "").strip(),
        company=company.strip(),
        location=location.strip(),
        url=(rec.get("redirect_url") or "").strip(),
        description=html_to_text(rec.get("description") or ""),
        tags=(category,) if category else (),
        posted_at=_parse_date(rec.get("created")),
        salary_raw=salary_raw,
    )


ADAPTERS = {
    "remotive": from_remotive,
    "remoteok": from_remoteok,
    "adzuna": from_adzuna,
}


def parse_snapshot(payload: dict) -> list[Posting]:
    """Take one snapshot document ({"source": ..., "jobs": [...]}) to normalized Postings."""
    source = payload.get("source", "")
    adapter = ADAPTERS.get(source)
    if adapter is None:
        raise ValueError(f"unknown source: {source!r} (known: {sorted(ADAPTERS)})")
    postings: list[Posting] = []
    for rec in payload.get("jobs") or []:
        if not rec.get("id") or "legal" in rec or "00-warning" in rec:
            continue  # board metadata, not a job
        try:
            p = adapter(rec)
        except (KeyError, TypeError, ValueError):
            continue
        if p.title and p.company:
            postings.append(p)
    return postings


def dedupe(postings: list[Posting]) -> tuple[list[Posting], int]:
    """Collapse duplicates by content hash, keeping the first seen. Returns (kept, dropped)."""
    seen: set[str] = set()
    kept: list[Posting] = []
    for p in postings:
        h = p.content_hash
        if h in seen:
            continue
        seen.add(h)
        kept.append(p)
    return kept, len(postings) - len(kept)
