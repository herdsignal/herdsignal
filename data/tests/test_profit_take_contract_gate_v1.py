import copy
import json

import pytest

from herd.profit_take_contract_gate_v1 import (
    CONTRACT_PATH,
    ProfitTakeContractGateError,
    build_report,
    validate_contract,
)


def test_checked_in_contracts_lock_target_frequency_and_costs(tmp_path):
    report = build_report(tmp_path / "report.json")
    assert report["status"] == "PROFIT_TAKE_TARGET_AND_FREQUENCY_LOCKED"
    assert all(report["checks"].values())
    assert report["direction_evidence_admitted"] is False
    assert report["operational_action"] == "HOLD"
    assert report["operational_action_ratio"] == 0.0


def test_contract_gate_rejects_action_authority():
    contract = json.loads(CONTRACT_PATH.read_text())
    changed = copy.deepcopy(contract)
    changed["firewall"]["operational_action_ratio"] = 0.05
    with pytest.raises(ProfitTakeContractGateError):
        validate_contract(changed)


def test_contract_gate_rejects_changed_hashed_input():
    contract = json.loads(CONTRACT_PATH.read_text())
    changed = copy.deepcopy(contract)
    changed["inputs"][0]["sha256"] = "0" * 64
    with pytest.raises(ProfitTakeContractGateError):
        from herd.profit_take_contract_gate_v1 import _load_inputs

        _load_inputs(validate_contract(changed))
