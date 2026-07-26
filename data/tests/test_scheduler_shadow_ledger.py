from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from scheduler.shadow_ledger import (
    ShadowLedgerError,
    append_shadow_observation,
    verify_shadow_ledger,
)


def _append(path: Path, ticker: str = "SPY") -> dict:
    return append_shadow_observation(
        path,
        candidate_id="candidate-a",
        observed_at=datetime(2026, 7, 26, 21, 0, tzinfo=UTC),
        as_of_date=date(2026, 7, 24),
        ticker=ticker,
        input_sha256="a" * 64,
        output={"score": 51, "state": "CALM"},
    )


def test_appends_and_verifies_hash_chain(tmp_path: Path) -> None:
    path = tmp_path / "shadow.jsonl"
    first = _append(path)
    second = _append(path, "AAPL")

    rows = verify_shadow_ledger(path)

    assert len(rows) == 2
    assert second["previousHash"] == first["recordHash"]


def test_rejects_action_output_and_tampering(tmp_path: Path) -> None:
    path = tmp_path / "shadow.jsonl"
    _append(path)
    path.write_text(
        path.read_text(encoding="utf-8").replace('"score": 51', '"score": 99'),
        encoding="utf-8",
    )
    with pytest.raises(ShadowLedgerError, match="해시 체인"):
        verify_shadow_ledger(path)

    with pytest.raises(ShadowLedgerError, match="행동 출력"):
        append_shadow_observation(
            tmp_path / "other.jsonl",
            candidate_id="candidate-a",
            observed_at=datetime.now(UTC),
            as_of_date=date.today(),
            ticker="SPY",
            input_sha256="a" * 64,
            output={"action": "SELL"},
        )
