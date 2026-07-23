"""vNext 단일 결합 가설의 패널 생성과 고정 복잡도 로지스틱 모델."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from herd.validation_universe import TICKER_SECTOR_ETF
from herd.long_price_snapshot import verify_snapshot
from herd.vnext_competing_path_economic_label_v1 import (
    classify_competing_path,
    load_contract as load_label_contract,
)


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json").with_name(
    "vnext_joint_hypothesis_v1.json"
)
PROTOCOL_VERSION = "HERD_VNEXT_JOINT_HYPOTHESIS_V1"


class VNextJointModelError(ValueError):
    """결합 가설의 데이터 시점·복잡도·역할 계약 위반."""


@dataclass(frozen=True)
class FittedJointModel:
    feature_names: tuple[str, ...]
    medians: dict[str, float]
    scales: dict[str, float]
    coefficients: tuple[float, ...]
    l2_penalty: float


def load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    if (
        protocol.get("protocol_version") != PROTOCOL_VERSION
        or protocol.get("status") != "LOCKED_BEFORE_JOINT_MODEL_RESULTS"
    ):
        raise VNextJointModelError("joint hypothesis is not locked")
    blocks = protocol.get("blocks", {})
    expected = [
        "MARKET_AND_SECTOR_REGIME",
        "STOCK_EXTENSION_AND_TRANSITION",
        "PEER_PARTICIPATION",
        "PIT_BUSINESS_VETO",
    ]
    if list(blocks) != expected or any(not blocks[name] for name in expected):
        raise VNextJointModelError("evidence block contract changed")
    model = protocol.get("model", {})
    if (
        model.get("family") != "RIDGE_LOGISTIC_REGRESSION"
        or model.get("l2_penalty") != 1.0
        or model.get("hyperparameter_search") is not False
    ):
        raise VNextJointModelError("model complexity is not fixed")
    interaction = protocol.get("single_interaction", {})
    if (
        interaction.get("id") != "STOCK_TREND_DAMAGE_X_PEER_HIGH_EXIT"
        or "TREND_QUALITY_DELTA_4W" not in interaction.get("formula", "")
        or "PEER_HIGH_EXIT_SHARE_DELTA_4W" not in interaction.get("formula", "")
    ):
        raise VNextJointModelError("single economic interaction changed")
    boundary = protocol.get("data_boundary", {})
    if (
        boundary.get("historical_role") != "PRE_HOLDOUT_ONLY"
        or boundary.get("survivorship_safe") is not False
        or boundary.get("final_blind_evidence") != "PROSPECTIVE_SHADOW_ONLY"
    ):
        raise VNextJointModelError("historical evidence boundary changed")
    forbidden = set(protocol.get("forbidden", []))
    required = {
        "SEARCH_L2_PENALTY",
        "ADD_INTERACTIONS_AFTER_RESULTS",
        "USE_PATH_LABEL_AS_FEATURE",
        "USE_PIT_FACT_ACCEPTED_AFTER_SIGNAL",
        "TREAT_BUSINESS_VETO_AS_STANDALONE_SELL",
        "AUTHORIZE_OPERATIONAL_ACTION",
    }
    if not required.issubset(forbidden):
        raise VNextJointModelError("critical anti-overfit boundary is missing")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "locked": True,
        "blocks": expected,
        "single_interaction": interaction["id"],
        "l2_penalty": 1.0,
        "historical_role": "PRE_HOLDOUT_ONLY",
        "survivorship_safe": False,
        "operational_action_authority": False,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_snapshot_frames(
    snapshot: Path,
    tickers: set[str],
    manifest: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    manifest = manifest or verify_snapshot(snapshot)
    missing = sorted(tickers - set(manifest["files"]))
    if missing:
        raise VNextJointModelError(f"snapshot missing tickers: {missing[:5]}")
    frames = {}
    for ticker in sorted(tickers):
        item = manifest["files"][ticker]
        path = snapshot / item["path"]
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as stream:
            frame = pd.read_csv(stream, parse_dates=["Date"]).set_index("Date")
        frames[ticker] = frame
    return frames


def _peer_feature_series(
    snapshot: Path,
    universe_path: Path,
    event_dates: pd.DataFrame,
    manifest: dict[str, Any] | None = None,
) -> pd.DataFrame:
    audit = pd.read_csv(universe_path)
    eligible = audit[audit["eligible"].astype(str).str.lower().eq("true")].copy()
    manifest = manifest or verify_snapshot(snapshot)
    rows = []
    for sector_etf, subjects in event_dates.groupby("sector_etf"):
        peers = eligible[eligible["sector_etf"] == sector_etf]["ticker"].tolist()
        peers = [ticker for ticker in peers if ticker in manifest["files"]]
        if len(peers) < 8:
            continue
        weekly = {}
        for ticker in peers:
            item = manifest["files"][ticker]
            path = snapshot / item["path"]
            opener = gzip.open if path.suffix == ".gz" else open
            with opener(path, "rt", encoding="utf-8") as stream:
                frame = pd.read_csv(stream, parse_dates=["Date"])
            weekly[ticker] = (
                frame.set_index("Date")["Adj Close"].astype(float).resample("W-FRI").last()
            )
        close = pd.DataFrame(weekly).sort_index()
        near_high = close.div(close.rolling(52, min_periods=52).max()).ge(0.95)
        advancing = close.pct_change(4, fill_method=None).gt(0)
        valid_near = close.notna() & close.rolling(52, min_periods=52).max().notna()
        valid_advance = close.pct_change(4, fill_method=None).notna()
        near_share = near_high.where(valid_near).mean(axis=1)
        advance_share = advancing.where(valid_advance).mean(axis=1)
        features = pd.DataFrame(
            {
                "feature_week": close.index,
                "PEER_HIGH_EXIT_SHARE_DELTA_4W": (1.0 - near_share).diff(4),
                "PEER_ADVANCE_BREADTH_DELTA_4W": advance_share.diff(4),
            }
        )
        left = subjects.sort_values("signal_date").copy()
        merged = pd.merge_asof(
            left,
            features.sort_values("feature_week"),
            left_on="signal_date",
            right_on="feature_week",
            direction="backward",
        )
        merged["peer_count"] = len(peers)
        rows.append(merged)
    if not rows:
        raise VNextJointModelError("no peer sectors met the minimum peer count")
    return pd.concat(rows, ignore_index=True)


def _attach_business_state(
    panel: pd.DataFrame,
    business_path: Path,
) -> pd.DataFrame:
    business = pd.read_csv(business_path)
    business["month_end"] = pd.to_datetime(business["month_end"])
    # 월말 스냅샷은 그날의 전체 접수 내역을 포함할 수 있으므로 다음 날짜부터만
    # 사용한다. 일자만 있는 가격 신호에서는 당일 접수시각을 추정하지 않는다.
    business["business_available_date"] = business["month_end"] + pd.Timedelta(
        days=1
    )
    business["latest_fact_accepted_at"] = pd.to_datetime(
        business["latest_fact_accepted_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)
    parts = []
    for ticker, events in panel.groupby("ticker", sort=True):
        left = events.sort_values("signal_date")
        right = business[business["ticker"] == ticker].sort_values("month_end")
        if right.empty:
            merged = left.copy()
            merged["guard_state"] = "UNKNOWN"
            merged["latest_fact_accepted_at"] = pd.NaT
        else:
            merged = pd.merge_asof(
                left,
                right[
                    [
                        "month_end",
                        "business_available_date",
                        "guard_state",
                        "latest_fact_accepted_at",
                        "flag_count",
                    ]
                ],
                left_on="signal_date",
                right_on="business_available_date",
                direction="backward",
            )
        parts.append(merged)
    result = pd.concat(parts, ignore_index=True)
    leaked = result["latest_fact_accepted_at"].notna() & (
        result["latest_fact_accepted_at"].dt.normalize() >= result["signal_date"]
    )
    if leaked.any():
        raise VNextJointModelError("PIT business fact leaked past signal")
    result["guard_state"] = result["guard_state"].fillna("UNKNOWN")
    result["BUSINESS_VETO"] = result["guard_state"].eq("VETO").astype(float)
    result["BUSINESS_UNKNOWN"] = result["guard_state"].eq("UNKNOWN").astype(float)
    return result


def build_joint_panel(
    protocol: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    locked = protocol or load_protocol()
    protocol_audit = validate_protocol(locked)
    boundary = locked["data_boundary"]
    episodes = pd.read_csv(ROOT / boundary["episode_source"])
    episodes["signal_date"] = pd.to_datetime(episodes["signal_date"])
    episodes["last_observed_session"] = pd.to_datetime(
        episodes["last_observed_session"]
    )
    episodes["sector_etf"] = episodes["ticker"].map(TICKER_SECTOR_ETF)
    if episodes["sector_etf"].isna().any():
        raise VNextJointModelError("episode sector mapping is incomplete")

    subjects = set(episodes["ticker"])
    price_snapshot = ROOT / boundary["price_snapshot"]
    peer_snapshot = ROOT / boundary["peer_snapshot"]
    price_manifest = verify_snapshot(price_snapshot)
    peer_manifest = verify_snapshot(peer_snapshot)
    subject_frames = _read_snapshot_frames(
        price_snapshot,
        subjects,
        price_manifest,
    )
    label_contract = load_label_contract()
    labels = []
    for event in episodes.itertuples(index=False):
        outcome = classify_competing_path(
            subject_frames[event.ticker],
            event.last_observed_session,
            label_contract,
        )
        labels.append(
            {
                "ticker": event.ticker,
                "episode_id": event.episode_id,
                "first_boundary": outcome.first_boundary,
                "vnext_path_label": outcome.terminal_path,
                "vnext_outcome_end": outcome.outcome_end,
            }
        )
    panel = episodes.drop(columns=["path_label"]).merge(
        pd.DataFrame(labels),
        on=["ticker", "episode_id"],
        how="left",
        validate="one_to_one",
    )
    peer_input = panel[
        ["ticker", "episode_id", "signal_date", "sector_etf"]
    ].copy()
    peers = _peer_feature_series(
        peer_snapshot,
        ROOT / "data/reports/independent_universe_v1.csv",
        peer_input,
        peer_manifest,
    )
    panel = panel.merge(
        peers[
            [
                "ticker",
                "episode_id",
                "feature_week",
                "peer_count",
                "PEER_HIGH_EXIT_SHARE_DELTA_4W",
                "PEER_ADVANCE_BREADTH_DELTA_4W",
            ]
        ],
        on=["ticker", "episode_id"],
        how="left",
        validate="one_to_one",
    )
    panel = _attach_business_state(panel, ROOT / boundary["business_source"])

    positive = set(locked["target"]["positive"])
    negative = set(locked["target"]["negative"])
    panel["target"] = np.where(
        panel["vnext_path_label"].isin(positive),
        1.0,
        np.where(panel["vnext_path_label"].isin(negative), 0.0, np.nan),
    )
    feature_columns = [
        feature for features in locked["blocks"].values() for feature in features
    ]
    report = {
        "report_version": "HERD_VNEXT_JOINT_PANEL_V1",
        "status": "PRE_HOLDOUT_PANEL_READY",
        "protocol": protocol_audit,
        "episodes": len(panel),
        "tickers": int(panel["ticker"].nunique()),
        "path_counts": panel["vnext_path_label"].value_counts().to_dict(),
        "fit_eligible_rows": int(panel["target"].notna().sum()),
        "feature_missing_fraction": {
            column: float(panel[column].isna().mean()) for column in feature_columns
        },
        "business_state_counts": panel["guard_state"].value_counts().to_dict(),
        "minimum_peer_count": (
            int(panel["peer_count"].min())
            if panel["peer_count"].notna().any()
            else None
        ),
        "input_artifacts": {
            "joint_protocol_sha256": _sha256(PROTOCOL_PATH),
            "label_contract_sha256": _sha256(
                ROOT
                / "data/herd/vnext_competing_path_economic_label_v1.json"
            ),
            "episode_source_sha256": _sha256(
                ROOT / boundary["episode_source"]
            ),
            "business_source_sha256": _sha256(
                ROOT / boundary["business_source"]
            ),
            "price_snapshot_sha256": price_manifest["snapshot_sha256"],
            "peer_snapshot_sha256": peer_manifest["snapshot_sha256"],
        },
        "historical_role": "PRE_HOLDOUT_ONLY",
        "survivorship_safe": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    }
    return panel, report


def _feature_names(
    protocol: dict[str, Any],
    omitted_block: str | None = None,
    *,
    include_interaction: bool = True,
) -> list[str]:
    names = [
        feature
        for block, features in protocol["blocks"].items()
        if block != omitted_block
        for feature in features
    ]
    parents = {"STOCK_EXTENSION_AND_TRANSITION", "PEER_PARTICIPATION"}
    if include_interaction and omitted_block not in parents:
        names.append(protocol["single_interaction"]["id"])
    return names


def _base_feature_values(frame: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
    base = frame[[name for name in feature_names if name in frame.columns]].astype(
        float
    )
    return base.replace([np.inf, -np.inf], np.nan)


def _design_matrix(
    frame: pd.DataFrame,
    feature_names: list[str],
    medians: dict[str, float],
    scales: dict[str, float],
) -> np.ndarray:
    base_names = [name for name in feature_names if name in frame.columns]
    base = _base_feature_values(frame, feature_names)
    standardized = pd.DataFrame(index=frame.index)
    for name in base_names:
        standardized[name] = (
            base[name].fillna(medians[name]) - medians[name]
        ) / scales[name]
    columns = [standardized[name].to_numpy() for name in base_names]
    interaction = "STOCK_TREND_DAMAGE_X_PEER_HIGH_EXIT"
    if interaction in feature_names:
        columns.append(
            -standardized["TREND_QUALITY_DELTA_4W"].to_numpy()
            * standardized["PEER_HIGH_EXIT_SHARE_DELTA_4W"].to_numpy()
        )
    return np.column_stack([np.ones(len(frame)), *columns])


def fit_joint_model(
    train: pd.DataFrame,
    protocol: dict[str, Any] | None = None,
    *,
    omitted_block: str | None = None,
    include_interaction: bool = True,
) -> FittedJointModel:
    locked = protocol or load_protocol()
    validate_protocol(locked)
    if omitted_block is not None and omitted_block not in locked["blocks"]:
        raise VNextJointModelError("unknown ablation block")
    eligible = train[train["target"].isin([0.0, 1.0])].copy()
    if eligible["target"].nunique() != 2:
        raise VNextJointModelError("training fold requires both target classes")
    feature_names = _feature_names(
        locked,
        omitted_block,
        include_interaction=include_interaction,
    )
    base = _base_feature_values(eligible, feature_names)
    all_missing = [name for name in base if base[name].notna().sum() == 0]
    if all_missing:
        raise VNextJointModelError(
            f"training fold has all-missing features: {all_missing}"
        )
    medians = {name: float(base[name].median()) for name in base.columns}
    scales = {}
    for name in base.columns:
        scale = float(base[name].quantile(0.75) - base[name].quantile(0.25))
        if not np.isfinite(scale) or scale <= 1e-12:
            scale = float(base[name].std(ddof=0))
        scales[name] = scale if np.isfinite(scale) and scale > 1e-12 else 1.0
    x = _design_matrix(eligible, feature_names, medians, scales)
    y = eligible["target"].to_numpy(dtype=float)
    penalty = float(locked["model"]["l2_penalty"])
    beta = np.zeros(x.shape[1], dtype=float)
    regularizer = np.eye(x.shape[1]) * penalty
    regularizer[0, 0] = 0.0
    converged = False
    for _ in range(int(locked["model"]["maximum_iterations"])):
        logits = np.clip(x @ beta, -35, 35)
        probabilities = 1.0 / (1.0 + np.exp(-logits))
        weights = np.clip(probabilities * (1.0 - probabilities), 1e-8, None)
        gradient = x.T @ (probabilities - y) + regularizer @ beta
        hessian = x.T @ (x * weights[:, None]) + regularizer
        step = np.linalg.lstsq(hessian, gradient, rcond=None)[0]
        next_beta = beta - step
        if np.max(np.abs(next_beta - beta)) < float(
            locked["model"]["convergence_tolerance"]
        ):
            beta = next_beta
            converged = True
            break
        beta = next_beta
    if not converged:
        raise VNextJointModelError("fixed logistic model did not converge")
    return FittedJointModel(
        feature_names=tuple(feature_names),
        medians=medians,
        scales=scales,
        coefficients=tuple(float(value) for value in beta),
        l2_penalty=penalty,
    )


def predict_joint_probability(
    model: FittedJointModel,
    frame: pd.DataFrame,
) -> np.ndarray:
    x = _design_matrix(
        frame,
        list(model.feature_names),
        model.medians,
        model.scales,
    )
    logits = np.clip(x @ np.asarray(model.coefficients), -35, 35)
    return 1.0 / (1.0 + np.exp(-logits))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    panel, report = build_joint_panel()
    args.panel.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.panel, index=False)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
