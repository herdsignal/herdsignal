"""Outcome-blind HERD State S1을 계산하고 두 고정 유니버스에서 안정성을 감사한다."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from herd.validation_universe import SECTOR_UNIVERSE, TICKER_SECTOR_ETF


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
DEFAULT_OUTPUT_DIR = ROOT / "data/walk_forward/herd-state-s1"
DEFAULT_REPORT = ROOT / "data/reports/herd_state_s1.json"
DEFAULT_LATEST = ROOT / "data/reports/herd_state_s1_latest.csv"
FAMILY_COLUMNS = [
    "PRICE_EXTENSION",
    "TREND_POSITION",
    "RELATIVE_POSITION",
    "PARTICIPATION",
]


class HerdStateS1Error(RuntimeError):
    """고정 입력·계산 계약이 깨졌을 때 발생한다."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise HerdStateS1Error(f"missing pinned input: {relative}")
    return path


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version") != "HERD_STATE_S1"
        or contract.get("status") != "LOCKED_BEFORE_STATE_STABILITY_RESULTS"
    ):
        raise HerdStateS1Error("HERD State S1 contract is not locked")
    if set(contract["legacy_boundary"].values()) != {
        "REFERENCE_ONLY_NO_FORMULA_OR_WEIGHT_REUSE"
    }:
        raise HerdStateS1Error("legacy formulas must remain reference-only")
    if contract["observation_contract"]["future_outcomes_allowed"]:
        raise HerdStateS1Error("state construction cannot read future outcomes")
    if contract["claim_boundary"]["operational_action_ratio"] != 0.0:
        raise HerdStateS1Error("state construction cannot authorize actions")
    weights = [float(item["weight"]) for item in contract["families"]]
    if len(weights) != 4 or not np.isclose(sum(weights), 1.0) or len(set(weights)) != 1:
        raise HerdStateS1Error("S1 requires four fixed equally weighted families")
    for specification in contract["inputs"].values():
        path = _rooted(specification["path"])
        if _sha256(path) != specification["sha256"]:
            raise HerdStateS1Error(f"pinned input hash changed: {specification['path']}")
    return contract


def _load_snapshot(manifest_path: Path, required: set[str]) -> dict[str, pd.DataFrame]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing = sorted(required - set(manifest.get("files", {})))
    if missing:
        raise HerdStateS1Error(f"snapshot is missing required tickers: {missing}")
    frames: dict[str, pd.DataFrame] = {}
    for ticker in sorted(required):
        item = manifest["files"][ticker]
        path = manifest_path.parent / item["path"]
        if _sha256(path) != item["sha256"]:
            raise HerdStateS1Error(f"price hash changed: {ticker}")
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            frame = pd.read_csv(stream, parse_dates=["Date"])
        if frame["Date"].duplicated().any() or not frame["Date"].is_monotonic_increasing:
            raise HerdStateS1Error(f"invalid price order: {ticker}")
        frames[ticker] = frame
    return frames


def _primary_mapping(manifest_path: Path) -> dict[str, str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    benchmarks = set(SECTOR_UNIVERSE["benchmark"])
    return {
        ticker: sector
        for ticker, sector in TICKER_SECTOR_ETF.items()
        if ticker not in benchmarks
        and ticker in manifest["files"]
        and manifest["files"][ticker].get("role") == "EQUITY"
    }


def _independent_mapping(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return {
        row["ticker"]: row["sector_etf"]
        for row in rows
        if row["eligible"] == "True"
    }


def _close(frame: pd.DataFrame) -> pd.Series:
    return (
        frame.set_index("Date")["Adj Close"]
        .astype(float)
        .sort_index()
        .replace([np.inf, -np.inf], np.nan)
    )


def _rolling_percentile(
    series: pd.Series,
    window: int,
    minimum: int,
) -> pd.Series:
    clean = series.replace([np.inf, -np.inf], np.nan)
    return clean.rolling(window, min_periods=minimum).rank(pct=True) * 100


def _component_scores(
    stock: pd.DataFrame,
    sector: pd.DataFrame,
    spy: pd.DataFrame,
    peer_breadth: pd.Series,
    contract: dict[str, Any],
) -> pd.DataFrame:
    stock_indexed = stock.set_index("Date").sort_index()
    close = stock_indexed["Adj Close"].astype(float)
    volume = stock_indexed["Volume"].astype(float)
    sector_close = _close(sector).reindex(close.index).ffill(limit=3)
    spy_close = _close(spy).reindex(close.index).ffill(limit=3)
    returns = close.pct_change(fill_method=None)
    realized_volatility = returns.rolling(63, min_periods=63).std(ddof=1) * np.sqrt(252)
    safe_volatility = realized_volatility.clip(lower=0.05)
    sma200 = close.rolling(200, min_periods=200).mean()
    low252 = close.rolling(252, min_periods=252).min()
    high252 = close.rolling(252, min_periods=252).max()
    range_width = (high252 - low252).replace(0, np.nan)

    signed_volume = np.sign(returns).fillna(0) * volume
    downside = returns.where(returns < 0)
    raw = pd.DataFrame(
        {
            "EXTENSION_MA200": np.log(close / sma200) / safe_volatility,
            "EXTENSION_RANGE": (close - low252) / range_width,
            "TREND_126": np.log(close / close.shift(126)) / safe_volatility,
            "TREND_252": np.log(close / close.shift(252)) / safe_volatility,
            "RELATIVE_STOCK_SECTOR": (
                np.log(close / close.shift(126))
                - np.log(sector_close / sector_close.shift(126))
            ),
            "RELATIVE_SECTOR_SPY": (
                np.log(sector_close / sector_close.shift(126))
                - np.log(spy_close / spy_close.shift(126))
            ),
            "PARTICIPATION_VOLUME": (
                signed_volume.rolling(63, min_periods=63).sum()
                / volume.rolling(63, min_periods=63).sum()
            ),
            "PARTICIPATION_PEERS": peer_breadth.reindex(close.index).ffill(limit=3),
            "DOWNSIDE_RISK_RAW": downside.rolling(63, min_periods=20).std(ddof=1)
            * np.sqrt(252),
        },
        index=close.index,
    )
    observation = contract["observation_contract"]
    window = int(observation["normalization_window_sessions"])
    minimum = int(observation["minimum_normalization_sessions"])
    scored = pd.DataFrame(
        {
            column: _rolling_percentile(raw[column], window, minimum)
            for column in raw.columns
        },
        index=raw.index,
    )
    return pd.DataFrame(
        {
            "PRICE_EXTENSION": scored[["EXTENSION_MA200", "EXTENSION_RANGE"]].median(axis=1),
            "TREND_POSITION": scored[["TREND_126", "TREND_252"]].median(axis=1),
            "RELATIVE_POSITION": scored[
                ["RELATIVE_STOCK_SECTOR", "RELATIVE_SECTOR_SPY"]
            ].median(axis=1),
            "PARTICIPATION": scored[
                ["PARTICIPATION_VOLUME", "PARTICIPATION_PEERS"]
            ].median(axis=1),
            "DOWNSIDE_RISK_CONTEXT": scored["DOWNSIDE_RISK_RAW"],
        },
        index=raw.index,
    )


def _peer_breadth(
    frames: dict[str, pd.DataFrame],
    mapping: dict[str, str],
) -> dict[str, pd.Series]:
    closes = pd.concat(
        {ticker: _close(frames[ticker]) for ticker in mapping},
        axis=1,
        sort=True,
    ).ffill(limit=3)
    returns_63 = closes.pct_change(63)
    sma200 = closes.rolling(200, min_periods=200).mean()
    valid = returns_63.notna() & sma200.notna()
    positive_trend = ((returns_63 > 0) & (closes > sma200)).where(valid)
    breadth: dict[str, pd.Series] = {}
    for sector in sorted(set(mapping.values())):
        tickers = [ticker for ticker, mapped in mapping.items() if mapped == sector]
        minimum_peers = min(3, len(tickers))
        breadth[sector] = positive_trend[tickers].mean(axis=1).where(
            positive_trend[tickers].notna().sum(axis=1) >= minimum_peers
        )
    return breadth


def _stage(score: pd.Series) -> pd.Series:
    return pd.cut(
        score,
        bins=[-np.inf, 15, 40, 60, 75, np.inf],
        labels=["FLEE", "SCATTER", "CALM", "DRIFT", "RUSH"],
        right=False,
    ).astype("string")


def build_state_panel(
    frames: dict[str, pd.DataFrame],
    mapping: dict[str, str],
    contract: dict[str, Any],
    universe_role: str,
    *,
    peer_mapping: dict[str, str] | None = None,
) -> pd.DataFrame:
    # 운영 화면에서 포트폴리오 종목이 추가·삭제될 때 참여도 기준까지
    # 흔들리지 않도록 출력 대상과 고정 peer universe를 분리할 수 있다.
    # 연구 재현 경로는 인자를 생략하므로 기존 결과가 그대로 유지된다.
    breadth = _peer_breadth(frames, peer_mapping or mapping)
    parts: list[pd.DataFrame] = []
    for ticker, sector in sorted(mapping.items()):
        scored = _component_scores(
            frames[ticker],
            frames[sector],
            frames["SPY"],
            breadth[sector],
            contract,
        )
        scored["last_observed_session"] = scored.index
        weekly = scored.resample("W-FRI").last()
        weekly = weekly.dropna(subset=FAMILY_COLUMNS)
        weekly["HERD_STATE"] = weekly[FAMILY_COLUMNS].mean(axis=1)
        weekly["HERD_STAGE"] = _stage(weekly["HERD_STATE"])
        weekly["ticker"] = ticker
        weekly["sector_etf"] = sector
        weekly["universe_role"] = universe_role
        weekly["signal_date"] = weekly.index
        parts.append(weekly.reset_index(drop=True))
    if not parts:
        raise HerdStateS1Error(f"no state rows emitted for {universe_role}")
    return pd.concat(parts, ignore_index=True).sort_values(
        ["ticker", "signal_date"]
    )


def _stability_summary(
    panel: pd.DataFrame,
    contract: dict[str, Any],
    role: str,
) -> dict[str, Any]:
    gates = contract["stability_gates"]
    rows_per_ticker = panel.groupby("ticker").size()
    scores = panel["HERD_STATE"]
    stage_fraction = panel["HERD_STAGE"].value_counts(normalize=True).to_dict()
    weekly_change = panel.groupby("ticker")["HERD_STATE"].diff().abs()
    pairwise = panel[FAMILY_COLUMNS].corr(method="spearman")
    pairwise_values = pairwise.where(
        ~np.eye(len(FAMILY_COLUMNS), dtype=bool)
    ).stack()
    latest = panel.sort_values("signal_date").groupby("ticker").tail(1)
    latest_sector_medians = latest.groupby("sector_etf")["HERD_STATE"].median()
    long_run_sector_medians = panel.groupby("sector_etf")["HERD_STATE"].median()
    score_span = float(scores.quantile(0.99) - scores.quantile(0.01))
    minimum_tickers = (
        gates["primary_minimum_covered_tickers"]
        if role == "PRIMARY"
        else gates["independent_minimum_covered_tickers"]
    )
    checks = {
        "minimum_covered_tickers": int(panel["ticker"].nunique()) >= minimum_tickers,
        "minimum_median_weekly_rows": float(rows_per_ticker.median())
        >= gates["minimum_median_weekly_rows"],
        "minimum_score_span": score_span
        >= gates["minimum_score_1_to_99_percentile_span"],
        "minimum_flee_fraction": float(stage_fraction.get("FLEE", 0))
        >= gates["minimum_flee_fraction"],
        "minimum_rush_fraction": float(stage_fraction.get("RUSH", 0))
        >= gates["minimum_rush_fraction"],
        "maximum_weekly_jump_fraction": float((weekly_change >= 25).mean())
        <= gates["maximum_25_point_weekly_jump_fraction"],
        "maximum_pairwise_family_spearman": float(pairwise_values.abs().max())
        <= gates["maximum_pairwise_family_spearman"],
        "maximum_long_run_sector_median_spread": float(
            long_run_sector_medians.max() - long_run_sector_medians.min()
        )
        <= gates["maximum_long_run_sector_median_spread"],
    }
    return {
        "role": role,
        "rows": int(len(panel)),
        "tickers": int(panel["ticker"].nunique()),
        "date_start": str(panel["signal_date"].min().date()),
        "date_end": str(panel["signal_date"].max().date()),
        "median_weekly_rows_per_ticker": float(rows_per_ticker.median()),
        "score_1_to_99_percentile_span": score_span,
        "stage_fraction": {key: float(value) for key, value in stage_fraction.items()},
        "weekly_25_point_jump_fraction": float((weekly_change >= 25).mean()),
        "pairwise_family_spearman": {
            left: {right: float(value) for right, value in values.items()}
            for left, values in pairwise.to_dict().items()
        },
        "maximum_absolute_pairwise_family_spearman": float(
            pairwise_values.abs().max()
        ),
        "long_run_sector_median_spread": float(
            long_run_sector_medians.max() - long_run_sector_medians.min()
        ),
        "latest_sector_median_spread_diagnostic": float(
            latest_sector_medians.max() - latest_sector_medians.min()
        ),
        "checks": checks,
        "passed": all(checks.values()),
    }


def _write_panel(panel: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.gz")
    panel.to_csv(temporary, index=False, compression="gzip")
    os.replace(temporary, path)


def run(
    contract_path: Path = CONTRACT_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_path: Path = DEFAULT_REPORT,
    latest_path: Path = DEFAULT_LATEST,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    primary_manifest = _rooted(
        contract["inputs"]["primary_snapshot_manifest"]["path"]
    )
    independent_manifest = _rooted(
        contract["inputs"]["independent_snapshot_manifest"]["path"]
    )
    independent_universe = _rooted(
        contract["inputs"]["independent_universe"]["path"]
    )
    specifications = [
        ("PRIMARY", primary_manifest, _primary_mapping(primary_manifest)),
        (
            "INDEPENDENT_CURRENT_CONSTITUENTS",
            independent_manifest,
            _independent_mapping(independent_universe),
        ),
    ]
    summaries = []
    latest_parts = []
    panel_receipts = {}
    for role, manifest_path, mapping in specifications:
        required = set(mapping) | set(mapping.values()) | {"SPY"}
        frames = _load_snapshot(manifest_path, required)
        panel = build_state_panel(frames, mapping, contract, role)
        filename = role.lower() + ".csv.gz"
        panel_path = output_dir / filename
        _write_panel(panel, panel_path)
        summaries.append(_stability_summary(panel, contract, role))
        latest_parts.append(
            panel.sort_values("signal_date").groupby("ticker").tail(1)
        )
        panel_receipts[role] = {
            "path": str(panel_path.relative_to(ROOT)),
            "sha256": _sha256(panel_path),
            "rows": int(len(panel)),
        }
    latest = pd.concat(latest_parts, ignore_index=True).sort_values(
        ["universe_role", "ticker"]
    )
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest.to_csv(latest_path, index=False)
    passed = all(item["passed"] for item in summaries)
    report = {
        "report_version": "HERD_STATE_S1",
        "status": "STATE_DISPLAY_READY" if passed else "STATE_STABILITY_GATE_FAILED",
        "contract_sha256": _sha256(contract_path),
        "input_manifest_sha256": {
            role: _sha256(manifest)
            for role, manifest, _ in specifications
        },
        "panels": panel_receipts,
        "universes": summaries,
        "latest_rows": int(len(latest)),
        "latest_sha256": _sha256(latest_path),
        "future_outcomes_read": False,
        "direction_prediction": False,
        "buy_or_profit_take_authority": False,
        "operational_action_ratio": 0.0,
        "survivorship_safe": False,
        "state_display_ready": passed,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--latest", type=Path, default=DEFAULT_LATEST)
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.contract, args.output_dir, args.report, args.latest),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
