"""Gap report: what a target role asks for that the resume never mentions.

The ranking tells you *which* jobs to look at. This tells you *what to write*.
For a goal role, it finds the postings closest to that role, counts the concrete
skills they ask for, and subtracts what the resume already claims.
"""

from __future__ import annotations

import psycopg

from .db import vector_literal
from .resume import extract_keywords


def summarise_requirements(postings: list[dict], have: set[str]) -> list[dict]:
    """Count skills across postings and mark which ones the resume already claims."""
    counts: dict[str, int] = {}
    examples: dict[str, str] = {}
    for posting in postings:
        text = f"{posting['title']} {posting['description']}"
        for term in extract_keywords(text):
            counts[term] = counts.get(term, 0) + 1
            examples.setdefault(term, posting["title"])

    total = max(len(postings), 1)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        {
            "term": term,
            "in_postings": n,
            "pct": round(100 * n / total, 1),
            "example_posting": examples[term],
            "have": term in have,
        }
        for term, n in ranked
    ]


def gap_report(
    conn: psycopg.Connection,
    embedder,
    target: str,
    resume_keywords: tuple[str, ...] | set[str] = (),
    k: int = 15,
) -> dict:
    """Compare a target role's postings against the skills a resume already lists.

    Frequency is the only weight: a skill named in 9 of 15 target postings is a
    real requirement; one named once may be noise.
    """
    vector = embedder.embed([target])[0]
    literal = vector_literal(vector)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, company, url, left(description, 6000) AS description
            FROM postings
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (literal, k),
        )
        postings = cur.fetchall()

    have = {t.lower() for t in resume_keywords}
    required = summarise_requirements(postings, have)
    return {
        "target": target,
        "postings_analyzed": len(postings),
        "resume_keywords": sorted(have),
        "have": [r["term"] for r in required if r["have"]],
        "missing": [r for r in required if not r["have"]],
        "sample_postings": [
            {"title": p["title"], "company": p["company"], "url": p["url"]} for p in postings[:5]
        ],
    }
