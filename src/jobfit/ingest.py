"""Snapshot -> postings -> embeddings -> rows. The whole M1 pipeline lives here."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import psycopg

from .sources import Posting, dedupe, parse_snapshot


@dataclass
class IngestReport:
    files: int = 0
    parsed: int = 0
    duplicates: int = 0
    inserted: int = 0
    already_present: int = 0
    embedded: int = 0
    total_in_db: int = 0

    def render(self) -> str:
        return (
            f"snapshot files : {self.files}\n"
            f"postings parsed: {self.parsed}\n"
            f"duplicates     : {self.duplicates} (dropped, same job on another board)\n"
            f"inserted       : {self.inserted}\n"
            f"already in db  : {self.already_present}\n"
            f"embedded       : {self.embedded}\n"
            f"total rows     : {self.total_in_db}"
        )


def load_snapshot_dir(path: Path) -> tuple[list[Posting], IngestReport]:
    report = IngestReport()
    postings: list[Posting] = []
    for file in sorted(path.glob("*.json")):
        payload = json.loads(file.read_text())
        report.files += 1
        try:
            postings.extend(parse_snapshot(payload))
        except ValueError as exc:
            raise SystemExit(f"{file.name}: {exc}") from exc
    report.parsed = len(postings)
    postings, report.duplicates = dedupe(postings)
    return postings, report


def upsert_postings(conn: psycopg.Connection, postings: list[Posting]) -> tuple[int, int]:
    """Insert new rows, ignore ones we've seen. Returns (inserted, already_present)."""
    inserted = 0
    for p in postings:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO postings
                    (source, external_id, title, company, location, url,
                     description, tags, posted_at, salary_raw, content_hash)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                (
                    p.source, p.external_id, p.title, p.company, p.location, p.url,
                    p.description, list(p.tags), p.posted_at, p.salary_raw, p.content_hash,
                ),
            )
            inserted += 1 if cur.fetchone() else 0
    conn.commit()
    return inserted, len(postings) - inserted


def embed_missing(conn: psycopg.Connection, embedder, batch_size: int = 16) -> int:
    """Embed every row with a NULL embedding. Idempotent: re-runs cost nothing."""
    from .db import vector_literal

    done = 0
    while True:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, embedding_text FROM ("
                "  SELECT id, concat_ws('. ', title, 'at ' || company,"
                "    'Location: ' || coalesce(nullif(location, ''), 'unspecified') || '.',"
                "    left(description, 4000)) AS embedding_text"
                "  FROM postings WHERE embedding IS NULL ORDER BY id LIMIT %s"
                ") q",
                (batch_size,),
            )
            rows = cur.fetchall()
        if not rows:
            return done
        vectors = embedder.embed([r["embedding_text"] for r in rows], kind="document")
        with conn.cursor() as cur:
            for row, vec in zip(rows, vectors, strict=True):
                cur.execute(
                    "UPDATE postings SET embedding = %s::vector, embedded_at = now() WHERE id = %s",
                    (vector_literal(vec), row["id"]),
                )
        conn.commit()
        done += len(rows)


def clear_embeddings(conn: psycopg.Connection) -> int:
    """Null every vector so the next embed pass rebuilds them (e.g. after a model change)."""
    with conn.cursor() as cur:
        cur.execute("UPDATE postings SET embedding = NULL, embedded_at = NULL")
        n = cur.rowcount
    conn.commit()
    return n


def count_rows(conn: psycopg.Connection) -> tuple[int, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) AS total, count(embedding) AS embedded FROM postings")
        row = cur.fetchone()
    return row["total"], row["embedded"]
