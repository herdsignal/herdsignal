import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from herd.herd_state_s1 import (
    FAMILY_COLUMNS,
    HerdStateS1Error,
    _peer_breadth,
    _rolling_percentile,
    _stage,
    load_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/herd/herd_state_s1.json"


def test_contract_is_outcome_blind_and_reference_only() -> None:
    contract = load_contract(CONTRACT)
    assert contract["observation_contract"]["future_outcomes_allowed"] is False
    assert contract["claim_boundary"]["operational_action_ratio"] == 0.0
    assert contract["legacy_boundary"] == {
        "HERD_V4": "REFERENCE_ONLY_NO_FORMULA_OR_WEIGHT_REUSE",
        "HERD_V6_1": "REFERENCE_ONLY_NO_FORMULA_OR_WEIGHT_REUSE",
    }
    assert [item["id"] for item in contract["families"]] == FAMILY_COLUMNS


def test_rolling_percentile_uses_only_trailing_values() -> None:
    original = pd.Series([1.0, 2.0, 3.0, 2.0, 5.0])
    changed_future = original.copy()
    changed_future.iloc[-1] = -100.0
    left = _rolling_percentile(original, window=3, minimum=2)
    right = _rolling_percentile(changed_future, window=3, minimum=2)
    pd.testing.assert_series_equal(left.iloc[:-1], right.iloc[:-1])
    assert left.iloc[-1] != right.iloc[-1]


def test_stage_boundaries_are_stable() -> None:
    values = pd.Series([0, 14.99, 15, 39.99, 40, 59.99, 60, 74.99, 75, 100])
    assert _stage(values).tolist() == [
        "FLEE",
        "FLEE",
        "SCATTER",
        "SCATTER",
        "CALM",
        "CALM",
        "DRIFT",
        "DRIFT",
        "RUSH",
        "RUSH",
    ]


def test_contract_rejects_action_authority(tmp_path: Path) -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    payload["claim_boundary"]["operational_action_ratio"] = 0.05
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(HerdStateS1Error, match="authorize actions"):
        load_contract(path)


def test_equal_family_aggregation_is_not_legacy_weighted() -> None:
    family_values = pd.DataFrame(
        {column: [10.0 + index * 10] for index, column in enumerate(FAMILY_COLUMNS)}
    )
    score = family_values[FAMILY_COLUMNS].mean(axis=1)
    assert np.isclose(score.iloc[0], 25.0)


def test_peer_breadth_keeps_warmup_period_missing() -> None:
    dates = pd.bdate_range("2020-01-01", periods=260)
    frames = {}
    mapping = {}
    for index, ticker in enumerate(("AAA", "BBB", "CCC")):
        frames[ticker] = pd.DataFrame(
            {
                "Date": dates,
                "Adj Close": np.linspace(100 + index, 150 + index, len(dates)),
            }
        )
        mapping[ticker] = "XLK"
    breadth = _peer_breadth(frames, mapping)["XLK"]
    assert breadth.iloc[:199].isna().all()
    assert breadth.iloc[-1] == 1.0
