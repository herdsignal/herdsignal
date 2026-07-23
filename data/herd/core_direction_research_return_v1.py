"""실패한 경로 분류에서 경제적 5% 행동 목표 연구로 복귀하는 경계를 고정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


PROTOCOL = Path(__file__).with_suffix(".json")
TARGET_COLUMNS = [
    "ticker", "episode_id", "signal_date", "sector_etf", "fold_id", "path_label",
    "damage_triggered", "damage_execution_date", "scheduled_execution_date", "outcome_end",
    "uplift_vs_buy_hold_base", "uplift_vs_buy_hold_stress",
    "triggered_trough_improvement_base", "triggered_trough_improvement_stress",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(protocol: dict) -> tuple[pd.DataFrame, dict]:
    events_path = Path(protocol["source_events"])
    audit_path = Path(protocol["source_audit"])
    admission_path = Path(protocol["profit_take_admission"])
    sec_path = Path(protocol["sec_authority"])
    survivorship_path = Path(protocol["survivorship_readiness"])
    events = pd.read_csv(events_path)
    missing = set(TARGET_COLUMNS) - set(events.columns)
    if missing:
        raise ValueError(f"economic target columns missing: {sorted(missing)}")
    if events["episode_id"].duplicated().any():
        raise ValueError("economic target episode ids must be unique")
    source_audit = json.loads(audit_path.read_text())
    admission = json.loads(admission_path.read_text())
    sec = json.loads(sec_path.read_text())
    survivorship = json.loads(survivorship_path.read_text())
    target = events[TARGET_COLUMNS].copy()
    target["research_use"] = "DISCOVERY_TARGET_DEFINITION_ONLY_NOT_OOS"
    target["direction_label"] = "NONE"
    target["operational_action_ratio"] = 0.0
    target = target.sort_values(["signal_date", "ticker", "episode_id"]).reset_index(drop=True)
    ready = bool(
        len(target) == source_audit["classified_events"]
        and not admission["decision"]["profit_take_evidence_admitted"]
        and not sec["effective_sec_veto_enabled"]
    )
    report = {
        "report_version": "herd-core-direction-research-return-v1",
        "economic_target_rows": len(target),
        "distinct_tickers": int(target["ticker"].nunique()),
        "folds": int(target["fold_id"].nunique()),
        "existing_profit_take_evidence_admitted": admission["decision"]["profit_take_evidence_admitted"],
        "existing_pre_damage_features_retained": source_audit["retained_count"],
        "sec_direction_authority": sec["create_sell_authority"] or sec["create_buy_authority"],
        "sec_veto_currently_enabled": sec["effective_sec_veto_enabled"],
        "survivorship_safe": bool(survivorship.get("survivorship_safe", False)),
        "failed_exact_hypotheses_quarantined": len(protocol["failed_exact_hypotheses_not_reusable"]),
        "target_ledger_ready": ready,
        "new_hypothesis_preregistered": False,
        "direction_evidence_admitted": False,
        "blind_holdout_opened": False,
        "next_decision": "PREREGISTER_ONE_NEW_NONREDUNDANT_ECONOMIC_HYPOTHESIS" if ready else "CORE_RETURN_CONTRACT_BLOCKED",
        "source_events_sha256": _sha256(events_path),
        "source_audit_sha256": _sha256(audit_path),
        "profit_take_admission_sha256": _sha256(admission_path),
        "sec_authority_sha256": _sha256(sec_path),
        "survivorship_readiness_sha256": _sha256(survivorship_path),
        "operational_action_ratio": 0.0,
    }
    return target, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    targets, report = build(protocol)
    targets.to_csv(args.targets, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = _sha256(PROTOCOL)
    report["targets_sha256"] = _sha256(args.targets)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
