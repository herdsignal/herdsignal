"""Evaluate the locked earnings-reaction formula on former constituents only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from herd.rush_negative_earnings_reaction_oos_v1 import evaluate
from herd.ticker_disjoint_earnings_reaction_oos_v1 import build_panel


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
OUTPUT_PATH = ROOT / "data/reports/ticker_disjoint_earnings_reaction_oos_v2.csv"
REPORT_PATH = ROOT / "data/reports/ticker_disjoint_earnings_reaction_oos_v2.json"
GATE_PATH = ROOT / "data/reports/ticker_disjoint_earnings_reaction_oos_v2_gate.json"


class TickerDisjointEarningsOosV2Error(RuntimeError):
    """Raised when the V2 lock or exact V1 formula lineage drifts."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("protocol_version") != "TICKER_DISJOINT_EARNINGS_REACTION_OOS_V2"
        or contract.get("status") != "LOCKED_BEFORE_EXPANSION_REACTION_RESULTS"
        or contract["sample_policy"]["combine_with_v1_for_gate"]
        or contract["sample_policy"]["threshold_retuning"]
        or contract["operational_action_ratio"] != 0.0
    ):
        raise TickerDisjointEarningsOosV2Error("independent OOS V2 contract is not locked")
    formula_path = ROOT / contract["formula_source"]["path"]
    if not formula_path.is_file() or _sha256(formula_path) != contract["formula_source"]["sha256"]:
        raise TickerDisjointEarningsOosV2Error("locked V1 formula source changed")
    formula = json.loads(formula_path.read_text(encoding="utf-8"))
    enriched = json.loads(json.dumps(contract))
    for field in contract["formula_source"]["reuse_exact_fields"]:
        enriched[field] = formula[field]
    for item in contract["inputs"]:
        source = (ROOT / item["path"]).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file() or _sha256(source) != item["sha256"]:
            raise TickerDisjointEarningsOosV2Error(f"locked input changed: {item['role']}")
    return enriched


def _empty_evaluation() -> dict[str, Any]:
    keys = (
        "mature_events", "distinct_tickers", "calendar_years", "positive_years",
        "adverse_precision", "terminal_wealth", "stress_terminal_wealth",
        "positive_completed_cycle_rate",
    )
    return {
        "checks": {key: False for key in keys},
        "passed": False,
        "mature_events": 0,
        "distinct_tickers": 0,
        "calendar_years": 0,
    }


def run(
    output_path: Path = OUTPUT_PATH,
    report_path: Path = REPORT_PATH,
    gate_path: Path = GATE_PATH,
) -> dict[str, Any]:
    contract = load_contract()
    panel, exclusions = build_panel(contract)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output_path, index=False)
    parent_path = next(ROOT / item["path"] for item in contract["inputs"] if item["role"] == "PARENT_HYPOTHESIS")
    evaluation_protocol = json.loads(parent_path.read_text(encoding="utf-8"))
    evaluation_protocol["sample_contract"]["first_eligible_event_date"] = contract["sample_policy"]["first_eligible_event_date"]
    result = evaluate(panel, evaluation_protocol) if len(panel) else _empty_evaluation()
    passed = bool(result["passed"])
    event_input = next(ROOT / item["path"] for item in contract["inputs"] if item["role"] == "SEC_EVENT_CATALOG")
    result.update({
        "report_version": "TICKER_DISJOINT_EARNINGS_REACTION_OOS_V2",
        "status": "INDEPENDENT_HISTORICAL_OOS_PASSED" if passed else "INDEPENDENT_HISTORICAL_OOS_FAILED",
        "historical_screen_passed": passed,
        "prospective_confirmation_allowed": passed,
        "combined_with_v1_for_gate": False,
        "thresholds_retuned": False,
        "direction_evidence_admitted": False,
        "candidate_action_enabled": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "input_rows": len(pd.read_csv(event_input)),
        "candidate_rows": len(panel),
        "exclusions": exclusions,
        "panel_path": str(output_path.relative_to(ROOT)),
        "panel_sha256": _sha256(output_path),
    })
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    gate = {
        "report_version": "TICKER_DISJOINT_EARNINGS_REACTION_OOS_V2_GATE",
        "status": "PROSPECTIVE_CONFIRMATION_ALLOWED" if passed else "HYPOTHESIS_REJECTED_NO_PROSPECTIVE_PROMOTION",
        "independent_historical_oos_passed": passed,
        "prospective_confirmation_allowed": passed,
        "direction_evidence_admitted": False,
        "candidate_action_enabled": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
    }
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
