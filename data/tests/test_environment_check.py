from importlib import metadata
from pathlib import Path

import pytest

from tools.environment_check import inspect_environment, read_locked_versions


def test_read_locked_versions_rejects_ranges(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("pandas>=2.2\n")

    with pytest.raises(ValueError, match="exact version"):
        read_locked_versions(lock)


def test_environment_check_reports_version_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("pandas==0.0.1\n")
    monkeypatch.setattr(metadata, "version", lambda package: "3.0.3")

    report = inspect_environment(lock)

    assert report["status"] == "FAIL"
    assert report["mismatches"][0]["status"] == "VERSION_MISMATCH"
