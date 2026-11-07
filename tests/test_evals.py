"""Metric maths for the eval harness. No DB, no model — pure ranking."""

from __future__ import annotations

from jobfit.evals import first_hit_rank, hit_at, reciprocal_rank, summarise


def test_first_hit_rank_is_one_based():
    assert first_hit_rank([9, 4, 7], {4}) == 2
    assert first_hit_rank([4, 9], {4}) == 1


def test_first_hit_rank_none_when_absent():
    assert first_hit_rank([1, 2, 3], {99}) is None


def test_hit_at_boundary():
    assert hit_at(5, 5) is True
    assert hit_at(6, 5) is False
    assert hit_at(None, 5) is False


def test_reciprocal_rank():
    assert reciprocal_rank(1) == 1.0
    assert reciprocal_rank(4) == 0.25
    assert reciprocal_rank(None) == 0.0


def test_summarise_aggregates_correctly():
    rows = [{"rank": 1}, {"rank": 3}, {"rank": 7}, {"rank": None}]
    m = summarise(rows)
    assert m["n"] == 4
    assert m["hit@5"] == 0.5          # ranks 1 and 3
    assert m["hit@10"] == 0.75        # plus rank 7
    assert m["mrr"] == round((1 + 1 / 3 + 1 / 7 + 0) / 4, 4)


def test_summarise_empty_does_not_divide_by_zero():
    assert summarise([])["hit@5"] == 0.0


def test_profile_tsquery_builds_or_query():
    from jobfit.watch import profile_tsquery

    q = profile_tsquery("junior python backend, sql and postgres")
    assert " | " in q
    assert "python" in q and "postgres" in q


def test_profile_tsquery_empty_when_no_known_terms():
    from jobfit.watch import profile_tsquery

    assert profile_tsquery("anything at all please") == ""
