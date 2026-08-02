"""Validate the append-only extension of the failed hypothesis ledger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from herd.failed_hypothesis_map_v1 import (
    FailedHypothesisMapError,
    load_failed_hypothesis_map as load_v1,
)


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = Path(__file__).with_suffix(".json")
MAP_VERSION = "HERD_FAILED_HYPOTHESIS_MAP_V2"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _get_path(payload: dict[str, Any], dotted_path: str) -> Any:
    value: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise FailedHypothesisMapError(f"missing assertion field: {dotted_path}")
        value = value[part]
    return value


def validate_failed_hypothesis_map_v2(mapping: dict[str, Any]) -> dict[str, Any]:
    if (
        mapping.get("map_version") != MAP_VERSION
        or mapping.get("status") != "LOCKED_APPEND_ONLY_POST_RESEARCH_AUDIT"
    ):
        raise FailedHypothesisMapError("failure map V2 is not locked")

    parent = mapping.get("parent", {})
    parent_path = (ROOT / parent.get("path", "")).resolve()
    if (
        not parent_path.is_relative_to(ROOT)
        or not parent_path.is_file()
        or _sha256(parent_path) != parent.get("sha256")
    ):
        raise FailedHypothesisMapError("failure map V1 parent changed")
    parent_mapping, parent_audit = load_v1(parent_path)
    if parent_audit["experiment_count"] != parent.get("experiment_count"):
        raise FailedHypothesisMapError("failure map V1 count changed")

    appended = mapping.get("appended_experiments", [])
    if len(appended) != 1:
        raise FailedHypothesisMapError("V2 must append exactly one experiment")
    experiment = appended[0]
    source_path = (ROOT / experiment["source"]["path"]).resolve()
    if (
        not source_path.is_relative_to(ROOT)
        or not source_path.is_file()
        or _sha256(source_path) != experiment["source"]["sha256"]
    ):
        raise FailedHypothesisMapError("appended result changed")
    result = json.loads(source_path.read_text(encoding="utf-8"))
    for dotted_path, expected in experiment["assertions"].items():
        if _get_path(result, dotted_path) != expected:
            raise FailedHypothesisMapError(
                f"source decision changed: {experiment['id']}:{dotted_path}"
            )
    if (
        experiment.get("decision") != "REJECTED"
        or not experiment.get("failure")
        or not experiment.get("retry_policy")
    ):
        raise FailedHypothesisMapError("appended rejection is incomplete")

    identifiers = [item["id"] for item in parent_mapping["experiments"]] + [
        experiment["id"]
    ]
    if len(identifiers) != len(set(identifiers)):
        raise FailedHypothesisMapError("duplicate experiment id")

    rules = mapping.get("global_rules", {})
    if (
        not all(
            rules.get(rule) is True
            for rule in (
                "same_sample_threshold_retuning_forbidden",
                "same_sample_horizon_retuning_forbidden",
                "rejected_feature_recombination_forbidden",
                "legacy_formula_reuse_forbidden",
            )
        )
        or rules.get("blind_holdout_access") is not False
        or rules.get("operational_action_ratio") != 0.0
    ):
        raise FailedHypothesisMapError("global research boundary weakened")

    expected = {
        "experiment_count": 11,
        "rejected_count": 11,
        "adoptable_direction_count": 0,
        "duplicate_experiment_ids": 0,
    }
    if mapping.get("audit_summary") != expected:
        raise FailedHypothesisMapError("V2 audit summary is inconsistent")
    return {
        "map_version": MAP_VERSION,
        **expected,
        "parent_experiment_count": parent_audit["experiment_count"],
        "appended_experiment_count": len(appended),
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
    }


def load_failed_hypothesis_map_v2(
    path: Path = MAP_PATH,
) -> tuple[dict[str, Any], dict[str, Any]]:
    mapping = json.loads(path.read_text(encoding="utf-8"))
    return mapping, validate_failed_hypothesis_map_v2(mapping)


if __name__ == "__main__":
    print(json.dumps(load_failed_hypothesis_map_v2()[1], indent=2))
