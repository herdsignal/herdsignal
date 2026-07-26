"""Rush 사건을 시점 정합 V2 연구 데이터셋으로 재현한다."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
OUTPUT_PATH = ROOT / "data/reports/rush_event_dataset_v2.csv"
REPORT_PATH = ROOT / "data/reports/rush_event_dataset_v2.json"
VERSION = "HERD_RUSH_EVENT_DATASET_V2"


class RushEventDatasetV2Error(ValueError):
    """Rush V2 데이터셋 계약 위반."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pinned(specification: dict[str, Any]) -> Path:
    path = (ROOT / specification["path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise RushEventDatasetV2Error(f"missing input: {specification['path']}")
    if _hash(path) != specification["sha256"]:
        raise RushEventDatasetV2Error(f"hash mismatch: {specification['path']}")
    return path


def _ordered_columns(protocol: dict[str, Any]) -> list[str]:
    schema = protocol["schema"]
    return [
        *schema["identity"],
        *schema["observation_time"],
        *schema["outcome_time"],
        *schema["pre_confirmation_features"],
        *schema["future_outcomes"],
    ]


def build_dataset(
    protocol: dict[str, Any],
    output_path: Path = OUTPUT_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    if (
        protocol.get("protocol_version") != VERSION
        or protocol.get("status") != "LOCKED_DIAGNOSTIC_DATASET"
    ):
        raise RushEventDatasetV2Error("dataset protocol is not locked")
    _pinned(protocol["split_contract"])
    source = _pinned(protocol["source"])
    with source.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    columns = _ordered_columns(protocol)
    labels = Counter()
    tickers: set[str] = set()
    episodes: set[str] = set()
    folds: set[str] = set()
    normalized: list[dict[str, str]] = []
    missing_features = 0
    for row in rows:
        episode_id = row["episode_id"]
        if episode_id in episodes:
            raise RushEventDatasetV2Error(f"duplicate episode: {episode_id}")
        episodes.add(episode_id)
        tickers.add(row["ticker"])
        folds.add(row["fold_id"])
        labels[row["path_label"]] += 1
        signal = date.fromisoformat(row["signal_date"])
        observed = date.fromisoformat(row["last_observed_session"])
        cutoff = date.fromisoformat(row["feature_cutoff_date"])
        damage = date.fromisoformat(row["damage_date"])
        execution = date.fromisoformat(row["damage_execution_date"])
        path_end = date.fromisoformat(row["path_end"])
        outcome_end = date.fromisoformat(row["outcome_end"])
        if not signal <= observed <= cutoff < damage < execution <= path_end <= outcome_end:
            raise RushEventDatasetV2Error(f"temporal leakage: {episode_id}")
        if not row["fold_id"]:
            raise RushEventDatasetV2Error(f"missing fold: {episode_id}")
        missing_features += sum(
            not row[name] for name in protocol["schema"]["pre_confirmation_features"]
        )
        normalized.append({name: row[name] for name in columns})

    if (
        len(rows) != protocol["source"]["expected_rows"]
        or len(tickers) != protocol["source"]["expected_tickers"]
        or dict(labels) != protocol["path_labels"]
    ):
        raise RushEventDatasetV2Error("source population or labels changed")
    authority = protocol["authority"]
    if (
        authority["dataset_role"] != "REPEATED_PREHOLDOUT_DIAGNOSTIC"
        or any(
            authority[name]
            for name in (
                "feature_selection",
                "threshold_retuning",
                "profit_take",
                "reentry",
                "blind_holdout_access",
                "survivorship_safe",
            )
        )
        or authority["operational_action_ratio"] != 0.0
    ):
        raise RushEventDatasetV2Error("dataset authority was widened")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(normalized)
    dataset_path = str(output_path.relative_to(ROOT)) if output_path.is_relative_to(ROOT) else str(output_path)
    report = {
        "protocol_version": VERSION,
        "status": "BUILT_DIAGNOSTIC_ONLY",
        "rows": len(rows),
        "tickers": len(tickers),
        "folds": sorted(folds),
        "path_labels": dict(labels),
        "missing_pre_confirmation_feature_cells": missing_features,
        "dataset_path": dataset_path,
        "dataset_sha256": _hash(output_path),
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(build_dataset(json.loads(PROTOCOL_PATH.read_text())), indent=2))
