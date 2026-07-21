"""5% 익절·재진입 경제성 상한의 사전등록 계약을 검증한다."""

from __future__ import annotations

import json
from pathlib import Path


PROTOCOL_PATH = Path(__file__).with_suffix(".json")


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_CYCLE_VALUE_RESULTS":
        raise ValueError("cycle value protocol must be locked before results")
    execution = protocol["execution"]
    if execution.get("profit_take_fraction") != 0.05:
        raise ValueError("initial research sleeve must remain five percent")
    constrained = protocol["ceilings"]["constrained_oracle"]
    if constrained.get("abstain_when_no_window") is not True:
        raise ValueError("feasibility ceiling must preserve buy-and-hold when no opportunity exists")
    interpretation = protocol["interpretation"]
    if interpretation.get("future_low_is_never_a_feature") is not True \
            or interpretation.get("oracle_result_does_not_authorize_action") is not True:
        raise ValueError("oracle safety boundary is missing")
    if "CHANGE_DISCOUNT_OR_WINDOW_AFTER_RESULTS" not in protocol.get("forbidden", []):
        raise ValueError("post-result threshold changes must be forbidden")
    return protocol
