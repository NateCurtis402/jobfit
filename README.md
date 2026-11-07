# JobFit

**What this is, and why:** an Omaha-area job search you can query in plain English.
Job boards give you a list sorted by date. JobFit gives you a ranked list sorted by
*how close a posting is to the work you actually want* — semantic search over an
embedded corpus, built to run entirely on one home server with no paid APIs.

Built by a Marine Corps logistics veteran (0621/0627, GCSS) switching into
AI/software engineering. The interesting part is not the search box; it is the
eval harness in M3 that measures whether the search actually works.

## Status

| Milestone | Scope | State |
|---|---|---|
| M1 | ingest postings → embed → queryable index | **done** — 111 postings, 111 embedded |
| M2 | FastAPI `/search` + `/match`, function-calling agent, OpenAPI docs | **done** — live on the LAN |
| M3 | eval harness: 50 hand-labeled query→result pairs, hit-rate in CI | not started |

No metrics are published yet on purpose. M3 produces them; until then the README
stays empty of numbers rather than full of invented ones.

## It runs as a service

```bash
make api-install     # systemd user unit, survives logout, restarts on failure
make api-logs
```

Live on the LAN: **http://192.168.50.208:8000/docs** (the clickable API page).

```bash
curl -s "http://192.168.50.208:8000/health"
curl -s "http://192.168.50.208:8000/search?q=python%20data%20pipeline&k=3"
curl -s -X POST http://192.168.50.208:8000/match \
  -H 'Content-Type: application/json' \
  -d '{"resume_text":"Logistics veteran. Python, SQL, Postgres, Docker.","k":5}'
curl -s -X POST http://192.168.50.208:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Are there any AI or LLM engineer roles here?"}'
```

`/match` takes `rank_by: "semantic" | "hybrid"`. Semantic-only is the baseline;
hybrid adds a small bonus per skill the resume and the posting share. Both are
kept because M3 measures which one actually wins instead of guessing.

## Architecture

```
data/snapshot/*.json  ──┐
  remotive (12)         │  normalize + dedupe by content hash
  remoteok (99)         ├─► Posting dataclass ──► Postgres 17 + pgvector
  adzuna  (M2, keyed)   │                            │
                        │                            ├── postings.embedding VECTOR(768)
                        │                            │   HNSW index, cosine distance
                        │                            │
  query text ───────────┴─► Ollama nomic-embed-text ─┴─► ORDER BY embedding <=> query
                                                          (local GPU, $0, no egress)
```

Why these choices:
- **pgvector over a separate vector DB** — one datastore for rows *and* vectors, so
  filters (location, date, source) stay in SQL. It is also the vector store most
  job postings actually name.
- **Local Ollama embeddings** — no API key, no per-query cost, and the corpus never
  leaves the house. `nomic-embed-text` is 768-dim and fast on a 12 GB card.
- **One vector per posting, first 4000 chars** — postings are short; chunking is a
  complication to earn later, not to start with.
- **Committed snapshot + `make refresh`** — the demo works offline on a recruiter's
  laptop. A live-scraping demo that breaks is worse than no demo.
- **Deduped by content hash, not board id** — the same job on two boards is one job.

## Quickstart

```bash
make venv                 # python deps into .venv (editable install)
cp .env.example .env      # dev-only values
make up                   # Postgres 17 + pgvector on 127.0.0.1:5432
make ingest               # embed the snapshot corpus
make query q="postgres etl pipeline python"
make stats
```

Requires: Docker, Python 3.11+, and Ollama with an embedding model:

```bash
ollama pull nomic-embed-text
```

## Data sources

See [data/SOURCES.md](data/SOURCES.md). Both boards are free and keyless;
attribution is required and kept there.

## Roadmap

- **M2** — FastAPI (`/search`, `/match`, `/health`), resume PDF → structured profile,
  a tool-calling agent that decides when to search vs. when to compare, OpenAPI docs.
- **M3** — `evals/` with 50 hand-labeled query→expected-result pairs, `hit@5`, `MRR`,
  and κ between a local LLM judge and the hand labels. Runs in CI on every push.

## License

MIT — see [LICENSE](LICENSE).
