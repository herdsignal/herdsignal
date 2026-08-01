import json

from scheduler.operational_reports import write_operational_reports


def test_writes_all_runtime_reports_atomically(tmp_path) -> None:
    reports = write_operational_reports(
        {"schemaVersion": "PROSPECTIVE", "status": "PASS"},
        {"schemaVersion": "READINESS", "status": "BLOCKED"},
        {"schemaVersion": "INTAKE", "status": "BLOCKED_NO_NEW_INPUT"},
        report_dir=tmp_path,
    )

    assert {path.name for path in reports} == {
        "prospective-evidence-latest.json",
        "model-readiness-latest.json",
        "action-research-intake-latest.json",
    }
    assert json.loads((tmp_path / "prospective-evidence-latest.json").read_text())[
        "status"
    ] == "PASS"
    assert not list(tmp_path.glob("*.tmp"))
