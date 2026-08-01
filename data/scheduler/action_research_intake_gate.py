"""새 행동 가설이 독립 OOS 연구에 들어갈 자격이 있는지 결과 전에 판정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from herd.failed_hypothesis_map_v1 import load_failed_hypothesis_map  # noqa: E402
from scheduler.model_readiness_audit import _observation_months  # noqa: E402
from scheduler.prospective_evidence import DEFAULT_ARCHIVE_DIR, audit_archive  # noqa: E402

ROOT = _DATA_DIR.parent
CONTRACT_PATH = ROOT / "data/config/action_research_intake_v1.json"
DEFAULT_OUTPUT = ROOT / "data/runtime/reports/action-research-intake-latest.json"


class ActionResearchIntakeError(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("schemaVersion") != "HERD_ACTION_RESEARCH_INTAKE_GATE_V1"
        or contract.get("status") != "LOCKED_BEFORE_NEW_HYPOTHESIS_RESULTS"
    ):
        raise ActionResearchIntakeError("intake gate is not locked")
    for item in contract["pinnedInputs"]:
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ActionResearchIntakeError(f"missing pinned input: {item['path']}")
        if _sha256(path) != item["sha256"]:
            raise ActionResearchIntakeError(f"pinned input changed: {item['path']}")


def _validate_candidate(
    candidate: dict[str, Any],
    contract: dict[str, Any],
    failed_map: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    missing = [
        key for key in contract["requiredCandidateFields"] if key not in candidate
    ]
    if missing:
        return [f"MISSING_FIELDS:{','.join(missing)}"]
    if candidate.get("status") != "LOCKED_BEFORE_OUTCOME_REVIEW":
        failures.append("OUTCOME_REVIEW_BEFORE_LOCK")
    if candidate.get("serviceObjective") != contract["serviceObjective"]:
        failures.append("OBJECTIVE_MISMATCH")

    rejected_ids = {row["id"] for row in failed_map["experiments"]}
    rejected_samples = {row["sample_id"] for row in failed_map["experiments"]}
    overlap = candidate["overlapAudit"]
    if set(overlap.get("reusedRejectedExperimentIds", [])) & rejected_ids:
        failures.append("REJECTED_EXPERIMENT_REUSE")
    if candidate["sampleId"] in rejected_samples:
        failures.append("SAME_SAMPLE_THRESHOLD_RETUNING")
    if overlap.get("sameSampleRetuning") is not False:
        failures.append("SAME_SAMPLE_THRESHOLD_RETUNING")
    if overlap.get("rejectedFeatureRecombination") is not False:
        failures.append("REJECTED_FEATURE_RECOMBINATION")
    if overlap.get("legacyFormulaReuse") is not False:
        failures.append("LEGACY_FORMULA_REUSE")

    if not str(candidate.get("formula", "")).strip():
        failures.append("FORMULA_MISSING")
    if not str(candidate.get("observationTiming", "")).strip():
        failures.append("OBSERVATION_TIMING_MISSING")
    frequency = candidate.get("expectedFrequencyPerYear")
    if not isinstance(frequency, (int, float)) or not 0 < frequency <= 5:
        failures.append("FREQUENCY_OUTSIDE_RARE_ACTION_SCOPE")
    if candidate.get("target") not in {
        "PROFIT_TAKE_DIRECTION",
        "REENTRY_SUPPORT",
        "COMPLETED_CYCLE_TERMINAL_WEALTH",
    }:
        failures.append("TARGET_OUTSIDE_SERVICE_OBJECTIVE")

    new_input = candidate["newInput"]
    source = (ROOT / str(new_input.get("path", ""))).resolve()
    if not source.is_relative_to(ROOT) or not source.is_file():
        failures.append("NEW_INPUT_MISSING")
    elif _sha256(source) != new_input.get("sha256"):
        failures.append("NEW_INPUT_HASH_MISMATCH")
    failed_sources = {row["source"]["path"] for row in failed_map["experiments"]}
    if new_input.get("path") in failed_sources:
        failures.append("NEW_INPUT_NOT_NEW")
    if (
        new_input.get("pointInTime") is not True
        or not new_input.get("availabilityTimestampField")
    ):
        failures.append("NEW_INPUT_NOT_POINT_IN_TIME")

    protocol = candidate["oosProtocol"]
    if (
        protocol.get("independentTickerOrTimeSplit") is not True
        or protocol.get("costStressIncluded") is not True
        or protocol.get("buyAndHoldComparator") is not True
        or protocol.get("blindHoldoutAccess") is not False
    ):
        failures.append("OOS_PROTOCOL_INCOMPLETE")
    return sorted(set(failures))


def build_report(
    prospective: dict[str, Any],
    candidate: dict[str, Any] | None = None,
    *,
    contract: dict[str, Any] | None = None,
    failed_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = contract or json.loads(CONTRACT_PATH.read_text())
    _validate_contract(contract)
    failed_map = failed_map or load_failed_hypothesis_map()[0]
    months = _observation_months(
        prospective.get("firstObservationDate"),
        prospective.get("latestObservationDate"),
    )
    matured = int(prospective.get("maturityByHorizon", {}).get("126", {}).get("matured", 0))
    tickers = int(prospective.get("distinctTickers", 0))
    maturity_ready = (
        months >= contract["minimumProspectiveObservationMonths"]
        and matured >= contract["minimumMatured126SessionOutcomes"]
        and tickers >= contract["minimumDistinctTickers"]
    )
    failures = [] if candidate is None else _validate_candidate(
        candidate, contract, failed_map
    )
    candidate_ready = candidate is not None and not failures
    return {
        "schemaVersion": "HERD_ACTION_RESEARCH_INTAKE_REPORT_V1",
        "status": (
            "READY_FOR_INDEPENDENT_OOS"
            if candidate_ready
            else "BLOCKED_INVALID_CANDIDATE"
            if candidate is not None
            else "BLOCKED_NO_NEW_INPUT"
        ),
        "candidateId": candidate.get("candidateId") if candidate else None,
        "candidateLocked": candidate_ready,
        "candidateValidationFailures": failures,
        "prospective": {
            "observationMonths": months,
            "matured126SessionOutcomes": matured,
            "distinctTickers": tickers,
            "policyReviewReady": maturity_ready,
        },
        "gates": {
            "independentOosAllowed": candidate_ready,
            "completedCycleAllowed": False,
            "blindHoldoutAllowed": False,
            "operationalActionAllowed": False,
        },
        "operationalAction": "HOLD",
        "operationalActionRatio": 0.0,
        "next": (
            "RUN_LOCKED_CANDIDATE_INDEPENDENT_OOS"
            if candidate_ready
            else "FIX_CANDIDATE_CONTRACT"
            if candidate is not None
            else "ACCUMULATE_OUTCOMES_AND_WAIT_FOR_ECONOMICALLY_NEW_INPUT"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    candidate = json.loads(args.candidate.read_text()) if args.candidate else None
    report = build_report(audit_archive(args.archive_dir), candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] != "BLOCKED_INVALID_CANDIDATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
