"""Walk-forward 파라미터 선택 안정성 진단."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median
from typing import Any


def _frequencies(rows: list[dict], key: str) -> dict[str, dict[str, float | int]]:
    counts = Counter(str(row[key]) for row in rows)
    total = len(rows)
    return {value: {"count": count, "rate": count / total * 100} for value, count in sorted(counts.items())}


def _selection_value(row: dict, key: str):
    return row.get(f"selected_{key}", row[key])


def _transition_stability(rows: list[dict]) -> dict[str, float | int | None]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["ticker"], row.get("mode", "unknown"))].append(row)
    comparisons = stable = 0
    for group in grouped.values():
        ordered = sorted(group, key=lambda row: row["test_start"])
        for previous, current in zip(ordered, ordered[1:]):
            comparisons += 1
            stable += (
                _selection_value(previous, "ratio_scale"),
                _selection_value(previous, "cooldown_days"),
            ) == (
                _selection_value(current, "ratio_scale"),
                _selection_value(current, "cooldown_days"),
            )
    return {"comparisons": comparisons, "same_parameter_count": stable,
            "same_parameter_rate": stable / comparisons * 100 if comparisons else None}


def analyze_parameter_stability(rows: list[dict], spike_threshold: float = 5.0) -> dict[str, Any]:
    if not rows:
        return {"samples": 0, "recommendation": "INSUFFICIENT_DATA"}
    diagnostic_rows = [
        {
            **row,
            "ratio_scale": _selection_value(row, "ratio_scale"),
            "cooldown_days": _selection_value(row, "cooldown_days"),
        }
        for row in rows
    ]
    combinations = Counter(f"{row['ratio_scale']}|{row['cooldown_days']}" for row in diagnostic_rows)
    objectives: dict[str, list[float]] = defaultdict(list)
    for row in diagnostic_rows:
        key = f"{row['ratio_scale']}|{row['cooldown_days']}"
        objectives[key].append(float(row["v61_return"]) + float(row["v61_mdd"]) * 0.5)
    medians = {key: median(values) for key, values in objectives.items()}
    ordered = sorted(medians.items(), key=lambda item: item[1], reverse=True)
    best_gap = ordered[0][1] - ordered[1][1] if len(ordered) > 1 else None
    dominant_rate = max(combinations.values()) / len(diagnostic_rows) * 100
    transition = _transition_stability(diagnostic_rows)
    unstable = (
        dominant_rate < 35
        or (transition["same_parameter_rate"] is not None and transition["same_parameter_rate"] < 40)
        or (best_gap is not None and best_gap > spike_threshold)
    )
    return {
        "samples": len(rows),
        "basis": "train_selection_diagnostics",
        "ratio_scale_frequency": _frequencies(diagnostic_rows, "ratio_scale"),
        "cooldown_frequency": _frequencies(diagnostic_rows, "cooldown_days"),
        "combination_frequency": dict(sorted(combinations.items())),
        "transition_stability": transition,
        "objective_median_by_combination": medians,
        "best_vs_second_gap": best_gap,
        "single_parameter_spike": best_gap is not None and best_gap > spike_threshold,
        "recommendation": "USE_FIXED_PARAMETERS" if unstable else "AUTO_SELECTION_ACCEPTABLE",
    }
