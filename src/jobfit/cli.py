"""Command line entrypoint: ingest, query, stats."""

from __future__ import annotations

import argparse
import sys
import time

import psycopg

from .config import Settings
from .db import connect, ensure_schema
from .embed import EmbeddingError, OllamaEmbedder
from .evals import DEFAULT_LABELS, evaluate, load_labels
from .gap import gap_report
from .ingest import (
    clear_embeddings,
    count_rows,
    embed_missing,
    load_snapshot_dir,
    upsert_postings,
)
from .search import search as run_search
from .watch import DEFAULT_PROFILE, find_matches, render_digest


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
    if getattr(args, "reembed", False):
        n = clear_embeddings(conn)
        print(f"cleared {n} embeddings (re-embedding everything)")
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
    hits = run_search(conn, embedder, args.text, k=args.k, mode=args.mode)
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


def cmd_label(args) -> int:
    """Interactive labeling: show the top hits for a query, record which are relevant."""
    import datetime as dt
    import json
    from pathlib import Path

    _, conn, embedder = _setup(require_embedder=True)
    queries = [q.strip() for q in Path(args.queries).read_text().splitlines() if q.strip()]
    path = Path(args.labels)
    payload = {"labels": []}
    if path.exists():
        payload = json.loads(path.read_text())
    done = {entry["query"] for entry in payload["labels"]}
    todo = [q for q in queries if q not in done]
    if not todo:
        print(f"all {len(queries)} queries already labeled in {path}")
        return 0
    print(f"{len(todo)} of {len(queries)} queries to label. y = relevant, n = not, q = stop and save.\n")
    for query in todo:
        # The database container can be recreated under us (compose config
        # change, host restart). Postgres drops every live connection when that
        # happens, so reconnect instead of losing the labeling session.
        for attempt in (1, 2):
            try:
                hits = run_search(conn, embedder, query, k=10)
                break
            except psycopg.OperationalError:
                if attempt == 2:
                    print(
                        "\ndatabase went away twice — answers up to the last completed "
                        f"query are saved in {path}. Rerun to resume."
                    )
                    return 3
                print("\ndatabase connection dropped; reconnecting and retrying this query...")
                time.sleep(2)
                fresh = Settings.load()
                conn = connect(fresh.database_url)
                ensure_schema(conn)
        print(f"\n=== {query} ===")
        for i, h in enumerate(hits, 1):
            print(f"  {i:>2}. [{h['score']:.3f}] {h['title'][:56]} — {h['company'][:26]} ({h['location'][:24]})")
        keep = []
        for i, h in enumerate(hits, 1):
            ans = input(f"  keep #{i}? [y/N/q] ").strip().lower()
            if ans == "q":
                path.write_text(json.dumps(payload, indent=1))
                print(f"\nsaved {len(payload['labels'])} labels -> {path}")
                return 0
            if ans in ("y", "yes"):
                keep.append(int(h["id"]))
        payload["labels"].append(
            {
                "id": f"q{len(payload['labels']) + 1:03d}",
                "query": query,
                "target_ids": keep,
                "labeled_by": "nate",
                "labeled_at": dt.date.today().isoformat(),
            }
        )
        path.write_text(json.dumps(payload, indent=1))
    print(f"\nsaved {len(payload['labels'])} labels -> {path}")
    return 0


def cmd_eval(args) -> int:
    from .evals import render

    _, conn, embedder = _setup(require_embedder=True)
    labels = load_labels(args.labels)
    if not labels:
        print(f"no labeled queries in {args.labels} — run: make label")
        return 1
    result = evaluate(conn, embedder, labels)
    print(render(result))
    best_mode = max(result["metrics"], key=lambda m: result["metrics"][m]["hit@5"])
    hit5 = result["metrics"][best_mode]["hit@5"]
    if args.min_hit5 and hit5 < args.min_hit5:
        print(f"\nFAIL: best hit@5 {hit5:.3f} ({best_mode}) is below the floor {args.min_hit5:.3f}")
        return 1
    return 0


def cmd_watch(args) -> int:
    _, conn, embedder = _setup(require_embedder=True)
    rows = find_matches(
        conn,
        embedder,
        profile=args.profile,
        min_score=args.min_score,
        limit=args.limit,
        days=args.days,
        dry_run=args.dry_run,
        exclude_senior=not args.include_senior,
    )
    if args.dry_run:
        print(f"(dry run — nothing marked as sent) {len(rows)} match(es)\n")
    print(render_digest(rows, args.profile))
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
    p_ingest.add_argument(
        "--reembed", action="store_true", help="rebuild every vector (after a model or prefix change)"
    )
    p_ingest.set_defaults(func=cmd_ingest)

    p_query = sub.add_parser("query", help="semantic search over the index")
    p_query.add_argument("text")
    p_query.add_argument("-k", type=int, default=5)
    p_query.add_argument("--mode", choices=["semantic", "lexical", "hybrid"], default="semantic")
    p_query.set_defaults(func=cmd_query)

    p_gap = sub.add_parser("gap", help="skills the goal role wants that the resume lacks")
    p_gap.add_argument("target")
    p_gap.add_argument("--resume", required=True, help="path to a .pdf or .txt resume")
    p_gap.add_argument("-k", type=int, default=15)
    p_gap.set_defaults(func=cmd_gap)

    p_eval = sub.add_parser("eval", help="score retrieval against hand-labeled queries")
    p_eval.add_argument("--labels", type=str, default=str(DEFAULT_LABELS))
    p_eval.add_argument("--min-hit5", type=float, default=0.0, dest="min_hit5")
    p_eval.set_defaults(func=cmd_eval)

    p_label = sub.add_parser("label", help="label query -> relevant postings, interactively")
    p_label.add_argument("--queries", type=str, default="evals/queries.txt")
    p_label.add_argument("--labels", type=str, default=str(DEFAULT_LABELS))
    p_label.set_defaults(func=cmd_label)

    p_watch = sub.add_parser("watch", help="new postings matching a profile (daily digest)")
    p_watch.add_argument("--profile", default=DEFAULT_PROFILE)
    p_watch.add_argument("--min-score", type=float, default=0.62, dest="min_score")
    p_watch.add_argument("--limit", type=int, default=8)
    p_watch.add_argument("--days", type=int, default=45)
    p_watch.add_argument("--dry-run", action="store_true", dest="dry_run")
    p_watch.add_argument(
        "--include-senior", action="store_true", help="do not hide senior/lead/director titles"
    )
    p_watch.set_defaults(func=cmd_watch)

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
