"""고정된 Rush 경로 사건 원장의 시점 정합성과 완전성을 감사한다."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = Path(__file__).with_suffix(".json")
LEDGER_VERSION = "HERD_MODEL_RUSH_EPISODE_LEDGER_V1"


class RushEpisodeLedgerError(ValueError):
    """사건 원장이 변조됐거나 미래 정보가 섞였을 때 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pinned(specification: dict[str, Any]) -> Path:
    path = (ROOT / specification["path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise RushEpisodeLedgerError(f"missing ledger input: {specification['path']}")
    if _sha256(path) != specification["sha256"]:
        raise RushEpisodeLedgerError(f"hash mismatch: {specification['path']}")
    return path


def validate_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    if (
        ledger.get("ledger_version") != LEDGER_VERSION
        or ledger.get("status") != "PINNED_DIAGNOSTIC_LEDGER"
    ):
        raise RushEpisodeLedgerError("episode ledger is not pinned")

    protocol = json.loads(_pinned(ledger["protocol"]).read_text(encoding="utf-8"))
    result = json.loads(_pinned(ledger["result"]).read_text(encoding="utf-8"))
    with _pinned(ledger["events"]).open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    events_spec = ledger["events"]
    if len(rows) != events_spec["expected_rows"]:
        raise RushEpisodeLedgerError("episode count changed")
    identifiers = [row["episode_id"] for row in rows]
    if len(set(identifiers)) != len(identifiers):
        raise RushEpisodeLedgerError("duplicate episode id")
    if len({row["ticker"] for row in rows}) != events_spec["expected_tickers"]:
        raise RushEpisodeLedgerError("ticker coverage changed")

    expected_labels = ledger["path_labels"]
    actual_labels = Counter(row["path_label"] for row in rows)
    if dict(actual_labels) != expected_labels or sum(expected_labels.values()) != len(rows):
        raise RushEpisodeLedgerError("path classification changed or is incomplete")

    for row in rows:
        signal = date.fromisoformat(row["signal_date"])
        observed = date.fromisoformat(row["last_observed_session"])
        feature_cutoff = date.fromisoformat(row["feature_cutoff_date"])
        damage = date.fromisoformat(row["damage_date"])
        execution = date.fromisoformat(row["damage_execution_date"])
        path_end = date.fromisoformat(row["path_end"])
        outcome_end = date.fromisoformat(row["outcome_end"])
        if not signal <= observed <= feature_cutoff < damage < execution <= path_end <= outcome_end:
            raise RushEpisodeLedgerError(f"temporal leakage in {row['episode_id']}")
        if not row["fold_id"]:
            raise RushEpisodeLedgerError(f"missing fold in {row['episode_id']}")

    authority = ledger["authority"]
    if (
        authority.get("descriptive_path_input") is not True
        or any(
            authority.get(key) is not False
            for key in ("feature_selection", "profit_take", "reentry", "blind_holdout_access", "survivorship_safe")
        )
        or authority.get("operational_action_ratio") != 0.0
        or result.get("classified_events") != len(rows)
        or result.get("retained_features") != []
        or result.get("profit_take_authorized") is not False
        or protocol.get("interpretation", {}).get("same_sample_action_authority") is not False
    ):
        raise RushEpisodeLedgerError("diagnostic evidence authority was widened")

    adverse = actual_labels["LARGE_PULLBACK"] + actual_labels["STRUCTURAL_BREAK"]
    return {
        "ledger_version": LEDGER_VERSION,
        "episodes": len(rows),
        "tickers": len({row["ticker"] for row in rows}),
        "path_counts": dict(actual_labels),
        "adverse_path_fraction": round(adverse / len(rows), 6),
        "temporal_leakage_rows": 0,
        "feature_selection_authority": False,
        "profit_take_authority": False,
        "survivorship_safe": False,
    }


def load_ledger(path: Path = LEDGER_PATH) -> tuple[dict[str, Any], dict[str, Any]]:
    ledger = json.loads(path.read_text(encoding="utf-8"))
    return ledger, validate_ledger(ledger)


if __name__ == "__main__":
    print(json.dumps(validate_ledger(json.loads(LEDGER_PATH.read_text())), indent=2))
