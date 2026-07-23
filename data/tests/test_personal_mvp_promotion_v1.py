import json
from pathlib import Path

import pytest

from herd.personal_mvp_promotion_v1 import (
    PersonalMvpPromotionError,
    decide,
    load_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/herd/personal_mvp_promotion_v1.json"


def test_current_evidence_promotes_observation_but_not_action() -> None:
    contract = load_contract(CONTRACT)
    result = decide(contract)
    assert result["status"] == "STATE_OBSERVATION_MVP_READY"
    assert result["state_observation_ready"] is True
    assert result["transition_observation_ready"] is True
    assert result["action_candidate_ready"] is False
    assert result["operational_action_ratio"] == 0.0
    assert "PERSONAL_POLICY_PREHOLDOUT_FAILED" in result["promotion_blockers"]


def test_contract_rejects_nonzero_action_ratio(tmp_path: Path) -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    payload["fail_closed_output"]["operational_action_ratio"] = 0.05
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PersonalMvpPromotionError, match="weakened"):
        load_contract(path)
