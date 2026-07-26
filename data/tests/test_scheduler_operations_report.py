from datetime import UTC, datetime
from pathlib import Path

import pytest

from scheduler.operation_log import write_operation_event
from scheduler.operations_report import build_weekly_report, load_verified_events


def test_builds_weekly_metrics_from_verified_events(tmp_path: Path) -> None:
    now = datetime(2026, 7, 26, 21, 0, tzinfo=UTC)
    write_operation_event(
        {
            "status": "SUCCESS",
            "total": 2,
            "success": ["AAPL", "SPY"],
            "failed": [],
            "skipped": [],
            "prospectiveEvidence": {
                "archive": {"status": "CREATED"},
                "maturity": {"created": 2, "pending": 7},
            },
        },
        output_dir=tmp_path,
        now=now,
    )

    report = build_weekly_report(
        load_verified_events(tmp_path),
        now=now,
    )

    assert report["runCount"] == 1
    assert report["statusCounts"] == {"SUCCESS": 1}
    assert report["tickerExecution"]["successRate"] == 1.0
    assert report["prospectiveEvidence"] == {
        "recordedRuns": 1,
        "createdObservations": 1,
        "maturedOutcomes": 2,
        "pendingOutcomes": 7,
    }


def test_rejects_tampered_operation_event(tmp_path: Path) -> None:
    target = write_operation_event(
        {"status": "SUCCESS"},
        output_dir=tmp_path,
        now=datetime(2026, 7, 26, 21, 0, tzinfo=UTC),
    )
    target.write_text(
        target.read_text(encoding="utf-8").replace("SUCCESS", "FAILED"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="해시 불일치"):
        load_verified_events(tmp_path)
