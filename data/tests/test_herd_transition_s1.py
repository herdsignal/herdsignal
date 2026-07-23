import json
from pathlib import Path

import pandas as pd
import pytest

from herd.herd_state_s1 import FAMILY_COLUMNS
from herd.herd_transition_s1 import (
    HerdTransitionS1Error,
    _stabilize_directional_labels,
    classify_transitions,
    load_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/herd/herd_transition_s1.json"


def _panel(values: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2020-01-03", periods=len(values), freq="W-FRI")
    frame = pd.DataFrame(
        {
            "ticker": "TEST",
            "signal_date": dates,
            "HERD_STATE": values,
            "HERD_STAGE": "CALM",
        }
    )
    for family in FAMILY_COLUMNS:
        frame[family] = values
    return frame


def test_contract_is_outcome_blind_and_actionless() -> None:
    contract = load_contract(CONTRACT)
    assert contract["observation_contract"]["future_outcomes_allowed"] is False
    assert contract["claim_boundary"]["operational_action_ratio"] == 0.0


def test_breaking_uses_only_trailing_state() -> None:
    contract = load_contract(CONTRACT)
    values = [80.0] * 13 + [78.0, 75.0, 70.0, 65.0, 60.0]
    result = classify_transitions(_panel(values), contract)
    assert result.iloc[-1]["RAW_HERD_TRANSITION"] == "BREAKING"
    assert result.iloc[-1]["HERD_TRANSITION"] == "BREAKING"
    assert result.iloc[-1]["FAMILY_DOWN_VOTES"] == 4


def test_recovering_requires_prior_low_and_family_agreement() -> None:
    contract = load_contract(CONTRACT)
    values = [30.0] * 13 + [31.0, 34.0, 38.0, 45.0, 50.0]
    result = classify_transitions(_panel(values), contract)
    assert result.iloc[-1]["RAW_HERD_TRANSITION"] == "RECOVERING"
    assert result.iloc[-1]["HERD_TRANSITION"] == "RECOVERING"
    assert result.iloc[-1]["FAMILY_UP_VOTES"] == 4


def test_future_rows_do_not_change_prior_transitions() -> None:
    contract = load_contract(CONTRACT)
    original = _panel([50.0] * 13 + [55.0, 60.0, 65.0, 70.0, 75.0])
    extended = pd.concat(
        [
            original,
            _panel([10.0, 5.0]).assign(
                signal_date=pd.date_range(
                    original["signal_date"].max() + pd.Timedelta(weeks=1),
                    periods=2,
                    freq="W-FRI",
                )
            ),
        ],
        ignore_index=True,
    )
    left = classify_transitions(original, contract)
    right = classify_transitions(extended, contract).iloc[: len(original)]
    assert left["HERD_TRANSITION"].tolist() == right["HERD_TRANSITION"].tolist()


def test_contract_rejects_action_ratio(tmp_path: Path) -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    payload["claim_boundary"]["operational_action_ratio"] = 0.05
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(HerdTransitionS1Error, match="authorize"):
        load_contract(path)


def test_direction_requires_confirmation_and_blocks_fast_opposite_flip() -> None:
    raw = pd.Series(
        [
            "NEUTRAL",
            "EXTENDING",
            "EXTENDING",
            "COOLING",
            "COOLING",
            "COOLING",
            "COOLING",
            "COOLING",
        ]
    )
    stabilized, suppressed = _stabilize_directional_labels(
        raw,
        confirmation_weeks=2,
        cooldown_weeks=4,
    )
    assert stabilized.iloc[1] == "NEUTRAL"
    assert stabilized.iloc[2] == "EXTENDING"
    assert stabilized.iloc[4] == "NEUTRAL"
    assert suppressed.iloc[4]
    assert stabilized.iloc[-1] == "COOLING"
