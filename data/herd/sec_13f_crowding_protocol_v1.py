"""SEC 13F 군중 맥락 연구 계약을 fail-closed로 검증한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = Path(__file__).with_suffix(".json")
DEFAULT_REPORT = ROOT / "data/reports/sec_13f_crowding_protocol_v1.json"


class Sec13fCrowdingProtocolError(RuntimeError):
    """13F 연구 경계나 고정 입력이 변경됐을 때 발생한다."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise Sec13fCrowdingProtocolError(f"missing pinned input: {relative}")
    return path


def _verify_prerequisite(specification: dict[str, Any]) -> dict[str, Any]:
    path = _rooted(specification["path"])
    digest = _sha256(path)
    if digest != specification["sha256"]:
        raise Sec13fCrowdingProtocolError(
            f"pinned prerequisite changed: {specification['path']}"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    required_decision = specification.get("required_decision")
    if required_decision and (
        payload.get("decision") or payload.get("status")
    ) != required_decision:
        raise Sec13fCrowdingProtocolError(
            f"required decision changed: {specification['path']}"
        )
    required_source = specification.get("required_source")
    if required_source:
        source = next(
            (
                item
                for item in payload.get("source_decisions", [])
                if item.get("source") == required_source
            ),
            None,
        )
        if source is None or source.get("status") != specification[
            "required_source_status"
        ]:
            raise Sec13fCrowdingProtocolError(
                f"required source boundary changed: {required_source}"
            )
    return {
        "path": specification["path"],
        "sha256": digest,
        "verified": True,
    }


def validate_contract(path: Path = CONTRACT) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("protocol_version") != "SEC_13F_CROWDING_PROTOCOL_V1":
        raise Sec13fCrowdingProtocolError("unexpected protocol version")
    if contract.get("status") != "LOCKED_BEFORE_13F_COLLECTION_AND_PRICE_OUTCOMES":
        raise Sec13fCrowdingProtocolError("13F protocol is not locked")

    pit = contract["point_in_time_contract"]
    firewall = contract["feature_firewall"]
    model = contract["model_boundary"]
    if pit["information_available_at"] != "EDGAR_ACCEPTANCE_DATETIME":
        raise Sec13fCrowdingProtocolError("acceptance datetime must define PIT")
    if pit["quarter_end_is_publication_time"]:
        raise Sec13fCrowdingProtocolError("quarter end cannot define availability")
    if pit["manager_cik_is_issuer_cik"]:
        raise Sec13fCrowdingProtocolError("manager CIK cannot identify the issuer")
    if pit["future_price_or_return_access_during_collection"]:
        raise Sec13fCrowdingProtocolError("collection must remain outcome blind")
    if firewall["role"] != "SLOW_CROWDING_CONTEXT_ONLY":
        raise Sec13fCrowdingProtocolError("13F must remain slow context")
    if any(
        firewall[key]
        for key in (
            "standalone_direction_allowed",
            "standalone_sell_allowed",
            "standalone_buy_allowed",
            "herd_weight_change_allowed",
        )
    ):
        raise Sec13fCrowdingProtocolError("13F context received excess authority")
    if model["operational_action_ratio"] != 0.0:
        raise Sec13fCrowdingProtocolError("operational actions must remain disabled")

    collection = contract["collection_gates"]
    oos = contract["oos_gates"]
    economics = contract["economic_gates"]
    if collection["minimum_history_years"] < 10:
        raise Sec13fCrowdingProtocolError("history gate was weakened")
    if collection["minimum_non_overlapping_eras"] < 4:
        raise Sec13fCrowdingProtocolError("era gate was weakened")
    if oos["minimum_non_overlapping_folds"] < 4:
        raise Sec13fCrowdingProtocolError("OOS fold gate was weakened")
    if oos["minimum_incremental_roc_auc"] <= 0:
        raise Sec13fCrowdingProtocolError("incremental evidence is required")
    if economics["profit_take_fraction"] != 0.05:
        raise Sec13fCrowdingProtocolError("initial action must remain 5 percent")
    if economics["minimum_median_upside_capture"] < 0.98:
        raise Sec13fCrowdingProtocolError("winner upside protection was weakened")
    if not contract["promotion_gates"][
        "blind_holdout_must_remain_closed_until_all_preholdout_gates_pass"
    ]:
        raise Sec13fCrowdingProtocolError("blind holdout boundary was weakened")

    prerequisites = [
        _verify_prerequisite(item)
        for item in contract["pinned_prerequisites"]
    ]
    return {
        "report_version": "SEC_13F_CROWDING_PROTOCOL_V1",
        "status": "PROTOCOL_LOCKED_COLLECTION_NOT_STARTED",
        "contract_sha256": _sha256(path),
        "prerequisites": prerequisites,
        "source_role": firewall["role"],
        "price_outcomes_opened": False,
        "direction_hypothesis_executed": False,
        "herd_weight_change_allowed": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "next_step": "BUILD_OFFICIAL_13F_IMMUTABLE_CORPUS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = validate_contract(args.contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
