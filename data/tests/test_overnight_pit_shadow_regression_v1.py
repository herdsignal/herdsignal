import subprocess

from herd.overnight_pit_shadow_regression_v1 import (
    OUTPUT_TAIL_LIMIT,
    command_contract,
    run_all,
)


def test_regression_contract_covers_all_service_layers():
    assert [row["id"] for row in command_contract()] == [
        "PYTHON_FULL",
        "BACKEND_TEST",
        "FRONTEND_LINT",
        "FRONTEND_TEST",
        "FRONTEND_BUILD",
        "GIT_DIFF_CHECK",
    ]


def test_runner_records_pass_without_shell_execution(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "ok", "")

    report = run_all(tmp_path / "report.json", runner=runner)
    assert report["status"] == "FULL_REGRESSION_PASS"
    assert report["passed_commands"] == report["command_count"] == 6
    assert all(kwargs["capture_output"] for _, kwargs in calls)
    assert all(kwargs["check"] is False for _, kwargs in calls)


def test_runner_fails_closed_and_truncates_output(tmp_path):
    def runner(command, **kwargs):
        code = 1 if command[0] == "npm" else 0
        return subprocess.CompletedProcess(
            command,
            code,
            "x" * (OUTPUT_TAIL_LIMIT + 100),
            "failure" if code else "",
        )

    report = run_all(tmp_path / "report.json", runner=runner)
    assert report["status"] == "FULL_REGRESSION_FAIL"
    assert report["all_commands_passed"] is False
    assert all(
        len(row["stdout_tail"]) <= OUTPUT_TAIL_LIMIT
        for row in report["commands"]
    )
