# Resume draft — technical section

Evidence for every line is in `docs/EVIDENCE.md`. Nothing here is aspirational.
No contact details in this file: this one is safe to commit, the real CV is not.

## Paste-ready block

```
TECHNICAL SKILLS
Languages:      Python (intermediate), SQL, Bash
Data:           PostgreSQL, pgvector (HNSW, cosine similarity), embeddings,
                semantic search, data normalization and deduplication
Web / API:      FastAPI, REST, OpenAPI, Pydantic
Tooling:        Docker, Docker Compose, Linux, systemd, git, GitHub Actions
Domain:         Logistics operations (GCSS-MC), inventory reconciliation,
                records management, Excel / Power BI reporting
```

Why phrased this way:
- **"Python (intermediate)"** is honest and still passes a keyword filter. A
  recruiter's screen is a string match; the interview is where you prove depth.
  Overclaiming here is the fastest way to lose the room.
- **pgvector / HNSW / cosine** are the words that make a reviewer stop scrolling,
  because they are specific and most candidates cannot explain them. You can —
  you have the code and this document.
- **Domain line stays in.** GCSS, inventory and records management are rare in a
  software candidate pool and are the reason an ops-heavy employer picks you over
  a bootcamp graduate.

## Personal infrastructure (homelab) — for the ops/DevOps angle

Label this section **"Personal Infrastructure (homelab)"** and never let it read as
employment. It is self-directed work on real hardware, and the specifics are what
make it count: 14 services, nine months of uptime, named failures diagnosed.

```
PERSONAL INFRASTRUCTURE (self-hosted, Jan 2026 - present)
- Operate an Ubuntu server running 14 Docker services (media, DNS filtering,
  VPN, secrets management, home automation) with restart policies and
  health checks; ~9 months continuous operation.
- Diagnosed a host-wide container DNS failure by isolating Docker's embedded
  resolver against direct upstream queries, then fixed it at the daemon level.
- Deploy applications as systemd user services with dependency ordering and
  automatic restart; manage cross-user file access with POSIX ACLs.
- Run local LLM inference on a 12 GB GPU (Ollama) serving embedding and
  tool-calling models to an application API at zero inference cost.
- Maintain nightly backups with restic and verify them with restore drills.
```

Why this is worth real space on the page: it is the only place a hiring manager
sees Linux and Docker **run by you, unattended, for months**, with failures you
found and fixed. "Familiar with Linux" is a claim; "14 containers, nine months,
here is the DNS bug I chased down" is evidence. Do not inflate the months — the
server's install date says January, and anyone technical will ask.

## Bullets (use 2, keep the third for the tech-only version)

- Built **JobFit**, a retrieval service that indexes 111 job postings and ranks
  them against a resume; runs entirely on a home server with locally hosted
  embeddings, no paid APIs.
- Designed normalization and deduplication for job data from two sources,
  including encoding repair (cp1252/latin-1 mojibake) and date-format variation,
  raising date-parse coverage from 0 to 111/111 records.
- Shipped it as a systemd service behind a FastAPI + PostgreSQL/pgvector API,
  with 28 automated tests covering text normalization, ranking maths and
  model output handling.

## Week-3 upgrades (swap in when the numbers exist)

- Add the eval result: "hit@5 of X across 50 hand-labeled query→result pairs,
  with judge-vs-human agreement κ = Y."
- Add latency and cost: "answers in Z s on consumer hardware at $0 inference
  cost."
- Then state the claim once, plainly, in the summary: you built a measured
  retrieval system, not a tutorial.

## Deliberately not claimed

- "3+ years of Python" — not true, and unverifiable.
- "CI/CD pipeline" — the workflow file exists; no badge has ever run.
- Omaha job-market coverage — corpus is remote-only until Adzuna is wired.
