"""Tests for resume parsing, chunking and the agent's text-call coercion."""

from __future__ import annotations

from pathlib import Path

import pytest

from jobfit.agent import _coerce_text_call, _summarise
from jobfit.resume import ResumeParseError, chunk, extract_keywords, parse, split_sections

FIXTURE = Path(__file__).parent / "fixtures" / "sample_resume.txt"

RESUME = """Jordan Doe
Omaha, NE

SUMMARY
Logistics veteran moving into data engineering. Python and SQL daily.

EXPERIENCE
Logistics Analyst, Marine Corps (2020-2025)
- Managed inventory reconciliation in GCSS-MC
- Automated a monthly report with Excel and Python

SKILLS
Python, SQL, Postgres, Docker, Linux
"""


def test_parse_produces_chunks_and_keywords():
    resume = parse(RESUME)
    assert len(resume.chunks) >= 3
    assert "python" in resume.keywords and "sql" in resume.keywords
    assert not resume.is_thin


def test_empty_resume_is_rejected():
    with pytest.raises(ResumeParseError):
        parse("   \n\n  ")


def test_thin_resume_is_flagged():
    assert parse("Jane Doe — python").is_thin


def test_sections_split_on_headers():
    sections = split_sections(RESUME)
    joined = " ".join(sections).lower()
    assert "experience" in joined and "skills" in joined


def test_chunk_stays_under_budget():
    long_text = "SKILLS\n" + ("python " * 400)
    chunks = chunk(long_text, max_chars=300)
    assert all(len(c) <= 320 for c in chunks)
    assert len(chunks) > 1


def test_keywords_are_word_bounded():
    # "gopher" must not match "go"; "postgres" must match.
    kws = extract_keywords("We use postgres, not gopher")
    assert "postgres" in kws
    assert "go" not in kws


def test_fixture_resume_parses():
    resume = parse(FIXTURE.read_text())
    assert resume.chunks
    assert {"python", "sql", "gcss"} <= set(resume.keywords)


def test_agent_coerces_json_text_tool_call():
    call = _coerce_text_call('{"name": "search_jobs", "arguments": {"query": "ai"}}')
    assert call is not None
    assert call["function"]["name"] == "search_jobs"
    assert call["function"]["arguments"]["query"] == "ai"


def test_agent_ignores_plain_prose():
    assert _coerce_text_call("There are three roles that fit.") is None
    assert _coerce_text_call('{"answer": "no tool"}') is None


def test_agent_summary_lists_company_names():
    text = _summarise([{"title": "AI Engineer", "company": "Benzinga"}])
    assert "AI Engineer" in text and "Benzinga" in text
