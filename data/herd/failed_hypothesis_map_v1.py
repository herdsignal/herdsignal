"""탈락 가설의 원본, 표본, 목표와 재시험 금지 경계를 검증한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = Path(__file__).with_suffix(".json")
MAP_VERSION = "HERD_FAILED_HYPOTHESIS_MAP_V1"


class FailedHypothesisMapError(ValueError):
    """탈락 결과가 변조되거나 재시험 경계가 완화됐을 때 발생한다."""


def _get_path(payload: dict[str, Any], dotted_path: str) -> Any:
    value: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise FailedHypothesisMapError(f"missing assertion field: {dotted_path}")
        value = value[part]
    return value


def _load_pinned(specification: dict[str, str]) -> dict[str, Any]:
    path = (ROOT / specification["path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise FailedHypothesisMapError(f"missing result: {specification['path']}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != specification["sha256"]:
        raise FailedHypothesisMapError(f"hash mismatch: {specification['path']}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_failed_hypothesis_map(mapping: dict[str, Any]) -> dict[str, Any]:
    if (
        mapping.get("map_version") != MAP_VERSION
        or mapping.get("status") != "LOCKED_POST_RESEARCH_AUDIT"
    ):
        raise FailedHypothesisMapError("failure map is not locked")
    if mapping.get("legacy_models") != {
        "HERD_V4": "LEGACY_REFERENCE_ONLY",
        "HERD_V6_1": "LEGACY_REFERENCE_ONLY",
    }:
        raise FailedHypothesisMapError("legacy model boundary changed")

    experiments = mapping["experiments"]
    identifiers = [experiment["id"] for experiment in experiments]
    experiment_keys = [
        (experiment["economic_family"], experiment["sample_id"], experiment["target"])
        for experiment in experiments
    ]
    if len(identifiers) != len(set(identifiers)):
        raise FailedHypothesisMapError("duplicate experiment id")
    if len(experiment_keys) != len(set(experiment_keys)):
        raise FailedHypothesisMapError("duplicate experiment key")

    for experiment in experiments:
        result = _load_pinned(experiment["source"])
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
            raise FailedHypothesisMapError(f"incomplete rejection: {experiment['id']}")

    rules = mapping["global_rules"]
    required_true = (
        "same_sample_threshold_retuning_forbidden",
        "same_sample_horizon_retuning_forbidden",
        "rejected_feature_recombination_forbidden",
        "legacy_formula_reuse_forbidden",
    )
    if (
        not all(rules.get(rule) is True for rule in required_true)
        or rules.get("blind_holdout_access") is not False
        or rules.get("operational_action_ratio") != 0.0
    ):
        raise FailedHypothesisMapError("global research boundary weakened")

    expected_summary = {
        "experiment_count": len(experiments),
        "rejected_count": len(experiments),
        "adoptable_direction_count": 0,
        "duplicate_experiment_keys": 0,
        "unmapped_retry_policy_count": 0,
    }
    if mapping.get("audit_summary") != expected_summary:
        raise FailedHypothesisMapError("audit summary is inconsistent")

    return {
        "map_version": MAP_VERSION,
        **expected_summary,
        "economic_families": len({item["economic_family"] for item in experiments}),
        "source_reports_verified": len(experiments),
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
    }


def load_failed_hypothesis_map(
    path: Path = MAP_PATH,
) -> tuple[dict[str, Any], dict[str, Any]]:
    mapping = json.loads(path.read_text(encoding="utf-8"))
    return mapping, validate_failed_hypothesis_map(mapping)


if __name__ == "__main__":
    print(
        json.dumps(
            validate_failed_hypothesis_map(json.loads(MAP_PATH.read_text())),
            indent=2,
        )
    )
