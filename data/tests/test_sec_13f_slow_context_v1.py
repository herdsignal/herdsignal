import json
from datetime import date
from pathlib import Path

from herd.sec_13f_pit_holdings_v1 import _initialize_database
from herd.sec_13f_slow_context_v1 import (
    _coverage_rows,
    _concentration,
    build_feature_rows,
    common_availability_date,
)


def _contract() -> dict:
    return {
        "history": {
            "first_valid_report_period": "2013-03-31",
            "expected_last_report_period": "2013-06-30",
        },
        "publication_wave": {"statutory_lag_days": 45},
        "gates": {"minimum_per_ticker_nonzero_fraction": 0.7},
    }


def _filing(
    connection,
    accession: str,
    manager: str,
    period: str,
    availability: str,
) -> None:
    connection.execute(
        """
        INSERT INTO filings VALUES (
          ?, ?, 'Fixture', ?, ?, ?, '13F-HR', 0, 0, '',
          'INITIAL_SNAPSHOT', 1, '', ''
        )
        """,
        (accession, manager, period, availability, availability),
    )


def _holding(
    connection,
    accession: str,
    manager: str,
    period: str,
    availability: str,
    ticker: str,
    shares: int,
) -> None:
    connection.execute(
        """
        INSERT INTO effective_holdings VALUES (
          ?, ?, ?, ?, ?, '0000000001', '000000001', 0, ?, ?
        )
        """,
        (
            accession,
            availability,
            manager,
            period,
            ticker,
            shares,
            accession,
        ),
    )


def test_common_availability_waits_until_session_after_deadline() -> None:
    assert common_availability_date(date(2024, 3, 31)) == date(2024, 5, 16)
    assert common_availability_date(date(2023, 9, 30)) == date(2023, 11, 15)


def test_concentration_uses_reported_shares_within_security() -> None:
    total, top1, top5, hhi = _concentration([60, 30, 10])
    assert total == 100
    assert top1 == 0.6
    assert top5 == 1.0
    assert round(hhi, 2) == 0.46


def test_feature_rows_use_latest_public_event_and_track_manager_sets(
    tmp_path: Path,
) -> None:
    connection = _initialize_database(tmp_path / "fixture.sqlite")
    _filing(connection, "a1", "m1", "2013-03-31", "2013-05-01")
    _filing(connection, "a2", "m2", "2013-03-31", "2013-05-02")
    _holding(connection, "a1", "m1", "2013-03-31", "2013-05-01", "AAA", 60)
    _holding(connection, "a2", "m2", "2013-03-31", "2013-05-02", "AAA", 40)

    _filing(connection, "b1", "m1", "2013-06-30", "2013-08-01")
    _filing(connection, "b2", "m3", "2013-06-30", "2013-08-02")
    _filing(connection, "late", "m4", "2013-06-30", "2013-09-01")
    _holding(connection, "b1", "m1", "2013-06-30", "2013-08-01", "AAA", 50)
    _holding(connection, "b2", "m3", "2013-06-30", "2013-08-02", "AAA", 50)
    _holding(
        connection,
        "late",
        "m4",
        "2013-06-30",
        "2013-09-01",
        "AAA",
        999,
    )
    connection.commit()

    intervals = {"AAA": [(date(2013, 3, 31), date(2013, 6, 30))]}
    rows, audit = build_feature_rows(connection, _contract(), intervals)
    connection.close()

    assert len(rows) == 2
    assert rows[0]["reporting_manager_breadth"] == 2
    assert rows[0]["top1_reported_share_concentration"] == 0.6
    assert rows[1]["reporting_manager_breadth"] == 2
    assert rows[1]["new_reporting_managers_1q"] == 1
    assert rows[1]["exited_reporting_managers_1q"] == 1
    assert rows[1]["total_reported_shares_diagnostic"] == 100
    assert audit["period_audit"][1]["late_or_excluded_filings"] == 1
    coverage = _coverage_rows(audit, 0.7)
    assert coverage == [
        {
            "ticker": "AAA",
            "active_report_periods": 2,
            "nonzero_report_periods": 2,
            "nonzero_fraction": 1.0,
            "evaluation_eligible": "true",
        }
    ]


def test_contract_blocks_split_adjusted_change_without_ledger() -> None:
    contract = json.loads(
        (
            Path(__file__).parents[1]
            / "herd/sec_13f_slow_context_v1.json"
        ).read_text(encoding="utf-8")
    )
    limits = contract["measurement_limits"]
    assert limits["reported_value_used"] is False
    assert limits["split_adjusted_reported_share_change_1q"].startswith(
        "BLOCKED_"
    )
    assert limits["standalone_buy_or_sell_allowed"] is False
