"""Search over the index: dense, lexical, or both fused.

Dense (pgvector cosine) finds paraphrases — "data pipelines" matches "ETL".
Lexical (Postgres full-text) nails exact tokens — "LLM", "Kubernetes", "GCSS".
Neither wins alone, so `hybrid` fuses the two rankings with reciprocal rank
fusion: score = sum of 1/(RRF_K + rank) across lists. RRF needs no calibration
between the two scores, which is why it is the safe way to fuse them.
"""

from __future__ import annotations

import psycopg

from .db import vector_literal

RRF_K = 60
MODES = ("semantic", "lexical", "hybrid")

_COLUMNS = "id, source, title, company, location, url, salary_raw, posted_at"


def _dedupe(rows: list[dict], k: int) -> list[dict]:
    """Recruiters post the same job several times; one role must not fill the top 5."""
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for row in rows:
        key = ((row["title"] or "").strip().lower(), (row["company"] or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
        if len(unique) >= k:
            break
    return unique


def _semantic(conn: psycopg.Connection, embedder, query: str, limit: int) -> list[dict]:
    """`<=>` is pgvector's cosine distance, so similarity = 1 - distance."""
    vector = embedder.embed([query], kind="query")[0]
    literal = vector_literal(vector)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_COLUMNS},
                   round((1 - (embedding <=> %s::vector))::numeric, 4) AS score
            FROM postings
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (literal, literal, limit),
        )
        return cur.fetchall()


def _lexical(conn: psycopg.Connection, query: str, limit: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_COLUMNS},
                   round(ts_rank(search_vector, websearch_to_tsquery('english', %s))::numeric, 4)
                       AS score
            FROM postings
            WHERE search_vector @@ websearch_to_tsquery('english', %s)
            ORDER BY score DESC
            LIMIT %s
            """,
            (query, query, limit),
        )
        return cur.fetchall()


def search(
    conn: psycopg.Connection,
    embedder,
    query: str,
    k: int = 5,
    mode: str = "semantic",
) -> list[dict]:
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")

    if mode == "semantic":
        return _dedupe(_semantic(conn, embedder, query, k * 3), k)
    if mode == "lexical":
        return _dedupe(_lexical(conn, query, k * 3), k)

    dense = _semantic(conn, embedder, query, k * 4)
    sparse = _lexical(conn, query, k * 4)
    fused: dict[int, dict] = {}
    for label, ranked_list in (("dense", dense), ("lexical", sparse)):
        for rank, row in enumerate(ranked_list, 1):
            pid = row["id"]
            if pid not in fused:
                fused[pid] = {**row, "score": 0.0, "found_by": []}
            fused[pid]["score"] = round(fused[pid]["score"] + 1.0 / (RRF_K + rank), 6)
            fused[pid]["found_by"].append(label)
    ordered = sorted(fused.values(), key=lambda r: r["score"], reverse=True)
    return _dedupe(ordered, k)
