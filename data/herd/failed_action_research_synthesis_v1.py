"""실패한 행동 연구를 목표·정보·경제성·신규 정보 관점에서 통합 감사한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
REPORT = ROOT / "data/reports/failed_action_research_synthesis_v1.json"


class FailedActionSynthesisError(ValueError):
    """Raised when locked failure evidence is missing, changed, or promoted."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_inputs(protocol: dict[str, Any]) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for item in protocol.get("inputs", []):
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise FailedActionSynthesisError(f"missing or unsafe input: {item['path']}")
        if _sha256(path) != item.get("sha256"):
            raise FailedActionSynthesisError(f"input hash changed: {item['path']}")
        loaded[item["id"]] = json.loads(path.read_text(encoding="utf-8"))
    if len(loaded) != 7:
        raise FailedActionSynthesisError("synthesis input set is incomplete")
    return loaded


def _all_experiments(failure_map: dict[str, Any]) -> list[dict[str, Any]]:
    parent_path = ROOT / failure_map["parent"]["path"]
    if _sha256(parent_path) != failure_map["parent"]["sha256"]:
        raise FailedActionSynthesisError("failed-hypothesis parent hash changed")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    experiments = parent["experiments"] + failure_map["appended_experiments"]
    if len(experiments) != 11 or any(row.get("decision") != "REJECTED" for row in experiments):
        raise FailedActionSynthesisError("failure ledger must contain eleven rejected experiments")
    return experiments


def _domain_summary(
    experiments: list[dict[str, Any]], domains: dict[str, list[str]]
) -> list[dict[str, Any]]:
    family_to_domain = {
        family: domain for domain, families in domains.items() for family in families
    }
    unknown = sorted({row["economic_family"] for row in experiments} - set(family_to_domain))
    if unknown:
        raise FailedActionSynthesisError(f"unclassified economic families: {unknown}")
    counts = Counter(family_to_domain[row["economic_family"]] for row in experiments)
    return [
        {
            "domain": domain,
            "experiment_count": counts[domain],
            "experiment_ids": [
                row["id"]
                for row in experiments
                if family_to_domain[row["economic_family"]] == domain
            ],
        }
        for domain in domains
    ]


def _baseline_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row
        for row in report["summaries"]
        if row["one_way_cost_bps"] == 10 and row["policy_id"] != "MATCHED_HOLD"
    ]
    expected = 2 * 4
    if len(rows) != expected:
        raise FailedActionSynthesisError("fixed-policy 10 bps comparison is incomplete")
    return [
        {
            "universe_role": row["universe_role"],
            "policy_id": row["policy_id"],
            "events": row["events"],
            "median_net_terminal_wealth_delta": row[
                "median_normalized_net_terminal_wealth_delta"
            ],
            "positive_net_value_rate": row["positive_net_value_rate"],
            "median_downside_avoided": row["median_downside_avoided"],
        }
        for row in rows
    ]


def synthesize(protocol_path: Path = PROTOCOL) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_SYNTHESIS":
        raise FailedActionSynthesisError("synthesis protocol is not locked")
    if protocol.get("authority", {}).get("operational_action_ratio") != 0.0:
        raise FailedActionSynthesisError("synthesis cannot have action authority")
    loaded = _load_inputs(protocol)
    failure_map = loaded["FAILED_HYPOTHESES"]
    experiments = _all_experiments(failure_map)
    path_target = loaded["RUSH_PATH_TARGET"]
    price_audit = loaded["PRICE_INFORMATION_AUDIT"]
    ceiling = loaded["OPPORTUNITY_CEILING"]
    baselines = loaded["FIXED_POLICY_BASELINES"]
    feasibility = loaded["LEADING_INFORMATION_FEASIBILITY"]
    identity_review = loaded["SEC_8K_IDENTITY_REVIEW"]

    if failure_map["audit_summary"]["adoptable_direction_count"] != 0:
        raise FailedActionSynthesisError("failure map unexpectedly admits direction evidence")
    if path_target["retained_count"] != 0 or path_target["profit_take_authorized"]:
        raise FailedActionSynthesisError("pre-damage target unexpectedly became separable")
    if baselines["direction_evidence_admitted"]:
        raise FailedActionSynthesisError("fixed policy baseline cannot become direction evidence")

    baseline_rows = _baseline_rows(baselines)
    target_exists = bool(ceiling["passed"])
    target_separable = failure_map["audit_summary"]["adoptable_direction_count"] > 0
    fixed_policy_safe = all(
        row["median_net_terminal_wealth_delta"] >= 0 for row in baseline_rows
    )
    distinct_source_ready = bool(
        feasibility["decision"]["new_historical_direction_hypothesis_allowed"]
    )
    new_hypothesis_allowed = target_separable and fixed_policy_safe and distinct_source_ready

    benign_events = (
        path_target["path_counts"]["TEMPORARY_PULLBACK"]
        + path_target["path_counts"]["RESUMED_UPTREND"]
    )
    adverse_events = (
        path_target["path_counts"]["LARGE_PULLBACK"]
        + path_target["path_counts"]["STRUCTURAL_BREAK"]
    )
    return {
        "report_version": "HERD_FAILED_ACTION_RESEARCH_SYNTHESIS_V1",
        "status": "SYNTHESIS_COMPLETE_NEW_HYPOTHESIS_BLOCKED",
        "protocol_sha256": _sha256(protocol_path),
        "target_validity_audit": {
            "economic_opportunity_exists": target_exists,
            "observed_events": path_target["classified_events"],
            "benign_events": benign_events,
            "benign_fraction": benign_events / path_target["classified_events"],
            "adverse_events": adverse_events,
            "adverse_fraction": adverse_events / path_target["classified_events"],
            "pre_damage_separators_retained": path_target["retained_count"],
            "independent_direction_experiments_admitted": failure_map[
                "audit_summary"
            ]["adoptable_direction_count"],
            "target_is_currently_separable": target_separable,
            "decision": "ECONOMIC_OPPORTUNITY_EXISTS_BUT_PRE_ACTION_CLASSIFICATION_IS_UNPROVEN",
        },
        "economic_family_redundancy_audit": {
            "locked_rejected_experiments": len(experiments),
            "domains": _domain_summary(experiments, protocol["economic_domains"]),
            "comparable_price_features": len(price_audit["features"]),
            "stable_redundant_price_pairs": len(price_audit["stable_redundant_pairs"]),
            "high_vif_price_features": len(price_audit["high_vif_features"]),
            "pca_components_for_90_percent": price_audit["pca"][
                "components_for_target"
            ],
            "price_family_compressed": price_audit["family_compressed"],
            "interpretation": "PRICE_FEATURES_ARE_NOT_NEAR_DUPLICATES_BUT_SHARE_A_PRICE_DERIVED_INFORMATION_BOUNDARY_AND_NONE_PROVED_DIRECTION",
        },
        "policy_opportunity_cost_audit": {
            "comparison_cost_bps": 10,
            "rows": baseline_rows,
            "all_non_control_medians_non_negative": fixed_policy_safe,
            "decision": "UNCONDITIONAL_FIVE_PERCENT_POLICIES_DO_NOT_CLEAR_BUY_AND_HOLD_FLOOR",
        },
        "distinct_information_availability_decision": {
            "historical_direction_source_ready_count": feasibility["decision"][
                "primary_long_horizon_source_ready_count"
            ],
            "prospective_shadow_source_count": feasibility["decision"][
                "prospective_shadow_source_count"
            ],
            "source_decisions": feasibility["source_decisions"],
            "sec_8k_identity_review_status": identity_review["status"],
            "sec_8k_reviewed_rows": identity_review["reviewed_rows"],
            "sec_8k_direction_hypothesis_allowed": identity_review[
                "direction_hypothesis_allowed"
            ],
            "distinct_historical_source_ready": distinct_source_ready,
            "decision": "NO_DISTINCT_HISTORICAL_DIRECTION_SOURCE_READY",
        },
        "next_stage": {
            "id": "INDEPENDENT_INFORMATION_ROLE_AND_COVERAGE_AUDIT",
            "new_hypothesis_allowed": new_hypothesis_allowed,
            "purpose": "Decide which evidence roles can be populated without pretending that observation context is direction evidence.",
            "investment_review_implication": "KEEP_SEPARATE_EVIDENCE_LANES_BUT_NO_VOTE_OR_FINAL_ACTION_SYNTHESIS",
        },
        "blind_holdout_access": False,
        "herd_formula_change_allowed": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()
    report = synthesize(args.protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
