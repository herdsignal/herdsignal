import json
from pathlib import Path

from herd.leading_information_feasibility_v1 import audit


ROOT = Path(__file__).resolve().parents[1]


def test_public_sec_sources_are_first_and_vendor_data_remains_blocked():
    protocol = json.loads((ROOT / "herd/leading_information_feasibility_v1.json").read_text())
    result = audit(protocol)
    assert result["primary_collectable_sources"] == [
        "SEC_8K_EARNINGS_GUIDANCE", "SEC_FORM4_INSIDER_TRANSACTIONS"
    ]
    assert "HISTORICAL_ANALYST_ESTIMATE_REVISIONS" in result["data_blocked_sources"]
    assert "HISTORICAL_EQUITY_OPTION_SURFACE" in result["data_blocked_sources"]
    assert result["next_implementation"] == "SEC_8K_EARNINGS_GUIDANCE_PIT_CORPUS"


def test_misleading_short_volume_substitution_and_formula_change_are_forbidden():
    protocol = json.loads((ROOT / "herd/leading_information_feasibility_v1.json").read_text())
    result = audit(protocol)
    assert result["rejected_proxy_sources"] == ["FINRA_DAILY_SHORT_SALE_VOLUME"]
    assert "TREAT_FINRA_SHORT_VOLUME_AS_SHORT_INTEREST" in protocol["forbidden"]
    assert result["herd_formula_change_allowed"] is False
    assert result["operational_action_ratio"] == 0.0
