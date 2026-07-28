"""익절 연구의 경제 목표·빈도·비용·행동 차단 계약을 함께 검증한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/profit_take_contract_gate_v1.json"
VERSION = "HERD_PROFIT_TAKE_CONTRACT_GATE_V1"


class ProfitTakeContractGateError(ValueError):
    """익절 계약의 의미 또는 행동 차단 경계가 어긋난 경우."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_inputs(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for item in contract["inputs"]:
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ProfitTakeContractGateError(f"missing input: {item['path']}")
        if _hash(path) != item["sha256"]:
            raise ProfitTakeContractGateError(f"input changed: {item['path']}")
        loaded[item["path"]] = json.loads(path.read_text())
    return loaded


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if (
        contract.get("contract_version") != VERSION
        or contract.get("status") != "LOCKED_BEFORE_GATE_RESULT"
    ):
        raise ProfitTakeContractGateError("profit-take gate is not locked")
    firewall = contract["firewall"]
    if (
        firewall["this_gate_authorizes_actions"] is not False
        or firewall["blind_holdout_access"] is not False
        or firewall["survivorship_safe"] is not False
        or firewall["operational_action"] != "HOLD"
        or firewall["operational_action_ratio"] != 0.0
    ):
        raise ProfitTakeContractGateError("action firewall was widened")
    return contract


def build_report(output_path: Path = REPORT_PATH) -> dict[str, Any]:
    contract = validate_contract(json.loads(CONTRACT_PATH.read_text()))
    loaded = _load_inputs(contract)
    protocol = loaded["data/herd/model_establishment_protocol_v1.json"]
    ceiling_contract = loaded[
        "data/herd/profit_take_opportunity_ceiling_v1.json"
    ]
    ceiling_report = loaded[
        "data/reports/profit_take_opportunity_ceiling_v1.json"
    ]
    label_contract = loaded["data/herd/profit_take_success_label_v2.json"]
    label_report = loaded["data/reports/profit_take_success_label_v2.json"]
    required = contract["required_contract"]
    action = protocol["action_boundary"]
    evaluation = protocol["evaluation"]
    execution = ceiling_contract["execution"]
    checks = {
        "initial_fraction": action["initial_fraction"]
        == required["initial_fraction"]
        == execution["trim_fraction"],
        "maximum_cumulative_fraction":
            action["maximum_cumulative_fraction"]
            == required["maximum_cumulative_fraction"],
        "candidate_frequency":
            action["maximum_profit_take_candidates_per_ticker_year"]
            == required["maximum_profit_take_candidates_per_ticker_year"]
            == ceiling_contract["event"][
                "maximum_events_per_ticker_calendar_year"
            ]
            == label_contract["population"]["maximum_events_per_ticker_year"],
        "completed_action_frequency":
            action["maximum_completed_actions_per_ticker_year"]
            == required["maximum_completed_actions_per_ticker_year"],
        "cooldown": action["minimum_cooldown_weeks"]
        == required["minimum_cooldown_weeks"],
        "execution": evaluation["execution"] == required["execution"],
        "base_round_trip_cost":
            2
            * (
                evaluation["base_one_way_commission"]
                + evaluation["base_one_way_slippage"]
            )
            == required["base_round_trip_cost_rate"],
        "stress_round_trip_cost":
            2
            * (
                evaluation["stress_one_way_commission"]
                + evaluation["stress_one_way_slippage"]
            )
            == required["stress_round_trip_cost_rate"],
        "complete_cycle":
            action["profit_take_without_reentry_is_incomplete"]
            is required["profit_take_without_reentry_is_incomplete"],
        "opportunity_ceiling": ceiling_report["status"]
        == "ECONOMIC_OPPORTUNITY_CEILING_PASSED",
        "label_coverage": label_report["coverage_passed"] is True,
        "healthy_continuation_preserved":
            label_report["label_counts"]["HEALTHY_CONTINUATION"] > 0,
        "structural_damage_preserved":
            label_report["label_counts"]["STRUCTURAL_DAMAGE"] > 0,
        "no_direction_authority":
            label_report["direction_evidence_admitted"] is False,
        "no_action_authority":
            label_report["labels_authorize_actions"] is False
            and label_report["operational_action_ratio"] == 0.0,
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise ProfitTakeContractGateError(
            f"profit-take contract mismatch: {', '.join(failed)}"
        )
    report = {
        "report_version": VERSION,
        "status": "PROFIT_TAKE_TARGET_AND_FREQUENCY_LOCKED",
        "checks": checks,
        "labeled_events": label_report["rows"],
        "tickers": label_report["tickers"],
        "folds": label_report["folds"],
        "next_gate": "INDEPENDENT_OOS_DIRECTION_EVIDENCE",
        "direction_evidence_admitted": False,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2))
