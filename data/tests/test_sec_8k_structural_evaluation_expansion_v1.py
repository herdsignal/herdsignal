import copy
import json

import pytest

from herd.sec_8k_structural_evaluation_expansion_v1 import (
    PROTOCOL,
    Sec8KStructuralEvaluationExpansionError,
    build,
)


def test_expansion_freezes_large_independent_population() -> None:
    rows, report = build()

    assert len(rows) == 185
    assert report["issuers"] == 101
    assert report["development_accession_overlap"] == 0
    assert report["prior_unseen_review_overlap"] == 0
    assert report["canonical_symbols_exposed"] == 0
    assert report["selection_uses_price_or_return_outcomes"] is False
    assert report["identity_promotion_allowed"] is False
    assert report["operational_action_ratio"] == 0.0


def test_expansion_queue_contains_only_collection_fields() -> None:
    rows, _ = build()

    assert all("canonical_symbol_at_filing" not in row for row in rows)
    assert all(row["primary_document_url"].startswith("https://www.sec.gov/") for row in rows)
    assert all(row["collection_status"] == "PENDING" for row in rows)


def test_expansion_rejects_action_authority(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(protocol)
    changed["authority"]["operational_action_ratio"] = 0.05
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(Sec8KStructuralEvaluationExpansionError, match="fail-closed"):
        build(path)
