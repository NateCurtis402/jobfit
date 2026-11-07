"""Semantic search over the index. One SQL statement, no in-Python ranking."""

from __future__ import annotations

import psycopg

from .db import vector_literal


def search(conn: psycopg.Connection, embedder, query: str, k: int = 5) -> list[dict]:
    """Cosine similarity search. `<=>` is pgvector's cosine distance, so score = 1 - distance."""
    vector = embedder.embed([query])[0]
    literal = vector_literal(vector)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, source, title, company, location, url, salary_raw, posted_at,
                   round((1 - (embedding <=> %s::vector))::numeric, 4) AS score
            FROM postings
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (literal, literal, k),
        )
        return cur.fetchall()
