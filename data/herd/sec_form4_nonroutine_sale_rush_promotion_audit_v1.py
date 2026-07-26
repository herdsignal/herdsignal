"""탈락한 Form 4–Rush 가설의 행동 계층 유입을 차단한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OOS_PATH = ROOT / "data/reports/sec_form4_nonroutine_sale_rush_oos_v1.json"
OUTPUT_PATH = ROOT / "data/reports/sec_form4_nonroutine_sale_rush_promotion_audit_v1.json"
VERSION = "HERD_SEC_FORM4_NONROUTINE_SALE_RUSH_PROMOTION_AUDIT_V1"


class Form4SaleRushPromotionError(RuntimeError):
    """탈락 증거에 행동 권한이 부여된 경우."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_audit(output_path: Path = OUTPUT_PATH) -> dict[str, Any]:
    report = json.loads(OOS_PATH.read_text())
    if (
        report["passed"] is not False
        or report["adoption_allowed"] is not False
        or report["operational_action_ratio"] != 0.0
    ):
        raise Form4SaleRushPromotionError("OOS rejection boundary changed")
    audit = {
        "report_version": VERSION,
        "status": "REJECTED_DIRECTIONALLY_INVERTED",
        "source": {
            "path": str(OOS_PATH.relative_to(ROOT)),
            "sha256": _hash(OOS_PATH),
        },
        "reason": (
            "The prespecified higher-risk direction failed in every fold; "
            "pooled adverse risk was lower, not higher, among exposed entries."
        ),
        "failed_hypothesis": (
            "FORM4_TIMING_NONROUTINE_MULTI_OWNER_SALE_30D_AT_S1_RUSH_ENTRY"
        ),
        "downstream": {
            "five_percent_profit_take": "BLOCKED",
            "reentry_rule": "BLOCKED_NO_VALIDATED_SALE_CASH",
            "completed_cycle": "BLOCKED",
            "shadow_action_layer": "BLOCKED",
        },
        "forbidden_interpretation": (
            "The inverse association is not permission to create a buy signal "
            "because that direction was not preregistered."
        ),
        "blind_holdout_access": False,
        "survivorship_safe": False,
        "operational_action_ratio": 0.0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(audit, indent=2) + "\n")
    return audit


if __name__ == "__main__":
    print(json.dumps(build_audit(), indent=2))
