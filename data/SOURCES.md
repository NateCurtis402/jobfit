# Data sources and attribution

Both feeds are free, keyless, and require a link back to the source. That
attribution is a term of use, not a courtesy — keep these links in the README
and in any UI built on this data.

| Source | Endpoint | Terms | Records in snapshot |
|---|---|---|---|
| Remotive | `https://remotive.com/api/remote-jobs?category=software-dev` | Link back to remotive.com | 12 (their free API caps responses; `limit` is ignored) |
| RemoteOK | `https://remoteok.com/api` | Link back to remoteok.com, followable | 99 |

Notes:
- Both are **remote-only** boards. Omaha-local postings need a source with local
  coverage — Adzuna's free tier (key you sign up for yourself) is the M2 target.
  Until then the corpus is a pipeline proof, not an Omaha market survey. Say so
  wherever results are shown.
- Snapshots are dated files under `data/snapshot/`, regenerated with `make refresh`.
  They are committed so the demo runs offline.
- Descriptions are stored as plain text (tags stripped). Job text remains the
  property of the posting employer.

## Known limitations

- 111 postings is a small corpus; nearest-neighbour results will be coarse until
  Adzuna (and later USAJobs for federal/veteran-preference roles) is wired in.
- No Omaha-specific geographic filter yet: `candidate_required_location` is
  free text ("USA Only", "Worldwide"), so it is stored and displayed, not queried.
