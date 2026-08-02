import json
from herd.ticker_disjoint_sec_earnings_census_v2 import (
    load_contract,
    preserve_collection_receipt,
)
from herd.ticker_disjoint_sec_earnings_census_v1 import load_cik_universe


def test_v2_contract_locks_the_former_constituent_universe():
    contract = load_contract()
    universe = load_cik_universe(contract)

    assert len(universe) == 21
    assert set(universe) == {
        "AAP", "BWA", "ETSY", "FLS", "FMC", "HRB", "IPGP", "LNC",
        "LUMN", "NOV", "NWL", "OGN", "QRVO", "RHI", "SEDG", "UNM",
        "VFC", "VNO", "WHR", "XRAY", "ZION",
    }
    assert contract["future_price_outcomes_read"] is False
    assert contract["operational_action_ratio"] == 0.0


def test_materialization_preserves_the_last_collection_receipt(tmp_path):
    report_path = tmp_path / "report.json"
    receipt = {"status": "SEC_EARNINGS_LEDGER_UPDATED", "appended": 7}
    report_path.write_text(json.dumps({"collection": receipt}))

    assert preserve_collection_receipt(None, report_path) == receipt
