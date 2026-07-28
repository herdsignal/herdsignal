"""S1 과거 재생 표본의 시대·섹터·동일 주간 의존성을 감사한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
DEFAULT_SUMMARY_PATH = (
    ROOT / "data/reports/historical_s1_dependency_summary_v1.csv"
)
DEFAULT_REPORT_PATH = (
    ROOT / "data/reports/historical_s1_dependency_audit_v1.json"
)
VERSION = "HERD_HISTORICAL_S1_DEPENDENCY_AUDIT_V1"


class HistoricalS1DependencyAuditError(RuntimeError):
    """입력 영수증·표본 경계 또는 행동 차단 계약이 깨졌을 때 발생한다."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise HistoricalS1DependencyAuditError(
            f"missing dependency audit input: {relative}"
        )
    return path


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    boundary = contract.get("claim_boundary", {})
    if (
        contract.get("contract_version") != VERSION
        or contract.get("status") != "LOCKED_DEPENDENCY_DIAGNOSTIC_ONLY"
        or contract.get("independence_units") != [
            "EPISODE", "TICKER", "SIGNAL_WEEK", "SECTOR_SIGNAL_WEEK", "ERA"
        ]
        or boundary.get("descriptive_outcomes_only") is not True
        or boundary.get("inferential_independence_claim") is not False
        or boundary.get("candidate_selection") is not False
        or boundary.get("direction_prediction") is not False
        or boundary.get("buy_or_profit_take_authority") is not False
        or boundary.get("operational_action") != "HOLD"
        or float(boundary.get("operational_action_ratio", -1)) != 0.0
        or boundary.get("blind_holdout_access") is not False
        or boundary.get("survivorship_safe") is not False
    ):
        raise HistoricalS1DependencyAuditError(
            "dependency audit contract is not locked"
        )
    return contract


def _stage(values: pd.Series) -> pd.Series:
    return pd.Series(
        np.select(
            [
                values < 15,
                values < 40,
                values < 60,
                values < 75,
            ],
            ["FLEE", "SCATTER", "CALM", "DRIFT"],
            default="RUSH",
        ),
        index=values.index,
    )


def build_regime_context(panel: pd.DataFrame) -> pd.DataFrame:
    required = {
        "ticker", "signal_date", "sector_etf", "HERD_STATE",
    }
    if not required.issubset(panel.columns):
        raise HistoricalS1DependencyAuditError(
            f"regime columns missing: {sorted(required - set(panel.columns))}"
        )
    rows = panel.copy()
    rows["signal_date"] = pd.to_datetime(rows["signal_date"], errors="coerce")
    rows["HERD_STATE"] = pd.to_numeric(rows["HERD_STATE"], errors="coerce")
    rows = rows.dropna(subset=["signal_date", "HERD_STATE"])
    rows = rows.drop_duplicates(["ticker", "signal_date"], keep="last")
    market = (
        rows.groupby("signal_date", sort=True)["HERD_STATE"]
        .median().rename("market_herd_state").reset_index()
    )
    market["market_herd_stage"] = _stage(market["market_herd_state"])
    sector = (
        rows.groupby(["signal_date", "sector_etf"], sort=True)["HERD_STATE"]
        .median().rename("sector_herd_state").reset_index()
    )
    sector["sector_herd_stage"] = _stage(sector["sector_herd_state"])
    return sector.merge(market, on="signal_date", how="left", validate="many_to_one")


def audit_dependency(
    ledger: pd.DataFrame,
    context: pd.DataFrame,
    contract: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame]:
    required = {
        "episode_id", "era_id", "universe_role", "ticker", "sector_etf",
        "signal_date", "event_kind", "horizon_sessions", "total_return",
        "maximum_favorable_excursion", "maximum_adverse_excursion",
        "direction_prediction", "operational_action", "operational_action_ratio",
    }
    if not required.issubset(ledger.columns):
        raise HistoricalS1DependencyAuditError(
            f"ledger columns missing: {sorted(required - set(ledger.columns))}"
        )
    rows = ledger.copy()
    rows["signal_date"] = pd.to_datetime(rows["signal_date"], errors="coerce")
    if rows["signal_date"].isna().any():
        raise HistoricalS1DependencyAuditError("ledger contains invalid signal dates")
    direction = rows["direction_prediction"]
    direction_locked = (
        direction.eq(False)
        if direction.dtype == bool
        else direction.astype(str).str.lower().eq("false")
    )
    if (
        not direction_locked.all()
        or not rows["operational_action"].eq("HOLD").all()
        or not pd.to_numeric(
            rows["operational_action_ratio"], errors="coerce"
        ).eq(0.0).all()
    ):
        raise HistoricalS1DependencyAuditError(
            "historical replay contains action authority"
        )
    if rows.duplicated(["episode_id", "horizon_sessions"]).any():
        raise HistoricalS1DependencyAuditError(
            "duplicate episode horizon in dependency input"
        )
    joined = rows.merge(
        context,
        on=["signal_date", "sector_etf"],
        how="left",
        validate="many_to_one",
    )
    if joined[[
        "market_herd_state", "market_herd_stage",
        "sector_herd_state", "sector_herd_stage",
    ]].isna().any().any():
        raise HistoricalS1DependencyAuditError(
            "market or sector regime context is incomplete"
        )
    episodes = joined.sort_values("horizon_sessions").drop_duplicates(
        "episode_id", keep="first"
    )
    week_counts = episodes.groupby("signal_date")["episode_id"].nunique()
    sector_week_count = int(
        episodes[["sector_etf", "signal_date"]].drop_duplicates().shape[0]
    )
    episode_count = int(episodes["episode_id"].nunique())
    gates = contract["diagnostic_gates"]
    single_week_fraction = (
        float(week_counts.max() / episode_count) if episode_count else 1.0
    )
    checks = {
        "minimum_signal_weeks": int(week_counts.size)
        >= int(gates["minimum_signal_weeks"]),
        "maximum_single_week_episode_fraction": single_week_fraction
        <= float(gates["maximum_single_week_episode_fraction"]),
    }
    group_columns = [
        "universe_role", "event_kind", "horizon_sessions", "era_id",
        "market_herd_stage", "sector_herd_stage",
    ]
    summary = (
        joined.groupby(group_columns, sort=True, observed=True)
        .agg(
            episodes=("episode_id", "nunique"),
            tickers=("ticker", "nunique"),
            signal_weeks=("signal_date", "nunique"),
            median_total_return=("total_return", "median"),
            positive_return_fraction=("total_return", lambda values: (values > 0).mean()),
            median_maximum_favorable_excursion=(
                "maximum_favorable_excursion", "median"
            ),
            median_maximum_adverse_excursion=(
                "maximum_adverse_excursion", "median"
            ),
        )
        .reset_index()
    )
    report = {
        "report_version": VERSION,
        "status": (
            "DEPENDENCY_DIAGNOSTIC_COMPLETE"
            if all(checks.values())
            else "DEPENDENCY_DIAGNOSTIC_GATE_FAILED"
        ),
        "independence_units": {
            "raw_horizon_rows": int(len(joined)),
            "episodes": episode_count,
            "tickers": int(episodes["ticker"].nunique()),
            "signal_weeks": int(week_counts.size),
            "sector_signal_weeks": sector_week_count,
            "eras": int(episodes["era_id"].nunique()),
        },
        "cluster_concentration": {
            "median_episodes_per_signal_week": float(week_counts.median()),
            "maximum_episodes_in_one_signal_week": int(week_counts.max()),
            "maximum_single_week_episode_fraction": single_week_fraction,
            "top_10_signal_week_episode_fraction": float(
                week_counts.nlargest(10).sum() / episode_count
            ),
        },
        "checks": checks,
        "inferential_independence_claim": False,
        "candidate_selection": False,
        "direction_prediction": False,
        "buy_or_profit_take_authority": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "survivorship_safe": False,
    }
    return report, summary


def _load_transition_panel(report: dict[str, Any]) -> pd.DataFrame:
    panels = []
    for role, receipt in report["panels"].items():
        path = _rooted(receipt["path"])
        if _sha256(path) != receipt["sha256"]:
            raise HistoricalS1DependencyAuditError(
                f"transition panel hash changed: {role}"
            )
        panels.append(pd.read_csv(path, compression="gzip"))
    return pd.concat(panels, ignore_index=True)


def run(
    contract_path: Path = CONTRACT_PATH,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    replay_report_path = _rooted(contract["source_replay_report"])
    replay_report = json.loads(replay_report_path.read_text(encoding="utf-8"))
    ledger_path = _rooted(replay_report["ledger"]["path"])
    if (
        replay_report.get("status") != "DESCRIPTIVE_REPLAY_COMPLETE"
        or _sha256(ledger_path) != replay_report["ledger"]["sha256"]
        or replay_report.get("operational_action") != "HOLD"
        or float(replay_report.get("operational_action_ratio", -1)) != 0.0
    ):
        raise HistoricalS1DependencyAuditError("replay receipt is not safe")
    transition_report_path = _rooted(contract["source_transition_report"])
    transition_report = json.loads(
        transition_report_path.read_text(encoding="utf-8")
    )
    if transition_report.get("status") != "TRANSITION_DISPLAY_READY":
        raise HistoricalS1DependencyAuditError("transition report is not ready")
    ledger = pd.read_csv(ledger_path, compression="gzip")
    context = build_regime_context(_load_transition_panel(transition_report))
    report, summary = audit_dependency(ledger, context, contract)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    report["inputs"] = {
        "contract_sha256": _sha256(contract_path),
        "replay_report_sha256": _sha256(replay_report_path),
        "replay_ledger_sha256": _sha256(ledger_path),
        "transition_report_sha256": _sha256(transition_report_path),
    }
    report["summary"] = {
        "path": str(summary_path.relative_to(ROOT)),
        "sha256": _sha256(summary_path),
        "rows": int(len(summary)),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()
    print(json.dumps(
        run(args.contract, args.summary, args.report),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
