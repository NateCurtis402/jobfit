"""Database access. psycopg 3, raw SQL — the schema is small enough that an ORM hides it."""

from __future__ import annotations

from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .config import REPO_ROOT


def connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn, row_factory=dict_row)


def ensure_schema(conn: psycopg.Connection, sql_path: Path | None = None) -> None:
    """Apply db/init.sql. Idempotent, so a stale volume heals without a wipe."""
    path = sql_path or (REPO_ROOT / "db" / "init.sql")
    with conn.cursor() as cur:
        cur.execute(path.read_text())
    conn.commit()


def vector_literal(vec: list[float]) -> str:
    """pgvector's text form; psycopg has no native vector type without an extra adapter."""
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"
