"""Command line entrypoint: ingest, query, stats."""

from __future__ import annotations

import argparse
import sys

from .config import Settings
from .db import connect, ensure_schema
from .embed import EmbeddingError, OllamaEmbedder
from .gap import gap_report
from .ingest import count_rows, embed_missing, load_snapshot_dir, upsert_postings
from .search import search as run_search


def _setup(require_embedder: bool):
    settings = Settings.load()
    conn = connect(settings.database_url)
    ensure_schema(conn)
    embedder = OllamaEmbedder(settings.ollama_url, settings.embed_model)
    if require_embedder:
        embedder.check()
    return settings, conn, embedder


def cmd_ingest(args) -> int:
    settings, conn, embedder = _setup(require_embedder=not args.no_embed)
    postings, report = load_snapshot_dir(settings.snapshot_dir)
    report.inserted, report.already_present = upsert_postings(conn, postings)
    if not args.no_embed:
        report.embedded = embed_missing(conn, embedder)
    report.total_in_db, embedded_total = count_rows(conn)
    print(report.render())
    print(f"vectors in db  : {embedded_total}")
    return 0


def cmd_query(args) -> int:
    _, conn, embedder = _setup(require_embedder=True)
    hits = run_search(conn, embedder, args.text, k=args.k)
    if not hits:
        print("no rows matched — run `make ingest` first")
        return 1
    for i, hit in enumerate(hits, 1):
        print(f"{i}. [{hit['score']:.4f}] {hit['title']} — {hit['company']}")
        print(f"   {hit['location'] or 'unspecified'} | {hit['source']} | {hit['url']}")
    return 0


def cmd_gap(args) -> int:
    from pathlib import Path

    from .resume import parse, pdf_to_text

    _, conn, embedder = _setup(require_embedder=True)
    path = Path(args.resume)
    text = pdf_to_text(path.read_bytes()) if path.suffix.lower() == ".pdf" else path.read_text()
    resume = parse(text)
    report = gap_report(conn, embedder, args.target, resume.keywords, k=args.k)
    print(f"target: {report['target']}  ({report['postings_analyzed']} postings analysed)")
    print(f"resume already covers: {', '.join(report['have']) or '(none)'}")
    print("\nmissing, most-demanded first:")
    for m in report["missing"][:15]:
        print(f"  {m['pct']:>5.1f}%  {m['term']:<18} (e.g. {m['example_posting'][:44]})")
    return 0


def cmd_stats(args) -> int:
    settings = Settings.load()
    conn = connect(settings.database_url)
    ensure_schema(conn)
    total, embedded = count_rows(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT source, count(*) AS n FROM postings GROUP BY source ORDER BY n DESC")
        by_source = cur.fetchall()
    print(f"postings: {total}   embedded: {embedded}   pending: {total - embedded}")
    for row in by_source:
        print(f"  {row['source']:<10} {row['n']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobfit", description="JobFit index CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="load snapshot files and embed new rows")
    p_ingest.add_argument("--no-embed", action="store_true", help="insert only, skip embeddings")
    p_ingest.set_defaults(func=cmd_ingest)

    p_query = sub.add_parser("query", help="semantic search over the index")
    p_query.add_argument("text")
    p_query.add_argument("-k", type=int, default=5)
    p_query.set_defaults(func=cmd_query)

    p_gap = sub.add_parser("gap", help="skills the goal role wants that the resume lacks")
    p_gap.add_argument("target")
    p_gap.add_argument("--resume", required=True, help="path to a .pdf or .txt resume")
    p_gap.add_argument("-k", type=int, default=15)
    p_gap.set_defaults(func=cmd_gap)

    p_stats = sub.add_parser("stats", help="corpus counts by source")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except EmbeddingError as exc:
        print(f"embedding error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # psycopg.OperationalError lands here: give the fix, not a traceback
        if type(exc).__name__ == "OperationalError":
            print(f"database error: {exc}\nIs the db up? Try: make up", file=sys.stderr)
            return 3
        raise


if __name__ == "__main__":  # `python -m jobfit.cli` and the `jobfit` script both work
    raise SystemExit(main())
