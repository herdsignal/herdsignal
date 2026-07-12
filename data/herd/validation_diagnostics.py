"""Validation v2 OOS 실패 원인을 집계하는 순수 분석 모듈."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from herd.validation_universe import SECTOR_UNIVERSE

TICKER_GROUP = {ticker: group for group, tickers in SECTOR_UNIVERSE.items() for ticker in tickers}
MATERIALITY = 0.05


def market_regime(buyhold_return: float) -> str:
    if buyhold_return <= -10: return "bear"
    if buyhold_return >= 10: return "bull"
    return "sideways"


def enrich(row: dict) -> dict:
    out = dict(row)
    out["sector_group"] = TICKER_GROUP.get(row["ticker"], "unknown")
    out["market_regime"] = market_regime(float(row["buyhold_return"]))
    out["return_delta_vs_fixed"] = float(row["v61_return"]) - float(row["fixed_return"])
    out["mdd_delta_vs_fixed"] = float(row["v61_mdd"]) - float(row["fixed_mdd"])
    out["return_status"] = "improved" if out["return_delta_vs_fixed"] > MATERIALITY else "worse" if out["return_delta_vs_fixed"] < -MATERIALITY else "equal"
    out["mdd_status"] = "improved" if out["mdd_delta_vs_fixed"] > MATERIALITY else "worse" if out["mdd_delta_vs_fixed"] < -MATERIALITY else "equal"
    out["return_improved"] = out["return_status"] == "improved"
    out["mdd_improved"] = out["mdd_status"] == "improved"
    out["joint_pass"] = out["return_status"] != "worse" and out["mdd_status"] != "worse"
    out["severity"] = abs(min(0.0, out["return_delta_vs_fixed"])) + abs(min(0.0, out["mdd_delta_vs_fixed"])) * 2
    reasons = []
    if out["return_status"] == "worse": reasons.append("lower_return_than_fixed")
    if out["mdd_status"] == "worse": reasons.append("worse_mdd_than_fixed")
    if out["market_regime"] == "bear" and out["mdd_status"] == "worse": reasons.append("bear_market_defense_failure")
    if out["market_regime"] == "bull" and out["return_status"] == "worse": reasons.append("bull_market_capture_failure")
    out["failure_reasons"] = reasons
    return out


def group_summary(rows: list[dict], key: str) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows: grouped[str(row[key])].append(row)
    result = []
    for value, items in sorted(grouped.items()):
        result.append({
            key: value,
            "samples": len(items),
            "return_improvement_rate": sum(i["return_improved"] for i in items) / len(items) * 100,
            "mdd_improvement_rate": sum(i["mdd_improved"] for i in items) / len(items) * 100,
            "joint_pass_rate": sum(i["joint_pass"] for i in items) / len(items) * 100,
            "return_underperformance_rate": sum(i["return_status"] == "worse" for i in items) / len(items) * 100,
            "mdd_underperformance_rate": sum(i["mdd_status"] == "worse" for i in items) / len(items) * 100,
            "median_return_delta": median(i["return_delta_vs_fixed"] for i in items),
            "median_mdd_delta": median(i["mdd_delta_vs_fixed"] for i in items),
        })
    return result


def diagnose(rows: list[dict]) -> dict:
    enriched = [enrich(row) for row in rows]
    ticker_stats = group_summary(enriched, "ticker")
    repeated = sorted(
        [row for row in ticker_stats if row["return_improvement_rate"] < 50 or row["joint_pass_rate"] < 40],
        key=lambda row: (row["joint_pass_rate"], row["return_improvement_rate"]),
    )
    reason_counts = Counter(reason for row in enriched for reason in row["failure_reasons"])
    parameter_counts = Counter((str(row.get("ratio_scale")), str(row.get("cooldown_days"))) for row in enriched)
    severe = sorted(enriched, key=lambda row: row["severity"], reverse=True)[:20]
    return {
        "summary": {
            "samples": len(enriched),
            "return_improvement_rate": sum(row["return_improved"] for row in enriched) / len(enriched) * 100,
            "mdd_improvement_rate": sum(row["mdd_improved"] for row in enriched) / len(enriched) * 100,
            "joint_pass_rate": sum(row["joint_pass"] for row in enriched) / len(enriched) * 100,
            "return_underperformance_rate": sum(row["return_status"] == "worse" for row in enriched) / len(enriched) * 100,
            "mdd_underperformance_rate": sum(row["mdd_status"] == "worse" for row in enriched) / len(enriched) * 100,
            "materiality_tolerance_pct_point": MATERIALITY,
            "failure_reasons": dict(reason_counts),
            "selected_parameters": {f"scale={key[0]},cooldown={key[1]}": count for key, count in parameter_counts.items()},
        },
        "by_sector": group_summary(enriched, "sector_group"),
        "by_year": group_summary(enriched, "test_start"),
        "by_market_regime": group_summary(enriched, "market_regime"),
        "by_mode": group_summary(enriched, "mode"),
        "repeated_failure_tickers": repeated,
        "most_severe_failures": severe,
        "rows": enriched,
    }


def write_diagnostics(source: Path, output_dir: Path) -> tuple[Path, Path]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    report = diagnose(payload["walk_forward"])
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "oos_diagnostics.json"
    csv_path = output_dir / "oos_failures.csv"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    failures = [row for row in report["rows"] if not row["joint_pass"]]
    if failures:
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=failures[0].keys())
            writer.writeheader(); writer.writerows(failures)
    return json_path, csv_path
