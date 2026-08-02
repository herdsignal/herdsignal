import copy
import csv
import json

import pytest

from herd.sec_8k_hard_adverse_event_corpus_v1 import (
    PROTOCOL_PATH,
    Sec8KHardAdverseCorpusError,
    build,
)


def _protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_current_corpus_matches_locked_inventory() -> None:
    rows, report = build(_protocol())
    assert len(rows) == 947
    assert report["source_issuer_count"] == 263
    assert report["price_outcomes_opened"] is False
    assert report["direction_hypothesis_allowed"] is False
    assert report["operational_action_ratio"] == 0.0


def test_corpus_has_no_price_or_outcome_columns() -> None:
    rows, _ = build(_protocol())
    forbidden = {"price", "return", "outcome", "label", "herd_score"}
    assert not forbidden & set(rows[0])
    assert all(row["accepted_at"] for row in rows)


def test_action_authority_cannot_be_enabled() -> None:
    protocol = copy.deepcopy(_protocol())
    protocol["authority"]["operational_action_ratio"] = 0.05
    with pytest.raises(Sec8KHardAdverseCorpusError):
        build(protocol)


def test_written_ledger_matches_builder() -> None:
    rows, _ = build(_protocol())
    with open(
        "data/reports/sec_8k_hard_adverse_event_corpus_v1.csv",
        newline="",
        encoding="utf-8",
    ) as handle:
        persisted = list(csv.DictReader(handle))
    assert persisted == rows
