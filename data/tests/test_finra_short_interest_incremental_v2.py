import json
from datetime import datetime, timezone
from email.message import Message

import pytest

from herd.finra_short_interest_incremental_v2 import (
    MANIFEST,
    PROTOCOL,
    REPORT,
    FinraIncrementalV2Error,
    _merge_entries,
    _parse_instant,
    collect_incremental,
)


def test_protocol_keeps_finra_in_prospective_shadow_only():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["status"] == "LOCKED_BEFORE_INCREMENTAL_COLLECTION"
    assert protocol["incremental_policy"]["append_only_raw_storage"] is True
    assert protocol["incremental_policy"]["atomic_manifest_publish"] is True
    assert len(protocol["scheduled_candidates"]) == 12
    assert protocol["authority"]["primary_long_horizon_oos_allowed"] is False
    assert protocol["authority"]["operational_action_ratio"] == 0.0


def test_publication_boundary_is_compared_as_an_instant():
    boundary = _parse_instant("2026-07-24T00:00:00-04:00")
    assert boundary == datetime(2026, 7, 24, 4, tzinfo=timezone.utc)


def test_merge_is_idempotent_by_settlement_date_and_hash():
    row = {"settlement_date": "2026-06-30", "sha256": "a"}
    rows = _merge_entries([row, dict(row)])
    assert rows == [row]


def test_before_publication_window_does_not_download_new_candidate(
    tmp_path,
):
    calls = []

    def downloader(url: str, timeout: int):
        calls.append(url)
        raise RuntimeError("revision probe unavailable in unit test")

    report = collect_incremental(
        manifest_path=tmp_path / "manifest.json",
        report_path=tmp_path / "report.json",
        now=datetime(2026, 7, 23, 16, tzinfo=timezone.utc),
        downloader=downloader,
    )
    assert report["status"] == "PENDING_OFFICIAL_PUBLICATION_WINDOW"
    assert len(report["pending_candidates"]) == 12
    assert all("20260715" not in url for url in calls)
    assert report["new_versions_this_run"] == 0
    assert report["settlement_date_count"] == 122


def test_due_new_file_failure_is_blocking(tmp_path):
    def downloader(url: str, timeout: int):
        if "20260715" in url:
            raise RuntimeError("not found")
        return _existing_file_payload(url)

    with pytest.raises(FinraIncrementalV2Error, match="due FINRA file"):
        collect_incremental(
            manifest_path=tmp_path / "manifest.json",
            report_path=tmp_path / "report.json",
            now=datetime(2026, 7, 24, 5, tzinfo=timezone.utc),
            downloader=downloader,
        )
    assert not (tmp_path / "manifest.json").exists()


def test_published_incremental_state_is_honest_before_release_window():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert report["status"] == "PENDING_OFFICIAL_PUBLICATION_WINDOW"
    assert report["all_baseline_hashes_verified"] is True
    assert report["new_versions_this_run"] == 0
    assert report["last_settlement_date"] == "2026-06-30"
    assert manifest["settlement_date_count"] == 122
    assert report["lifecycle_gate"]["all_target_identifiers_complete"] is False
    assert report["primary_long_horizon_oos_allowed"] is False
    assert report["price_outcomes_opened"] is False


def _existing_file_payload(url: str) -> tuple[bytes, Message]:
    # Tests that need successful downloads can substitute a full fixture later.
    raise RuntimeError(f"fixture not configured: {url}")
