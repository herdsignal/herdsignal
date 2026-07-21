"""매수·익절·재진입 방향 증거 사전등록 계약을 검증한다."""

from __future__ import annotations

import json
from pathlib import Path


PATH = Path(__file__).with_name("action_direction_hypotheses.json")
VERSION = "HERD_ACTION_DIRECTION_V1"
ACTIONS = {"NEW_ENTRY", "ADD_BUY", "PROFIT_TAKE", "REENTRY"}


class ActionDirectionRegistryError(RuntimeError):
    pass


def validate_registry(registry: dict) -> dict:
    if (registry.get("registry_version") != VERSION
            or registry.get("status") != "LOCKED_BEFORE_OOS_RESULTS"
            or registry.get("default_action") != "HOLD"
            or registry.get("operational_authorization") is not False
            or registry.get("blind_holdout_access") is not False):
        raise ActionDirectionRegistryError("action direction registry is not safely locked")
    common = registry.get("common_contract", {})
    if (common.get("minimum_directional_folds", 0) < 4
            or common.get("multiple_testing") != "HOLM_WITHIN_ACTION_FAMILY"
            or common.get("exclude_failed_tickers") is not False):
        raise ActionDirectionRegistryError("OOS inference contract is incomplete")

    hypotheses = registry.get("hypotheses", [])
    ids = [row.get("id") for row in hypotheses]
    if len(ids) != len(set(ids)) or not hypotheses:
        raise ActionDirectionRegistryError("hypothesis ids are missing or duplicated")
    for row in hypotheses:
        if (row.get("action") not in ACTIONS or not row.get("formula")
                or row.get("parameters_locked") is not True
                or not row.get("horizons_months")):
            raise ActionDirectionRegistryError(f"incomplete hypothesis: {row.get('id')}")
        if row.get("action") == "REENTRY" and row.get("stage") != "CONTINGENT_BLOCKED":
            raise ActionDirectionRegistryError("reentry must remain blocked before profit evidence")

    forbidden = set(registry.get("forbidden", []))
    required = {"HIGH_HERD_ALONE_SELLS", "LOW_HERD_ALONE_BUYS",
                "COMBINE_STANDALONE_HYPOTHESES_BEFORE_ADMISSION",
                "OPEN_BLIND_HOLDOUT", "ENABLE_OPERATIONAL_ACTION_RATIO"}
    if not required.issubset(forbidden):
        raise ActionDirectionRegistryError("critical shortcuts are not forbidden")
    return {"registry_version": VERSION, "hypothesis_count": len(hypotheses),
            "actions": sorted({row["action"] for row in hypotheses}),
            "operational_authorization": False}


def load_registry(path: Path = PATH) -> tuple[dict, dict]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    return registry, validate_registry(registry)
