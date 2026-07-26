"""차세대 HERD의 개발·OOS·블라인드·전향 관측 경계를 검증한다."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SPLIT_PATH = Path(__file__).with_suffix(".json")
SPLIT_VERSION = "HERD_MODEL_ESTABLISHMENT_SPLIT_V1"


class ModelEstablishmentSplitError(ValueError):
    """연구 구간이 겹치거나 봉인된 평가 경계가 약해졌을 때 발생한다."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pinned(spec: dict[str, Any], path_key: str = "path", hash_key: str = "sha256") -> Path:
    path = (REPOSITORY_ROOT / spec[path_key]).resolve()
    if not path.is_relative_to(REPOSITORY_ROOT) or not path.is_file():
        raise ModelEstablishmentSplitError(f"missing pinned input: {spec[path_key]}")
    if _sha256(path) != spec[hash_key]:
        raise ModelEstablishmentSplitError(f"hash mismatch: {spec[path_key]}")
    return path


def _read_folds(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _validate_lane(name: str, specification: dict[str, Any]) -> tuple[int, float]:
    rows = _read_folds(_pinned(specification))
    if len(rows) < specification["minimum_complete_folds"]:
        raise ModelEstablishmentSplitError(f"{name} has insufficient folds")

    test_intervals: list[tuple[date, date]] = []
    for row in rows:
        train_end = date.fromisoformat(row["train_end"])
        gap_start = date.fromisoformat(row["gap_start"])
        gap_end = date.fromisoformat(row["gap_end"])
        test_start = date.fromisoformat(row["test_start"])
        test_end = date.fromisoformat(row["test_end"])
        if not train_end < gap_start <= gap_end < test_start <= test_end:
            raise ModelEstablishmentSplitError(f"{name} fold chronology is invalid")
        test_intervals.append((test_start, test_end))

    ordered = sorted(test_intervals)
    if any(previous[1] >= current[0] for previous, current in zip(ordered, ordered[1:])):
        raise ModelEstablishmentSplitError(f"{name} test windows overlap")
    oos_days = sum((end - start).days + 1 for start, end in ordered)
    oos_years = oos_days / 365.2425
    if oos_years < specification["minimum_oos_years"]:
        raise ModelEstablishmentSplitError(f"{name} has insufficient OOS years")
    return len(rows), oos_years


def validate_split(split: dict[str, Any]) -> dict[str, Any]:
    if (
        split.get("split_version") != SPLIT_VERSION
        or split.get("status") != "LOCKED_WITH_BLIND_HOLDOUT_UNASSIGNED"
    ):
        raise ModelEstablishmentSplitError("split contract is not locked")

    input_contract = json.loads(_pinned(split["input_contract"]).read_text(encoding="utf-8"))
    protocol = json.loads(_pinned(split["fold_protocol"]).read_text(encoding="utf-8"))
    boundary = split["historical_data_boundary"]
    if (
        input_contract.get("research_period") != {"start": boundary["start"], "end": boundary["end"]}
        or protocol.get("status") != "LOCKED_BEFORE_NEW_HYPOTHESIS_RESULTS"
        or boundary.get("may_become_blind_holdout") is not False
    ):
        raise ModelEstablishmentSplitError("historical boundary is inconsistent")

    lane_audits = {
        name: _validate_lane(name, specification)
        for name, specification in split["historical_lanes"].items()
    }

    blind = split["blind_holdout"]
    if (
        blind.get("holdout_id") != "HERD_VNEXT_UNASSIGNED"
        or blind.get("assignment") is not None
        or blind.get("data_path") is not None
        or blind.get("status") != "SEALED_UNASSIGNED"
        or blind.get("evaluation_count") != 0
        or blind.get("access_allowed") is not False
        or blind.get("legacy_v61_holdout_reusable") is not False
    ):
        raise ModelEstablishmentSplitError("blind holdout was assigned or opened")

    shadow = split["prospective_shadow"]
    shadow_protocol = json.loads(
        _pinned(shadow, "protocol_path", "protocol_sha256").read_text(encoding="utf-8")
    )
    if (
        date.fromisoformat(shadow["start_after"]) < date.fromisoformat(boundary["end"])
        or shadow.get("role") != "FORWARD_OBSERVATION_ONLY"
        or shadow.get("may_train_or_select_candidate") is not False
        or shadow.get("may_authorize_action") is not False
        or shadow_protocol.get("authority", {}).get("blind_holdout_access") is not False
    ):
        raise ModelEstablishmentSplitError("prospective shadow boundary is unsafe")

    invariants = split["invariants"]
    if (
        invariants.get("current_constituent_universe_is_not_survivorship_safe") is not True
        or invariants.get("operational_action_ratio") != 0.0
        or not all(
            invariants.get(key) is True
            for key in (
                "fold_test_windows_non_overlapping_within_lane",
                "label_outcome_must_end_inside_test_fold",
                "purge_and_embargo_required",
                "cross_fold_event_reuse_forbidden",
                "blind_dates_must_remain_unassigned_until_prerequisites_pass",
                "prospective_shadow_must_not_be_backfilled",
            )
        )
    ):
        raise ModelEstablishmentSplitError("split invariant weakened")

    return {
        "split_version": SPLIT_VERSION,
        "historical_start": boundary["start"],
        "historical_end": boundary["end"],
        "lanes": {
            name: {"folds": folds, "oos_years": round(years, 2)}
            for name, (folds, years) in lane_audits.items()
        },
        "blind_holdout": "SEALED_UNASSIGNED",
        "prospective_shadow": "FORWARD_OBSERVATION_ONLY",
        "survivorship_safe": False,
        "operational_action_ratio": 0.0,
    }


def load_split(path: Path = SPLIT_PATH) -> tuple[dict[str, Any], dict[str, Any]]:
    split = json.loads(path.read_text(encoding="utf-8"))
    return split, validate_split(split)


if __name__ == "__main__":
    print(json.dumps(validate_split(json.loads(SPLIT_PATH.read_text())), indent=2))
