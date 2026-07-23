"""야간 PIT shadow 확장의 계약 검증과 중단·재개 상태를 관리한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = Path(__file__).with_name("overnight_pit_shadow_expansion_v1.json")
DEFAULT_STATE = (
    ROOT / "data/reference/sec/overnight-pit-shadow-expansion-v1/state.json"
)


class OvernightExpansionError(RuntimeError):
    """계약 또는 실행 상태가 안전하지 않을 때 발생한다."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted_path(relative_path: str, root: Path = ROOT) -> Path:
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise OvernightExpansionError(
            f"locked input escapes repository: {relative_path}"
        )
    return path


def load_and_verify_contract(
    contract_path: Path = CONTRACT,
    root: Path = ROOT,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract["status"] != "LOCKED_BEFORE_OVERNIGHT_EXPANSION":
        raise OvernightExpansionError("overnight contract is not locked")

    authority = contract["authority"]
    closed_flags = (
        "price_outcomes_opened",
        "future_return_labels_allowed",
        "direction_hypothesis_allowed",
        "herd_formula_change_allowed",
        "blind_holdout_access",
        "production_signal_allowed",
        "automatic_commit_on_failure",
    )
    if any(authority[name] for name in closed_flags):
        raise OvernightExpansionError("research authority is not closed")
    if authority["operational_action_ratio"] != 0.0:
        raise OvernightExpansionError("operational action ratio must remain zero")

    sec_policy = contract["source_policy"]["sec"]
    if (
        not sec_policy["user_agent_required"]
        or sec_policy["requests_per_second"] <= 0
        or sec_policy["requests_per_second"]
        > sec_policy["official_maximum_requests_per_second"]
    ):
        raise OvernightExpansionError("unsafe SEC request policy")

    mismatches = []
    for locked in contract["locked_inputs"]:
        path = _rooted_path(locked["path"], root)
        if not path.is_file():
            mismatches.append({"path": locked["path"], "reason": "MISSING"})
        elif sha256(path) != locked["sha256"]:
            mismatches.append({"path": locked["path"], "reason": "HASH_MISMATCH"})
    if mismatches:
        raise OvernightExpansionError(
            f"locked input verification failed: {mismatches}"
        )
    return contract


@dataclass(frozen=True)
class RunStateStore:
    path: Path

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        pending = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        pending.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        pending.replace(self.path)

    def initialize(
        self,
        contract_path: Path = CONTRACT,
        root: Path = ROOT,
    ) -> dict[str, Any]:
        contract = load_and_verify_contract(contract_path, root)
        contract_hash = sha256(contract_path)
        existing = self.load()
        if existing is not None:
            if existing["contract_sha256"] != contract_hash:
                raise OvernightExpansionError(
                    "checkpoint belongs to a different contract"
                )
            return existing
        state = {
            "state_version": "HERD_OVERNIGHT_PIT_SHADOW_STATE_V1",
            "contract_sha256": contract_hash,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "last_completed_stage": None,
            "stages": {
                stage["id"]: {
                    "status": "PENDING",
                    "completed_items": 0,
                    "completed_item_ids": [],
                    "failed_items": [],
                }
                for stage in contract["stages"]
            },
        }
        self.save(state)
        return state

    def record_item(
        self,
        stage_id: str,
        item_id: str,
        *,
        error: str | None = None,
    ) -> dict[str, Any]:
        state = self.load()
        if state is None:
            raise OvernightExpansionError("run state is not initialized")
        stages = list(state["stages"])
        if stage_id not in stages:
            raise OvernightExpansionError(f"unknown stage: {stage_id}")
        position = stages.index(stage_id)
        if any(
            state["stages"][prior]["status"] != "COMPLETE"
            for prior in stages[:position]
        ):
            raise OvernightExpansionError(
                "a later stage cannot run before prior stages"
            )
        stage = state["stages"][stage_id]
        if stage["status"] == "COMPLETE":
            raise OvernightExpansionError("completed stage is immutable")

        failures = {
            row["item_id"]: row
            for row in stage["failed_items"]
        }
        if error is None:
            if item_id not in stage["completed_item_ids"]:
                stage["completed_item_ids"].append(item_id)
                stage["completed_item_ids"].sort()
            failures.pop(item_id, None)
        else:
            if item_id not in stage["completed_item_ids"]:
                failures[item_id] = {"item_id": item_id, "error": error}
        stage["completed_items"] = len(stage["completed_item_ids"])
        stage["failed_items"] = sorted(
            failures.values(),
            key=lambda row: row["item_id"],
        )
        stage["status"] = "RUNNING"
        state["updated_at_utc"] = datetime.now(UTC).isoformat()
        self.save(state)
        return state

    def complete_stage(
        self,
        stage_id: str,
        completed_items: int,
        manifest_sha256: str,
    ) -> dict[str, Any]:
        state = self.load()
        if state is None:
            raise OvernightExpansionError("run state is not initialized")
        stages = list(state["stages"])
        if stage_id not in stages:
            raise OvernightExpansionError(f"unknown stage: {stage_id}")
        position = stages.index(stage_id)
        if any(
            state["stages"][prior]["status"] != "COMPLETE"
            for prior in stages[:position]
        ):
            raise OvernightExpansionError(
                "a later stage cannot complete before prior stages"
            )
        stage = state["stages"][stage_id]
        if stage["failed_items"]:
            raise OvernightExpansionError(
                "stage has unresolved failures and cannot complete"
            )
        if completed_items != len(stage["completed_item_ids"]):
            raise OvernightExpansionError(
                "completed item count does not match checkpoint"
            )
        if (
            len(manifest_sha256) != 64
            or any(character not in "0123456789abcdef" for character in manifest_sha256)
        ):
            raise OvernightExpansionError("manifest sha256 is invalid")
        stage.update({
            "status": "COMPLETE",
            "completed_items": completed_items,
            "manifest_sha256": manifest_sha256,
            "completed_at_utc": datetime.now(UTC).isoformat(),
        })
        state["last_completed_stage"] = stage_id
        self.save(state)
        return state


def preflight(
    contract_path: Path = CONTRACT,
    state_path: Path = DEFAULT_STATE,
    root: Path = ROOT,
) -> dict[str, Any]:
    contract = load_and_verify_contract(contract_path, root)
    free_bytes = shutil.disk_usage(root).free
    minimum = contract["storage_policy"]["minimum_free_disk_bytes"]
    if free_bytes < minimum:
        raise OvernightExpansionError(
            f"insufficient disk: {free_bytes} < {minimum}"
        )
    state = RunStateStore(state_path).initialize(contract_path, root)
    return {
        "status": "PREFLIGHT_PASS",
        "contract_sha256": sha256(contract_path),
        "free_disk_bytes": free_bytes,
        "minimum_free_disk_bytes": minimum,
        "last_completed_stage": state["last_completed_stage"],
        "price_outcomes_opened": False,
        "operational_action_ratio": 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if not args.preflight:
        parser.error("--preflight is required")
    print(json.dumps(
        preflight(args.contract, args.state),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
