from pathlib import Path

import pandas as pd
import pytest

from herd.historical_prospective_bridge_v1 import (
    HistoricalProspectiveBridgeError,
    build_report,
    load_contract,
    summarize_historical,
)


def _ledger() -> pd.DataFrame:
    return pd.DataFrame({
        "universe_role": ["PRIMARY"] * 3,
        "event_kind": ["STAGE_ENTRY_RUSH"] * 3,
        "horizon_sessions": [21, 63, 126],
        "total_return": [0.01, -0.02, 0.03],
        "maximum_favorable_excursion": [0.02, 0.01, 0.05],
        "maximum_adverse_excursion": [-0.01, -0.03, -0.02],
        "direction_prediction": [False] * 3,
        "operational_action": ["HOLD"] * 3,
        "operational_action_ratio": [0.0] * 3,
    })


def _historical_report() -> dict:
    return {
        "report_version": "HERD_HISTORICAL_S1_REPLAY_V1",
        "status": "DESCRIPTIVE_REPLAY_COMPLETE",
        "survivorship_safe": False,
        "operational_action_ratio": 0.0,
    }


def test_historical_summary_uses_only_exact_prospective_horizons() -> None:
    summary = summarize_historical(_ledger(), load_contract())

    assert summary["horizon_sessions"].tolist() == [21, 63, 126]
    assert summary["episodes"].tolist() == [1, 1, 1]


def test_bridge_keeps_actions_blocked_while_prospective_is_pending() -> None:
    contract = load_contract()
    summary = summarize_historical(_ledger(), contract)
    audit = {
        "observationArchives": 1,
        "observationRecords": 439,
        "maturedOutcomes": 0,
        "maturityByHorizon": {
            "21": {"matured": 0},
            "63": {"matured": 0},
            "126": {"matured": 0},
        },
    }

    report = build_report(_historical_report(), summary, audit, contract)

    assert report["status"] == "HISTORICAL_CONTEXT_READY_PROSPECTIVE_PENDING"
    assert report["historical_context"]["ready"] is True
    assert report["prospective"]["transition_comparison_ready"] is False
    assert report["operational_action"] == "HOLD"
    assert report["operational_action_ratio"] == 0.0


def test_bridge_requires_all_locked_horizons() -> None:
    ledger = _ledger().query("horizon_sessions != 126")

    with pytest.raises(HistoricalProspectiveBridgeError):
        summarize_historical(ledger, load_contract())


def test_contract_rejects_action_ratio(tmp_path: Path) -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "herd/historical_prospective_bridge_v1.json"
    )
    unsafe = source.read_text(encoding="utf-8").replace(
        '"operational_action_ratio": 0.0',
        '"operational_action_ratio": 0.05',
    )
    path = tmp_path / "unsafe.json"
    path.write_text(unsafe, encoding="utf-8")

    with pytest.raises(HistoricalProspectiveBridgeError):
        load_contract(path)
