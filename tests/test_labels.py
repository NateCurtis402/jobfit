"""The committed ground truth is code-adjacent, so it gets tested like code.

A malformed labels file would silently change the published metric. This runs in
CI on every push, which is why the workflow does not need a heredoc.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

LABELS_PATH = Path(__file__).resolve().parents[1] / "evals" / "labels.json"
PAYLOAD = json.loads(LABELS_PATH.read_text())
LABELS = PAYLOAD.get("labels", [])


def test_labels_file_exists_and_is_not_empty():
    assert LABELS, "evals/labels.json has no labels"


def test_label_ids_are_unique():
    ids = [entry["id"] for entry in LABELS]
    assert len(ids) == len(set(ids)), "duplicate label ids"


def test_every_label_has_a_query_and_targets():
    bad = [e["id"] for e in LABELS if not e.get("query") or not e.get("target_ids")]
    assert not bad, f"labels missing a query or targets: {bad}"


def test_targets_are_ints_and_positive():
    for entry in LABELS:
        for target in entry["target_ids"]:
            assert isinstance(target, int) and target > 0, f"{entry['id']}: bad target {target!r}"


def test_queries_are_distinct():
    queries = [e["query"].strip().lower() for e in LABELS]
    assert len(queries) == len(set(queries)), "the same query is labeled twice"


@pytest.mark.parametrize("field", ["id", "query", "target_ids", "labeled_at"])
def test_required_fields_present(field):
    missing = [e.get("id", "?") for e in LABELS if field not in e]
    assert not missing, f"labels missing {field}: {missing}"
