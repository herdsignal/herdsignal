from pathlib import Path

import pandas as pd
import pytest

from herd.historical_s1_product_context_v1 import (
    HistoricalS1ProductContextError,
    build_context,
    load_contract,
)


def _ledger() -> pd.DataFrame:
    rows = []
    for ticker in ["A", "B"]:
        for episode in range(5):
            for horizon in [21, 63, 126]:
                rows.append({
                    "episode_id": f"{ticker}-{episode}",
                    "ticker": ticker,
                    "signal_date": pd.Timestamp("2020-01-03"),
                    "event_kind": "STAGE_ENTRY_RUSH",
                    "horizon_sessions": horizon,
                    "total_return": 0.01,
                    "maximum_favorable_excursion": 0.03,
                    "maximum_adverse_excursion": -0.02,
                    "direction_prediction": False,
                    "operational_action": "HOLD",
                    "operational_action_ratio": 0.0,
                })
    return pd.DataFrame(rows)


def test_builds_ticker_and_reference_context_without_action() -> None:
    context = build_context(_ledger(), load_contract())

    assert context["tickers"]["A"]["RUSH"]["evidenceStatus"] == "DESCRIPTIVE_ONLY"
    assert context["reference"]["RUSH"]["episodeCount"] == 10
    assert context["reference"]["RUSH"]["evidenceStatus"] == "INSUFFICIENT_SAMPLE"
    assert context["operationalAction"] == "HOLD"
    assert context["operationalActionRatio"] == 0.0
    assert context["survivorshipSafe"] is False


def test_rejects_action_authority() -> None:
    ledger = _ledger()
    ledger.loc[0, "operational_action"] = "REDUCE"

    with pytest.raises(HistoricalS1ProductContextError):
        build_context(ledger, load_contract())


def test_contract_rejects_changed_stage_set(tmp_path: Path) -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "herd/historical_s1_product_context_v1.json"
    )
    changed = source.read_text(encoding="utf-8").replace(
        '    "RUSH"\n', '    "RUSH",\n    "EXTRA"\n'
    )
    path = tmp_path / "changed.json"
    path.write_text(changed, encoding="utf-8")

    with pytest.raises(HistoricalS1ProductContextError):
        load_contract(path)
