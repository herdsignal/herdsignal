import copy

import pytest

from herd.model_rush_episode_ledger_v1 import (
    RushEpisodeLedgerError,
    load_ledger,
    validate_ledger,
)


def test_pinned_rush_episode_ledger_is_complete_and_time_valid():
    _, audit = load_ledger()
    assert audit["episodes"] == 1998
    assert audit["tickers"] == 381
    assert audit["temporal_leakage_rows"] == 0
    assert audit["path_counts"]["STRUCTURAL_BREAK"] == 192
    assert audit["profit_take_authority"] is False


def test_diagnostic_ledger_cannot_authorize_profit_take():
    ledger, _ = load_ledger()
    changed = copy.deepcopy(ledger)
    changed["authority"]["profit_take"] = True
    with pytest.raises(RushEpisodeLedgerError, match="authority"):
        validate_ledger(changed)
