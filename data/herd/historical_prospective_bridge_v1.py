"""S1 과거 설명 재생과 전향 관측 원장의 비교 가능 상태를 감사한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from scheduler.prospective_evidence import audit_archive


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
HISTORICAL_REPORT_PATH = ROOT / "data/reports/historical_s1_replay_v1.json"
DEFAULT_ARCHIVE_DIR = ROOT / "data/runtime/prospective-evidence"
DEFAULT_SUMMARY_PATH = (
    ROOT / "data/reports/historical_prospective_bridge_v1.csv"
)
DEFAULT_REPORT_PATH = (
    ROOT / "data/reports/historical_prospective_bridge_v1.json"
)
VERSION = "HERD_HISTORICAL_PROSPECTIVE_BRIDGE_V1"
LOCKED_HORIZONS = [21, 63, 126]


class HistoricalProspectiveBridgeError(RuntimeError):
    """비교 계약·입력 무결성 또는 행동 차단 경계가 깨진 경우."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    boundary = contract.get("claim_boundary", {})
    if (
        contract.get("contract_version") != VERSION
        or contract.get("status") != "LOCKED_DESCRIPTIVE_BRIDGE_ONLY"
        or contract.get("comparison_horizons_sessions") != LOCKED_HORIZONS
        or contract.get("historical_grouping")
        != ["universe_role", "event_kind", "horizon_sessions"]
        or int(contract.get("minimum_matured_outcomes_per_group", 0)) != 30
        or boundary.get(
            "historical_context_only_until_prospective_ready"
        ) is not True
        or boundary.get("candidate_selection") is not False
        or boundary.get("direction_prediction") is not False
        or boundary.get("buy_or_profit_take_authority") is not False
        or boundary.get("operational_action") != "HOLD"
        or float(boundary.get("operational_action_ratio", -1)) != 0.0
        or boundary.get("blind_holdout_access") is not False
        or boundary.get("survivorship_safe") is not False
    ):
        raise HistoricalProspectiveBridgeError("bridge contract is not locked")
    return contract


def summarize_historical(
    ledger: pd.DataFrame,
    contract: dict[str, Any],
) -> pd.DataFrame:
    required = {
        "universe_role", "event_kind", "horizon_sessions", "total_return",
        "maximum_favorable_excursion", "maximum_adverse_excursion",
        "direction_prediction", "operational_action", "operational_action_ratio",
    }
    if not required.issubset(ledger.columns):
        raise HistoricalProspectiveBridgeError(
            f"historical columns missing: {sorted(required - set(ledger.columns))}"
        )
    if (
        ledger["direction_prediction"].fillna(True).astype(bool).any()
        or not ledger["operational_action"].eq("HOLD").all()
        or not pd.to_numeric(
            ledger["operational_action_ratio"], errors="coerce"
        ).eq(0.0).all()
    ):
        raise HistoricalProspectiveBridgeError(
            "historical ledger contains action authority"
        )
    comparable = ledger[
        ledger["horizon_sessions"].isin(contract["comparison_horizons_sessions"])
    ].copy()
    if set(comparable["horizon_sessions"].unique()) != set(LOCKED_HORIZONS):
        raise HistoricalProspectiveBridgeError(
            "historical replay is missing prospective comparison horizons"
        )
    comparable["positive"] = comparable["total_return"].gt(0).astype(float)
    summary = (
        comparable.groupby(
            contract["historical_grouping"], observed=True, sort=True
        )
        .agg(
            episodes=("total_return", "size"),
            mean_return=("total_return", "mean"),
            median_return=("total_return", "median"),
            positive_fraction=("positive", "mean"),
            median_mfe=("maximum_favorable_excursion", "median"),
            median_mae=("maximum_adverse_excursion", "median"),
        )
        .reset_index()
    )
    return summary


def build_report(
    historical_report: dict[str, Any],
    summary: pd.DataFrame,
    prospective_audit: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    if (
        historical_report.get("report_version")
        != contract["historical_replay_version"]
        or historical_report.get("status") != "DESCRIPTIVE_REPLAY_COMPLETE"
        or historical_report.get("survivorship_safe") is not False
        or float(historical_report.get("operational_action_ratio", -1)) != 0.0
    ):
        raise HistoricalProspectiveBridgeError(
            "historical replay report is not safe"
        )
    observation_dates = int(prospective_audit.get("observationArchives", 0))
    transition_ready = observation_dates >= int(
        contract["minimum_prospective_observation_dates_for_transition_comparison"]
    )
    maturity = prospective_audit.get("maturityByHorizon", {})
    minimum = int(contract["minimum_matured_outcomes_per_group"])
    comparison_ready = {
        str(horizon): (
            transition_ready
            and int(maturity.get(str(horizon), {}).get("matured", 0)) >= minimum
        )
        for horizon in LOCKED_HORIZONS
    }
    all_ready = all(comparison_ready.values())
    return {
        "report_version": VERSION,
        "status": (
            "HISTORICAL_AND_PROSPECTIVE_DESCRIPTIVE_COMPARISON_READY"
            if all_ready
            else "HISTORICAL_CONTEXT_READY_PROSPECTIVE_PENDING"
        ),
        "historical_context": {
            "ready": not summary.empty,
            "groups": int(len(summary)),
            "rows": int(summary["episodes"].sum()),
            "survivorship_safe": False,
            "use": "DESCRIPTIVE_CONTEXT_ONLY",
        },
        "prospective": {
            "observation_dates": observation_dates,
            "observation_records": int(
                prospective_audit.get("observationRecords", 0)
            ),
            "matured_outcomes": int(
                prospective_audit.get("maturedOutcomes", 0)
            ),
            "transition_comparison_ready": transition_ready,
            "comparison_ready_by_horizon": comparison_ready,
            "minimum_matured_outcomes_per_group": minimum,
        },
        "waiting_does_not_block": [
            "HERD_STATE_S1_OBSERVATION",
            "HERD_TRANSITION_S1_OBSERVATION",
            "HISTORICAL_DESCRIPTIVE_CONTEXT",
        ],
        "still_blocked": [
            "DIRECTION_PREDICTION",
            "BUY_OR_PROFIT_TAKE_AUTHORITY",
            "OPERATIONAL_ACTION_RATIO",
        ],
        "candidate_selection": False,
        "direction_prediction": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "survivorship_safe": False,
    }


def run(
    contract_path: Path = CONTRACT_PATH,
    historical_report_path: Path = HISTORICAL_REPORT_PATH,
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    historical_report = json.loads(
        historical_report_path.read_text(encoding="utf-8")
    )
    ledger_path = ROOT / historical_report["ledger"]["path"]
    if _sha256(ledger_path) != historical_report["ledger"]["sha256"]:
        raise HistoricalProspectiveBridgeError(
            "historical replay ledger hash changed"
        )
    ledger = pd.read_csv(ledger_path, compression="gzip")
    summary = summarize_historical(ledger, contract)
    prospective_audit = audit_archive(archive_dir)
    report = build_report(
        historical_report, summary, prospective_audit, contract
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    report["inputs"] = {
        "contract_sha256": _sha256(contract_path),
        "historical_report_sha256": _sha256(historical_report_path),
        "historical_ledger_sha256": _sha256(ledger_path),
    }
    report["summary"] = {
        "path": str(summary_path.relative_to(ROOT)),
        "sha256": _sha256(summary_path),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--historical-report", type=Path, default=HISTORICAL_REPORT_PATH)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()
    print(json.dumps(
        run(
            args.contract,
            args.historical_report,
            args.archive_dir,
            args.summary,
            args.report,
        ),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
