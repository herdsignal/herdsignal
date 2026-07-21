"""시장·섹터 공통수익을 제거한 종목 고유 충격을 독립 발견 비교한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.reentry_feature_discovery_v1 import compare


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
FEATURES = ["RESIDUAL_RETURN_20D", "RESIDUAL_VOLATILITY_RATIO_20_63"]


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_FEATURE_RESULTS":
        raise ValueError("idiosyncratic shock protocol must be locked")
    if [row["id"] for row in protocol["candidate_features"]] != FEATURES:
        raise ValueError("idiosyncratic candidate set changed")
    return protocol


def _returns(frame: pd.DataFrame, name: str) -> pd.Series:
    values = frame[["Date", "Adj Close"]].copy()
    values["Date"] = pd.to_datetime(values["Date"])
    values = values.drop_duplicates("Date").set_index("Date")["Adj Close"].astype(float)
    return np.log(values).diff().rename(name)


def event_features(stock: pd.DataFrame, spy: pd.DataFrame, sector: pd.DataFrame, signal_date: pd.Timestamp, protocol: dict) -> dict:
    aligned = pd.concat([
        _returns(stock, "stock"), _returns(spy, "spy"), _returns(sector, "sector")
    ], axis=1, join="inner").dropna()
    aligned = aligned[aligned.index <= pd.Timestamp(signal_date)].tail(protocol["regression"]["lookback_sessions"])
    if len(aligned) < protocol["regression"]["minimum_observations"]:
        return {feature: np.nan for feature in FEATURES}
    design = np.column_stack([
        np.ones(len(aligned)), aligned["spy"].to_numpy(),
        (aligned["sector"] - aligned["spy"]).to_numpy(),
    ])
    coefficients = np.linalg.lstsq(design, aligned["stock"].to_numpy(), rcond=None)[0]
    residual = pd.Series(aligned["stock"].to_numpy() - design @ coefficients, index=aligned.index)
    recent = residual.iloc[-20:]
    prior = residual.iloc[-83:-20]
    prior_volatility = prior.std(ddof=1)
    return {
        FEATURES[0]: float(recent.sum()),
        FEATURES[1]: float(recent.std(ddof=1) / prior_volatility) if prior_volatility > 0 else np.nan,
    }


def attach_features(targets: pd.DataFrame, snapshot: Path, audit_path: Path, protocol: dict) -> pd.DataFrame:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    audit = pd.read_csv(audit_path).set_index("ticker")
    cache: dict[str, pd.DataFrame] = {}

    def frame(ticker: str) -> pd.DataFrame:
        if ticker not in cache:
            cache[ticker] = pd.read_csv(snapshot / manifest["files"][ticker]["path"], parse_dates=["Date"])
        return cache[ticker]

    rows = []
    for row in targets.itertuples(index=False):
        values = row._asdict()
        sector = audit.at[row.ticker, "sector_etf"]
        values.update(event_features(frame(row.ticker), frame("SPY"), frame(sector), pd.Timestamp(row.signal_date), protocol))
        rows.append(values)
    return pd.DataFrame(rows)


def evaluate(panel: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    adapter = {
        "candidate_features": protocol["candidate_features"], "comparison": protocol["comparison"],
        "retention_gate": {**protocol["retention_gate"], "minimum_absolute_rank_biserial": protocol["retention_gate"]["minimum_directional_rank_biserial"]},
    }
    table = compare(panel, adapter)
    directions = {row["id"]: row["expected_direction"] for row in protocol["candidate_features"]}
    table["expected_direction"] = table["feature"].map(directions)
    threshold = protocol["retention_gate"]["minimum_directional_rank_biserial"]
    table["direction_matched"] = table.apply(
        lambda row: row["rank_biserial"] <= -threshold if row["expected_direction"] == "LOWER" else row["rank_biserial"] >= threshold,
        axis=1,
    )
    table["retained_for_new_sample_preregistration"] &= table["direction_matched"]
    return table


def run(protocol_path: Path = PROTOCOL_PATH) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    if json.loads((ROOT / protocol["target_report"]).read_text(encoding="utf-8")).get("status") != "DISCOVERY_TARGET_READY":
        raise ValueError("reentry target is not ready")
    panel = attach_features(pd.read_csv(ROOT / protocol["target_rows"]), ROOT / protocol["snapshot"], ROOT / protocol["universe_audit"], protocol)
    comparison = evaluate(panel, protocol)
    retained = comparison.loc[comparison["retained_for_new_sample_preregistration"], "feature"].tolist()
    report = {
        "report_version": "HERD_IDIOSYNCRATIC_SHOCK_V1", "status": "DISCOVERY_COMPLETE",
        "target_events": len(panel), "features_compared": len(FEATURES), "retained_features": retained,
        "independent_oos_passed_features": [], "operational_action_ratio": 0.0, "blind_holdout_access": False,
    }
    return panel, comparison, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    panel, comparison, report = run()
    panel.to_csv(args.panel, index=False)
    comparison.to_json(args.comparison, orient="records", indent=2)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
