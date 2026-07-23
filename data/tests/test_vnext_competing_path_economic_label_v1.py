import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.vnext_competing_path_economic_label_v1 import (
    VNextLabelError,
    classify_competing_path,
    evaluate_trim_counterfactual,
    load_contract,
    validate_contract,
)


def _frame(future: list[float]) -> tuple[pd.DataFrame, pd.Timestamp]:
    history = list(np.linspace(90.0, 100.0, 80))
    values = history + future
    index = pd.bdate_range("2020-01-01", periods=len(values))
    close = pd.Series(values, index=index)
    frame = pd.DataFrame(
        {"Open": close, "Close": close, "Adj Close": close},
        index=index,
    )
    return frame, index[len(history) - 1]


def test_contract_separates_paths_and_economic_authority():
    report = validate_contract(load_contract())
    assert report["first_boundary_is_separate_from_terminal_path"] is True
    assert report["open_trim_is_success"] is False
    assert report["labels_authorize_actions"] is False


def test_continuation_records_upside_as_first_boundary():
    frame, signal = _frame(list(np.linspace(101.0, 125.0, 126)))
    outcome = classify_competing_path(frame, signal)
    assert outcome.first_boundary == "UPSIDE_CONTINUATION"
    assert outcome.terminal_path == "CONTINUATION"


def test_pullback_and_recovery_are_not_continuation():
    future = list(np.linspace(99.0, 92.0, 30)) + list(
        np.linspace(92.0, 106.0, 96)
    )
    frame, signal = _frame(future)
    outcome = classify_competing_path(frame, signal)
    assert outcome.first_boundary == "DOWNSIDE_PULLBACK"
    assert outcome.terminal_path == "TRADABLE_PULLBACK"


def test_incomplete_future_is_right_censored_not_failure():
    frame, signal = _frame(list(np.linspace(100.0, 105.0, 40)))
    outcome = classify_competing_path(frame, signal)
    assert outcome.status == "RIGHT_CENSORED"
    assert outcome.terminal_path == "RIGHT_CENSORED"


def test_open_trim_is_never_counted_as_success():
    future = list(np.linspace(100.0, 80.0, 126))
    frame, signal = _frame(future)
    outcome = evaluate_trim_counterfactual(frame, signal)
    assert outcome.open_trim_terminal_wealth_delta > 0
    assert outcome.complete_cycle is False
    assert outcome.economic_label == "INCOMPLETE_CYCLE"


def test_observable_lower_reentry_creates_positive_complete_cycle():
    future = (
        list(np.linspace(100.0, 80.0, 30))
        + list(np.linspace(80.0, 110.0, 96))
    )
    frame, signal = _frame(future)
    reentry_signal = frame.index[80 + 20]
    outcome = evaluate_trim_counterfactual(
        frame,
        signal,
        reentry_signal_session=reentry_signal,
    )
    assert outcome.complete_cycle is True
    assert outcome.share_delta > 0
    assert outcome.economic_label == "POSITIVE_COMPLETE_CYCLE"


def test_reentry_before_trim_is_rejected():
    frame, signal = _frame(list(np.linspace(100.0, 90.0, 126)))
    with pytest.raises(VNextLabelError, match="after"):
        evaluate_trim_counterfactual(
            frame,
            signal,
            reentry_signal_session=signal,
        )


def test_contract_cannot_enable_future_low_reentry():
    contract = json.loads(json.dumps(load_contract()))
    contract["forbidden"].remove("USE_FUTURE_LOW_AS_REENTRY")
    with pytest.raises(VNextLabelError, match="weakened"):
        validate_contract(contract)


def test_non_finite_execution_price_is_rejected():
    frame, signal = _frame(list(np.linspace(100.0, 90.0, 126)))
    frame.loc[frame.index[90], "Open"] = np.inf
    with pytest.raises(VNextLabelError, match="finite"):
        evaluate_trim_counterfactual(frame, signal)
