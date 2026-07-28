"""State S1 관측과 성숙 결과를 서로 다른 불변 원장에 기록한다."""

from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from scheduler.observation_store import validate_observation_bundle


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "data/config/prospective_evidence_v1.json"
DEFAULT_ARCHIVE_DIR = ROOT / "data/runtime/prospective-evidence"
SCHEMA_VERSION = "HERD_PROSPECTIVE_EVIDENCE_V1"
OUTCOME_SCHEMA_VERSION = "HERD_PROSPECTIVE_OUTCOME_V1"
LEVERAGED_ETFS = {
    "BITX", "BOIL", "FNGU", "LABU", "NVDL", "SOXL", "SOXS",
    "SPXL", "SPXS", "SQQQ", "TQQQ", "TSLL", "UPRO", "YINN",
}
PRICE_COLUMNS = ("Date", "Open", "High", "Low", "Close", "Volume")


class ProspectiveEvidenceError(ValueError):
    """불변성, 관측시점 또는 행동 차단 계약이 깨진 경우."""


def _canonical(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    boundary = contract.get("claim_boundary", {})
    if (
        contract.get("schema_version") != SCHEMA_VERSION
        or contract.get("status") != "LOCKED_OBSERVATION_ONLY"
        or boundary.get("descriptive_outcomes_only") is not True
        or boundary.get("candidate_selection") is not False
        or boundary.get("direction_prediction") is not False
        or boundary.get("buy_or_profit_take_authority") is not False
        or boundary.get("operational_action") != "HOLD"
        or float(boundary.get("operational_action_ratio", -1)) != 0.0
        or boundary.get("blind_holdout_access") is not False
        or boundary.get("survivorship_safe") is not False
    ):
        raise ProspectiveEvidenceError("prospective evidence contract is not locked")
    horizons = contract.get("horizons_sessions")
    if horizons != [21, 63, 126]:
        raise ProspectiveEvidenceError("prospective horizons changed")
    return contract


def _normalized_rows(frame: pd.DataFrame, cutoff: str) -> list[list[Any]]:
    missing = set(PRICE_COLUMNS) - set(frame.columns)
    if missing:
        raise ProspectiveEvidenceError(f"price columns missing: {sorted(missing)}")
    normalized = frame.loc[:, PRICE_COLUMNS].copy()
    normalized["Date"] = pd.to_datetime(normalized["Date"], errors="coerce")
    normalized = normalized[
        normalized["Date"].notna()
        & normalized["Date"].le(pd.Timestamp(cutoff))
    ].sort_values("Date")
    rows: list[list[Any]] = []
    for row in normalized.itertuples(index=False, name=None):
        values = [pd.Timestamp(row[0]).date().isoformat()]
        for value in row[1:]:
            number = float(value)
            if not math.isfinite(number):
                raise ProspectiveEvidenceError("non-finite price input")
            values.append(round(number, 8))
        rows.append(values)
    if not rows:
        raise ProspectiveEvidenceError(f"no price rows through {cutoff}")
    return rows


def _input_manifest(
    frames: dict[str, pd.DataFrame],
    *,
    cutoff: str,
) -> dict[str, Any]:
    sources = {}
    for ticker, frame in sorted(frames.items()):
        rows = _normalized_rows(frame, cutoff)
        sources[ticker] = {
            "rowCount": len(rows),
            "firstDate": rows[0][0],
            "lastDate": rows[-1][0],
            "sha256": _sha256(rows),
        }
    manifest = {
        "cutoffDate": cutoff,
        "columns": list(PRICE_COLUMNS),
        "sources": sources,
    }
    return {**manifest, "manifestSha256": _sha256(manifest)}


def _scopes(ticker: str, tracking: dict[str, set[str]]) -> list[str]:
    scopes = set(tracking.get(ticker, set()))
    if ticker == "SPY":
        scopes.add("MARKET")
    if not scopes:
        scopes.add("REFERENCE")
    if ticker in LEVERAGED_ETFS:
        scopes.add("LEVERAGED_ETF")
    return sorted(scopes)


def _stable_evidence(
    bundle: dict[str, Any],
    manifest: dict[str, Any],
    tracking: dict[str, set[str]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    validate_observation_bundle(bundle)
    dates = {record["asOfDate"] for record in bundle["records"].values()}
    if len(dates) != 1:
        raise ProspectiveEvidenceError("bundle contains multiple observation dates")
    records = []
    for ticker, record in sorted(bundle["records"].items()):
        if (
            record.get("directionPrediction") is not False
            or record.get("action") != "HOLD"
            or float(record.get("actionRatio", -1)) != 0.0
        ):
            raise ProspectiveEvidenceError(f"{ticker} contains action authority")
        records.append({
            "ticker": ticker,
            "trackingScopes": _scopes(ticker, tracking),
            "observation": record,
        })
    return {
        "schemaVersion": SCHEMA_VERSION,
        "contractSha256": _sha256(contract),
        "stateModelVersion": bundle["stateModelVersion"],
        "transitionModelVersion": bundle["transitionModelVersion"],
        "observationDate": dates.pop(),
        "referenceUniverse": bundle["referenceUniverse"],
        "claimBoundary": bundle["claimBoundary"],
        "inputManifest": manifest,
        "records": records,
        "unavailable": [
            {
                "ticker": ticker,
                "reason": reason,
                "trackingScopes": _scopes(ticker, tracking),
            }
            for ticker, reason in sorted(bundle.get("unavailable", {}).items())
            if ticker in tracking
        ],
    }


def archive_observation(
    bundle: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    tracking: dict[str, set[str]],
    *,
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
    recorded_at: datetime | None = None,
    contract_path: Path = CONTRACT_PATH,
) -> dict[str, Any]:
    """관측일 하나를 덮어쓰지 않는 JSON envelope로 저장한다."""
    contract = load_contract(contract_path)
    dates = {record["asOfDate"] for record in bundle["records"].values()}
    if len(dates) != 1:
        raise ProspectiveEvidenceError("bundle contains multiple observation dates")
    observation_date = next(iter(dates))
    path = archive_dir / "observations" / f"{observation_date}.json"
    if path.exists():
        existing = verify_observation(path)
        return {
            "status": "EXISTS",
            "path": str(path),
            "recordCount": len(existing["evidence"]["records"]),
        }
    cutoff = max(
        record["lastObservedSession"] for record in bundle["records"].values()
    )
    manifest = _input_manifest(frames, cutoff=cutoff)
    evidence = _stable_evidence(bundle, manifest, tracking, contract)
    evidence_hash = _sha256(evidence)
    timestamp = (recorded_at or datetime.now(UTC)).astimezone(UTC)
    envelope = {
        "recordedAt": timestamp.isoformat().replace("+00:00", "Z"),
        "evidence": evidence,
        "evidenceSha256": evidence_hash,
    }
    envelope["envelopeSha256"] = _sha256(envelope)
    _atomic_json(path, envelope)
    return {"status": "CREATED", "path": str(path), "recordCount": len(evidence["records"])}


def verify_observation(path: Path) -> dict[str, Any]:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    expected_envelope = envelope.pop("envelopeSha256", None)
    if expected_envelope != _sha256(envelope):
        raise ProspectiveEvidenceError(f"observation envelope hash mismatch: {path}")
    if envelope.get("evidenceSha256") != _sha256(envelope.get("evidence")):
        raise ProspectiveEvidenceError(f"observation evidence hash mismatch: {path}")
    envelope["envelopeSha256"] = expected_envelope
    return envelope


def verify_outcome(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    digest = payload.pop("outcomeSha256", None)
    if (
        payload.get("schemaVersion") != OUTCOME_SCHEMA_VERSION
        or digest != _sha256(payload)
        or payload.get("directionPrediction") is not False
        or payload.get("operationalAction") != "HOLD"
        or float(payload.get("operationalActionRatio", -1)) != 0.0
        or payload.get("economicLabel") != "NOT_ASSIGNED_OBSERVATION_ONLY"
    ):
        raise ProspectiveEvidenceError(f"outcome contract/hash mismatch: {path}")
    payload["outcomeSha256"] = digest
    return payload


def _normalize_outcome_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(PRICE_COLUMNS) - set(frame.columns)
    if missing:
        raise ProspectiveEvidenceError(f"price columns missing: {sorted(missing)}")
    rows = frame.loc[:, PRICE_COLUMNS].copy()
    rows["Date"] = pd.to_datetime(rows["Date"], errors="coerce")
    return rows.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)


def _outcome(
    record: dict[str, Any],
    source_hash: str,
    rows: pd.DataFrame,
    horizon: int,
) -> dict[str, Any] | None:
    observation = record["observation"]
    future = rows[rows["Date"].gt(pd.Timestamp(observation["lastObservedSession"]))]
    if len(future) < horizon:
        return None
    window = future.iloc[:horizon]
    entry = float(window.iloc[0]["Open"])
    terminal = float(window.iloc[-1]["Close"])
    if not math.isfinite(entry) or entry <= 0 or not math.isfinite(terminal):
        raise ProspectiveEvidenceError(f"invalid outcome price: {record['ticker']}")
    highs = pd.to_numeric(window["High"], errors="coerce") / entry - 1
    lows = pd.to_numeric(window["Low"], errors="coerce") / entry - 1
    payload = {
        "schemaVersion": OUTCOME_SCHEMA_VERSION,
        "sourceEvidenceSha256": source_hash,
        "ticker": record["ticker"],
        "trackingScopesAtObservation": record["trackingScopes"],
        "observationDate": observation["asOfDate"],
        "lastObservedSession": observation["lastObservedSession"],
        "horizonSessions": horizon,
        "entry": {
            "date": pd.Timestamp(window.iloc[0]["Date"]).date().isoformat(),
            "basis": "NEXT_AVAILABLE_SESSION_OPEN",
            "price": round(entry, 8),
        },
        "terminal": {
            "date": pd.Timestamp(window.iloc[-1]["Date"]).date().isoformat(),
            "price": round(terminal, 8),
        },
        "descriptiveOutcome": {
            "return": round(terminal / entry - 1, 8),
            "maximumFavorableExcursion": round(float(highs.max()), 8),
            "maximumAdverseExcursion": round(float(lows.min()), 8),
        },
        "economicLabel": "NOT_ASSIGNED_OBSERVATION_ONLY",
        "directionPrediction": False,
        "operationalAction": "HOLD",
        "operationalActionRatio": 0.0,
    }
    return {**payload, "outcomeSha256": _sha256(payload)}


def mature_outcomes(
    frames: dict[str, pd.DataFrame],
    *,
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
    contract_path: Path = CONTRACT_PATH,
) -> dict[str, Any]:
    """기간이 실제로 지난 관측만 별도 불변 결과 파일로 확정한다."""
    contract = load_contract(contract_path)
    normalized_frames = {
        ticker: _normalize_outcome_frame(frame)
        for ticker, frame in frames.items()
    }
    summary = {"archives": 0, "created": 0, "existing": 0, "pending": 0, "unavailable": 0}
    for path in sorted((archive_dir / "observations").glob("*.json")):
        envelope = verify_observation(path)
        evidence = envelope["evidence"]
        summary["archives"] += 1
        for record in evidence["records"]:
            ticker = record["ticker"]
            frame = normalized_frames.get(ticker)
            for horizon in contract["horizons_sessions"]:
                if frame is None:
                    summary["unavailable"] += 1
                    continue
                outcome = _outcome(record, envelope["evidenceSha256"], frame, horizon)
                if outcome is None:
                    summary["pending"] += 1
                    continue
                target = (
                    archive_dir / "outcomes" / evidence["observationDate"]
                    / f"{ticker}-{horizon}.json"
                )
                if target.exists():
                    existing = verify_outcome(target)
                    if existing.get("outcomeSha256") != outcome["outcomeSha256"]:
                        raise ProspectiveEvidenceError(
                            f"immutable outcome conflict: {target}"
                        )
                    summary["existing"] += 1
                else:
                    _atomic_json(target, outcome)
                    summary["created"] += 1
    summary["status"] = "SUCCESS"
    return summary


def audit_archive(
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
    *,
    contract_path: Path = CONTRACT_PATH,
) -> dict[str, Any]:
    """모든 관측·결과 파일의 해시와 행동 차단 경계를 검사한다."""
    contract = load_contract(contract_path)
    observations = [
        verify_observation(path)
        for path in sorted((archive_dir / "observations").glob("*.json"))
    ]
    outcomes = [
        verify_outcome(path)
        for path in sorted((archive_dir / "outcomes").glob("*/*.json"))
    ]
    source_hashes = {item["evidenceSha256"] for item in observations}
    orphan_outcomes = [
        item for item in outcomes
        if item["sourceEvidenceSha256"] not in source_hashes
    ]
    if orphan_outcomes:
        raise ProspectiveEvidenceError("outcome without source observation")
    horizons = contract["horizons_sessions"]
    outcome_keys = {
        (
            item["sourceEvidenceSha256"],
            item["ticker"],
            int(item["horizonSessions"]),
        )
        for item in outcomes
    }
    maturity_by_horizon = {}
    pending_outcomes = 0
    for horizon in horizons:
        eligible = [
            (observation["evidenceSha256"], record["ticker"], horizon)
            for observation in observations
            for record in observation["evidence"]["records"]
        ]
        matured = sum(key in outcome_keys for key in eligible)
        pending = len(eligible) - matured
        pending_outcomes += pending
        maturity_by_horizon[str(horizon)] = {
            "expected": len(eligible),
            "matured": matured,
            "pending": pending,
        }
    observation_dates = [
        item["evidence"]["observationDate"] for item in observations
    ]
    distinct_tickers = {
        record["ticker"]
        for observation in observations
        for record in observation["evidence"]["records"]
    }
    return {
        "schemaVersion": "HERD_PROSPECTIVE_EVIDENCE_AUDIT_V1",
        "status": "PASS",
        "observationArchives": len(observations),
        "firstObservationDate": observation_dates[0] if observation_dates else None,
        "latestObservationDate": observation_dates[-1] if observation_dates else None,
        "observationRecords": sum(
            len(item["evidence"]["records"]) for item in observations
        ),
        "distinctTickers": len(distinct_tickers),
        "unavailableRecords": sum(
            len(item["evidence"].get("unavailable", [])) for item in observations
        ),
        "maturedOutcomes": len(outcomes),
        "pendingOutcomes": pending_outcomes,
        "maturityByHorizon": maturity_by_horizon,
        "operationalAction": "HOLD",
        "operationalActionRatio": 0.0,
    }
