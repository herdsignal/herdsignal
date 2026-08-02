from herd.ticker_disjoint_sec_earnings_census_v2 import load_contract
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
