import copy
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.instrument_class_ledger_v1 import (
    EVENT_LEDGER_PATH,
    REPORT_PATH,
    SEGMENT_PATH,
    TICKER_LEDGER_PATH,
    InstrumentClassLedgerError,
    _company_style,
    classify_security_structure,
    latest_pit_feature,
    load_contract,
)
from scheduler.prospective_evidence import LEVERAGED_ETFS


def test_contract_locks_fail_closed_instrument_boundaries():
    contract = load_contract()

    assert contract["firewall"]["operational_action"] == "HOLD"
    assert contract["firewall"]["operational_action_ratio"] == 0.0
    assert contract["reporting"]["select_policy_from_class_results"] is False
    assert set(contract["security_structure"]["leveraged_or_inverse_etps"]) == LEVERAGED_ETFS


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda c: c["security_structure"]["leveraged_or_inverse_etps"].remove("SOXL"),
            "security structure",
        ),
        (
            lambda c: c["economic_company_style"]["profitable_large_cap_growth"].update(
                {"requires_point_in_time_market_cap": False}
            ),
            "economic company style",
        ),
        (
            lambda c: c["reporting"].update({"select_policy_from_class_results": True}),
            "reporting boundary",
        ),
        (
            lambda c: c["firewall"].update({"operational_action_ratio": 0.05}),
            "firewall",
        ),
    ],
)
def test_contract_mutations_fail_closed(tmp_path, mutation, message):
    contract = copy.deepcopy(load_contract())
    mutation(contract)
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(InstrumentClassLedgerError, match=message):
        load_contract(path)


def test_security_structure_prevents_leveraged_etp_pooling():
    contract = load_contract()

    assert classify_security_structure("SOXL", "ETF", contract) == "LEVERAGED_OR_INVERSE_ETP"
    assert classify_security_structure("SPY", "MARKET_ETF", contract) == "BROAD_MARKET_ETF"
    assert classify_security_structure("XLK", "SECTOR_ETF", contract) == "SECTOR_ETF"
    assert classify_security_structure("NVDA", "EQUITY", contract) == "OPERATING_COMPANY_EQUITY"


def test_large_growth_stays_unresolved_without_pit_market_cap():
    contract = load_contract()
    feature = pd.Series({"revenue_yoy": 0.35, "net_margin": 0.22})

    style, reason = _company_style(feature, contract)

    assert style == "UNRESOLVED"
    assert reason == "UNRESOLVED_MISSING_PIT_MARKET_CAP"


def test_same_day_after_close_filing_is_deferred_to_next_observation():
    features = pd.DataFrame(
        [
            {
                "ticker": "TEST",
                "month_end": pd.Timestamp("2026-07-31"),
                "latest_fact_accepted_at": pd.Timestamp("2026-08-01T21:00:00Z"),
                "corpus_status": "PIT_FACTS_READY",
            }
        ]
    )

    assert latest_pit_feature(features, "TEST", pd.Timestamp("2026-08-01")) is None
    assert latest_pit_feature(features, "TEST", pd.Timestamp("2026-08-02")) is not None


def test_committed_ledgers_are_complete_and_do_not_select_a_policy():
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    ticker_ledger = pd.read_csv(TICKER_LEDGER_PATH)
    event_ledger = pd.read_csv(EVENT_LEDGER_PATH)
    segments = pd.read_csv(SEGMENT_PATH)

    assert report["complete"] is True
    assert report["ticker_count"] == len(ticker_ledger) == 531
    assert report["event_count"] == report["classified_event_count"] == len(event_ledger) == 2161
    assert report["leveraged_events_in_fixed_baseline"] == 0
    assert report["profitable_large_cap_growth_events"] == 0
    assert report["class_results_selected_policy"] is None
    assert report["direction_evidence_admitted"] is False
    assert set(segments["one_way_cost_bps"]) == {10, 25, 50}


def test_event_ledger_uses_reproducible_gzip_header():
    header = EVENT_LEDGER_PATH.read_bytes()[:10]

    assert header[:2] == b"\x1f\x8b"
    assert int.from_bytes(header[4:8], "little") == 0
