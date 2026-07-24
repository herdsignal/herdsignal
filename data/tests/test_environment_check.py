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


def test_environment_check_rejects_removed_pandas_ta(
    tmp_path: Path,
    monkeypatch,
) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("pandas==3.0.3\n")

    def installed_version(package: str) -> str:
        if package in {"pandas", "pandas-ta"}:
            return "3.0.3" if package == "pandas" else "0.4.71b0"
        raise metadata.PackageNotFoundError(package)

    monkeypatch.setattr(metadata, "version", installed_version)

    report = inspect_environment(lock)

    assert report["status"] == "FAIL"
    assert report["forbidden_packages"] == [{
        "package": "pandas-ta",
        "actual": "0.4.71b0",
        "status": "FORBIDDEN_INSTALLED",
    }]
