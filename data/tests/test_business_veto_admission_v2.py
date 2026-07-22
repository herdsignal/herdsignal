import json
from pathlib import Path

from herd.business_veto_admission_v2 import audit


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "data/herd/business_veto_admission_v2.json").read_text())


def test_rejected_business_guard_cannot_authorize_any_action() -> None:
    report = audit(PROTOCOL)
    assert report["primary_outcomes_passed"] == 0
    assert report["primary_outcomes_required"] == 2
    assert report["business_veto_evidence_admitted"] is False
    assert report["add_buy_veto_ablation_allowed"] is False
    assert report["sell_authority"] is False
    assert report["herd_weight_authority"] is False
    assert report["new_parser_sample_used_for_oos"] is False
    assert report["decision"] == "REJECT_BUSINESS_VETO_EVIDENCE"
    assert report["operational_action_ratio"] == 0
