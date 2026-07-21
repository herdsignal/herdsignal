import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.confirmed_reentry_v1 import find_confirmation, load_protocol


def _frame(close):
    dates = pd.bdate_range("2020-01-01", periods=len(close))
    values = np.asarray(close, dtype=float)
    return pd.DataFrame({"Date": dates, "Open": values, "Close": values, "Adj Close": values})


def test_confirmation_uses_only_close_then_executes_later_by_contract():
    protocol = load_protocol()
    base = np.linspace(100, 80, 80).tolist() + [80] * 11 + np.linspace(81, 90, 30).tolist()
    benchmark = np.linspace(100, 82, len(base))
    result = find_confirmation(_frame(base), _frame(benchmark), _frame(benchmark), pd.bdate_range("2020-01-01", periods=len(base))[79], protocol)
    assert pd.notna(result["confirmation_date"])
    assert result["confirmation_wait_sessions"] >= 10
    assert "USE_CONFIRMATION_DAY_OPEN_FOR_EXECUTION" in protocol["forbidden"]


def test_future_mutation_does_not_change_existing_confirmation():
    protocol = load_protocol()
    base = np.linspace(100, 80, 80).tolist() + [80] * 11 + np.linspace(81, 90, 30).tolist() + [90] * 20
    benchmark = np.linspace(100, 82, len(base))
    signal = pd.bdate_range("2020-01-01", periods=len(base))[79]
    first = find_confirmation(_frame(base), _frame(benchmark), _frame(benchmark), signal, protocol)
    changed = base.copy(); changed[-10:] = [200] * 10
    second = find_confirmation(_frame(changed), _frame(benchmark), _frame(benchmark), signal, protocol)
    assert first == second


def test_unconfirmed_events_must_remain_in_strategy_return():
    protocol = load_protocol()
    assert protocol["portfolio"]["unconfirmed_action"] == "KEEP_CASH"
    assert "EXCLUDE_UNCONFIRMED_FROM_STRATEGY_RETURN" in protocol["forbidden"]


def test_admission_registry_pins_rejected_results():
    root = Path(__file__).resolve().parents[2]
    registry = json.loads((root / "data/herd/evidence_admission_registry_v5.json").read_text())
    assert registry["decision"]["reentry_evidence_admitted"] is False
    for item in registry["source_artifacts"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
