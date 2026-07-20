"""HERD 연구 모델의 운영 승격 검토 자격을 판정한다.

수치 통과는 운영 배포가 아니라 사람의 검토를 받을 수 있는 후보 자격만 부여한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AdoptionThresholds:
    version: str = "2026.07-v3"
    minimum_coverage: float = 0.95
    minimum_universe_size: int = 55
    minimum_oos_years: float = 5.0
    minimum_median_excess_cagr: float = 0.0
    minimum_positive_excess_rate: float = 60.0
    minimum_upside_capture: float = 0.85
    maximum_downside_capture: float = 0.90
    minimum_cost_stress_excess_cagr: float = 0.0
    minimum_average_exposure: float = 0.80
    minimum_oos_improvement_rate: float = 60.0
    minimum_oos_mdd_improvement: float = 0.0
    minimum_bottom_decile_capture: float = 60.0
    minimum_parameter_stability: float = 70.0
    maximum_pbo: float = 0.20
    minimum_dsr_probability: float = 0.95


def _criterion(name: str, passed: bool, actual: Any, threshold: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "actual": actual, "threshold": threshold}


def evaluate_adoption_gate(
    metadata: dict[str, Any],
    thresholds: AdoptionThresholds = AdoptionThresholds(),
    *,
    stage: str = "FINAL",
) -> dict[str, Any]:
    """검증 메타데이터를 fail-closed 방식으로 평가한다."""
    if stage not in {"PRE_HOLDOUT", "FINAL"}:
        raise ValueError("stage must be PRE_HOLDOUT or FINAL")
    run = metadata.get("validation_run", {})
    walk = metadata.get("walk_forward_summary", {})
    stability = metadata.get("parameter_stability", {})
    transition = stability.get("transition_stability", {})
    overfitting = metadata.get("overfitting", {})
    cscv = overfitting.get("cscv", {})
    dsr = overfitting.get("deflated_sharpe", {})
    survivorship = metadata.get("survivorship_coverage", {})
    parameter_policy = metadata.get("parameter_policy", {})
    benchmark = metadata.get("benchmark_summary", {})
    cost_stress = metadata.get("cost_stress", {})
    action_efficacy = metadata.get("action_efficacy", {})
    blind = metadata.get("blind_holdout", {})

    coverage = run.get("coverage")
    universe_size = run.get("universe_size")
    oos_years = run.get("oos_years")
    median_excess_cagr = benchmark.get("median_excess_cagr")
    positive_excess_rate = benchmark.get("positive_excess_rate")
    upside_capture = benchmark.get("median_upside_capture")
    downside_capture = benchmark.get("median_downside_capture")
    stressed_excess_cagr = cost_stress.get("median_excess_cagr")
    average_exposure = benchmark.get("median_average_exposure")
    improvement_rate = walk.get("improvement_rate")
    mdd_improvement = walk.get("mdd_improvement_median")
    bottom_capture = walk.get("capture_bottom_decile_mean")
    stability_rate = transition.get("same_parameter_rate")
    pbo = cscv.get("pbo")
    dsr_probability = dsr.get("probability")

    criteria = [
        _criterion("validation_complete", run.get("status") == "COMPLETE", run.get("status"), "COMPLETE"),
        _criterion("coverage", coverage is not None and coverage >= thresholds.minimum_coverage,
                   coverage, f">={thresholds.minimum_coverage}"),
        _criterion("universe_size", universe_size is not None and universe_size >= thresholds.minimum_universe_size,
                   universe_size, f">={thresholds.minimum_universe_size}"),
        _criterion("oos_years", oos_years is not None and oos_years >= thresholds.minimum_oos_years,
                   oos_years, f">={thresholds.minimum_oos_years}"),
        _criterion("score_parity", metadata.get("score_parity", {}).get("passed") is True,
                   metadata.get("score_parity", {}).get("passed"), True),
        _criterion("fixed_parameter_policy",
                   parameter_policy.get("mode") == "fixed"
                   and parameter_policy.get("automatic_selection_applied") is False,
                   parameter_policy.get("mode"), "fixed"),
        _criterion("median_excess_cagr",
                   median_excess_cagr is not None and median_excess_cagr > thresholds.minimum_median_excess_cagr,
                   median_excess_cagr, f">{thresholds.minimum_median_excess_cagr}"),
        _criterion("positive_excess_rate",
                   positive_excess_rate is not None and positive_excess_rate >= thresholds.minimum_positive_excess_rate,
                   positive_excess_rate, f">={thresholds.minimum_positive_excess_rate}"),
        _criterion("upside_capture",
                   upside_capture is not None and upside_capture >= thresholds.minimum_upside_capture,
                   upside_capture, f">={thresholds.minimum_upside_capture}"),
        _criterion("downside_capture",
                   downside_capture is not None and downside_capture <= thresholds.maximum_downside_capture,
                   downside_capture, f"<={thresholds.maximum_downside_capture}"),
        _criterion("cost_stress",
                   stressed_excess_cagr is not None
                   and stressed_excess_cagr > thresholds.minimum_cost_stress_excess_cagr,
                   stressed_excess_cagr, f">{thresholds.minimum_cost_stress_excess_cagr}"),
        _criterion(
            "average_exposure",
            average_exposure is not None
            and average_exposure >= thresholds.minimum_average_exposure,
            average_exposure,
            f">={thresholds.minimum_average_exposure}",
        ),
        _criterion(
            "completed_action_cycle_metrics",
            action_efficacy.get("status") == "COMPLETE"
            and action_efficacy.get("required_metrics_complete") is True,
            {
                "status": action_efficacy.get("status"),
                "required_metrics_complete": action_efficacy.get(
                    "required_metrics_complete"
                ),
            },
            {
                "status": "COMPLETE",
                "required_metrics_complete": True,
            },
        ),
        _criterion("oos_improvement_rate", improvement_rate is not None and improvement_rate >= thresholds.minimum_oos_improvement_rate,
                   improvement_rate, f">={thresholds.minimum_oos_improvement_rate}"),
        _criterion("oos_mdd_improvement", mdd_improvement is not None and mdd_improvement >= thresholds.minimum_oos_mdd_improvement,
                   mdd_improvement, f">={thresholds.minimum_oos_mdd_improvement}"),
        _criterion("bottom_decile_capture", bottom_capture is not None and bottom_capture >= thresholds.minimum_bottom_decile_capture,
                   bottom_capture, f">={thresholds.minimum_bottom_decile_capture}"),
        _criterion("parameter_stability", stability_rate is not None and stability_rate >= thresholds.minimum_parameter_stability,
                   stability_rate, f">={thresholds.minimum_parameter_stability}"),
        _criterion("no_single_parameter_spike", stability.get("single_parameter_spike") is False,
                   stability.get("single_parameter_spike"), False),
        _criterion("pbo", pbo is not None and pbo <= thresholds.maximum_pbo,
                   pbo, f"<={thresholds.maximum_pbo}"),
        _criterion("deflated_sharpe", dsr_probability is not None and dsr_probability >= thresholds.minimum_dsr_probability,
                   dsr_probability, f">={thresholds.minimum_dsr_probability}"),
        _criterion("survivorship", survivorship.get("point_in_time_ready") is True,
                   survivorship.get("status"), "POINT_IN_TIME_READY"),
    ]
    if stage == "FINAL":
        criteria.append(
            _criterion("blind_holdout_single_use",
                       blind.get("status") == "COMPLETE"
                       and blind.get("evaluation_count") == 1
                       and blind.get("passed") is True,
                       {
                           "status": blind.get("status"),
                           "evaluation_count": blind.get("evaluation_count"),
                           "passed": blind.get("passed"),
                       },
                       {"status": "COMPLETE", "evaluation_count": 1, "passed": True})
        )
    failed = [item["name"] for item in criteria if not item["passed"]]
    eligible = not failed
    return {
        "policy_version": thresholds.version,
        "stage": stage,
        "status": (
            "READY_FOR_BLIND_HOLDOUT"
            if eligible and stage == "PRE_HOLDOUT"
            else "PROMOTION_CANDIDATE"
            if eligible
            else "RESEARCH_VALIDATION"
        ),
        "eligible_for_holdout": eligible if stage == "PRE_HOLDOUT" else False,
        "eligible_for_human_review": eligible if stage == "FINAL" else False,
        "automatic_production_promotion": False,
        "failed_criteria": failed,
        "criteria": criteria,
    }
