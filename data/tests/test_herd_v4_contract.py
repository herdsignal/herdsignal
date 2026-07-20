import json
from pathlib import Path

import pytest

from config.settings import HERD_THRESHOLDS, HERD_WEIGHTS
from herd.calculator import calc_herd_scores, get_stage


CONTRACT_PATH = Path(__file__).parents[1] / "contracts" / "herd_v4_golden_cases.json"


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_operational_configuration_matches_versioned_contract():
    contract = _contract()
    expected_weights = contract["weights"]

    assert contract["contractVersion"] == "HERD_V4_CONTRACT_1"
    assert contract["modelVersion"] == "HERD_v4"
    assert contract["rounding"] == "PYTHON_HALF_EVEN_2DP"
    assert HERD_WEIGHTS["monthly_rsi"] == expected_weights["monthly_rsi"]
    assert HERD_WEIGHTS["weekly_rsi"] == expected_weights["weekly_rsi"]
    assert HERD_WEIGHTS["52w_position"] == expected_weights["position_52w"]
    assert HERD_WEIGHTS["ma200_deviation"] == expected_weights["ma200_deviation"]
    assert HERD_WEIGHTS["volume_strength"] == expected_weights["volume_strength"]
    assert HERD_WEIGHTS["ma200_weekly"] == expected_weights["ma200_weekly"]
    assert HERD_THRESHOLDS == {"flee": 15.0, "rush": 75.0}


@pytest.mark.parametrize("case", _contract()["cases"], ids=lambda case: case["id"])
def test_python_calculator_matches_golden_cases(case):
    result = calc_herd_scores(
        case["indicators"],
        case["epsMultiplier"],
        case["sectorMultiplier"],
    )

    assert result["herd_base"] == case["expectedBase"]
    assert result["herd_v4"] == case["expectedV4"]
    assert get_stage(result["herd_v4"]) == case["expectedStage"]
