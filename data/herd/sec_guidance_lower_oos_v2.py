"""사전등록된 경영진 가이던스 하향 가설을 불변 가격에서 독립 평가한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


PROTOCOL = Path(__file__).with_suffix(".json")
PANEL_COLUMNS = [
    "ticker",
    "cik",
    "metric",
    "fiscal_period",
    "accounting_basis",
    "metric_subtype",
    "unit",
    "current_accession",
    "accepted_at",
    "fold_id",
    "direction",
    "midpoint_delta_ratio",
    "sector_etf",
    "price_snapshot",
    "execution_session",
    "outcome_session",
    "stock_return_126d",
    "sector_return_126d",
    "sector_residual_return_126d",
    "spy_return_126d",
    "spy_residual_return_126d",
    "forward_max_drawdown_126d",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_locked_inputs(protocol: dict) -> None:
    for artifact in protocol["locked_inputs"].values():
        path = Path(artifact["path"])
        if _sha256(path) != artifact["sha256"]:
            raise ValueError(f"locked input changed: {path}")


def _load_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for ticker, metadata in manifest["files"].items():
        price_path = path.parent / metadata["path"]
        if not price_path.exists():
            raise ValueError(f"missing immutable price file: {ticker}")
    return manifest


def _load_price(
    ticker: str,
    manifests: list[tuple[Path, dict]],
    cache: dict[tuple[str, str], pd.DataFrame],
) -> tuple[pd.DataFrame, str] | None:
    for manifest_path, manifest in manifests:
        if ticker not in manifest["files"]:
            continue
        key = (str(manifest_path), ticker)
        if key not in cache:
            metadata = manifest["files"][ticker]
            path = manifest_path.parent / metadata["path"]
            if _sha256(path) != metadata["sha256"]:
                raise ValueError(f"price bytes changed after snapshot lock: {ticker}")
            frame = pd.read_csv(path, parse_dates=["Date"]).sort_values("Date")
            required = {"Date", "Open", "Close", "Adj Close"}
            if not required.issubset(frame.columns):
                raise ValueError(f"price columns missing for {ticker}")
            factor = frame["Adj Close"].astype(float) / frame["Close"].astype(float)
            frame["Adj Open"] = frame["Open"].astype(float) * factor
            cache[key] = frame.set_index("Date")
        return cache[key], manifest["snapshot_id"]
    return None


def _forward_path(
    frame: pd.DataFrame, accepted_at: pd.Timestamp, horizon: int
) -> dict | None:
    accepted_date = accepted_at.tz_convert("UTC").tz_localize(None).normalize()
    future = frame.loc[frame.index > accepted_date]
    if len(future) < horizon:
        return None
    path = future.iloc[:horizon]
    entry = float(path["Adj Open"].iloc[0])
    if not np.isfinite(entry) or entry <= 0:
        return None
    closes = path["Adj Close"].astype(float)
    terminal_return = float(closes.iloc[-1] / entry - 1)
    wealth = pd.concat([pd.Series([entry]), closes.reset_index(drop=True)], ignore_index=True)
    max_drawdown = float((wealth / wealth.cummax() - 1).min())
    return {
        "execution_session": path.index[0],
        "outcome_session": path.index[-1],
        "terminal_return": terminal_return,
        "max_drawdown": max_drawdown,
    }


def _fold_id(date: pd.Timestamp, folds: list[dict]) -> str | None:
    normalized = date.tz_convert("UTC").tz_localize(None).normalize()
    for fold in folds:
        if pd.Timestamp(fold["start"]) <= normalized <= pd.Timestamp(fold["end"]):
            return fold["fold_id"]
    return None


def _bootstrap_mean(
    values: np.ndarray, iterations: int, seed: int
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    samples = rng.choice(values, size=(iterations, len(values)), replace=True).mean(axis=1)
    lower, upper = np.quantile(samples, [0.025, 0.975])
    return float(lower), float(upper)


def _issuer_effects(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (cik, ticker), group in panel.groupby(["cik", "ticker"]):
        treatment = group[group["direction"].eq("LOWER")]
        control = group[group["direction"].eq("NON_LOWER")]
        if treatment.empty or control.empty:
            continue
        rows.append({
            "cik": cik,
            "ticker": ticker,
            "lower_events": len(treatment),
            "control_events": len(control),
            "sector_residual_effect": (
                treatment["sector_residual_return_126d"].mean()
                - control["sector_residual_return_126d"].mean()
            ),
            "max_drawdown_effect": (
                treatment["forward_max_drawdown_126d"].mean()
                - control["forward_max_drawdown_126d"].mean()
            ),
        })
    return pd.DataFrame(rows)


def _fold_effects(panel: pd.DataFrame, folds: list[dict]) -> list[dict]:
    rows = []
    for fold in folds:
        group = panel[panel["fold_id"].eq(fold["fold_id"])]
        lower = group[group["direction"].eq("LOWER")]
        control = group[group["direction"].eq("NON_LOWER")]
        primary = (
            float(lower["sector_residual_return_126d"].median()
                  - control["sector_residual_return_126d"].median())
            if not lower.empty and not control.empty else None
        )
        drawdown = (
            float(lower["forward_max_drawdown_126d"].median()
                  - control["forward_max_drawdown_126d"].median())
            if not lower.empty and not control.empty else None
        )
        rows.append({
            "fold_id": fold["fold_id"],
            "events": len(group),
            "tickers": int(group["ticker"].nunique()),
            "lower_events": len(lower),
            "lower_tickers": int(lower["ticker"].nunique()),
            "sector_residual_effect": primary,
            "max_drawdown_effect": drawdown,
            "both_effects_in_preregistered_direction": bool(
                primary is not None and drawdown is not None
                and primary < 0 and drawdown < 0
            ),
        })
    return rows


def run(protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if protocol["status"] != "PREREGISTERED_BEFORE_PRICE_OUTCOME_JOIN":
        raise ValueError("guidance OOS protocol is not preregistered")
    _verify_locked_inputs(protocol)
    pair_report = json.loads(
        Path(protocol["locked_inputs"]["atomic_pair_report"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if not pair_report["pair_coverage_gate_passed"]:
        raise ValueError("atomic pair coverage gate did not pass")

    pairs = pd.read_csv(
        protocol["locked_inputs"]["atomic_pairs"]["path"], dtype={"cik": str}
    )
    pairs["accepted_at"] = pd.to_datetime(pairs["current_accepted_at"], utc=True)
    pairs["fold_id"] = pairs["accepted_at"].map(
        lambda value: _fold_id(value, protocol["folds"])
    )
    pairs = pairs[pairs["fold_id"].notna()].copy()
    pairs["direction"] = np.where(pairs["midpoint_delta"] < 0, "LOWER", "NON_LOWER")

    sector_map = pd.read_csv(
        protocol["locked_inputs"]["sector_map"]["path"]
    ).drop_duplicates("ticker").set_index("ticker")["sector_etf"].to_dict()
    manifest_paths = [
        Path(protocol["locked_inputs"]["primary_price_snapshot"]["path"]),
        Path(protocol["locked_inputs"]["supplemental_price_snapshot"]["path"]),
    ]
    manifests = [(path, _load_manifest(path)) for path in manifest_paths]
    cache: dict[tuple[str, str], pd.DataFrame] = {}
    horizon = int(protocol["timing"]["horizon_sessions"])
    cutoff = pd.Timestamp(protocol["timing"]["outcome_must_finish_by"])
    rows, exclusions = [], {}

    for pair in pairs.itertuples(index=False):
        sector = sector_map.get(pair.ticker)
        stock_loaded = _load_price(pair.ticker, manifests, cache)
        sector_loaded = _load_price(sector, manifests, cache) if sector else None
        spy_loaded = _load_price("SPY", manifests, cache)
        reason = None
        if not sector:
            reason = "SECTOR_MAPPING_MISSING"
        elif stock_loaded is None:
            reason = "STOCK_PRICE_MISSING"
        elif sector_loaded is None:
            reason = "SECTOR_PRICE_MISSING"
        elif spy_loaded is None:
            reason = "SPY_PRICE_MISSING"
        if reason:
            exclusions[reason] = exclusions.get(reason, 0) + 1
            continue
        stock_path = _forward_path(stock_loaded[0], pair.accepted_at, horizon)
        sector_path = _forward_path(sector_loaded[0], pair.accepted_at, horizon)
        spy_path = _forward_path(spy_loaded[0], pair.accepted_at, horizon)
        if stock_path is None or sector_path is None or spy_path is None:
            exclusions["INCOMPLETE_FORWARD_PATH"] = (
                exclusions.get("INCOMPLETE_FORWARD_PATH", 0) + 1
            )
            continue
        if max(
            stock_path["outcome_session"],
            sector_path["outcome_session"],
            spy_path["outcome_session"],
        ) > cutoff:
            exclusions["OUTCOME_AFTER_LOCKED_CUTOFF"] = (
                exclusions.get("OUTCOME_AFTER_LOCKED_CUTOFF", 0) + 1
            )
            continue
        rows.append({
            "ticker": pair.ticker,
            "cik": pair.cik,
            "metric": pair.metric,
            "fiscal_period": pair.fiscal_period,
            "accounting_basis": pair.accounting_basis,
            "metric_subtype": pair.metric_subtype,
            "unit": pair.unit,
            "current_accession": pair.current_accession,
            "accepted_at": pair.accepted_at.isoformat(),
            "fold_id": pair.fold_id,
            "direction": pair.direction,
            "midpoint_delta_ratio": pair.midpoint_delta_ratio,
            "sector_etf": sector,
            "price_snapshot": stock_loaded[1],
            "execution_session": stock_path["execution_session"],
            "outcome_session": stock_path["outcome_session"],
            "stock_return_126d": stock_path["terminal_return"],
            "sector_return_126d": sector_path["terminal_return"],
            "sector_residual_return_126d": (
                stock_path["terminal_return"] - sector_path["terminal_return"]
            ),
            "spy_return_126d": spy_path["terminal_return"],
            "spy_residual_return_126d": (
                stock_path["terminal_return"] - spy_path["terminal_return"]
            ),
            "forward_max_drawdown_126d": stock_path["max_drawdown"],
        })

    panel = pd.DataFrame(rows, columns=PANEL_COLUMNS)
    issuer_effects = _issuer_effects(panel)
    if issuer_effects.empty:
        primary_effect = drawdown_effect = None
        primary_ci = drawdown_ci = (None, None)
    else:
        primary_values = issuer_effects["sector_residual_effect"].to_numpy(float)
        drawdown_values = issuer_effects["max_drawdown_effect"].to_numpy(float)
        primary_effect = float(primary_values.mean())
        drawdown_effect = float(drawdown_values.mean())
        estimation = protocol["estimation"]
        primary_ci = _bootstrap_mean(
            primary_values, 10_000, estimation["bootstrap_seed"]
        )
        drawdown_ci = _bootstrap_mean(
            drawdown_values, 10_000, estimation["bootstrap_seed"] + 1
        )

    folds = _fold_effects(panel, protocol["folds"])
    consistent_folds = sum(
        fold["both_effects_in_preregistered_direction"] for fold in folds
    )
    lower = panel[panel["direction"].eq("LOWER")]
    gate = protocol["adoption_gate"]
    checks = {
        "minimum_evaluated_pairs": len(panel) >= gate["minimum_evaluated_pairs"],
        "minimum_evaluated_tickers": (
            panel["ticker"].nunique() >= gate["minimum_evaluated_tickers"]
        ),
        "minimum_lower_events": len(lower) >= gate["minimum_lower_events"],
        "minimum_lower_tickers": (
            lower["ticker"].nunique() >= gate["minimum_lower_tickers"]
        ),
        "minimum_issuers_with_both_classes": (
            len(issuer_effects) >= gate["minimum_issuers_with_both_classes"]
        ),
        "minimum_directionally_consistent_folds": (
            consistent_folds >= gate["minimum_directionally_consistent_folds"]
        ),
        "minimum_primary_effect": (
            primary_effect is not None
            and primary_effect <= gate["minimum_primary_effect"]
        ),
        "primary_bootstrap_95_upper": (
            primary_ci[1] is not None
            and primary_ci[1] < gate["primary_bootstrap_95_upper_must_be_below"]
        ),
        "minimum_drawdown_effect": (
            drawdown_effect is not None
            and drawdown_effect <= gate["minimum_drawdown_effect"]
        ),
        "drawdown_bootstrap_95_upper": (
            drawdown_ci[1] is not None
            and drawdown_ci[1] < gate["drawdown_bootstrap_95_upper_must_be_below"]
        ),
    }
    passed = all(checks.values())
    report = {
        "report_version": "herd-sec-guidance-lower-oos-v2",
        "status": "INDEPENDENT_OOS_COMPLETE",
        "hypothesis_id": protocol["economic_hypothesis"]["id"],
        "evaluated_pairs": len(panel),
        "evaluated_tickers": int(panel["ticker"].nunique()),
        "lower_events": len(lower),
        "lower_tickers": int(lower["ticker"].nunique()),
        "issuers_with_both_classes": len(issuer_effects),
        "issuer_balanced_sector_residual_effect": primary_effect,
        "issuer_cluster_bootstrap_95_interval": list(primary_ci),
        "issuer_balanced_max_drawdown_effect": drawdown_effect,
        "drawdown_cluster_bootstrap_95_interval": list(drawdown_ci),
        "directionally_consistent_folds": consistent_folds,
        "folds": folds,
        "gate_checks": checks,
        "adoption_gate_passed": passed,
        "decision": (
            "ADMIT_FUNDAMENTAL_DAMAGE_VETO_CANDIDATE"
            if passed else "REJECT_GUIDANCE_LOWER_HYPOTHESIS"
        ),
        "claim_boundary": protocol["claim_boundary"],
        "exclusions": exclusions,
        "price_outcomes_observed": True,
        "blind_holdout_access": False,
        "operational_action_authority": False,
        "operational_action_ratio": 0.0,
    }
    return panel, issuer_effects, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--issuer-effects", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    panel, issuer_effects, report = run(protocol)
    panel.to_csv(args.panel, index=False, float_format="%.12g", lineterminator="\n")
    issuer_effects.to_csv(
        args.issuer_effects, index=False, float_format="%.12g", lineterminator="\n"
    )
    report["protocol_sha256"] = _sha256(PROTOCOL)
    report["panel_sha256"] = _sha256(args.panel)
    report["issuer_effects_sha256"] = _sha256(args.issuer_effects)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
