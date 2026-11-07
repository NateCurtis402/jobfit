"""Re-fetch live boards into data/snapshot/. Network only; no database needed.

Both boards are free and keyless. Their terms require attribution, which lives in
data/SOURCES.md and the README.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

import httpx

SNAPSHOT_DIR = pathlib.Path(__file__).resolve().parents[1] / "data" / "snapshot"
HEADERS = {"User-Agent": "jobfit/0.1 (portfolio project; contact via github)"}

FEEDS = {
    "remotive": "https://remotive.com/api/remote-jobs?category=software-dev&limit=100",
    "remoteok": "https://remoteok.com/api",
}


def fetch(name: str, url: str) -> dict:
    with httpx.Client(timeout=45, headers=HEADERS, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        data = r.json()
    # Remotive returns {"jobs": [...]}; RemoteOK returns a bare list whose first item is a notice.
    jobs = data["jobs"] if isinstance(data, dict) else [x for x in data if x.get("id")]
    return {
        "source": name,
        "fetched_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "source_url": url,
        "jobs": jobs,
    }


def main() -> int:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    for name, url in FEEDS.items():
        try:
            payload = fetch(name, url)
        except (httpx.HTTPError, ValueError) as exc:
            print(f"{name}: FAILED ({exc}) — keeping the existing snapshot")
            continue
        path = SNAPSHOT_DIR / f"{name}_{stamp}.json"
        path.write_text(json.dumps(payload, indent=1))
        print(f"{name}: {len(payload['jobs'])} records -> {path.relative_to(SNAPSHOT_DIR.parents[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
