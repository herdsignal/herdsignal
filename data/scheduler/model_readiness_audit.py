"""현재 HERD 사용 범위와 다음 행동 모델 연구 착수 조건을 감사한다."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from herd.research_decision_v5 import load_and_validate  # noqa: E402
from scheduler.prospective_evidence import (  # noqa: E402
    DEFAULT_ARCHIVE_DIR,
    audit_archive,
)


ROOT = _DATA_DIR.parent
SURVIVORSHIP_PATH = ROOT / "data/herd/survivorship_readiness_v2.json"
CLAIM_SCOPE_PATH = ROOT / "data/herd/research_claim_scope_v1.json"


def _observation_months(first: str | None, latest: str | None) -> int:
    if not first or not latest:
        return 0
    start = date.fromisoformat(first)
    end = date.fromisoformat(latest)
    return max(0, (end.year - start.year) * 12 + end.month - start.month)


def build_readiness(
    decision: dict[str, Any],
    survivorship: dict[str, Any],
    claim_scope: dict[str, Any],
    prospective: dict[str, Any],
) -> dict[str, Any]:
    """기존 고정 계약을 완화하지 않고 현재 연구 가능 범위를 계산한다."""
    lane = claim_scope["lanes"]["PERSONAL_PROSPECTIVE_SHADOW"]
    months = _observation_months(
        prospective.get("firstObservationDate"),
        prospective.get("latestObservationDate"),
    )
    horizon_126 = prospective.get("maturityByHorizon", {}).get("126", {})
    preholdout_passed = decision["adoptable_action_candidates"] > 0
    prospective_review_ready = (
        preholdout_passed
        and months >= lane["minimum_observation_months_before_policy_review"]
        and int(horizon_126.get("matured", 0))
        >= lane["minimum_complete_candidate_events_before_policy_review"]
        and int(prospective.get("distinctTickers", 0))
        >= lane["minimum_distinct_tickers_before_policy_review"]
    )
    survivorship_safe = (
        survivorship.get("decision", {}).get("survivorship_safe") is True
    )
    pending_source_decisions = int(decision.get("pending_source_decisions", 0))
    decision_next_stage = decision.get("next_stage")

    return {
        "schemaVersion": "HERD_MODEL_READINESS_AUDIT_V1",
        "status": "OBSERVATION_READY_ACTION_RESEARCH_BLOCKED",
        "product": {
            "stateObservationReady": decision["product_scope"]
            == "STATE_AND_TRANSITION_OBSERVATION",
            "operationalAction": "HOLD",
            "operationalActionRatio": 0.0,
        },
        "evidence": {
            "adoptableActionCandidates": decision["adoptable_action_candidates"],
            "preholdoutDirectionAndCyclePassed": preholdout_passed,
            "prospectiveObservationArchives": prospective["observationArchives"],
            "prospectiveObservationRecords": prospective["observationRecords"],
            "prospectiveDistinctTickers": prospective.get("distinctTickers", 0),
            "prospectiveObservationMonths": months,
            "matured126SessionOutcomes": int(horizon_126.get("matured", 0)),
            "survivorshipSafe": survivorship_safe,
            "pendingSourceDecisions": pending_source_decisions,
        },
        "gates": {
            "personalProspectivePolicyReviewReady": prospective_review_ready,
            "marketGeneralActionResearchReady": survivorship_safe,
            "blindHoldoutAllowed": False,
            "operationalActionAllowed": False,
        },
        "nextWork": {
            "primary": decision_next_stage
            or "ACCUMULATE_PROSPECTIVE_OBSERVATIONS_AND_OUTCOMES",
            "prospective": "ACCUMULATE_PROSPECTIVE_OBSERVATIONS_AND_OUTCOMES",
            "research": (
                "COMPLETE_LOCKED_SOURCE_REVIEW_BEFORE_DIRECTION_RESEARCH"
                if pending_source_decisions
                else "PREREGISTER_ONE_ECONOMICALLY_NON_DUPLICATIVE_HYPOTHESIS_ONLY_WHEN_A_NEW_INPUT_EXISTS"
            ),
            "forbidden": [
                "RETUNE_REJECTED_THRESHOLDS",
                "COMBINE_REJECTED_FEATURES",
                "OPEN_BLIND_HOLDOUT",
                "ENABLE_OPERATIONAL_ACTION",
            ],
        },
    }


def load_and_build(archive_dir: Path = DEFAULT_ARCHIVE_DIR) -> dict[str, Any]:
    return build_readiness(
        load_and_validate(),
        json.loads(SURVIVORSHIP_PATH.read_text()),
        json.loads(CLAIM_SCOPE_PATH.read_text()),
        audit_archive(archive_dir),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = load_and_build(args.archive_dir)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
