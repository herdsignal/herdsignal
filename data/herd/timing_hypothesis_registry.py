"""차세대 HERD 타이밍 가설 사전등록 계약을 검증한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).with_name(
    "timing_hypothesis_registry.json"
)
EXPECTED_FAMILIES = {
    "PRICE_EXTENSION",
    "TREND_MATURITY",
    "PARTICIPATION",
    "RELATIVE_OVERHEAT",
    "MARKET_RISK",
    "BUSINESS_GUARD",
}
EXPECTED_HYPOTHESES = {f"H{number}" for number in range(1, 8)}
EXPECTED_STATES = ("FLEE", "SCATTER", "CALM", "DRIFT", "RUSH")


class TimingHypothesisRegistryError(RuntimeError):
    """사전등록 계약이 불완전하거나 모순될 때 발생한다."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def registry_sha256(registry: dict) -> str:
    return hashlib.sha256(_canonical_json(registry)).hexdigest()


def validate_registry(registry: dict) -> dict:
    objective = registry.get("objective", {})
    if (
        registry.get("status") != "LOCKED_BEFORE_HYPOTHESIS_RESULTS"
        or objective.get("default_action") != "HOLD"
        or objective.get("personal_inputs_in_score") is not False
    ):
        raise TimingHypothesisRegistryError(
            "objective is not locked to universal long-term timing"
        )

    states = registry.get("state_bands", [])
    if tuple(row.get("name") for row in states) != EXPECTED_STATES:
        raise TimingHypothesisRegistryError("state order changed")
    expected_minimum = 0
    for row in states:
        if row.get("minimum") != expected_minimum:
            raise TimingHypothesisRegistryError("state bands have a gap")
        if row.get("maximum", -1) < row["minimum"]:
            raise TimingHypothesisRegistryError("invalid state band")
        expected_minimum = row["maximum"] + 1
    if expected_minimum != 101:
        raise TimingHypothesisRegistryError(
            "state bands must cover 0 through 100"
        )

    families = registry.get("evidence_families", [])
    family_ids = {row.get("id") for row in families}
    if family_ids != EXPECTED_FAMILIES or len(families) != len(family_ids):
        raise TimingHypothesisRegistryError(
            "evidence families are missing or duplicated"
        )
    if any(not row.get("candidate_features") for row in families):
        raise TimingHypothesisRegistryError(
            "every family needs candidate features"
        )

    hypotheses = registry.get("hypotheses", [])
    hypothesis_ids = {row.get("id") for row in hypotheses}
    if (
        hypothesis_ids != EXPECTED_HYPOTHESES
        or len(hypotheses) != len(hypothesis_ids)
    ):
        raise TimingHypothesisRegistryError(
            "H1-H7 must be registered exactly once"
        )
    for hypothesis in hypotheses:
        required = set(hypothesis.get("required_families", []))
        if (
            not required
            or not required.issubset(family_ids)
            or not hypothesis.get("forward_horizons_months")
            or not hypothesis.get("test_type")
        ):
            raise TimingHypothesisRegistryError(
                f"incomplete hypothesis: {hypothesis.get('id')}"
            )

    action = registry.get("action_contract", {})
    if (
        action.get("full_liquidation_allowed") is not False
        or action.get("rush_alone_can_sell") is not False
        or action.get("flee_alone_can_buy") is not False
        or action.get("business_guard_can_block_add_buy") is not True
        or action.get("default_target_exposure_minimum", 0) < 0.8
        or action.get("research_target_exposure_floor", 0) <= 0
        or action.get("maximum_monthly_change", 1) > 0.15
    ):
        raise TimingHypothesisRegistryError(
            "action contract violates long-term partial-action policy"
        )

    evaluation = registry.get("evaluation_contract", {})
    if (
        evaluation.get("oos_only_for_candidate_adoption") is not True
        or evaluation.get("blind_holdout_single_use") is not True
        or evaluation.get("minimum_average_exposure", 0) < 0.8
        or "COMPLETED_CYCLE_WEALTH_DELTA"
        not in evaluation.get("action_metrics", [])
    ):
        raise TimingHypothesisRegistryError(
            "evaluation contract is incomplete"
        )

    forbidden = set(registry.get("forbidden_shortcuts", []))
    required_forbidden = {
        "TREAT_HIGH_RSI_AS_AUTOMATIC_SELL",
        "TREAT_LOW_HERD_AS_AUTOMATIC_BUY",
        "IGNORE_REENTRY_AFTER_PROFIT_TAKING",
        "COMBINE_UNVALIDATED_FAMILIES",
    }
    if not required_forbidden.issubset(forbidden):
        raise TimingHypothesisRegistryError(
            "critical shortcuts are not forbidden"
        )

    return {
        "registry_version": registry["registry_version"],
        "status": registry["status"],
        "sha256": registry_sha256(registry),
        "family_count": len(families),
        "hypothesis_count": len(hypotheses),
        "state_count": len(states),
    }


def load_registry(path: Path = REGISTRY_PATH) -> tuple[dict, dict]:
    registry = json.loads(Path(path).read_text(encoding="utf-8"))
    return registry, validate_registry(registry)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    args = parser.parse_args()
    _, audit = load_registry(args.registry)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
