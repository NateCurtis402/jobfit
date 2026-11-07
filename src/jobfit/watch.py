"""Daily watcher: postings that match a profile and have not been sent before.

The "seen" table is the whole trick. Without it a watcher re-sends the same jobs
every morning and gets ignored within a week.
"""

from __future__ import annotations

import psycopg

from .db import vector_literal
from .resume import extract_keywords

# Titles that mean "not what a junior profile asked for". Off by flag if he wants
# everything back; this is the user's stated preference, not a guess about years.
SENIOR_TITLES = ("senior", "staff", "principal", "lead", "director", "head of", "manager")


def profile_tsquery(profile: str) -> str:
    """OR the profile's concrete terms into a tsquery: 'python | sql | postgres'."""
    terms = extract_keywords(profile)
    if not terms:
        return ""
    return " | ".join(t.replace(" ", " <-> ") for t in terms)

DEFAULT_PROFILE = (
    "entry level or junior python backend or data engineering role; SQL, Postgres, "
    "APIs, docker; Omaha Nebraska or remote; internships and new-grad friendly"
)


def find_matches(
    conn: psycopg.Connection,
    embedder,
    profile: str = DEFAULT_PROFILE,
    min_score: float = 0.62,
    limit: int = 8,
    days: int = 45,
    dry_run: bool = False,
    exclude_senior: bool = True,
) -> list[dict]:
    vector = embedder.embed([profile], kind="query")[0]
    literal = vector_literal(vector)
    tsquery = profile_tsquery(profile)
    # Two gates, because dense similarity alone put "Senior Firmware Engineer"
    # on an entry-level profile: the posting must mention at least one concrete
    # term from the profile, and its title must not be a senior one.
    filters = ["p.embedding IS NOT NULL", "w.posting_id IS NULL"]
    params: list[object] = [literal]
    if tsquery:
        filters.append("p.search_vector @@ to_tsquery('english', %s)")
        params.append(tsquery)
    if exclude_senior:
        for word in SENIOR_TITLES:
            filters.append("p.title NOT ILIKE %s")
            params.append(f"%{word}%")
    where = " AND ".join(filters)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT p.id, p.title, p.company, p.location, p.url, p.source, p.posted_at,
                   round((1 - (p.embedding <=> %s::vector))::numeric, 4) AS score
            FROM postings p
            LEFT JOIN watcher_seen w ON w.posting_id = p.id
            WHERE {where}
              AND (p.posted_at IS NULL OR p.posted_at >= current_date - %s::int)
            ORDER BY p.embedding <=> %s::vector
            LIMIT %s
            """,
            (*params, days, literal, limit * 4),
        )
        rows = [r for r in cur.fetchall() if float(r["score"]) >= min_score][:limit]

    if rows and not dry_run:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    "INSERT INTO watcher_seen (posting_id) VALUES (%s) ON CONFLICT DO NOTHING",
                    (row["id"],),
                )
        conn.commit()
    return rows


def render_digest(rows: list[dict], profile: str = DEFAULT_PROFILE) -> str:
    if not rows:
        return "JobFit: no new postings above the bar today."
    lines = [f"JobFit — {len(rows)} new posting(s) matching your profile"]
    for row in rows:
        loc = row["location"] or "location unlisted"
        lines.append(
            f"• {row['title']} — {row['company']} ({loc}) [{row['score']}] {row['url']}"
        )
    return "\n".join(lines)
