"""SEC 13F PIT 보유를 분기별 느린 기관 군중 맥락으로 변환한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from herd.sec_13f_pit_holdings_v1 import DATABASE, next_market_session
from herd.sec_13f_security_ledger_v1 import ROOT, sha256


CONTRACT = ROOT / "data/herd/sec_13f_slow_context_v1.json"
SECURITY_INTERVALS = ROOT / "data/reports/sec_13f_security_intervals_v1.csv"
FEATURES = ROOT / "data/reports/sec_13f_slow_context_v1.csv"
COVERAGE = ROOT / "data/reports/sec_13f_slow_context_coverage_v1.csv"
REPORT = ROOT / "data/reports/sec_13f_slow_context_v1.json"
FORMAT_VERSION = "SEC_13F_SLOW_CONTEXT_V1"


class Sec13fSlowContextError(RuntimeError):
    """13F 느린 맥락의 PIT·입력·품질 계약 위반 시 발생한다."""


def _is_quarter_end(day: date) -> bool:
    return (day.month, day.day) in {
        (3, 31),
        (6, 30),
        (9, 30),
        (12, 31),
    }


def _first_market_session_on_or_after(day: date) -> date:
    return next_market_session(day - timedelta(days=1))


def common_availability_date(report_period: date, lag_days: int = 45) -> date:
    deadline = _first_market_session_on_or_after(
        report_period + timedelta(days=lag_days)
    )
    return next_market_session(deadline)


def _verify_pinned_inputs(contract: dict[str, Any]) -> dict[str, Any]:
    loaded = {}
    for item in contract["pinned_inputs"]:
        path = ROOT / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise Sec13fSlowContextError(
                f"pinned 13F input changed: {item['path']}"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") != item["required_status"]:
            raise Sec13fSlowContextError(
                f"pinned 13F input gate failed: {item['path']}"
            )
        loaded[item["path"]] = payload
    return loaded


def _verify_database(
    database_path: Path,
    pit_report: dict[str, Any],
    *,
    verify_hash: bool,
) -> None:
    expected = pit_report["database"]
    if not database_path.is_file():
        raise Sec13fSlowContextError("13F PIT database is missing")
    if database_path.stat().st_size != expected["bytes"]:
        raise Sec13fSlowContextError("13F PIT database size changed")
    if verify_hash and sha256(database_path) != expected["sha256"]:
        raise Sec13fSlowContextError("13F PIT database hash changed")


def _load_active_intervals(
    path: Path,
) -> dict[str, list[tuple[date, date]]]:
    intervals: dict[str, list[tuple[date, date]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            intervals[row["ticker"]].append(
                (
                    date.fromisoformat(row["valid_from_report_period"]),
                    date.fromisoformat(row["valid_to_report_period"]),
                )
            )
    if len(intervals) < 300:
        raise Sec13fSlowContextError("13F security interval universe is too small")
    return intervals


def _active_tickers(
    intervals: dict[str, list[tuple[date, date]]],
    report_period: date,
) -> set[str]:
    return {
        ticker
        for ticker, ranges in intervals.items()
        if any(start <= report_period <= end for start, end in ranges)
    }


def _valid_report_periods(
    connection: sqlite3.Connection,
    contract: dict[str, Any],
) -> tuple[list[date], int]:
    first = date.fromisoformat(
        contract["history"]["first_valid_report_period"]
    )
    periods = [
        date.fromisoformat(row[0])
        for row in connection.execute(
            "SELECT DISTINCT report_period FROM filings ORDER BY report_period"
        )
    ]
    legacy = sum(period < first for period in periods)
    selected = [period for period in periods if period >= first]
    non_quarter = [period for period in selected if not _is_quarter_end(period)]
    if non_quarter:
        raise Sec13fSlowContextError(
            f"non-quarter report periods found: {non_quarter[:3]}"
        )
    expected_last = date.fromisoformat(
        contract["history"]["expected_last_report_period"]
    )
    if not selected or selected[-1] != expected_last:
        raise Sec13fSlowContextError("unexpected final 13F report period")
    return selected, legacy


def _period_positions(
    connection: sqlite3.Connection,
    report_period: date,
    availability: date,
) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    parameters = (report_period.isoformat(), availability.isoformat())
    rows = connection.execute(
        """
        WITH ranked AS (
            SELECT accession_number, manager_cik,
                   ROW_NUMBER() OVER (
                       PARTITION BY manager_cik
                       ORDER BY availability_date DESC, filing_date DESC,
                                accession_number DESC
                   ) AS sequence_number
            FROM filings
            WHERE report_period=? AND amendment_usable=1
              AND availability_date<=?
        )
        SELECT eh.ticker, r.manager_cik, SUM(eh.reported_shares)
        FROM ranked r
        JOIN effective_holdings eh
          ON eh.event_accession_number=r.accession_number
        WHERE r.sequence_number=1
        GROUP BY eh.ticker, r.manager_cik
        HAVING SUM(eh.reported_shares)>0
        ORDER BY eh.ticker, r.manager_cik
        """,
        parameters,
    )
    positions: dict[str, dict[str, int]] = defaultdict(dict)
    for ticker, manager_cik, shares in rows:
        positions[str(ticker)][str(manager_cik)] = int(shares)
    stats = {
        "included_managers": int(
            connection.execute(
                """
                SELECT COUNT(DISTINCT manager_cik) FROM filings
                WHERE report_period=? AND amendment_usable=1
                  AND availability_date<=?
                """,
                parameters,
            ).fetchone()[0]
        ),
        "late_or_excluded_filings": int(
            connection.execute(
                """
                SELECT COUNT(*) FROM filings
                WHERE report_period=?
                  AND (amendment_usable=0 OR availability_date>?)
                """,
                parameters,
            ).fetchone()[0]
        ),
    }
    return positions, stats


def _concentration(shares: Iterable[int]) -> tuple[int, float, float, float]:
    ordered = sorted((int(value) for value in shares if value > 0), reverse=True)
    total = sum(ordered)
    if not ordered or total <= 0:
        return 0, math.nan, math.nan, math.nan
    weights = [value / total for value in ordered]
    return (
        total,
        weights[0],
        sum(weights[:5]),
        sum(weight * weight for weight in weights),
    )


def build_feature_rows(
    connection: sqlite3.Connection,
    contract: dict[str, Any],
    intervals: dict[str, list[tuple[date, date]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    periods, legacy_periods = _valid_report_periods(connection, contract)
    lag_days = int(contract["publication_wave"]["statutory_lag_days"])
    previous: dict[str, dict[str, Any]] = {}
    active_counts: dict[str, int] = defaultdict(int)
    nonzero_counts: dict[str, int] = defaultdict(int)
    output: list[dict[str, Any]] = []
    period_audit = []

    for index, report_period in enumerate(periods, start=1):
        availability = common_availability_date(report_period, lag_days)
        positions, stats = _period_positions(
            connection,
            report_period,
            availability,
        )
        active = _active_tickers(intervals, report_period)
        for ticker in sorted(active):
            manager_shares = positions.get(ticker, {})
            managers = set(manager_shares)
            breadth = len(managers)
            total, top1, top5, hhi = _concentration(manager_shares.values())
            prior = previous.get(ticker)
            active_counts[ticker] += 1
            nonzero_counts[ticker] += breadth > 0
            output.append(
                {
                    "report_period": report_period.isoformat(),
                    "context_available_date": availability.isoformat(),
                    "ticker": ticker,
                    "reporting_manager_breadth": breadth,
                    "breadth_change_1q": (
                        "" if prior is None else breadth - prior["breadth"]
                    ),
                    "breadth_change_fraction_1q": (
                        ""
                        if prior is None or prior["breadth"] == 0
                        else round(
                            (breadth - prior["breadth"]) / prior["breadth"],
                            10,
                        )
                    ),
                    "new_reporting_managers_1q": (
                        "" if prior is None else len(managers - prior["managers"])
                    ),
                    "exited_reporting_managers_1q": (
                        "" if prior is None else len(prior["managers"] - managers)
                    ),
                    "total_reported_shares_diagnostic": total,
                    "top1_reported_share_concentration": (
                        "" if math.isnan(top1) else round(top1, 10)
                    ),
                    "top5_reported_share_concentration": (
                        "" if math.isnan(top5) else round(top5, 10)
                    ),
                    "reported_share_hhi": (
                        "" if math.isnan(hhi) else round(hhi, 10)
                    ),
                    "top5_concentration_change_1q": (
                        ""
                        if prior is None
                        or math.isnan(top5)
                        or math.isnan(prior["top5"])
                        else round(top5 - prior["top5"], 10)
                    ),
                    "hhi_change_1q": (
                        ""
                        if prior is None
                        or math.isnan(hhi)
                        or math.isnan(prior["hhi"])
                        else round(hhi - prior["hhi"], 10)
                    ),
                    "split_adjusted_share_change_1q": "",
                    "split_adjusted_share_change_status": (
                        "BLOCKED_NO_TIME_VALID_CORPORATE_ACTION_LEDGER"
                    ),
                }
            )
            previous[ticker] = {
                "breadth": breadth,
                "managers": managers,
                "top5": top5,
                "hhi": hhi,
            }
        period_audit.append(
            {
                "report_period": report_period.isoformat(),
                "context_available_date": availability.isoformat(),
                "active_tickers": len(active),
                **stats,
            }
        )
        print(
            f"[13F slow context] {index}/{len(periods)} "
            f"{report_period} active={len(active)} "
            f"positions={sum(len(value) for value in positions.values())}",
            flush=True,
        )

    minimum_fraction = contract["gates"][
        "minimum_per_ticker_nonzero_fraction"
    ]
    evaluable = {
        ticker
        for ticker, count in active_counts.items()
        if count and nonzero_counts[ticker] / count >= minimum_fraction
    }
    return output, {
        "periods": periods,
        "legacy_periods_excluded": legacy_periods,
        "period_audit": period_audit,
        "active_counts": dict(active_counts),
        "nonzero_counts": dict(nonzero_counts),
        "evaluable_tickers": evaluable,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise Sec13fSlowContextError("13F slow context output is empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _coverage_rows(
    audit: dict[str, Any],
    minimum_fraction: float,
) -> list[dict[str, Any]]:
    return [
        {
            "ticker": ticker,
            "active_report_periods": active,
            "nonzero_report_periods": audit["nonzero_counts"][ticker],
            "nonzero_fraction": round(
                audit["nonzero_counts"][ticker] / active,
                10,
            ),
            "evaluation_eligible": str(
                audit["nonzero_counts"][ticker] / active >= minimum_fraction
            ).lower(),
        }
        for ticker, active in sorted(audit["active_counts"].items())
    ]


def _build_report(
    contract: dict[str, Any],
    rows: list[dict[str, Any]],
    audit: dict[str, Any],
    coverage_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    gates = contract["gates"]
    periods = audit["periods"]
    years = (periods[-1] - periods[0]).days / 365.25
    keys = {(row["report_period"], row["ticker"]) for row in rows}
    duplicates = len(rows) - len(keys)
    range_violations = sum(
        value != ""
        and not 0.0 <= float(value) <= 1.0
        for row in rows
        for value in (
            row["top1_reported_share_concentration"],
            row["top5_reported_share_concentration"],
            row["reported_share_hhi"],
        )
    )
    future_rows = sum(
        row["context_available_date"] <= row["report_period"] for row in rows
    )
    results = {
        "minimum_distinct_report_periods": (
            len(periods) >= gates["minimum_distinct_report_periods"]
        ),
        "minimum_history_years": years >= gates["minimum_history_years"],
        "minimum_active_tickers": (
            len(audit["active_counts"]) >= gates["minimum_active_tickers"]
        ),
        "minimum_evaluable_tickers": (
            len(audit["evaluable_tickers"])
            >= gates["minimum_evaluable_tickers"]
        ),
        "maximum_duplicate_feature_keys": (
            duplicates <= gates["maximum_duplicate_feature_keys"]
        ),
        "maximum_non_quarter_end_periods": (
            sum(not _is_quarter_end(period) for period in periods)
            <= gates["maximum_non_quarter_end_periods"]
        ),
        "maximum_future_available_rows": (
            future_rows <= gates["maximum_future_available_rows"]
        ),
        "maximum_feature_range_violations": (
            range_violations <= gates["maximum_feature_range_violations"]
        ),
        "maximum_reported_value_uses": (
            0 <= gates["maximum_reported_value_uses"]
        ),
    }
    passed = all(results.values())
    fractions = {
        ticker: audit["nonzero_counts"][ticker] / active
        for ticker, active in audit["active_counts"].items()
    }
    return {
        "report_version": FORMAT_VERSION,
        "status": (
            "SEC_13F_SLOW_CONTEXT_GATE_PASSED"
            if passed
            else "SEC_13F_SLOW_CONTEXT_GATE_FAILED"
        ),
        "features": {
            "path": FEATURES.relative_to(ROOT).as_posix(),
            "sha256": sha256(FEATURES),
            "rows": len(rows),
            "distinct_tickers": len(audit["active_counts"]),
            "evaluable_tickers": len(audit["evaluable_tickers"]),
            "distinct_report_periods": len(periods),
            "first_report_period": periods[0].isoformat(),
            "last_report_period": periods[-1].isoformat(),
            "history_years": round(years, 4),
            "minimum_nonzero_fraction": round(min(fractions.values()), 6),
            "median_nonzero_fraction": round(
                sorted(fractions.values())[len(fractions) // 2],
                6,
            ),
        },
        "coverage": {
            "path": COVERAGE.relative_to(ROOT).as_posix(),
            "sha256": sha256(COVERAGE),
            "rows": len(coverage_rows),
            "ineligible_tickers": [
                row["ticker"]
                for row in coverage_rows
                if row["evaluation_eligible"] == "false"
            ],
        },
        "availability": {
            "first_context_available_date": rows[0][
                "context_available_date"
            ],
            "last_context_available_date": max(
                row["context_available_date"] for row in rows
            ),
            "legacy_report_periods_excluded": audit[
                "legacy_periods_excluded"
            ],
            "late_or_excluded_filings": sum(
                period["late_or_excluded_filings"]
                for period in audit["period_audit"]
            ),
            "common_publication_wave": True,
        },
        "measurement_limits": contract["measurement_limits"],
        "gate_results": results,
        "price_outcomes_opened": False,
        "direction_hypothesis_executed": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "next_step": (
            "RUN_INCREMENTAL_13F_CONTEXT_OOS"
            if passed
            else "STOP_AND_REPAIR_13F_CONTEXT"
        ),
    }


def generate(
    *,
    contract_path: Path = CONTRACT,
    database_path: Path = DATABASE,
    security_intervals_path: Path = SECURITY_INTERVALS,
    features_path: Path = FEATURES,
    coverage_path: Path = COVERAGE,
    report_path: Path = REPORT,
    verify_database_hash: bool = True,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    pinned = _verify_pinned_inputs(contract)
    pit_report = pinned["data/reports/sec_13f_pit_holdings_v1.json"]
    _verify_database(
        database_path,
        pit_report,
        verify_hash=verify_database_hash,
    )
    security_report = pinned[
        "data/reports/sec_13f_security_ledger_v1.json"
    ]
    if sha256(security_intervals_path) != security_report[
        "security_interval_ledger"
    ]["sha256"]:
        raise Sec13fSlowContextError("13F security intervals changed")
    intervals = _load_active_intervals(security_intervals_path)
    connection = sqlite3.connect(database_path)
    try:
        rows, audit = build_feature_rows(connection, contract, intervals)
    finally:
        connection.close()
    minimum_fraction = contract["gates"][
        "minimum_per_ticker_nonzero_fraction"
    ]
    coverage_rows = _coverage_rows(audit, minimum_fraction)
    eligible = {
        row["ticker"]
        for row in coverage_rows
        if row["evaluation_eligible"] == "true"
    }
    for row in rows:
        row["feature_usable"] = str(
            row["ticker"] in eligible
            and row["reporting_manager_breadth"] > 0
        ).lower()
    _write_csv(features_path, rows)
    _write_csv(coverage_path, coverage_rows)
    report = _build_report(contract, rows, audit, coverage_rows)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def verify_outputs(report_path: Path = REPORT) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("report_version") != FORMAT_VERSION:
        raise Sec13fSlowContextError("unexpected 13F context report")
    for key in ("features", "coverage"):
        artifact = report[key]
        path = ROOT / artifact["path"]
        if not path.is_file() or sha256(path) != artifact["sha256"]:
            raise Sec13fSlowContextError(
                f"13F context {key} hash changed"
            )
    if report["price_outcomes_opened"] or report["blind_holdout_access"]:
        raise Sec13fSlowContextError("13F context research firewall changed")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument(
        "--skip-database-hash",
        action="store_true",
        help="Only for local reruns after an earlier full hash verification.",
    )
    args = parser.parse_args()
    report = (
        verify_outputs()
        if args.verify_only
        else generate(verify_database_hash=not args.skip_database_hash)
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"].endswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
