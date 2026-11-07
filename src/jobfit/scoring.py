"""Score a resume against every posting.

Scoring is max-over-chunks cosine similarity: a resume wins a posting if *any*
part of it is close to that posting, which avoids diluting a good match under
pages of unrelated history. SQL does the ranking in one round trip.
"""

from __future__ import annotations

import psycopg

from .db import vector_literal
from .resume import Resume, extract_keywords


def score_resume(
    conn: psycopg.Connection,
    embedder,
    resume: Resume,
    k: int = 10,
    min_score: float = 0.0,
    rank_by: str = "semantic",
) -> list[dict]:
    if not resume.chunks:
        return []
    vectors = embedder.embed(list(resume.chunks))
    literals = [vector_literal(v) for v in vectors]

    # One VALUES list of resume-chunk vectors, cross-joined against postings:
    # max similarity per posting, plus which chunk produced it.
    values_sql = ", ".join(["(%s::vector, %s)"] * len(literals))
    params: list[object] = []
    for idx, lit in enumerate(literals):
        params.extend([lit, idx])

    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH chunks(chunk_vec, chunk_idx) AS (VALUES {values_sql})
            SELECT p.id, p.source, p.title, p.company, p.location, p.url,
                   p.tags, p.posted_at, p.salary_raw,
                   left(p.description, 4000) AS description,
                   max(round((1 - (p.embedding <=> c.chunk_vec))::numeric, 4)) AS score,
                   (array_agg(c.chunk_idx ORDER BY p.embedding <=> c.chunk_vec))[1] AS best_chunk_idx
            FROM postings p
            CROSS JOIN chunks c
            WHERE p.embedding IS NOT NULL
            GROUP BY p.id
            HAVING max(1 - (p.embedding <=> c.chunk_vec)) >= %s
            ORDER BY score DESC
            LIMIT %s
            """,
            [*params, min_score, k],
        )
        rows = cur.fetchall()

    resume_terms = set(resume.keywords)
    out: list[dict] = []
    for row in rows:
        idx = row.pop("best_chunk_idx")
        posting_terms = set(extract_keywords(row.pop("description", "")))
        row["score"] = float(row["score"])
        row["best_chunk"] = resume.chunks[idx][:180].replace("\n", " ") if idx is not None else ""
        row["matched_terms"] = sorted(posting_terms & resume_terms)
        out.append(row)

    if rank_by == "hybrid":
        # Small explicit bonus per concrete skill shared with the resume. Kept as
        # a separate mode so M3 can measure semantic-only vs hybrid instead of
        # arguing about which "feels" better.
        for row in out:
            row["score"] = round(row["score"] + 0.015 * len(row["matched_terms"]), 4)
        out.sort(key=lambda r: r["score"], reverse=True)
        out = out[:k]
    return out
