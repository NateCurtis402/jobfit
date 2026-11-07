# Evidence log

Every resume bullet gets its source here first. If a claim is not in this file,
it does not go on the resume. Append to it as work ships — the week-3 resume is
extracted from this, not remembered.

Rule: the number and the commit are the proof. "Familiar with X" is not evidence;
"X, doing Y, measured Z" is.

## JobFit — M1, index (7 Nov 2026, commits f330a55, c65ffd0)
- Built an ingest pipeline that normalizes job postings from two different APIs
  into one record shape, dedupes the same job appearing on both boards by
  content hash, and embeds them for semantic search.
- Corpus: **111 real postings** (99 RemoteOK + 12 Remotive), **111/111 embedded**.
- Storage: PostgreSQL 17 + pgvector, `VECTOR(768)`, HNSW index with cosine distance.
- Embeddings run locally on a 12 GB GPU (nomic-embed-text via Ollama) — zero API
  cost, no data leaves the house.
- Semantic search returns ranked hits in **one SQL statement**; sample query
  "build retrieval augmented generation features with LLMs" returned AI Engineer
  roles at 0.63 / 0.63 similarity.

## JobFit — M2, service (7 Nov 2026, commit 5191dda)
- FastAPI service with `/health`, `/search`, `/match`, `/match/upload`, `/ask`,
  auto-generated OpenAPI docs; deployed as a **systemd user service** on the LAN
  at port 8000, restart-on-failure, starts its own database first.
- Resume matching: section-aware chunking (17 chunks on a real 2-page CV),
  max-over-chunks cosine similarity computed in a single SQL cross join.
- Added a **tool-calling agent** over the local model (llama3.1:8b) that chooses
  between search and match; end-to-end answer in **3.8 s** on consumer hardware.
- **28 automated tests**, ruff clean; tests cover text normalization, date
  parsing across three formats, keyword word-boundary behaviour, agent output
  coercion, and gap-ranking maths.

## JobFit — M2.5, gap report (7 Nov 2026, commit b4caa84)
- Built a "gap report": given a goal role and a resume, ranks the concrete
  skills the role demands that the resume never mentions. Real output on a
  DoD-operations CV targeting "AI Engineer": python 20%, api 13.3%, rest 13.3%.
- Exposed as both a REST endpoint and a CLI command.

## Debugging evidence (interview material — these are the real stories)
- **Encoding:** scraped descriptions arrived as UTF-8 decoded as cp1252 *and* as
  latin-1, in the same corpus. Wrote a per-run repair that only accepts a fix if
  the result is clean, so healthy text is untouched. 723 mojibake markers → 0.
- **Dates:** RemoteOK sends ISO-8601 with a UTC offset; a naive
  `%Y-%m-%dT%H:%M:%S` parse silently produced NULL for all 99 records. Caught by
  printing date-parse coverage against real data → 111/111 after the fix.
- **Row factory:** the connection pool returned tuples while the query code read
  columns by name, so every request 500'd. Fixed at the pool, not per query.
- **Serialization:** tool results embedded Postgres `date` objects, which JSON
  refuses; added a converter rather than stringifying by hand in three places.
- **Model behaviour:** `qwen2.5-coder:7b` emits tool calls as JSON *text* instead
  of structured `tool_calls`. Added a coercion path instead of switching models
  and hoping.

## Evals — first real numbers, not yet publishable (7 Nov 2026)
- 3 hand-labeled queries (Nero), semantic mode: **hit@5 = 1.000, hit@10 = 1.000,
  MRR = 0.750**; lexical 0.667 / 0.500; hybrid 0.667 / 0.722.
- **n=3. This is not a metric yet** — 3 queries cannot distinguish a good system
  from a lucky one. It becomes a published number at 20+ hand labels.
- What the harness already proved: adding the model's task prefixes
  (`search_query:` / `search_document:`) took dense retrieval from hit@5 = 0.000
  to 1.000 on the same queries. That is a measured improvement, not a vibe.

## Homelab (verified facts, 7 Nov 2026)
- Root filesystem and Docker engine installed **2026-01-20**; **14 containers
  running** as of 2026-11-07 → ~9.5 months of continuous self-hosted operation.
- Diagnosed broken container name-resolution across every container (embedded
  resolver 127.0.0.11 timing out; direct upstream queries fine) and fixed it at
  the daemon level with a DNS override.
- Deployed a FastAPI application as a systemd user service with a non-destructive
  ExecStartPre, restart-on-failure, and dependency ordering.
- Managed cross-user access on a shared repository with POSIX ACLs, including
  diagnosing that a directory ACL is useless without traverse permission on its
  parent — after breaking my own access to the tree.

## Daily watcher (7 Nov 2026, commit 9df1db7)
- Built a scheduled job that refreshes live job feeds, embeds new postings, and
  reports only postings never sent before, tracked in a Postgres table so a job
  is delivered exactly once. Runs with no model call, so it costs $0 per day.

## Pending — do not claim until true
- Eval harness numbers (hit@5, MRR, judge-vs-human agreement) — M3.
- "CI green" — the workflow file exists, but the repo is not public yet, so it
  has never run. Do not write "CI passing" until a badge shows it.
- Omaha-area coverage — the corpus is remote-only until an Adzuna key is added.
