"""Fetch Omaha-area postings from Adzuna into a dated snapshot.

Adzuna needs app_id + app_key in .env (free key from developer.adzuna.com).
Credentials are read from Settings and never printed, logged or written to the
snapshot. Free tier is ~25 req/min, 250/day, 2,500/month — this script uses ~10.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from jobfit.config import Settings

SNAPSHOT_DIR = pathlib.Path(__file__).resolve().parents[1] / "data" / "snapshot"
API = "https://api.adzuna.com/v1/api/jobs/us/search"
QUERIES = ("software engineer", "data engineer", "python developer", "AI engineer", "data analyst")
WHERE = "Omaha"
PAGES = (1, 2)
PER_PAGE = 50


def main() -> int:
    settings = Settings.load()
    if not (settings.adzuna_app_id and settings.adzuna_app_key):
        print("ADZUNA_APP_ID / ADZUNA_APP_KEY missing from .env — nothing to do")
        return 1

    jobs: list[dict] = []
    total_available = 0
    seen: set[str] = set()
    with httpx.Client(timeout=45) as client:
        for what in QUERIES:
            for page in PAGES:
                params = {
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "what": what,
                    "where": WHERE,
                    "results_per_page": PER_PAGE,
                    "content-type": "application/json",
                    "max_days_old": 60,
                    # NOTE: the page number lives in the URL path, not the query
                    # string — sending "page" as a parameter returns 400.
                }
                try:
                    r = client.get(f"{API}/{page}", params=params)
                    r.raise_for_status()
                except httpx.HTTPError as exc:
                    print(f"{what} p{page}: FAILED ({type(exc).__name__}) — stopping this query")
                    break
                data = r.json()
                total_available += data.get("count", 0)
                got = 0
                for job in data.get("results", []):
                    key = str(job.get("id"))
                    if key in seen:
                        continue
                    seen.add(key)
                    jobs.append(job)
                    got += 1
                print(f"{what} p{page}: {got} new (of {len(data.get('results', []))} returned)")

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"adzuna_{WHERE.lower()}_{dt.date.today().isoformat()}.json"
    path.write_text(
        json.dumps(
            {
                "source": "adzuna",
                "fetched_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                "source_url": f"{API} (app_id/key withheld)",
                "attribution": "https://www.adzuna.com",
                "where": WHERE,
                "jobs": jobs,
            },
            indent=1,
        )
    )
    print(f"\nsaved {len(jobs)} unique postings -> {path.name}")
    print(f"adzuna reports up to {total_available} matches across {len(QUERIES)} queries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
