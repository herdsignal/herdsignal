"""후보 전체 이력 기반 백테스트 과최적화 진단."""

from __future__ import annotations

import itertools
import math
from collections import defaultdict
from statistics import NormalDist, mean, pstdev
from typing import Any


def _candidate_matrix(history: list[dict]) -> dict[str, dict[str, float]]:
    matrix: dict[str, dict[str, float]] = defaultdict(dict)
    for row in history:
        matrix[str(row["evaluation_id"])][str(row["candidate_id"])] = float(row["objective"])
    return dict(matrix)


def cscv_pbo(history: list[dict], max_splits: int = 200) -> dict[str, Any]:
    """평가 구간을 절반씩 나눠 학습 최상위 후보의 OOS 순위로 PBO를 계산한다."""
    matrix = _candidate_matrix(history)
    evaluations = sorted(matrix)
    candidates = sorted(set.intersection(*(set(matrix[key]) for key in evaluations))) if evaluations else []
    half = len(evaluations) // 2
    if len(evaluations) < 4 or len(candidates) < 2 or half == 0:
        return {"splits": 0, "pbo": None, "status": "INSUFFICIENT_DATA"}
    logits: list[float] = []
    for train_ids in itertools.islice(itertools.combinations(evaluations, half), max_splits):
        train_set = set(train_ids)
        test_ids = [key for key in evaluations if key not in train_set]
        train_mean = {c: mean(matrix[e][c] for e in train_ids) for c in candidates}
        selected = max(candidates, key=train_mean.get)
        test_mean = {c: mean(matrix[e][c] for e in test_ids) for c in candidates}
        ordered = sorted(candidates, key=test_mean.get)
        rank = ordered.index(selected) + 1
        percentile = (rank - 0.5) / len(candidates)
        logits.append(math.log(percentile / (1 - percentile)))
    pbo = sum(value <= 0 for value in logits) / len(logits) * 100
    return {"splits": len(logits), "pbo": pbo, "median_logit": sorted(logits)[len(logits) // 2],
            "status": "HIGH_RISK" if pbo >= 50 else "ACCEPTABLE"}


def deflated_sharpe_ratio(returns_pct: list[float], trials: int) -> dict[str, float | int | None | str]:
    """시험 후보 수로 기대 최대 Sharpe를 보정한 DSR 확률을 계산한다."""
    values = [float(value) / 100 for value in returns_pct]
    if len(values) < 3 or pstdev(values) == 0:
        return {"observations": len(values), "trials": trials, "probability": None, "status": "INSUFFICIENT_DATA"}
    avg, sigma = mean(values), pstdev(values)
    sharpe = avg / sigma
    n = len(values)
    centered = [(value - avg) / sigma for value in values]
    skew = mean(value ** 3 for value in centered)
    kurtosis = mean(value ** 4 for value in centered)
    normal = NormalDist()
    effective_trials = max(1, trials)
    gamma = 0.5772156649
    expected_max = 0.0 if effective_trials == 1 else (
        (1 - gamma) * normal.inv_cdf(1 - 1 / effective_trials)
        + gamma * normal.inv_cdf(1 - 1 / (effective_trials * math.e))
    )
    denominator = math.sqrt(max(1e-12, 1 - skew * sharpe + (kurtosis - 1) * sharpe * sharpe / 4))
    probability = normal.cdf((sharpe - expected_max) * math.sqrt(n - 1) / denominator) * 100
    return {"observations": n, "trials": effective_trials, "sharpe": sharpe,
            "expected_max_sharpe": expected_max, "probability": probability,
            "status": "PASS" if probability >= 95 else "FAIL"}


def sensitivity_table(history: list[dict]) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in history:
        grouped[str(row["candidate_id"])].append(float(row["objective"]))
    return {key: {"samples": len(values), "mean": mean(values), "std": pstdev(values)}
            for key, values in sorted(grouped.items())}


def analyze_overfitting(history: list[dict], oos_rows: list[dict]) -> dict[str, Any]:
    candidates = {row["candidate_id"] for row in history}
    return {"candidate_evaluations": len(history), "parameters_tested": len(candidates),
            "cscv": cscv_pbo(history),
            "deflated_sharpe": deflated_sharpe_ratio([row["v61_return"] for row in oos_rows], len(candidates)),
            "parameter_sensitivity": sensitivity_table(history)}
