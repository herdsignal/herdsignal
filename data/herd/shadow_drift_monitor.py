"""운영 모델과 연구 후보의 shadow 관측 차이를 fail-closed로 감사한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import ceil
from statistics import median
from typing import Any, Iterable


@dataclass(frozen=True)
class ShadowDriftThresholds:
    minimum_observations: int = 500
    minimum_coverage: float = 0.99
    maximum_stale_rate: float = 0.01
    maximum_score_median_absolute_error: float = 10.0
    maximum_score_p95_absolute_error: float = 25.0
    maximum_action_disagreement_rate: float = 0.10


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def evaluate_shadow_drift(
    observations: Iterable[dict[str, Any]],
    *,
    as_of: date,
    thresholds: ShadowDriftThresholds = ShadowDriftThresholds(),
) -> dict[str, Any]:
    """동일 시점의 운영/후보 출력을 비교한다.

    후보 출력이 없거나 날짜가 잘못된 행은 coverage 실패로 계산한다.
    이 결과는 승격을 허용하지 않고 사람의 검토를 차단하거나 요청하는 데만 쓴다.
    """
    rows = list(observations)
    paired: list[dict[str, Any]] = []
    stale_count = 0
    for row in rows:
        observed_on = _parse_date(row.get("observed_on"))
        if observed_on is not None and observed_on < as_of:
            stale_count += 1
        required = (
            observed_on,
            row.get("ticker"),
            row.get("production_score"),
            row.get("shadow_score"),
            row.get("production_action"),
            row.get("shadow_action"),
        )
        if all(value is not None for value in required):
            paired.append(row)

    total = len(rows)
    coverage = len(paired) / total if total else 0.0
    stale_rate = stale_count / total if total else 1.0
    score_errors = [
        abs(float(row["production_score"]) - float(row["shadow_score"]))
        for row in paired
    ]
    disagreements = sum(
        str(row["production_action"]) != str(row["shadow_action"])
        for row in paired
    )
    disagreement_rate = disagreements / len(paired) if paired else 1.0

    metrics = {
        "observation_count": total,
        "paired_count": len(paired),
        "coverage": coverage,
        "stale_rate": stale_rate,
        "score_median_absolute_error": median(score_errors) if score_errors else None,
        "score_p95_absolute_error": _percentile(score_errors, 0.95) if score_errors else None,
        "action_disagreement_rate": disagreement_rate,
    }
    failures = [
        name
        for name, passed in (
            ("minimum_observations", total >= thresholds.minimum_observations),
            ("coverage", coverage >= thresholds.minimum_coverage),
            ("stale_rate", stale_rate <= thresholds.maximum_stale_rate),
            (
                "score_median_absolute_error",
                bool(score_errors)
                and metrics["score_median_absolute_error"]
                <= thresholds.maximum_score_median_absolute_error,
            ),
            (
                "score_p95_absolute_error",
                bool(score_errors)
                and metrics["score_p95_absolute_error"]
                <= thresholds.maximum_score_p95_absolute_error,
            ),
            (
                "action_disagreement_rate",
                disagreement_rate <= thresholds.maximum_action_disagreement_rate,
            ),
        )
        if not passed
    ]
    return {
        "status": "OBSERVATION_READY" if not failures else "BLOCKED_DRIFT_REVIEW",
        "promotion_authorized": False,
        "metrics": metrics,
        "failed_checks": failures,
    }
