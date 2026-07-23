"""Part 1~7의 산출물·권한·회귀 결과를 하나의 완료 감사로 묶는다."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

from herd.research_artifact_catalog import (
    load_catalog,
    validate_active_chain,
)


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
REPORT = ROOT / "data/reports/overnight_pit_shadow_completion_v1.json"


class OvernightCompletionV1Error(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str, root: Path = ROOT) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise OvernightCompletionV1Error(f"path escapes repository: {relative}")
    return path


def _load_and_verify(
    protocol_path: Path,
    root: Path = ROOT,
) -> tuple[dict, dict[str, Path]]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "LOCKED_BEFORE_COMPLETION_AUDIT":
        raise OvernightCompletionV1Error("completion protocol is not locked")
    paths = {}
    for item in protocol["locked_inputs"]:
        path = _rooted(item["path"], root)
        if not path.is_file() or _sha256(path) != item["sha256"]:
            raise OvernightCompletionV1Error(
                f"completion input changed: {item['path']}"
            )
        paths[item["role"]] = path
    return protocol, paths


def _evaluate_reports(payloads: dict[str, dict]) -> dict:
    contract = payloads["EXECUTION_CONTRACT"]
    gap = payloads["IDENTIFIER_GAP_REPORT"]
    cover = payloads["TARGETED_COVER_REPORT"]
    ledger = payloads["LIFECYCLE_LEDGER_REPORT"]
    lifecycle = payloads["LIFECYCLE_COVERAGE_REPORT"]
    finra = payloads["FINRA_INCREMENTAL_REPORT"]
    panel = payloads["UNIFIED_PANEL_REPORT"]
    regression = payloads["FULL_REGRESSION_REPORT"]

    as_of = datetime.fromisoformat(finra["as_of_utc"].replace("Z", "+00:00"))
    pending_is_not_due = all(
        item["status"] == "PENDING_OFFICIAL_PUBLICATION_WINDOW"
        and as_of < datetime.fromisoformat(item["download_not_before"])
        for item in finra["pending_candidates"]
    )
    checks = {
        "PART_1": (
            contract["status"] == "LOCKED_BEFORE_OVERNIGHT_EXPANSION"
            and contract["authority"]["operational_action_ratio"] == 0.0
        ),
        "PART_2": gap["status"] == "HASH_LOCKED_TARGET_QUEUE_READY",
        "PART_3": (
            cover["status"] == "HASH_LOCKED_ELIGIBLE_SOURCE_EXHAUSTED"
            and cover["unresolved_failures"] == 0
        ),
        "PART_4": (
            ledger["status"] == "TIME_VALID_LIFECYCLE_LEDGER_BUILT"
            and ledger["conflict_excluded_interval_count"] == 0
            and lifecycle["finra_shadow_identifier_gate_passed"]
            and lifecycle["target_gap_audit"]["blocked_target_count"] == 5
        ),
        "PART_5": (
            finra["all_baseline_hashes_verified"]
            and finra["status"] in {
                "PENDING_OFFICIAL_PUBLICATION_WINDOW",
                "HASH_LOCKED_INCREMENTAL_CENSUS_UPDATED",
            }
            and (
                finra["status"] != "PENDING_OFFICIAL_PUBLICATION_WINDOW"
                or pending_is_not_due
            )
        ),
        "PART_6": (
            panel["status"]
            == "HASH_LOCKED_PROSPECTIVE_SEED_SNAPSHOT_READY"
            and panel["finra_current_snapshot_coverage_gate"]["passed"]
            and not panel["price_or_return_outcomes_opened"]
            and not panel["direction_labels_created"]
        ),
        "PART_7": (
            regression["status"] == "FULL_REGRESSION_PASS"
            and regression["all_commands_passed"]
        ),
    }
    return {
        "stage_checks": checks,
        "all_stage_checks_passed": all(checks.values()),
        "pending_finra_candidates_are_not_due": pending_is_not_due,
    }


def audit(
    protocol_path: Path = PROTOCOL,
    report_path: Path = REPORT,
    root: Path = ROOT,
) -> dict:
    protocol, paths = _load_and_verify(protocol_path, root)
    json_roles = protocol["json_report_roles"]
    payloads = {
        role: json.loads(paths[role].read_text(encoding="utf-8"))
        for role in json_roles
    }
    evaluated = _evaluate_reports(payloads)
    catalog = load_catalog(paths["ARTIFACT_CATALOG"])
    missing_active = validate_active_chain(catalog, root)
    docs_present = all(
        paths[role].stat().st_size > 0
        for role in ("RESEARCH_STATUS_DOC", "REPRODUCIBILITY_DOC")
    )
    part7_complete = (
        evaluated["stage_checks"]["PART_7"]
        and not missing_active
        and docs_present
    )
    evaluated["stage_checks"]["PART_7"] = part7_complete
    all_complete = all(evaluated["stage_checks"].values())
    lifecycle = payloads["LIFECYCLE_COVERAGE_REPORT"]
    finra = payloads["FINRA_INCREMENTAL_REPORT"]
    report = {
        "report_version": "OVERNIGHT_PIT_SHADOW_COMPLETION_V1",
        "status": (
            "OVERNIGHT_PIPELINE_COMPLETE_RESEARCH_BLOCKED"
            if all_complete
            else "OVERNIGHT_PIPELINE_INCOMPLETE"
        ),
        "stage_results": [
            {
                "stage": stage,
                "status": "COMPLETE" if passed else "INCOMPLETE",
            }
            for stage, passed in evaluated["stage_checks"].items()
        ],
        "all_stages_complete": all_complete,
        "locked_input_count": len(protocol["locked_inputs"]),
        "artifact_catalog_missing_active": missing_active,
        "documentation_present": docs_present,
        "known_blockers": {
            "individual_identifier_targets": [
                row["ticker"]
                for row in lifecycle["target_gap_audit"]["blocked_targets"]
            ],
            "finra_pending_settlement_dates": [
                row["settlement_date"]
                for row in finra["pending_candidates"]
            ],
            "admitted_buy_or_profit_take_direction_evidence": 0,
            "primary_long_horizon_finra_oos_allowed": False,
        },
        "pipeline_completion_is_not_model_adoption": True,
        "price_outcomes_opened": False,
        "direction_hypothesis_preregistered": False,
        "herd_formula_change_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_priority": (
            "ACCUMULATE_PROSPECTIVE_SOURCE_FACTS_WITHOUT_ACTION_AUTHORITY"
        ),
        "protocol_sha256": _sha256(protocol_path),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_name(f".{report_path.name}.tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, report_path)
    if not all_complete:
        raise OvernightCompletionV1Error(
            "one or more overnight stages are incomplete"
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    result = audit(args.protocol, args.report)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
