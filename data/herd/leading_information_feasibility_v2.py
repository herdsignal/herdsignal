"""공개 선행정보의 최신 연구 권한을 fail-closed로 감사한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
VERSION = "HERD_LEADING_INFORMATION_FEASIBILITY_V2"


class LeadingInformationFeasibilityV2Error(ValueError):
    """공개 선행정보 계약 또는 기존 판정이 변경됨."""


def _load(specification: dict[str, str]) -> dict[str, Any]:
    path = (ROOT / specification["path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise LeadingInformationFeasibilityV2Error(f"missing input: {specification['path']}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != specification["sha256"]:
        raise LeadingInformationFeasibilityV2Error(f"hash mismatch: {specification['path']}")
    return json.loads(path.read_text())


def validate_feasibility(protocol: dict[str, Any]) -> dict[str, Any]:
    if (
        protocol.get("protocol_version") != VERSION
        or protocol.get("status") != "LOCKED_PUBLIC_SOURCE_REASSESSMENT"
    ):
        raise LeadingInformationFeasibilityV2Error("feasibility protocol is not locked")
    reports = {spec["id"]: _load(spec) for spec in protocol["inputs"]}
    expected = {
        "FORM4": reports["FORM4_OOS"]["status"] == "REJECT_INSIDER_PURCHASE_SUPPORT_HYPOTHESIS",
        "GUIDANCE": reports["GUIDANCE_OOS"]["decision"] == "REJECT_GUIDANCE_LOWER_HYPOTHESIS",
        "SEC_13F": reports["13F_OOS"]["decision"] == "KEEP_13F_AS_NON_DIRECTIONAL_CONTEXT_ONLY",
        "FINRA_SHORT_INTEREST": reports["FINRA_INCREMENTAL"]["primary_long_horizon_oos_allowed"] is False,
    }
    if not all(expected.values()):
        raise LeadingInformationFeasibilityV2Error("prior source decision changed")
    decision = protocol["decision"]
    if (
        decision["primary_long_horizon_source_ready_count"] != 0
        or decision["new_historical_direction_hypothesis_allowed"] is not False
        or decision["prospective_shadow_source_count"] != 1
        or decision["blind_holdout_access"] is not False
        or decision["operational_action_ratio"] != 0.0
    ):
        raise LeadingInformationFeasibilityV2Error("unsupported source authority granted")
    return {
        "protocol_version": VERSION,
        "source_status": protocol["source_decisions"],
        "form4_independent_issuers": reports["FORM4_CENSUS"]["independent_issuers"],
        "guidance_valid_rows": reports["GUIDANCE_BINDINGS"]["valid_rows_promoted"],
        "finra_settlement_dates": reports["FINRA_INCREMENTAL"]["settlement_date_count"],
        **decision,
    }


if __name__ == "__main__":
    print(json.dumps(validate_feasibility(json.loads(PROTOCOL_PATH.read_text())), indent=2))
