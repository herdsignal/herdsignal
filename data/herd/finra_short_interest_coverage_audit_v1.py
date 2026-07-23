"""FINRA census의 원본 무결성·ticker 관측·PIT CIK 연결 coverage만 감사한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_name("finra_short_interest_immutable_census_v1.json")
MANIFEST = Path(__file__).with_name(
    "finra_short_interest_immutable_census_v1_manifest.json"
)
REPORT = ROOT / "data/reports/finra_short_interest_coverage_audit_v1.json"
DETAIL = ROOT / "data/reports/finra_short_interest_ticker_coverage_v1.csv"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _root_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"path escapes repository: {relative}")
    return path


def _canonical_symbol(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", symbol.upper())


def _observation_symbol(
    research_ticker: str,
    overrides: dict[str, str] | None,
) -> str:
    return (overrides or {}).get(research_ticker, research_ticker)


def _read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _cohorts(protocol: dict) -> dict[str, dict[str, str]]:
    locked = {
        Path(item["path"]).name: item
        for item in protocol["identifier_policy"]["locked_inputs"]
    }
    business_item = locked["business_state_features_v2.csv"]
    independent_item = locked["independent_universe_v1.csv"]
    business_rows = _read_rows(_root_path(business_item["path"]))
    independent_rows = _read_rows(_root_path(independent_item["path"]))
    original = {row["ticker"]: row["cik"].zfill(10) for row in business_rows}
    independent = {
        row["ticker"]: row["cik"].zfill(10)
        for row in independent_rows
        if row["eligible"] == "True"
    }
    current = {row["ticker"]: row["cik"].zfill(10) for row in independent_rows}
    return {
        "ORIGINAL_RESEARCH_51": original,
        "INDEPENDENT_ELIGIBLE_388": independent,
        "CURRENT_SP500_REFERENCE_503": current,
    }


def _verified_intervals(protocol: dict) -> list[dict]:
    intervals = []
    locked = {
        Path(item["path"]).name: item
        for item in protocol["identifier_policy"]["locked_inputs"]
    }
    price_periods = locked["price_universe_cik_periods.csv"]
    for row in _read_rows(_root_path(price_periods["path"])):
        if not row["status"].startswith(("VERIFIED_", "OUTSIDE_CURRENT_")):
            continue
        intervals.append({
            "ticker": row["ticker"],
            "canonical_symbol": _canonical_symbol(row["ticker"]),
            "cik": row["cik"].zfill(10),
            "valid_from": row["valid_from"],
            "valid_to": row["valid_to"] or None,
            "source": "PRICE_UNIVERSE_CIK_PERIODS",
        })
    alias_ledger = locked["ticker_alias_ledger.csv"]
    for row in _read_rows(_root_path(alias_ledger["path"])):
        if row["verification_status"] != "VERIFIED":
            continue
        intervals.append({
            "ticker": row["ticker"],
            "canonical_symbol": _canonical_symbol(row["ticker"]),
            "cik": row["cik"].zfill(10),
            "valid_from": row["valid_from"],
            "valid_to": row["valid_to"] or None,
            "source": "VERIFIED_TICKER_ALIAS_LEDGER",
        })
    return intervals


def _date_in_interval(day: str, interval: dict) -> bool:
    return (
        day >= interval["valid_from"]
        and (interval["valid_to"] is None or day <= interval["valid_to"])
    )


def _verify_inputs(protocol_path: Path, protocol: dict, manifest: dict) -> dict:
    if _sha256(protocol_path) != manifest["protocol_sha256"]:
        raise ValueError("tracked FINRA manifest protocol hash mismatch")
    locked = [
        protocol["prerequisite"],
        *protocol["identifier_policy"]["locked_inputs"],
    ]
    for item in locked:
        if _sha256(_root_path(item["path"])) != item["sha256"]:
            raise ValueError(f"locked FINRA audit input changed: {item['path']}")
    missing, bad_hash, bad_receipt = [], [], []
    for entry in manifest["entries"]:
        raw = _root_path(entry["raw_path"])
        receipt = _root_path(entry["receipt_path"])
        if not raw.is_file():
            missing.append(entry["raw_path"])
        elif _sha256(raw) != entry["sha256"]:
            bad_hash.append(entry["raw_path"])
        if not receipt.is_file():
            bad_receipt.append(entry["receipt_path"])
        else:
            receipt_data = json.loads(receipt.read_text(encoding="utf-8"))
            if (
                receipt_data.get("sha256") != entry["sha256"]
                or receipt_data.get("settlement_date") != entry["settlement_date"]
            ):
                bad_receipt.append(entry["receipt_path"])
    return {
        "files_expected": manifest["file_count"],
        "files_missing": len(missing),
        "files_with_bad_hash": len(bad_hash),
        "receipts_missing": len(bad_receipt),
        "all_raw_hashes_verified": not missing and not bad_hash and not bad_receipt,
    }


def audit(
    protocol_path: Path = PROTOCOL,
    manifest_path: Path = MANIFEST,
    report_path: Path = REPORT,
    detail_path: Path = DETAIL,
    *,
    intervals_override: list[dict] | None = None,
    strict_reference_cik: bool = True,
    report_version: str = "FINRA_SHORT_INTEREST_COVERAGE_AUDIT_V1",
    next_priority: str = (
        "EXTEND_VERIFIED_SEC_TICKER_INTERVAL_LEDGER_"
        "BEFORE_ANY_SHORT_INTEREST_HYPOTHESIS"
    ),
    cohort_symbol_overrides: dict[str, str] | None = None,
    cohort_identity_aliases: dict[str, dict] | None = None,
) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    integrity = _verify_inputs(protocol_path, protocol, manifest)
    cohorts = _cohorts(protocol)
    intervals = (
        list(intervals_override)
        if intervals_override is not None
        else _verified_intervals(protocol)
    )
    intervals_by_symbol: dict[str, list[dict]] = defaultdict(list)
    for interval in intervals:
        intervals_by_symbol[interval["canonical_symbol"]].append(interval)

    dates = [entry["settlement_date"] for entry in manifest["entries"]]
    expected_date_set = set(dates)
    observed_dates: dict[str, set[str]] = defaultdict(set)
    observed_issue_names: dict[tuple[str, str], set[str]] = defaultdict(set)
    symbols_by_canonical: dict[str, set[str]] = defaultdict(set)
    duplicate_symbol_rows = 0
    for entry in manifest["entries"]:
        seen: set[str] = set()
        raw = _root_path(entry["raw_path"])
        with raw.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, delimiter="|")
            if reader.fieldnames != protocol["required_columns"]:
                raise ValueError(f"schema drift after collection: {raw}")
            for row in reader:
                symbol = row["symbolCode"].strip()
                canonical = _canonical_symbol(symbol)
                if canonical in seen:
                    duplicate_symbol_rows += 1
                seen.add(canonical)
                observed_dates[canonical].add(entry["settlement_date"])
                observed_issue_names[
                    (canonical, entry["settlement_date"])
                ].add(row["issueName"].strip())
                symbols_by_canonical[canonical].add(symbol)

    details: list[dict] = []
    cohort_reports = []
    required_pit_link_coverage = 0.95
    for cohort_name, members in cohorts.items():
        canonical_owner: dict[str, list[str]] = defaultdict(list)
        for ticker in members:
            identity = (cohort_identity_aliases or {}).get(ticker)
            observed_tickers = (
                identity["symbols"]
                if identity
                else [_observation_symbol(ticker, cohort_symbol_overrides)]
            )
            for observed_ticker in observed_tickers:
                canonical_owner[_canonical_symbol(observed_ticker)].append(ticker)
        ambiguous_canonical = {
            key: tickers for key, tickers in canonical_owner.items()
            if len(tickers) > 1
        }
        total_opportunities = len(members) * len(dates)
        observed_opportunities = 0
        verified_cik_opportunities = 0
        tickers_ever_observed = 0
        tickers_with_any_verified_cik = 0
        delayed_or_partial_tickers = []
        never_observed_tickers = []
        for ticker, cik in sorted(members.items()):
            identity = (cohort_identity_aliases or {}).get(ticker)
            observed_tickers = (
                identity["symbols"]
                if identity
                else [_observation_symbol(ticker, cohort_symbol_overrides)]
            )
            canonical_symbols = [
                _canonical_symbol(symbol) for symbol in observed_tickers
            ]
            issue_name_regex = (
                re.compile(identity["issue_name_regex"], re.IGNORECASE)
                if identity and identity.get("issue_name_regex")
                else None
            )
            ticker_dates_by_symbol: dict[str, set[str]] = {}
            for canonical in canonical_symbols:
                dates_for_symbol = set(observed_dates.get(canonical, set()))
                if canonical in ambiguous_canonical:
                    dates_for_symbol = set()
                if issue_name_regex:
                    dates_for_symbol = {
                        day for day in dates_for_symbol
                        if any(
                            issue_name_regex.search(name)
                            for name in observed_issue_names.get(
                                (canonical, day), set()
                            )
                        )
                    }
                ticker_dates_by_symbol[canonical] = dates_for_symbol
            ticker_dates = set().union(*ticker_dates_by_symbol.values())
            observed_count = len(ticker_dates & expected_date_set)
            observed_opportunities += observed_count
            if observed_count:
                tickers_ever_observed += 1
            else:
                never_observed_tickers.append(ticker)
            sources = set()
            matched_ciks_by_date: dict[str, set[str]] = defaultdict(set)
            matched_sources_by_date: dict[str, set[str]] = defaultdict(set)
            for canonical, symbol_dates in ticker_dates_by_symbol.items():
                for interval in intervals_by_symbol.get(canonical, []):
                    if strict_reference_cik and interval["cik"] != cik:
                        continue
                    if strict_reference_cik:
                        # V1의 고정 산출물은 날짜 밖 후보 source도 표시했다.
                        # 역사 감사 파일의 byte-level 재현성을 위해 유지한다.
                        sources.add(interval["source"])
                    for day in symbol_dates:
                        if not _date_in_interval(day, interval):
                            continue
                        matched_ciks_by_date[day].add(interval["cik"])
                        matched_sources_by_date[day].add(interval["source"])
            verified_dates = {
                day for day, matched_ciks in matched_ciks_by_date.items()
                if len(matched_ciks) == 1
            }
            for day in verified_dates:
                sources.update(matched_sources_by_date[day])
            verified_count = len(verified_dates)
            verified_cik_opportunities += verified_count
            if verified_count:
                tickers_with_any_verified_cik += 1
            sorted_observed = sorted(ticker_dates)
            if observed_count and observed_count < len(dates):
                delayed_or_partial_tickers.append(ticker)
            detail = {
                "cohort": cohort_name,
                "ticker": ticker,
                "cik": cik,
                "finra_symbols_observed": "|".join(
                    sorted({
                        symbol
                        for canonical in canonical_symbols
                        for symbol in symbols_by_canonical.get(canonical, set())
                    })
                ),
                "first_observed_settlement_date": (
                    sorted_observed[0] if sorted_observed else ""
                ),
                "last_observed_settlement_date": (
                    sorted_observed[-1] if sorted_observed else ""
                ),
                "observed_settlement_dates": observed_count,
                "expected_settlement_dates": len(dates),
                "symbol_date_coverage": observed_count / len(dates),
                "time_valid_cik_linked_dates": verified_count,
                "time_valid_cik_link_coverage": verified_count / len(dates),
                "link_sources": "|".join(sorted(sources)),
                "link_status": (
                    "TIME_VALID_CIK_VERIFIED"
                    if verified_count == observed_count and observed_count > 0
                    else "PARTIAL_TIME_VALID_CIK"
                    if verified_count > 0
                    else "CURRENT_SYMBOL_OBSERVED_PIT_CIK_UNVERIFIED"
                    if observed_count > 0
                    else "SYMBOL_NOT_OBSERVED"
                ),
            }
            if cohort_symbol_overrides or cohort_identity_aliases:
                detail["observation_ticker"] = "|".join(observed_tickers)
                detail["cohort_symbol_overridden"] = (
                    observed_tickers != [ticker]
                )
                detail["identity_issue_name_regex"] = (
                    identity.get("issue_name_regex", "") if identity else ""
                )
            details.append(detail)
        symbol_coverage = (
            observed_opportunities / total_opportunities if total_opportunities else 0.0
        )
        pit_coverage = (
            verified_cik_opportunities / total_opportunities
            if total_opportunities else 0.0
        )
        cohort_reports.append({
            "cohort": cohort_name,
            "ticker_count": len(members),
            "settlement_date_count": len(dates),
            "ticker_date_opportunities": total_opportunities,
            "ticker_date_observed": observed_opportunities,
            "ticker_date_symbol_coverage": symbol_coverage,
            "tickers_ever_observed": tickers_ever_observed,
            "ticker_ever_observed_coverage": tickers_ever_observed / len(members),
            "time_valid_cik_linked_opportunities": verified_cik_opportunities,
            "time_valid_cik_link_coverage": pit_coverage,
            "tickers_with_any_time_valid_cik_link": tickers_with_any_verified_cik,
            "required_time_valid_cik_link_coverage": required_pit_link_coverage,
            "pit_identifier_gate_passed": pit_coverage >= required_pit_link_coverage,
            "never_observed_tickers": never_observed_tickers,
            "partial_observation_tickers": delayed_or_partial_tickers,
            "ambiguous_canonical_symbols": ambiguous_canonical,
        })

    detail_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(details[0])
    with detail_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(details)

    pit_ready = all(
        item["pit_identifier_gate_passed"]
        for item in cohort_reports
        if item["cohort"] != "CURRENT_SP500_REFERENCE_503"
    )
    revised_files = sum(entry["revision_flag_rows"] > 0 for entry in manifest["entries"])
    last_modified_present = 0
    last_modified_after_publication = 0
    for entry in manifest["entries"]:
        value = entry["http"]["last_modified"]
        if not value:
            continue
        last_modified_present += 1
        modified = parsedate_to_datetime(value).date()
        publication = date.fromisoformat(entry["derived_publication_date"])
        last_modified_after_publication += int(modified > publication)
    report = {
        "report_version": report_version,
        "status": (
            "HASH_LOCKED_AND_PIT_IDENTIFIER_READY"
            if integrity["all_raw_hashes_verified"] and pit_ready
            else "HASH_LOCKED_PIT_IDENTIFIER_INCOMPLETE"
        ),
        "protocol_sha256": _sha256(protocol_path),
        "manifest_sha256": _sha256(manifest_path),
        "research_tier": protocol["research_tier"],
        "allowed_research_role": protocol["authority"]["allowed_research_role"],
        "corpus": {
            "file_count": manifest["file_count"],
            "settlement_date_count": manifest["settlement_date_count"],
            "first_settlement_date": manifest["first_settlement_date"],
            "last_settlement_date": manifest["last_settlement_date"],
            "total_bytes": manifest["total_bytes"],
            "total_rows": manifest["total_rows"],
            "revision_flag_rows": manifest["revision_flag_rows"],
            "files_with_revision_flag": revised_files,
            "duplicate_canonical_symbol_rows": duplicate_symbol_rows,
            "local_prior_versions_recovered": len(
                manifest["settlement_dates_with_multiple_local_versions"]
            ),
            "source_prior_versions_recoverable": False,
        },
        "integrity": integrity,
        "publication_time_audit": {
            "settlement_date_used_as_publication_date": False,
            "derived_publication_date_count": manifest["file_count"],
            "derivation": "SEVENTH_FINRA_BUSINESS_DAY_AFTER_SETTLEMENT",
            "safe_availability": "NEXT_CALENDAR_DAY_00_00_AMERICA_NEW_YORK",
            "exact_intraday_publication_time_available": False,
            "http_last_modified_present_files": last_modified_present,
            "http_last_modified_after_derived_publication_files": (
                last_modified_after_publication
            ),
            "http_last_modified_interpretation": "REVISION_METADATA_ONLY",
        },
        "identifier_ledger": {
            "verified_interval_count": len(intervals),
            "verified_canonical_symbol_count": len(intervals_by_symbol),
            "current_symbol_presence_is_not_pit_cik_proof": True,
            "current_ticker_backfill_performed": False,
            **({
                "cohort_symbol_overrides": cohort_symbol_overrides,
                "cohort_symbol_override_is_identity_correction": True,
            } if cohort_symbol_overrides else {}),
            **({
                "cohort_identity_aliases": cohort_identity_aliases,
                "cohort_identity_aliases_require_issue_name_match": True,
            } if cohort_identity_aliases else {}),
        },
        "cohorts": cohort_reports,
        "detail_path": detail_path.relative_to(ROOT).as_posix(),
        "detail_sha256": _sha256(detail_path),
        "coverage_does_not_authorize_hypothesis": True,
        "new_direction_hypothesis_preregistered": False,
        "price_outcomes_opened": False,
        "herd_formula_change_allowed": False,
        "blind_holdout_access": False,
        "operational_action_authority": False,
        "operational_action_ratio": 0.0,
        "decision": (
            "ALLOW_PROSPECTIVE_SHADOW_CORPUS_MAINTENANCE_ONLY"
            if integrity["all_raw_hashes_verified"]
            else "BLOCK_CORPUS_USE"
        ),
        "next_priority": next_priority,
    }
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--detail", type=Path, default=DETAIL)
    args = parser.parse_args()
    result = audit(args.protocol, args.manifest, args.report, args.detail)
    print(json.dumps({
        "status": result["status"],
        "decision": result["decision"],
        "cohorts": result["cohorts"],
        "price_outcomes_opened": result["price_outcomes_opened"],
        "new_direction_hypothesis_preregistered": (
            result["new_direction_hypothesis_preregistered"]
        ),
        "next_priority": result["next_priority"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
