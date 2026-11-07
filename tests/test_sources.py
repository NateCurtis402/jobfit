"""Unit tests for the normalization layer. No DB, no network, no model."""

from __future__ import annotations

from jobfit.sources import (
    Posting,
    dedupe,
    from_remoteok,
    from_remotive,
    html_to_text,
    parse_snapshot,
)

REMOTIVE_REC = {
    "id": 1185979,
    "title": "Backend Engineer",
    "company_name": "Acme",
    "candidate_required_location": "USA Only",
    "url": "https://remotive.com/remote-jobs/software-dev/backend-1185979",
    "description": "<p>Build <b>ETL</b> pipelines.</p><script>track()</script><p>Python.</p>",
    "tags": ["python", "postgres"],
    "publication_date": "2026-11-04T16:53:35",
    "salary": "$120k",
}


def test_html_to_text_strips_tags_and_scripts():
    text = html_to_text(REMOTIVE_REC["description"])
    assert "<" not in text and "track()" not in text
    assert "ETL" in text and "Python." in text


def test_html_to_text_handles_empty():
    assert html_to_text("") == ""


def test_from_remotive_maps_fields():
    p = from_remotive(REMOTIVE_REC)
    assert (p.source, p.external_id) == ("remotive", "1185979")
    assert p.company == "Acme"
    assert p.tags == ("python", "postgres")
    assert p.posted_at is not None and p.posted_at.year == 2026


def test_content_hash_ignores_board_but_not_content():
    a = from_remotive(REMOTIVE_REC)
    b = from_remotive({**REMOTIVE_REC, "id": 999, "url": "https://elsewhere"})
    assert a.content_hash == b.content_hash  # same job, different board id
    c = from_remotive({**REMOTIVE_REC, "title": "Data Engineer"})
    assert a.content_hash != c.content_hash


def test_embedding_text_leads_with_title_company_tags():
    text = from_remotive(REMOTIVE_REC).embedding_text
    assert text.startswith("Backend Engineer at Acme.")
    assert "python, postgres" in text


def test_embedding_text_is_bounded():
    big = Posting(source="x", external_id="1", title="T", company="C", description="a" * 20000)
    assert len(big.embedding_text) < 4200


def test_parse_snapshot_skips_board_metadata():
    payload = {
        "source": "remoteok",
        "jobs": [
            {"legal": "link back to remoteok.com", "last_updated": 1},
            {"id": "1", "position": "Data Engineer", "company": "Beta", "description": "<p>x</p>"},
            {"id": "2", "position": "", "company": "NoTitle"},
        ],
    }
    postings = parse_snapshot(payload)
    assert len(postings) == 1
    assert postings[0].title == "Data Engineer"


def test_parse_snapshot_rejects_unknown_source():
    try:
        parse_snapshot({"source": "indeed", "jobs": []})
    except ValueError as exc:
        assert "unknown source" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_dedupe_keeps_first_and_counts_drops():
    a = from_remotive(REMOTIVE_REC)
    b = from_remotive({**REMOTIVE_REC, "id": 2})
    kept, dropped = dedupe([a, b])
    assert len(kept) == 1 and dropped == 1


def test_iso_dates_with_utc_offset_parse():
    """RemoteOK sends 2026-11-06T00:00:11+00:00; a naive %Y-%m-%dT%H:%M:%S misses all of them."""
    p = from_remoteok(
        {"id": "9", "position": "Platform Engineer", "company": "Gamma",
         "date": "2026-11-06T00:00:11+00:00", "description": "x"}
    )
    assert p.posted_at is not None and p.posted_at.isoformat() == "2026-11-06"


def test_unparseable_date_becomes_none_not_a_guess():
    p = from_remoteok({"id": "9", "position": "T", "company": "C", "date": "last tuesday"})
    assert p.posted_at is None


def test_mojibake_is_repaired_cp1252_variant():
    """Boards that decoded UTF-8 as cp1252 produce â€™ / â€“."""
    fixed = html_to_text("<p>weâ€™re hiring â€“ remote</p>")
    assert "we’re hiring – remote" in fixed


def test_mojibake_is_repaired_c1_control_variant():
    """Boards that decoded UTF-8 as latin-1 leave C1 controls (U+0080-U+009F)."""
    broken = "we\u00e2\u0080\u0099re hiring"
    assert "we’re hiring" in html_to_text(f"<p>{broken}</p>")


def test_healthy_unicode_is_untouched():
    text = html_to_text("<p>Café role — déjà vu</p>")
    assert "Café role — déjà vu" in text
