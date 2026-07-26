import json
from pathlib import Path

from herd.sec_form4_nonroutine_sale_rush_promotion_audit_v1 import (
    build_audit,
)


def test_rejected_hypothesis_blocks_all_action_layers(tmp_path):
    audit = build_audit(tmp_path / "audit.json")
    assert audit["status"] == "REJECTED_DIRECTIONALLY_INVERTED"
    assert set(audit["downstream"].values()) == {
        "BLOCKED",
        "BLOCKED_NO_VALIDATED_SALE_CASH",
    }
    assert audit["blind_holdout_access"] is False
    assert audit["operational_action_ratio"] == 0.0


def test_checked_in_audit_remains_non_operational():
    audit = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "reports/sec_form4_nonroutine_sale_rush_promotion_audit_v1.json"
        ).read_text()
    )
    assert audit["downstream"]["five_percent_profit_take"] == "BLOCKED"
    assert audit["operational_action_ratio"] == 0.0
