"""Form 4·SEC guidance·FINRA의 source facts를 prospective snapshot으로 합친다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
PANEL = ROOT / "data/reports/unified_pit_shadow_panel_v1.csv"
REPORT = ROOT / "data/reports/unified_pit_shadow_panel_v1.json"
NEW_YORK = ZoneInfo("America/New_York")

FIELDS = [
    "panel_row_id",
    "ticker",
    "cik",
    "observed_at",
    "available_at",
    "source",
    "feature_name",
    "feature_value",
    "unit",
    "source_record_id",
    "source_url",
    "source_sha256",
    "revision_status",
    "identity_confidence",
    "source_scope",
    "dimensions_json",
    "source_fact_authority",
    "direction_authority",
    "veto_authority",
]


class UnifiedPitShadowPanelV1Error(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise UnifiedPitShadowPanelV1Error(f"path escapes repository: {relative}")
    return path


def _source(protocol: dict, role: str) -> Path:
    return _rooted(next(
        row["path"] for row in protocol["locked_inputs"]
        if row["role"] == role
    ))


def _read_csv(path: Path, delimiter: str = ",") -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def _verify(protocol: dict) -> None:
    for item in protocol["locked_inputs"]:
        if _sha256(_rooted(item["path"])) != item["sha256"]:
            raise UnifiedPitShadowPanelV1Error(
                f"locked input changed: {item['path']}"
            )
    form4_gate = json.loads(
        _source(protocol, "FORM4_CENSUS_GATE").read_text(encoding="utf-8")
    )
    if not form4_gate["passed"]:
        raise UnifiedPitShadowPanelV1Error("Form 4 census gate is not passed")
    guidance = json.loads(
        _source(protocol, "GUIDANCE_BINDING_REPORT").read_text(
            encoding="utf-8"
        )
    )
    if not guidance["source_fact_authority_only"]:
        raise UnifiedPitShadowPanelV1Error(
            "guidance bindings exceeded source-fact authority"
        )
    finra = json.loads(
        _source(protocol, "FINRA_INCREMENTAL_REPORT").read_text(
            encoding="utf-8"
        )
    )
    if not finra["all_baseline_hashes_verified"]:
        raise UnifiedPitShadowPanelV1Error("FINRA raw integrity is incomplete")


def _canonical(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", symbol.upper())


def _as_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise UnifiedPitShadowPanelV1Error(f"timezone missing: {value}")
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _next_new_york_midnight(day: str) -> str:
    next_day = date.fromisoformat(day) + timedelta(days=1)
    return _iso_utc(datetime.combine(next_day, time.min, NEW_YORK))


def _finra_available(entry: dict) -> datetime:
    value = entry["safe_availability_time"]
    if not value.endswith("[America/New_York]"):
        raise UnifiedPitShadowPanelV1Error(
            "unexpected FINRA availability timezone"
        )
    local_value = value.removesuffix("[America/New_York]")
    naive = datetime.fromisoformat(local_value)
    if naive.tzinfo is not None:
        raise UnifiedPitShadowPanelV1Error(
            "FINRA local availability unexpectedly contains an offset"
        )
    return naive.replace(tzinfo=NEW_YORK).astimezone(timezone.utc)


def _panel_id(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _base_row(
    *,
    ticker: str,
    cik: str,
    observed_at: str,
    available_at: str,
    source: str,
    feature_name: str,
    feature_value: str,
    unit: str,
    source_record_id: str,
    source_url: str,
    source_sha256: str,
    revision_status: str,
    identity_confidence: str,
    source_scope: str,
    dimensions: dict,
) -> dict:
    values = [
        ticker,
        cik,
        available_at,
        source,
        feature_name,
        source_record_id,
    ]
    return {
        "panel_row_id": _panel_id(values),
        "ticker": ticker,
        "cik": cik,
        "observed_at": observed_at,
        "available_at": available_at,
        "source": source,
        "feature_name": feature_name,
        "feature_value": feature_value,
        "unit": unit,
        "source_record_id": source_record_id,
        "source_url": source_url,
        "source_sha256": source_sha256,
        "revision_status": revision_status,
        "identity_confidence": identity_confidence,
        "source_scope": source_scope,
        "dimensions_json": json.dumps(
            dimensions, sort_keys=True, separators=(",", ":")
        ),
        "source_fact_authority": "True",
        "direction_authority": "False",
        "veto_authority": "False",
    }


def _current_universe(protocol: dict) -> tuple[dict[str, str], dict[str, list[str]]]:
    rows = _read_csv(_source(protocol, "CURRENT_REFERENCE_UNIVERSE"))
    ticker_to_cik = {
        row["ticker"]: row["cik"].zfill(10) for row in rows
    }
    cik_to_tickers: dict[str, list[str]] = defaultdict(list)
    for ticker, cik in ticker_to_cik.items():
        cik_to_tickers[cik].append(ticker)
    return ticker_to_cik, {
        cik: sorted(tickers) for cik, tickers in cik_to_tickers.items()
    }


def _identity_intervals(protocol: dict) -> dict[str, list[dict]]:
    rows = _read_csv(_source(protocol, "SEC_IDENTITY_INTERVALS"))
    result: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["status"] != "TIME_VALID_CIK_VERIFIED":
            continue
        result[row["canonical_symbol"]].append({
            "cik": row["cik"].zfill(10),
            "valid_from": row["valid_from"],
            "valid_to": row["valid_to"],
        })
    return result


def _finra_rows(protocol: dict, cutoff: datetime) -> tuple[list[dict], dict]:
    manifest = json.loads(
        _source(protocol, "FINRA_INCREMENTAL_MANIFEST").read_text(
            encoding="utf-8"
        )
    )
    entries_by_date: dict[str, list[dict]] = defaultdict(list)
    for entry in manifest["entries"]:
        available = _finra_available(entry)
        if available <= cutoff:
            entries_by_date[entry["settlement_date"]].append(entry)
    if not entries_by_date:
        return [], {"latest_settlement_date": None, "source_records": 0}
    latest_day = max(entries_by_date)
    entry = max(
        entries_by_date[latest_day],
        key=lambda row: (row["retrieved_at_utc"], row["sha256"]),
    )
    raw = _rooted(entry["raw_path"])
    if _sha256(raw) != entry["sha256"]:
        raise UnifiedPitShadowPanelV1Error("latest FINRA raw hash mismatch")
    ticker_to_cik, _ = _current_universe(protocol)
    identity_protocol = json.loads(
        _source(protocol, "SEC_IDENTITY_PROTOCOL").read_text(encoding="utf-8")
    )
    aliases = identity_protocol["finra_identity_aliases"]
    targets: dict[str, list[tuple[str, re.Pattern | None]]] = defaultdict(list)
    for ticker in ticker_to_cik:
        identity = aliases.get(ticker)
        symbols = identity["symbols"] if identity else [ticker]
        pattern = (
            re.compile(identity["issue_name_regex"], re.IGNORECASE)
            if identity and identity.get("issue_name_regex")
            else None
        )
        for symbol in symbols:
            targets[_canonical(symbol)].append((ticker, pattern))
    intervals = _identity_intervals(protocol)
    metrics = {
        "currentShortPositionQuantity": ("finra_short_position", "SHARES"),
        "previousShortPositionQuantity": (
            "finra_previous_short_position",
            "SHARES",
        ),
        "averageDailyVolumeQuantity": (
            "finra_average_daily_volume",
            "SHARES",
        ),
        "daysToCoverQuantity": ("finra_days_to_cover", "DAYS"),
        "changePercent": ("finra_change_percent", "PERCENT"),
        "changePreviousNumber": (
            "finra_change_previous_quantity",
            "SHARES",
        ),
    }
    rows = []
    matched_source_records = 0
    matched_tickers = set()
    interval_linked_tickers = set()
    current_snapshot_linked_tickers = set()
    with raw.open(newline="", encoding="utf-8-sig") as handle:
        for source in csv.DictReader(handle, delimiter="|"):
            canonical = _canonical(source["symbolCode"])
            target_matches = [
                ticker for ticker, pattern in targets.get(canonical, [])
                if pattern is None or pattern.search(source["issueName"])
            ]
            if len(set(target_matches)) != 1:
                continue
            ticker = target_matches[0]
            matched_ciks = {
                interval["cik"]
                for interval in intervals.get(canonical, [])
                if interval["valid_from"] <= latest_day <= interval["valid_to"]
            }
            if len(matched_ciks) == 1:
                cik = next(iter(matched_ciks))
                identity_confidence = "TIME_VALID_SEC_CIK_EXACT"
                interval_linked_tickers.add(ticker)
            elif not matched_ciks:
                cik = ticker_to_cik[ticker]
                identity_confidence = "CURRENT_REFERENCE_SNAPSHOT_CIK"
                current_snapshot_linked_tickers.add(ticker)
            else:
                continue
            source_record_id = _panel_id([
                entry["sha256"],
                latest_day,
                source["symbolCode"],
                source["issueName"],
                source["marketClassCode"],
            ])
            matched_source_records += 1
            matched_tickers.add(ticker)
            for column, (feature, unit) in metrics.items():
                value = source[column].strip()
                if not value:
                    continue
                rows.append(_base_row(
                    ticker=ticker,
                    cik=cik,
                    observed_at=f"{latest_day}T00:00:00Z",
                    available_at=_iso_utc(_finra_available(entry)),
                    source="FINRA_SHORT_INTEREST",
                    feature_name=feature,
                    feature_value=value,
                    unit=unit,
                    source_record_id=source_record_id,
                    source_url=entry["source_url"],
                    source_sha256=entry["sha256"],
                    revision_status=(
                        "REVISED_ROW"
                        if source["revisionFlag"].strip()
                        else "AS_PUBLISHED"
                    ),
                    identity_confidence=identity_confidence,
                    source_scope="LATEST_AVAILABLE_SETTLEMENT_SNAPSHOT",
                    dimensions={
                        "issue_name": source["issueName"],
                        "market_class": source["marketClassCode"],
                        "reported_symbol": source["symbolCode"],
                        "settlement_date": latest_day,
                    },
                ))
    return rows, {
        "latest_settlement_date": latest_day,
        "source_records": matched_source_records,
        "current_reference_ticker_count": len(ticker_to_cik),
        "current_reference_tickers_observed": len(matched_tickers),
        "current_reference_ticker_coverage": (
            len(matched_tickers) / len(ticker_to_cik)
        ),
        "time_valid_interval_linked_tickers": len(interval_linked_tickers),
        "current_snapshot_reference_linked_tickers": len(
            current_snapshot_linked_tickers
        ),
        "current_reference_identity_used_for_historical_backfill": False,
    }


def _form4_rows(protocol: dict, cutoff: datetime) -> tuple[list[dict], dict]:
    source_path = _source(protocol, "FORM4_PURCHASE_FACTS")
    source_hash = _sha256(source_path)
    _, cik_to_tickers = _current_universe(protocol)
    eligible = []
    for row in _read_csv(source_path):
        cik = row["issuerCik"].zfill(10)
        if cik not in cik_to_tickers:
            continue
        available = _as_utc(_next_new_york_midnight(row["filingDate"]))
        if available <= cutoff:
            eligible.append((row, cik, available))
    latest_by_cik: dict[str, str] = {}
    for row, cik, _ in eligible:
        latest_by_cik[cik] = max(
            latest_by_cik.get(cik, ""),
            row["filingDate"],
        )
    metrics = {
        "transactionShares": ("form4_purchase_shares", "SHARES"),
        "transactionPricePerShare": (
            "form4_purchase_price_per_share",
            "USD_PER_SHARE",
        ),
        "sharesOwnedFollowingTransaction": (
            "form4_post_transaction_holdings",
            "SHARES",
        ),
    }
    rows = []
    source_records = 0
    for source, cik, available in eligible:
        if source["filingDate"] != latest_by_cik[cik]:
            continue
        source_records += 1
        ticker = "|".join(cik_to_tickers[cik])
        confidence = (
            "CIK_EXACT_CURRENT_REFERENCE"
            if len(cik_to_tickers[cik]) == 1
            else "CIK_EXACT_MULTI_CLASS_TICKER_AMBIGUOUS"
        )
        for column, (feature, unit) in metrics.items():
            value = source[column].strip()
            if not value:
                continue
            rows.append(_base_row(
                ticker=ticker,
                cik=cik,
                observed_at=f"{source['transactionDate']}T00:00:00Z",
                available_at=_iso_utc(available),
                source="SEC_FORM4_CODE_P",
                feature_name=feature,
                feature_value=value,
                unit=unit,
                source_record_id=source["atomicTransactionId"],
                source_url="",
                source_sha256=source_hash,
                revision_status="AS_FILED_BULK_FACT",
                identity_confidence=confidence,
                source_scope="LATEST_FILING_DATE_PER_CURRENT_REFERENCE_CIK",
                dimensions={
                    "accession_number": source["accessionNumber"],
                    "direct_or_indirect": source[
                        "directOrIndirectOwnership"
                    ],
                    "filing_date": source["filingDate"],
                    "reporting_owner_cik": source["reportingOwnerCik"],
                    "routine_status": source["routineStatus"],
                    "transaction_code": source["transactionCode"],
                },
            ))
    return rows, {
        "current_reference_ciks_with_purchase_fact": len(latest_by_cik),
        "source_records": source_records,
    }


def _guidance_rows(protocol: dict, cutoff: datetime) -> tuple[list[dict], dict]:
    candidates = []
    for row in _read_csv(_source(protocol, "GUIDANCE_SOURCE_REVIEWED_FACTS")):
        available = _as_utc(row["accepted_at"])
        if (
            available <= cutoff
            and row["atomic_binding_authority"]
            == "SOURCE_REVIEWED_FACT_ONLY"
            and row["direction_authority"] == "False"
            and row["veto_authority"] == "False"
        ):
            candidates.append((row, available))
    identity_fields = (
        "cik",
        "metric",
        "accounting_basis",
        "metric_subtype",
        "unit",
    )
    latest: dict[tuple[str, ...], datetime] = {}
    for row, available in candidates:
        key = tuple(row[field] for field in identity_fields)
        latest[key] = max(latest.get(key, available), available)
    metrics = {
        "lower_bound": "guidance_lower_bound",
        "upper_bound": "guidance_upper_bound",
        "midpoint": "guidance_midpoint",
    }
    rows = []
    source_records = set()
    for source, available in candidates:
        key = tuple(source[field] for field in identity_fields)
        if available != latest[key]:
            continue
        source_records.add(source["binding_id"])
        for column, feature in metrics.items():
            value = source[column].strip()
            if not value:
                continue
            rows.append(_base_row(
                ticker=source["ticker"],
                cik=source["cik"].zfill(10),
                observed_at=_iso_utc(available),
                available_at=_iso_utc(available),
                source="SEC_8K_GUIDANCE",
                feature_name=feature,
                feature_value=value,
                unit=source["unit"],
                source_record_id=source["binding_id"],
                source_url=source["source_url"],
                source_sha256=source["source_sha256"],
                revision_status="SOURCE_REVIEWED_AS_FILED_FACT",
                identity_confidence="SOURCE_REVIEWED_CIK_TICKER",
                source_scope="LATEST_ACCEPTED_FACT_PER_METRIC_IDENTITY",
                dimensions={
                    "accession_number": source["accession_number"],
                    "accounting_basis": source["accounting_basis"],
                    "fiscal_period": source["fiscal_period"],
                    "metric": source["metric"],
                    "metric_subtype": source["metric_subtype"],
                    "pair_eligible": source["pair_eligible"],
                },
            ))
    return rows, {
        "latest_metric_identities": len(latest),
        "source_records": len(source_records),
    }


def _atomic_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def build(
    protocol_path: Path = PROTOCOL,
    panel_path: Path = PANEL,
    report_path: Path = REPORT,
) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "LOCKED_BEFORE_PANEL_BUILD":
        raise UnifiedPitShadowPanelV1Error("panel protocol is not locked")
    _verify(protocol)
    cutoff = _as_utc(protocol["panel_cutoff_utc"])
    finra, finra_summary = _finra_rows(protocol, cutoff)
    form4, form4_summary = _form4_rows(protocol, cutoff)
    guidance, guidance_summary = _guidance_rows(protocol, cutoff)
    minimum_finra_coverage = protocol["snapshot_policy"][
        "minimum_finra_current_reference_ticker_coverage"
    ]
    finra_gate = (
        finra_summary["current_reference_ticker_coverage"]
        >= minimum_finra_coverage
    )
    if not finra_gate:
        raise UnifiedPitShadowPanelV1Error(
            "latest FINRA current-reference coverage below locked minimum"
        )
    rows = sorted(
        [*finra, *form4, *guidance],
        key=lambda row: (
            row["available_at"],
            row["source"],
            row["ticker"],
            row["source_record_id"],
            row["feature_name"],
        ),
    )
    ids = [row["panel_row_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise UnifiedPitShadowPanelV1Error("duplicate panel row id")
    if any(_as_utc(row["available_at"]) > cutoff for row in rows):
        raise UnifiedPitShadowPanelV1Error("post-cutoff fact escaped panel")
    _atomic_csv(panel_path, rows)
    source_counts = {
        source: sum(row["source"] == source for row in rows)
        for source in sorted({row["source"] for row in rows})
    }
    report = {
        "report_version": "UNIFIED_PIT_SHADOW_PANEL_V1",
        "status": "HASH_LOCKED_PROSPECTIVE_SEED_SNAPSHOT_READY",
        "panel_cutoff_utc": _iso_utc(cutoff),
        "panel_role": protocol["snapshot_policy"]["role"],
        "row_count": len(rows),
        "source_counts": source_counts,
        "source_summaries": {
            "FINRA_SHORT_INTEREST": finra_summary,
            "SEC_FORM4_CODE_P": form4_summary,
            "SEC_8K_GUIDANCE": guidance_summary,
        },
        "finra_current_snapshot_coverage_gate": {
            "minimum": minimum_finra_coverage,
            "actual": finra_summary["current_reference_ticker_coverage"],
            "passed": finra_gate,
            "historical_current_reference_backfill_performed": False,
        },
        "distinct_tickers": len({row["ticker"] for row in rows}),
        "distinct_ciks": len({row["cik"] for row in rows}),
        "panel_path": (
            panel_path.resolve().relative_to(ROOT.resolve()).as_posix()
            if panel_path.resolve().is_relative_to(ROOT.resolve())
            else panel_path.resolve().as_posix()
        ),
        "panel_sha256": _sha256(panel_path),
        "protocol_sha256": _sha256(protocol_path),
        "full_source_history_duplicated": False,
        "price_or_return_outcomes_opened": False,
        "direction_labels_created": False,
        "direction_hypothesis_preregistered": False,
        "veto_authority_granted": False,
        "herd_formula_change_allowed": False,
        "primary_long_horizon_oos_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_priority": "AUDIT_RECOVERY_LINEAGE_AND_RUN_FULL_REGRESSION",
    }
    _atomic_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--panel", type=Path, default=PANEL)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    print(json.dumps(
        build(args.protocol, args.panel, args.report),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
