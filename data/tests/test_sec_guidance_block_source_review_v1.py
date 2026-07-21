import hashlib
from pathlib import Path

import pandas as pd
import pytest

from herd.sec_guidance_block_source_review_v1 import adjudicate


PROTOCOL = {"review_gate": {"minimum_stratified_rows": 2, "minimum_distinct_tickers": 2, "minimum_wilson_95_lower_bound": 0.0}}


def fixture(tmp_path: Path):
    template = tmp_path / "review.csv"
    pd.DataFrame({
        "review_id": ["A", "B"], "ticker": ["AAA", "BBB"],
        "review_decision": ["PENDING", "PENDING"], "review_reason": ["", ""],
        "reviewer": ["", ""], "reviewed_at": ["", ""],
    }).to_csv(template, index=False)
    config = {
        "review_template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
        "allowed_decisions": ["VALID", "INVALID", "AMBIGUOUS"],
        "reviewer": "TEST", "reviewed_at": "2026-07-22", "price_outcomes_observed": False,
    }
    return template, config


def test_requires_exactly_one_label_for_every_locked_row(tmp_path):
    template, config = fixture(tmp_path)
    labels = tmp_path / "labels.csv"
    pd.DataFrame({"review_id": ["A"], "review_decision": ["VALID"], "review_reason": ["OK"]}).to_csv(labels, index=False)
    with pytest.raises(ValueError, match="cover"):
        adjudicate(template, labels, config, PROTOCOL)


def test_applies_complete_review_without_opening_direction_preregistration(tmp_path):
    template, config = fixture(tmp_path)
    labels = tmp_path / "labels.csv"
    pd.DataFrame({
        "review_id": ["A", "B"], "review_decision": ["VALID", "INVALID"], "review_reason": ["OK", "WRONG"],
    }).to_csv(labels, index=False)
    rows, report = adjudicate(template, labels, config, PROTOCOL)
    assert list(rows["review_decision"]) == ["VALID", "INVALID"]
    assert report["reviewed_rows"] == 2
    assert report["price_outcomes_observed"] is False
    assert report["ready_for_direction_preregistration"] is False
