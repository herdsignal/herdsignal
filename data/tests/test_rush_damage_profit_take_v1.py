import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.rush_damage_profit_take_v1 import find_damage, load_protocol


def _frame(close):
    dates = pd.bdate_range("2020-01-01", periods=len(close)); values = np.asarray(close, dtype=float)
    return pd.DataFrame({"Date": dates, "Open": values, "Close": values, "Adj Close": values})


def test_high_rush_without_breakdown_does_not_trigger():
    protocol = load_protocol(); stock = np.linspace(100, 180, 180); benchmark = np.linspace(100, 140, 180)
    result = find_damage(_frame(stock), _frame(benchmark), _frame(benchmark), pd.bdate_range("2020-01-01", periods=180)[100], protocol)
    assert pd.isna(result["damage_date"])


def test_breakdown_requires_close_information_and_next_open_by_contract():
    protocol = load_protocol(); stock = np.r_[np.linspace(100, 160, 110), np.linspace(159, 100, 70)]; benchmark = np.linspace(100, 150, 180)
    result = find_damage(_frame(stock), _frame(benchmark), _frame(benchmark), pd.bdate_range("2020-01-01", periods=180)[109], protocol)
    assert pd.notna(result["damage_date"])
    assert "USE_DAMAGE_DAY_OPEN" in protocol["forbidden"]


def test_untriggered_episodes_remain_buy_and_hold():
    protocol = load_protocol()
    assert protocol["portfolio"]["unconfirmed_action"] == "BUY_AND_HOLD"
    assert "DROP_UNTRIGGERED_EPISODES" in protocol["forbidden"]


def test_registry_pins_rejected_profit_take_rule():
    root = Path(__file__).resolve().parents[2]
    registry = json.loads((root / "data/herd/evidence_admission_registry_v7.json").read_text())
    assert registry["decision"]["profit_take_evidence_admitted"] is False
    for item in registry["source_artifacts"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
