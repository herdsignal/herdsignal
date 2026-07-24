"""대표 13F 보통주 보유를 보수적 공개시점과 amendment 의미로 정규화한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import zipfile
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from herd.finra_short_interest_census_v1 import (
    us_securities_market_holidays,
)
from herd.sec_13f_security_ledger_v1 import (
    BULK_SNAPSHOT,
    ROOT,
    _parse_date,
    _security_id,
    _tsv_chunks,
    _tsv_rows,
    sha256,
)


SECURITY_LEDGER_REPORT = ROOT / "data/reports/sec_13f_security_ledger_v1.json"
SECURITY_INTERVALS = ROOT / "data/reports/sec_13f_security_intervals_v1.csv"
BULK_REPORT = ROOT / "data/reports/sec_13f_bulk_v1.json"
DATABASE = BULK_SNAPSHOT / "derived/sec-13f-pit-holdings-v1.sqlite"
REPORT = ROOT / "data/reports/sec_13f_pit_holdings_v1.json"
AMENDMENT_AUDIT = ROOT / "data/reports/sec_13f_amendment_audit_v1.csv"
FORMAT_VERSION = "SEC_13F_PIT_HOLDINGS_V1"
KNOWN_AMENDMENT_TYPES = {"RESTATEMENT", "NEW HOLDINGS"}
EXCEPTIONAL_MARKET_CLOSURES = {
    date(2018, 12, 5),  # National Day of Mourning for George H. W. Bush
    date(2025, 1, 9),  # National Day of Mourning for Jimmy Carter
}


class Sec13fPitHoldingsError(RuntimeError):
    """PIT 공개시점·수정 공시·보유 원장 경계 위반 시 발생한다."""


def next_market_session(day: date) -> date:
    current = day
    while True:
        current += timedelta(days=1)
        if (
            current.weekday() < 5
            and current not in us_securities_market_holidays(current.year)
            and current not in EXCEPTIONAL_MARKET_CLOSURES
        ):
            return current


def _load_security_map(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    mapping: dict[str, dict[str, str]] = {}
    for row in rows:
        cusip = row["cusip"]
        previous = mapping.setdefault(
            cusip,
            {
                "ticker": row["ticker"],
                "issuer_cik": row["cik"],
            },
        )
        if (
            previous["ticker"] != row["ticker"]
            or previous["issuer_cik"] != row["cik"]
        ):
            raise Sec13fPitHoldingsError(
                f"selected CUSIP maps to multiple targets: {cusip}"
            )
    if len(mapping) < 300:
        raise Sec13fPitHoldingsError("security identifier ledger is too small")
    return mapping


def _submission_metadata(
    archive: zipfile.ZipFile,
) -> dict[str, dict[str, str]]:
    metadata = {}
    for row in _tsv_rows(archive, "SUBMISSION.tsv"):
        accession = row["ACCESSION_NUMBER"].strip()
        metadata[accession] = {
            "filing_date": _parse_date(row["FILING_DATE"]).isoformat(),
            "submission_type": row["SUBMISSIONTYPE"].strip().upper(),
            "manager_cik": row["CIK"].strip().zfill(10),
            "report_period": _parse_date(
                row["PERIODOFREPORT"]
            ).isoformat(),
        }
    return metadata


def _cover_metadata(
    archive: zipfile.ZipFile,
) -> dict[str, dict[str, str]]:
    metadata = {}
    for row in _tsv_rows(archive, "COVERPAGE.tsv"):
        accession = row["ACCESSION_NUMBER"].strip()
        metadata[accession] = {
            "is_amendment": row["ISAMENDMENT"].strip().upper(),
            "amendment_number": row["AMENDMENTNO"].strip(),
            "amendment_type": re.sub(
                r"\s+", " ", row["AMENDMENTTYPE"].strip().upper()
            ),
            "filing_manager_name": row["FILINGMANAGER_NAME"].strip(),
            "report_type": row["REPORTTYPE"].strip(),
            "form_13f_file_number": row["FORM13FFILENUMBER"].strip(),
        }
    return metadata


def _integer(value: Any) -> int:
    text = str(value).strip()
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError as error:
        raise Sec13fPitHoldingsError(f"invalid numeric holding value: {text}") from error


def _extract_holdings(
    archive: zipfile.ZipFile,
    security_map: dict[str, dict[str, str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    columns = [
        "ACCESSION_NUMBER",
        "NAMEOFISSUER",
        "TITLEOFCLASS",
        "CUSIP",
        "FIGI",
        "VALUE",
        "SSHPRNAMT",
        "SSHPRNAMTTYPE",
        "PUTCALL",
        "INVESTMENTDISCRETION",
        "OTHERMANAGER",
        "VOTING_AUTH_SOLE",
        "VOTING_AUTH_SHARED",
        "VOTING_AUTH_NONE",
    ]
    holdings: dict[tuple[str, str], dict[str, Any]] = {}
    selected_cusips = set(security_map)
    for chunk in _tsv_chunks(archive, "INFOTABLE.tsv", columns):
        normalized_cusip = (
            chunk["CUSIP"]
            .str.upper()
            .str.replace(r"[^A-Z0-9]", "", regex=True)
        )
        selected = chunk.loc[
            chunk["PUTCALL"].str.strip().eq("")
            & chunk["SSHPRNAMTTYPE"].str.strip().str.upper().eq("SH")
            & normalized_cusip.isin(selected_cusips)
        ].copy()
        selected["NORMALIZED_CUSIP"] = normalized_cusip[selected.index]
        for row in selected.to_dict("records"):
            accession = str(row["ACCESSION_NUMBER"]).strip()
            cusip, figi = _security_id(row)
            if not cusip or cusip not in security_map:
                continue
            key = (accession, cusip)
            holding = holdings.get(key)
            if holding is None:
                target = security_map[cusip]
                holding = {
                    "accession_number": accession,
                    "ticker": target["ticker"],
                    "issuer_cik": target["issuer_cik"],
                    "cusip": cusip,
                    "figis": set(),
                    "issuer_names": set(),
                    "class_titles": set(),
                    "value": 0,
                    "shares": 0,
                    "discretions": set(),
                    "other_managers": set(),
                    "voting_sole": 0,
                    "voting_shared": 0,
                    "voting_none": 0,
                    "source_rows": 0,
                }
                holdings[key] = holding
            if figi:
                holding["figis"].add(figi)
            holding["issuer_names"].add(str(row["NAMEOFISSUER"]).strip())
            holding["class_titles"].add(str(row["TITLEOFCLASS"]).strip())
            holding["value"] += _integer(row["VALUE"])
            holding["shares"] += _integer(row["SSHPRNAMT"])
            discretion = str(row["INVESTMENTDISCRETION"]).strip()
            if discretion:
                holding["discretions"].add(discretion)
            other_manager = str(row["OTHERMANAGER"]).strip()
            if other_manager:
                holding["other_managers"].add(other_manager)
            holding["voting_sole"] += _integer(row["VOTING_AUTH_SOLE"])
            holding["voting_shared"] += _integer(row["VOTING_AUTH_SHARED"])
            holding["voting_none"] += _integer(row["VOTING_AUTH_NONE"])
            holding["source_rows"] += 1
    return holdings


def _initialize_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;
        CREATE TABLE filings (
            accession_number TEXT PRIMARY KEY,
            manager_cik TEXT NOT NULL,
            manager_name TEXT NOT NULL,
            report_period TEXT NOT NULL,
            filing_date TEXT NOT NULL,
            availability_date TEXT NOT NULL,
            submission_type TEXT NOT NULL,
            is_amendment INTEGER NOT NULL,
            amendment_number INTEGER,
            amendment_type TEXT NOT NULL,
            amendment_operation TEXT NOT NULL,
            amendment_usable INTEGER NOT NULL,
            report_type TEXT NOT NULL,
            form_13f_file_number TEXT NOT NULL
        );
        CREATE TABLE holdings (
            accession_number TEXT NOT NULL,
            ticker TEXT NOT NULL,
            issuer_cik TEXT NOT NULL,
            cusip TEXT NOT NULL,
            figis TEXT NOT NULL,
            issuer_names TEXT NOT NULL,
            class_titles TEXT NOT NULL,
            reported_value INTEGER NOT NULL,
            reported_shares INTEGER NOT NULL,
            investment_discretions TEXT NOT NULL,
            other_manager_ids TEXT NOT NULL,
            voting_sole INTEGER NOT NULL,
            voting_shared INTEGER NOT NULL,
            voting_none INTEGER NOT NULL,
            source_rows INTEGER NOT NULL,
            PRIMARY KEY (accession_number, ticker, cusip),
            FOREIGN KEY (accession_number) REFERENCES filings(accession_number)
        );
        CREATE TABLE effective_holdings (
            event_accession_number TEXT NOT NULL,
            availability_date TEXT NOT NULL,
            manager_cik TEXT NOT NULL,
            report_period TEXT NOT NULL,
            ticker TEXT NOT NULL,
            issuer_cik TEXT NOT NULL,
            cusip TEXT NOT NULL,
            reported_value INTEGER NOT NULL,
            reported_shares INTEGER NOT NULL,
            source_accession_number TEXT NOT NULL,
            PRIMARY KEY (event_accession_number, ticker, cusip),
            FOREIGN KEY (event_accession_number)
                REFERENCES filings(accession_number),
            FOREIGN KEY (source_accession_number)
                REFERENCES filings(accession_number)
        );
        """
    )
    return connection


def _amendment_semantics(
    submission_type: str,
    cover: dict[str, str],
) -> tuple[bool, str, str, bool]:
    is_amendment = (
        submission_type.endswith("/A")
        or cover.get("is_amendment") == "Y"
    )
    if not is_amendment:
        return False, "", "INITIAL_SNAPSHOT", True
    amendment_type = cover.get("amendment_type", "")
    if amendment_type == "RESTATEMENT":
        return True, amendment_type, "REPLACE_SNAPSHOT_FROM_AVAILABILITY", True
    if amendment_type == "NEW HOLDINGS":
        return True, amendment_type, "ADD_NEW_HOLDINGS_FROM_AVAILABILITY", True
    return True, amendment_type, "EXCLUDE_UNKNOWN_AMENDMENT_SEMANTICS", False


def _insert_archive(
    connection: sqlite3.Connection,
    archive_path: Path,
    security_map: dict[str, dict[str, str]],
) -> tuple[int, int]:
    with zipfile.ZipFile(archive_path) as archive:
        submissions = _submission_metadata(archive)
        covers = _cover_metadata(archive)
        holdings = _extract_holdings(archive, security_map)
    accessions = sorted({key[0] for key in holdings})
    filing_rows = []
    for accession in accessions:
        submission = submissions.get(accession)
        cover = covers.get(accession)
        if submission is None or cover is None:
            raise Sec13fPitHoldingsError(
                f"selected holding is missing filing metadata: {accession}"
            )
        is_amendment, amendment_type, operation, usable = _amendment_semantics(
            submission["submission_type"], cover
        )
        filing_date = date.fromisoformat(submission["filing_date"])
        amendment_number = cover.get("amendment_number", "")
        filing_rows.append(
            (
                accession,
                submission["manager_cik"],
                cover["filing_manager_name"],
                submission["report_period"],
                filing_date.isoformat(),
                next_market_session(filing_date).isoformat(),
                submission["submission_type"],
                int(is_amendment),
                int(amendment_number) if amendment_number.isdigit() else None,
                amendment_type,
                operation,
                int(usable),
                cover["report_type"],
                cover["form_13f_file_number"],
            )
        )
    connection.executemany(
        "INSERT OR IGNORE INTO filings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        filing_rows,
    )
    holding_rows = []
    for holding in holdings.values():
        holding_rows.append(
            (
                holding["accession_number"],
                holding["ticker"],
                holding["issuer_cik"],
                holding["cusip"],
                "|".join(sorted(holding["figis"])),
                "|".join(sorted(holding["issuer_names"])),
                "|".join(sorted(holding["class_titles"])),
                holding["value"],
                holding["shares"],
                "|".join(sorted(holding["discretions"])),
                "|".join(sorted(holding["other_managers"])),
                holding["voting_sole"],
                holding["voting_shared"],
                holding["voting_none"],
                holding["source_rows"],
            )
        )
    connection.executemany(
        "INSERT OR IGNORE INTO holdings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        holding_rows,
    )
    connection.commit()
    return len(filing_rows), len(holding_rows)


def _create_indexes(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE INDEX filings_manager_period_idx
            ON filings(manager_cik, report_period, availability_date);
        CREATE INDEX filings_availability_idx
            ON filings(availability_date);
        CREATE INDEX holdings_ticker_idx
            ON holdings(ticker, accession_number);
        """
    )
    connection.commit()


def _create_effective_indexes(connection: sqlite3.Connection) -> None:
    """대량 상태 적재 뒤에만 인덱스를 만들어 행별 갱신 비용을 피한다."""
    connection.execute(
        """
        CREATE INDEX effective_holdings_asof_idx
        ON effective_holdings(
            ticker, availability_date, manager_cik, report_period
        )
        """
    )
    connection.commit()


def _materialize_effective_holdings(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    """각 수정공시 직후 시장에 알려진 manager×quarter 보유 상태를 만든다."""
    connection.execute("DELETE FROM effective_holdings")
    rows = connection.execute(
        """
        SELECT
            f.manager_cik, f.report_period, f.availability_date,
            f.filing_date, f.accession_number, f.amendment_operation,
            h.ticker, h.issuer_cik, h.cusip,
            h.reported_value, h.reported_shares
        FROM filings f
        JOIN holdings h USING (accession_number)
        WHERE f.amendment_usable = 1
        ORDER BY
            f.manager_cik, f.report_period, f.availability_date,
            f.filing_date, f.accession_number, h.ticker, h.cusip
        """
    )
    current_group: tuple[str, str] | None = None
    current_accession: str | None = None
    current_event: dict[str, str] | None = None
    filing_holdings: list[tuple[Any, ...]] = []
    state: dict[tuple[str, str], tuple[Any, ...]] = {}
    effective_rows: list[tuple[Any, ...]] = []
    stats = {
        "usable_events": 0,
        "initial_events": 0,
        "restatement_events": 0,
        "new_holdings_events": 0,
        "new_holdings_overlap_rows_ignored": 0,
        "events_without_initial_snapshot": 0,
    }

    def flush_event() -> None:
        nonlocal state
        if current_event is None:
            return
        operation = current_event["operation"]
        if operation == "INITIAL_SNAPSHOT":
            state = {
                (str(row[0]), str(row[2])): row
                for row in filing_holdings
            }
            stats["initial_events"] += 1
        elif operation == "REPLACE_SNAPSHOT_FROM_AVAILABILITY":
            if not state:
                stats["events_without_initial_snapshot"] += 1
            state = {
                (str(row[0]), str(row[2])): row
                for row in filing_holdings
            }
            stats["restatement_events"] += 1
        elif operation == "ADD_NEW_HOLDINGS_FROM_AVAILABILITY":
            if not state:
                stats["events_without_initial_snapshot"] += 1
            for row in filing_holdings:
                key = (str(row[0]), str(row[2]))
                if key in state:
                    stats["new_holdings_overlap_rows_ignored"] += 1
                    continue
                state[key] = row
            stats["new_holdings_events"] += 1
        else:
            raise Sec13fPitHoldingsError(
                f"unexpected usable amendment operation: {operation}"
            )
        stats["usable_events"] += 1
        for row in state.values():
            effective_rows.append(
                (
                    current_event["accession"],
                    current_event["availability_date"],
                    current_event["manager_cik"],
                    current_event["report_period"],
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                )
            )
        if len(effective_rows) >= 50_000:
            connection.executemany(
                "INSERT INTO effective_holdings VALUES (?,?,?,?,?,?,?,?,?,?)",
                effective_rows,
            )
            effective_rows.clear()

    for row in rows:
        group = (str(row[0]), str(row[1]))
        accession = str(row[4])
        if current_accession is not None and accession != current_accession:
            flush_event()
            filing_holdings = []
        if group != current_group:
            if current_accession is not None and accession == current_accession:
                raise Sec13fPitHoldingsError(
                    "one accession spans multiple manager/report groups"
                )
            state = {}
            current_group = group
        if accession != current_accession:
            current_accession = accession
            current_event = {
                "manager_cik": str(row[0]),
                "report_period": str(row[1]),
                "availability_date": str(row[2]),
                "accession": accession,
                "operation": str(row[5]),
            }
        filing_holdings.append(
            (
                str(row[6]),
                str(row[7]),
                str(row[8]),
                int(row[9]),
                int(row[10]),
                accession,
            )
        )
    flush_event()
    if effective_rows:
        connection.executemany(
            "INSERT INTO effective_holdings VALUES (?,?,?,?,?,?,?,?,?,?)",
            effective_rows,
        )
    connection.commit()
    return stats


def _scalar(connection: sqlite3.Connection, query: str) -> int:
    return int(connection.execute(query).fetchone()[0])


def _write_amendment_audit(
    connection: sqlite3.Connection,
    path: Path,
) -> list[dict[str, Any]]:
    rows = [
        {
            "submission_type": row[0],
            "is_amendment": row[1],
            "amendment_type": row[2],
            "amendment_operation": row[3],
            "amendment_usable": row[4],
            "filing_count": row[5],
            "holding_count": row[6],
        }
        for row in connection.execute(
            """
            SELECT f.submission_type, f.is_amendment, f.amendment_type,
                   f.amendment_operation, f.amendment_usable,
                   COUNT(DISTINCT f.accession_number), COUNT(h.cusip)
            FROM filings f
            JOIN holdings h USING (accession_number)
            GROUP BY 1,2,3,4,5
            ORDER BY 1,3
            """
        )
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return rows


def _build_report(
    connection: sqlite3.Connection,
    database_path: Path,
    amendment_path: Path,
    materialization: dict[str, int],
) -> dict[str, Any]:
    minimum_date, maximum_date = connection.execute(
        "SELECT MIN(availability_date), MAX(availability_date) FROM filings"
    ).fetchone()
    distinct_tickers = _scalar(
        connection, "SELECT COUNT(DISTINCT ticker) FROM holdings"
    )
    distinct_periods = _scalar(
        connection, "SELECT COUNT(DISTINCT report_period) FROM filings"
    )
    unknown_amendments = _scalar(
        connection,
        "SELECT COUNT(*) FROM filings WHERE is_amendment=1 AND amendment_usable=0",
    )
    duplicate_keys = _scalar(
        connection,
        """
        SELECT COUNT(*) FROM (
            SELECT accession_number, ticker, cusip, COUNT(*) AS n
            FROM holdings GROUP BY 1,2,3 HAVING n > 1
        )
        """,
    )
    duplicate_effective_keys = _scalar(
        connection,
        """
        SELECT COUNT(*) FROM (
            SELECT event_accession_number, ticker, cusip, COUNT(*) AS n
            FROM effective_holdings GROUP BY 1,2,3 HAVING n > 1
        )
        """,
    )
    quarter_end_as_availability = _scalar(
        connection,
        """
        SELECT COUNT(*) FROM filings
        WHERE availability_date = report_period
        """,
    )
    non_forward_availability = _scalar(
        connection,
        """
        SELECT COUNT(*) FROM filings
        WHERE availability_date <= filing_date
        """,
    )
    history_years = (
        date.fromisoformat(maximum_date) - date.fromisoformat(minimum_date)
    ).days / 365.25
    gates = {
        "minimum_history_years": history_years >= 10.0,
        "minimum_distinct_quarters": distinct_periods >= 40,
        "minimum_mapped_research_tickers": distinct_tickers >= 300,
        "maximum_duplicate_raw_holding_keys": duplicate_keys == 0,
        "maximum_duplicate_effective_holding_keys": (
            duplicate_effective_keys == 0
        ),
        "maximum_future_available_rows": non_forward_availability == 0,
        "maximum_quarter_end_as_availability_rows": (
            quarter_end_as_availability == 0
        ),
        "unknown_amendments_excluded": connection.execute(
            """
            SELECT COUNT(*) FROM filings
            WHERE is_amendment=1 AND amendment_usable=0
              AND amendment_operation != 'EXCLUDE_UNKNOWN_AMENDMENT_SEMANTICS'
            """
        ).fetchone()[0]
        == 0,
    }
    return {
        "report_version": FORMAT_VERSION,
        "status": (
            "CONSERVATIVE_PIT_HOLDINGS_LEDGER_GATE_PASSED"
            if all(gates.values())
            else "CONSERVATIVE_PIT_HOLDINGS_LEDGER_GATE_FAILED"
        ),
        "database": {
            "path": database_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(database_path),
            "bytes": database_path.stat().st_size,
            "filings": _scalar(connection, "SELECT COUNT(*) FROM filings"),
            "holdings": _scalar(connection, "SELECT COUNT(*) FROM holdings"),
            "effective_holdings": _scalar(
                connection, "SELECT COUNT(*) FROM effective_holdings"
            ),
        },
        "amendment_audit": {
            "path": amendment_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(amendment_path),
            "unknown_amendment_filings_excluded": unknown_amendments,
        },
        "coverage": {
            "distinct_tickers": distinct_tickers,
            "distinct_manager_ciks": _scalar(
                connection, "SELECT COUNT(DISTINCT manager_cik) FROM filings"
            ),
            "distinct_report_periods": distinct_periods,
            "first_availability_date": minimum_date,
            "last_availability_date": maximum_date,
            "history_years": round(history_years, 4),
        },
        "availability_contract": {
            "bulk_has_exact_acceptance_datetime": False,
            "effective_availability": (
                "NEXT_US_SECURITIES_MARKET_SESSION_AFTER_FILING_DATE"
            ),
            "same_day_use_allowed": False,
            "quarter_end_as_publication_allowed": False,
            "exact_acceptance_enrichment_required_for_source_review": True,
        },
        "amendment_contract": {
            "RESTATEMENT": "REPLACE_SNAPSHOT_FROM_AVAILABILITY",
            "NEW HOLDINGS": "ADD_NEW_HOLDINGS_FROM_AVAILABILITY",
            "UNKNOWN": "EXCLUDE_UNKNOWN_AMENDMENT_SEMANTICS",
            "NEW_HOLDINGS_OVERLAP": (
                "KEEP_PRIOR_POSITION_AND_IGNORE_OVERLAPPING_AMENDMENT_ROW"
            ),
        },
        "effective_state_materialization": materialization,
        "reported_value_contract": (
            "SOURCE_REPORTED_VALUE_ONLY; UNIT_NORMALIZATION_REQUIRED_BEFORE_"
            "CROSS_PERIOD_COMPARISON"
        ),
        "gate_results": gates,
        "price_outcomes_opened": False,
        "direction_hypothesis_executed": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "next_step": (
            "BUILD_STRATIFIED_13F_SOURCE_REVIEW"
            if all(gates.values())
            else "REPAIR_PIT_HOLDINGS_LEDGER"
        ),
    }


def generate(
    *,
    bulk_snapshot: Path = BULK_SNAPSHOT,
    security_intervals: Path = SECURITY_INTERVALS,
    database_path: Path = DATABASE,
    report_path: Path = REPORT,
    amendment_path: Path = AMENDMENT_AUDIT,
) -> dict[str, Any]:
    security_report = json.loads(
        SECURITY_LEDGER_REPORT.read_text(encoding="utf-8")
    )
    if security_report["status"] != "SECURITY_IDENTIFIER_LEDGER_GATE_PASSED":
        raise Sec13fPitHoldingsError("security identifier gate is not passed")
    if sha256(security_intervals) != security_report[
        "security_interval_ledger"
    ]["sha256"]:
        raise Sec13fPitHoldingsError("security interval ledger hash changed")
    bulk_report = json.loads(BULK_REPORT.read_text(encoding="utf-8"))
    manifest_path = bulk_snapshot / "manifest.json"
    if sha256(manifest_path) != bulk_report["manifest_sha256"]:
        raise Sec13fPitHoldingsError("13F bulk manifest hash changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    security_map = _load_security_map(security_intervals)
    temporary = database_path.with_suffix(".sqlite.tmp")
    temporary.unlink(missing_ok=True)
    connection = _initialize_database(temporary)
    try:
        for index, item in enumerate(manifest["archives"], start=1):
            filing_count, holding_count = _insert_archive(
                connection,
                bulk_snapshot / item["path"],
                security_map,
            )
            print(
                f"[13F PIT] {index}/{len(manifest['archives'])} "
                f"{item['filename']} filings={filing_count} "
                f"holdings={holding_count}",
                flush=True,
            )
        _create_indexes(connection)
        materialization = _materialize_effective_holdings(connection)
        _create_effective_indexes(connection)
        amendment_path.parent.mkdir(parents=True, exist_ok=True)
        _write_amendment_audit(connection, amendment_path)
        connection.close()
        temporary.replace(database_path)
        connection = sqlite3.connect(database_path)
        report = _build_report(
            connection,
            database_path,
            amendment_path,
            materialization,
        )
    finally:
        connection.close()
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def verify_outputs(
    report_path: Path = REPORT,
) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("report_version") != FORMAT_VERSION:
        raise Sec13fPitHoldingsError("unexpected PIT holdings report")
    for key in ("database", "amendment_audit"):
        item = report[key]
        path = ROOT / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise Sec13fPitHoldingsError(
                f"PIT holdings output hash changed: {item['path']}"
            )
    if report["price_outcomes_opened"] or report["blind_holdout_access"]:
        raise Sec13fPitHoldingsError("research firewall changed")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    report = verify_outputs() if args.verify_only else generate()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"].endswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
