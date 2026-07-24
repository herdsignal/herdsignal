from pathlib import Path

from tools.storage_audit import audit_storage, generated_stats


def test_generated_stats_excludes_virtualenv_and_nested_cache(tmp_path: Path) -> None:
    cache = tmp_path / "src" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "module.pyc").write_bytes(b"1234")
    nested = cache / "build"
    nested.mkdir()
    (nested / "nested.bin").write_bytes(b"12")
    venv_cache = tmp_path / ".venv" / "lib" / "__pycache__"
    venv_cache.mkdir(parents=True)
    (venv_cache / "ignored.pyc").write_bytes(b"123456")

    stats = generated_stats(tmp_path)

    assert stats == {"directories": 1, "files": 2, "bytes": 6}


def test_storage_audit_never_deletes_and_reports_target_sizes(tmp_path: Path) -> None:
    reports = tmp_path / "data" / "reports"
    reports.mkdir(parents=True)
    report = reports / "result.json"
    report.write_text("{}")

    result = audit_storage(tmp_path)

    assert report.exists()
    assert result["targets"]["data/reports"]["files"] == 1
    assert result["policy"] == "READ_ONLY_NO_AUTOMATIC_DELETE"
