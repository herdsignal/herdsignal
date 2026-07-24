"""State S1 관찰 번들을 검증한 뒤 한 트랜잭션으로 저장한다."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from init_db import HerdObservation
from scheduler.observation_s1 import FORMAT_VERSION


STATE_MODEL_VERSION = "HERD_STATE_S1"
TRANSITION_MODEL_VERSION = "HERD_TRANSITION_S1"
FAMILY_BINDINGS = {
    "PRICE_EXTENSION": "price_extension",
    "TREND_POSITION": "trend_position",
    "RELATIVE_POSITION": "relative_position",
    "PARTICIPATION": "participation",
}


class ObservationStoreError(ValueError):
    """관찰 번들의 행동 경계나 저장 계약이 깨진 경우."""


def _decimal(value: Any, field: str, *, lower: float | None = None,
             upper: float | None = None) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ObservationStoreError(f"{field} must be numeric") from exc
    if not math.isfinite(float(number)):
        raise ObservationStoreError(f"{field} must be finite")
    if lower is not None and number < Decimal(str(lower)):
        raise ObservationStoreError(f"{field} must be >= {lower}")
    if upper is not None and number > Decimal(str(upper)):
        raise ObservationStoreError(f"{field} must be <= {upper}")
    return number


def _date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ObservationStoreError(f"{field} must be an ISO date") from exc


def _utc_datetime(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ObservationStoreError(f"{field} must be an ISO datetime") from exc
    if parsed.tzinfo is None:
        raise ObservationStoreError(f"{field} must include a timezone")
    return parsed.astimezone(UTC).replace(tzinfo=None)


def _require_state_only(boundary: dict[str, Any], prefix: str) -> None:
    if (
        boundary.get("directionPrediction") is not False
        or boundary.get("operationalAction") != "HOLD"
        or _decimal(
            boundary.get("operationalActionRatio"),
            f"{prefix}.operationalActionRatio",
        ) != 0
        or boundary.get("blindHoldoutAccess") is not False
    ):
        raise ObservationStoreError(f"{prefix} violates state-only boundary")


def _record_values(
    ticker_key: str,
    record: dict[str, Any],
    bundle: dict[str, Any],
    generated_at: datetime,
) -> dict[str, Any]:
    ticker = str(record.get("ticker", "")).strip().upper()
    if not ticker or ticker != ticker_key:
        raise ObservationStoreError(
            f"record key/ticker mismatch: {ticker_key}/{ticker or '<empty>'}"
        )
    if (
        record.get("directionPrediction") is not False
        or record.get("action") != "HOLD"
        or _decimal(record.get("actionRatio"), f"{ticker}.actionRatio") != 0
    ):
        raise ObservationStoreError(f"{ticker} violates state-only boundary")

    scope = record.get("scope")
    if scope not in {"EQUITY", "MARKET_AGGREGATE"}:
        raise ObservationStoreError(f"{ticker}.scope is unsupported")
    if scope == "MARKET_AGGREGATE" and (
        not record.get("label") or not record.get("claim")
    ):
        raise ObservationStoreError(
            f"{ticker} market aggregate requires label and claim"
        )

    families = record.get("families")
    if not isinstance(families, dict):
        raise ObservationStoreError(f"{ticker}.families must be an object")
    values = {
        attribute: _decimal(
            families.get(source),
            f"{ticker}.families.{source}",
            lower=0,
            upper=100,
        )
        for source, attribute in FAMILY_BINDINGS.items()
    }
    reference_coverage = record.get("referenceCoverageFraction")
    values.update(
        {
            "ticker": ticker,
            "schema_version": bundle["schemaVersion"],
            "state_model_version": bundle["stateModelVersion"],
            "transition_model_version": bundle["transitionModelVersion"],
            "observation_date": _date(record.get("asOfDate"), f"{ticker}.asOfDate"),
            "last_observed_session": _date(
                record.get("lastObservedSession"),
                f"{ticker}.lastObservedSession",
            ),
            "generated_at": generated_at,
            "source_scope": scope,
            "display_label": record.get("label"),
            "claim_code": record.get("claim"),
            "state_score": _decimal(
                record.get("stateScore"),
                f"{ticker}.stateScore",
                lower=0,
                upper=100,
            ),
            "herd_stage": str(record.get("stage", "")).strip(),
            "transition_code": str(record.get("transition", "")).strip(),
            "raw_transition_code": str(
                record.get("rawTransition", "")
            ).strip(),
            "transition_event": record.get("transitionEvent"),
            "delta_4w": _decimal(record.get("delta4w"), f"{ticker}.delta4w"),
            "delta_13w": _decimal(record.get("delta13w"), f"{ticker}.delta13w"),
            "downside_risk_context": _decimal(
                record.get("downsideRiskContext"),
                f"{ticker}.downsideRiskContext",
                lower=0,
                upper=100,
            ),
            "sector_etf": str(record.get("sectorEtf", "")).strip().upper(),
            "reference_coverage_fraction": (
                None
                if reference_coverage is None
                else _decimal(
                    reference_coverage,
                    f"{ticker}.referenceCoverageFraction",
                    lower=0,
                    upper=1,
                )
            ),
            "direction_prediction": False,
            "operational_action": "HOLD",
            "operational_action_ratio": Decimal("0"),
            "survivorship_safe": False,
        }
    )
    required_text = (
        "herd_stage",
        "transition_code",
        "raw_transition_code",
        "sector_etf",
    )
    if any(not values[field] for field in required_text):
        raise ObservationStoreError(f"{ticker} has an empty required field")
    if not isinstance(values["transition_event"], bool):
        raise ObservationStoreError(f"{ticker}.transitionEvent must be boolean")
    return values


def validate_observation_bundle(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """DB 연결 전에 전체 번들을 검증해 부분 저장 가능성을 제거한다."""
    if bundle.get("schemaVersion") != FORMAT_VERSION:
        raise ObservationStoreError("unexpected observation schema version")
    if bundle.get("stateModelVersion") != STATE_MODEL_VERSION:
        raise ObservationStoreError("unexpected state model version")
    if bundle.get("transitionModelVersion") != TRANSITION_MODEL_VERSION:
        raise ObservationStoreError("unexpected transition model version")
    boundary = bundle.get("claimBoundary")
    if not isinstance(boundary, dict):
        raise ObservationStoreError("claimBoundary must be an object")
    _require_state_only(boundary, "claimBoundary")
    reference = bundle.get("referenceUniverse")
    if (
        not isinstance(reference, dict)
        or reference.get("survivorshipSafe") is not False
    ):
        raise ObservationStoreError("reference universe boundary is missing")
    generated_at = _utc_datetime(bundle.get("generatedAt"), "generatedAt")
    records = bundle.get("records")
    if not isinstance(records, dict) or not records:
        raise ObservationStoreError("records must be a non-empty object")
    return [
        _record_values(ticker, record, bundle, generated_at)
        for ticker, record in sorted(records.items())
    ]


def save_observation_bundle(
    bundle: dict[str, Any],
    session_factory: Callable,
) -> dict[str, int]:
    """동일 모델·종목·기준일은 갱신하고 번들 전체를 한 번에 커밋한다."""
    values_list = validate_observation_bundle(bundle)
    inserted = 0
    updated = 0
    with session_factory() as session:
        try:
            for values in values_list:
                row = (
                    session.query(HerdObservation)
                    .filter_by(
                        ticker=values["ticker"],
                        state_model_version=values["state_model_version"],
                        observation_date=values["observation_date"],
                    )
                    .one_or_none()
                )
                if row is None:
                    row = HerdObservation(**values)
                    session.add(row)
                    inserted += 1
                else:
                    for field, value in values.items():
                        setattr(row, field, value)
                    updated += 1
            session.commit()
        except Exception:
            session.rollback()
            raise
    return {"inserted": inserted, "updated": updated}
