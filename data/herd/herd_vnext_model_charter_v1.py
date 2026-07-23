"""HERD vNext의 제품 목표·모델 계층·출력·행동 경계를 검증한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CHARTER_PATH = Path(__file__).with_suffix(".json")
SPARSE_ACTION_PATH = Path(__file__).with_name("sparse_action_protocol_v1.json")
CONTRACT_VERSION = "HERD_VNEXT_MODEL_CHARTER_V1"
EXPECTED_LAYERS = [
    "HERD_STATE",
    "TRANSITION_STATE",
    "BUSINESS_GATE",
    "ACTION_EDGE",
    "PORTFOLIO_POLICY",
    "PROMOTION_GATE",
]


class ModelCharterError(ValueError):
    """vNext 계약이 완화되거나 기존 행동 계약과 충돌할 때 발생한다."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ModelCharterError(message)


def validate_charter(
    charter: dict[str, Any],
    sparse_action: dict[str, Any],
) -> dict[str, Any]:
    _require(
        charter.get("contract_version") == CONTRACT_VERSION
        and charter.get("status") == "LOCKED_BEFORE_VNEXT_FEATURE_RESULTS",
        "vNext model charter is not locked",
    )

    scope = charter.get("product_scope", {})
    _require(scope.get("default_action") == "HOLD", "default action must be HOLD")
    _require(
        scope.get("does_not_select_good_companies") is True,
        "company selection must remain outside vNext",
    )
    _require(
        scope.get("does_not_promise_buy_and_hold_outperformance") is True,
        "outperformance cannot be promised",
    )

    layers = charter.get("model_layers", [])
    layer_ids = [layer.get("id") for layer in layers]
    _require(layer_ids == EXPECTED_LAYERS, "model layer order or identity changed")
    _require(len(set(layer_ids)) == len(layer_ids), "model layers must be unique")
    action_authorities = [
        layer["id"] for layer in layers if layer.get("authorizes_action") is True
    ]
    _require(
        action_authorities == ["PROMOTION_GATE"],
        "only the promotion gate may authorize an action",
    )
    personal_layers = [
        layer["id"]
        for layer in layers
        if layer.get("personal_portfolio_input_allowed") is True
    ]
    _require(
        personal_layers == ["PORTFOLIO_POLICY"],
        "personal inputs must stay outside objective HERD",
    )

    output = charter.get("output_contract", {})
    _require(
        output.get("herd", {}).get("stages")
        == ["FLEE", "SCATTER", "CALM", "DRIFT", "RUSH"],
        "HERD stage vocabulary changed",
    )
    _require(
        output.get("action", {}).get("research_default") == "HOLD"
        and output.get("action", {}).get("unapproved_ratio") == 0.0,
        "unapproved action must fail closed",
    )
    _require(
        output.get("business_gate", {}).get("unknown_policy")
        == "DOES_NOT_AUTHORIZE_ADD_OR_REENTRY",
        "unknown business state must fail closed",
    )

    action = charter.get("action_policy", {})
    sparse = sparse_action.get("action_constraints", {})
    frequency = sparse_action.get("research_frequency_bounds", {})
    expected_pairs = {
        "initial_profit_take_fraction": sparse.get("initial_profit_take_fraction"),
        "maximum_cumulative_profit_take_fraction": sparse.get(
            "maximum_cumulative_profit_take_fraction"
        ),
        "full_exit_allowed": not sparse.get("full_exit_forbidden"),
        "minimum_cooldown_weeks": sparse.get("minimum_cooldown_weeks"),
        "maximum_profit_take_events_per_ticker_year": frequency.get(
            "profit_take_candidates_per_ticker_year_maximum"
        ),
        "maximum_completed_actions_per_ticker_year": frequency.get(
            "all_completed_actions_per_ticker_year_maximum"
        ),
    }
    for key, expected in expected_pairs.items():
        _require(action.get(key) == expected, f"action policy drifted: {key}")
    _require(
        action.get("reentry_requires_prior_matched_sale_cash") is True
        and action.get("profit_take_without_reentry_is_incomplete_cycle") is True
        and action.get("leverage_supported") is False,
        "complete-cycle or leverage boundary changed",
    )

    legacy = charter.get("legacy_boundary", {})
    _require(
        legacy.get("legacy_model_promotion_allowed") is False
        and legacy.get("legacy_threshold_retuning_allowed") is False,
        "legacy model cannot become vNext",
    )
    validation = charter.get("validation_boundary", {})
    _require(
        validation.get("historical_period_may_be_relabelled_blind_holdout") is False
        and validation.get("final_blind_evidence") == "PROSPECTIVE_SHADOW_ONLY"
        and validation.get("operational_action_ratio_before_promotion") == 0.0,
        "historical or operational promotion boundary changed",
    )

    forbidden = set(charter.get("forbidden", []))
    required_forbidden = {
        "USE_HIGH_HERD_ALONE_AS_SELL",
        "USE_LOW_HERD_ALONE_AS_BUY",
        "PUT_PERSONAL_POSITION_INSIDE_OBJECTIVE_HERD",
        "MERGE_PROFIT_TAKE_AND_REENTRY_TARGETS",
        "PROMOTE_WITHOUT_COMPLETE_CYCLE",
        "USE_LEVERAGE",
        "FULL_EXIT",
    }
    _require(
        required_forbidden.issubset(forbidden),
        "critical forbidden behavior is missing",
    )

    return {
        "report_version": "HERD_VNEXT_MODEL_CHARTER_AUDIT_V1",
        "status": "VNEXT_CHARTER_VERIFIED",
        "model_layers": layer_ids,
        "operational_action_authority": "PROMOTION_GATE",
        "default_action": "HOLD",
        "initial_action_fraction": action["initial_profit_take_fraction"],
        "maximum_action_fraction": action[
            "maximum_cumulative_profit_take_fraction"
        ],
        "historical_role": validation["historical_data_role"],
        "final_blind_evidence": validation["final_blind_evidence"],
        "operational_action_ratio": 0.0,
    }


def load_and_validate(
    charter_path: Path = CHARTER_PATH,
    sparse_action_path: Path = SPARSE_ACTION_PATH,
) -> tuple[dict[str, Any], dict[str, Any]]:
    charter = json.loads(charter_path.read_text(encoding="utf-8"))
    sparse_action = json.loads(sparse_action_path.read_text(encoding="utf-8"))
    return charter, validate_charter(charter, sparse_action)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    _, report = load_and_validate()
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
