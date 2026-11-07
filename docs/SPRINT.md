# Sprint plan — 7 Nov to 27 Nov 2026

Two tracks, one repo. Track A ships JobFit; Track B files the paperwork that
pays for the certs. Track B's *courses* run into December — the sprint
deliverable is enrollment filed, not coursework finished.

## Hard gates

| Date | Gate | Why it can't slip |
|---|---|---|
| Mon 9 Nov | WIOA: ETPL list + ITA cap confirmed, Nebraska Approved Training filed | Must be ≥2 weeks before the 23 Nov course start |
| Fri 13 Nov | M1 shipped, repo public, CI green | A repo nobody can see does not exist |
| Fri 20 Nov | GLE "Enterprise Data Science in Practice" enrollment | Enrollment closes; course runs 23 Nov – 20 Dec |
| Fri 27 Nov | GLE "AI for Sustainability" enrollment | Enrollment closes; course runs 30 Nov – 27 Dec |

## Week 1 — 7–13 Nov: M1 closed, repo public

- Sat: stack up (`make up` → `make ingest` → `make query`), 111 postings embedded
- Sun: switch commit identity to GitHub noreply, push, CI badge green
- Mon: **WIOA paperwork** — press Heartland for ETPL + ITA cap, file the form
- Tue–Thu: M2 begins — `/health`, `/search`, `/match` in FastAPI
- Fri: M2 on the LAN (`http://192.168.50.208:8000/docs`), one curl example in README

## Week 2 — 14–20 Nov: M2 done, labels started

- Resume PDF → structured profile; `/match` scores postings against it
- Tool-calling agent that decides search vs. compare
- **Nero's job:** hand-label 50 query → expected-result pairs (AI formats, never labels)
- Fri 20 Nov: enroll in GLE #1

## Week 3 — 21–27 Nov: M3, metrics, publishing

- Eval harness: `hit@5`, `MRR`, judge-vs-human κ, run in CI with the score on the job summary
- README gets real numbers from a real run, plus the architecture diagram
- Fri 27 Nov: enroll in GLE #2
- Writeup: 500 words on what the evals actually measured

## Every day, same shape

- 45 min — applications (target 10/week, logged)
- 3 h — JobFit
- 30 min — self-paced cert filler (AI Literacy → Generative AI Essentials)

## Standing rules

- One repo. No new side projects until M3 has numbers.
- Nero owns: schema, labels, tests, README numbers, architecture. AI owns implementation.
- Quiz before merge; a line he cannot explain does not ship.
- No metric in the README that was not produced by a run in CI.
