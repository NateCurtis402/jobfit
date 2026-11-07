"""Gap-report maths: frequency ranking and have/missing split. No DB, no model."""

from __future__ import annotations

from jobfit.gap import summarise_requirements

POSTINGS = [
    {"title": "AI Engineer", "description": "Python and Postgres. Build RAG."},
    {"title": "ML Engineer", "description": "Python, docker, kubernetes, embeddings."},
    {"title": "Data Engineer", "description": "python sql airflow"},
]


def test_terms_ranked_by_frequency():
    rows = summarise_requirements(POSTINGS, have=set())
    assert rows[0]["term"] == "python" and rows[0]["in_postings"] == 3
    assert rows[0]["pct"] == 100.0


def test_have_and_missing_are_split():
    rows = summarise_requirements(POSTINGS, have={"python", "sql"})
    have = {r["term"] for r in rows if r["have"]}
    assert have == {"python", "sql"}
    assert all(not r["have"] for r in rows if r["term"] not in have)


def test_empty_corpus_does_not_divide_by_zero():
    assert summarise_requirements([], have={"python"}) == []


def test_frequency_beats_alphabetical_at_equal_counts():
    postings = [
        {"title": "A", "description": "docker"},
        {"title": "B", "description": "kubernetes"},
    ]
    rows = summarise_requirements(postings, have=set())
    assert [r["term"] for r in rows] == ["docker", "kubernetes"]
