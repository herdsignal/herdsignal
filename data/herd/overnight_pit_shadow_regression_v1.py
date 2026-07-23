"""야간 PIT 확장 후 전체 회귀 명령을 실행하고 재현 가능한 영수증을 남긴다."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "data/reports/overnight_pit_shadow_regression_v1.json"
OUTPUT_TAIL_LIMIT = 6000


def command_contract() -> list[dict]:
    return [
        {
            "id": "PYTHON_FULL",
            "command": [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "data/tests",
            ],
            "cwd": ROOT,
            "timeout_seconds": 3600,
        },
        {
            "id": "BACKEND_TEST",
            "command": ["./gradlew", "test"],
            "cwd": ROOT / "backend",
            "timeout_seconds": 1800,
        },
        {
            "id": "FRONTEND_LINT",
            "command": ["npm", "run", "lint"],
            "cwd": ROOT / "frontend",
            "timeout_seconds": 900,
        },
        {
            "id": "FRONTEND_TEST",
            "command": ["npm", "test", "--", "--run"],
            "cwd": ROOT / "frontend",
            "timeout_seconds": 1800,
        },
        {
            "id": "FRONTEND_BUILD",
            "command": ["npm", "run", "build"],
            "cwd": ROOT / "frontend",
            "timeout_seconds": 1800,
        },
        {
            "id": "GIT_DIFF_CHECK",
            "command": ["git", "diff", "--check"],
            "cwd": ROOT,
            "timeout_seconds": 120,
        },
    ]


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _tail(value: str) -> str:
    return value[-OUTPUT_TAIL_LIMIT:]


def run_all(
    report_path: Path = REPORT,
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict:
    started = datetime.now(UTC)
    results = []
    for item in command_contract():
        tick = time.monotonic()
        try:
            completed = runner(
                item["command"],
                cwd=item["cwd"],
                text=True,
                capture_output=True,
                timeout=item["timeout_seconds"],
                check=False,
            )
            returncode = completed.returncode
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            status = "PASS" if returncode == 0 else "FAIL"
        except subprocess.TimeoutExpired as error:
            returncode = None
            stdout = error.stdout or ""
            stderr = error.stderr or ""
            status = "TIMEOUT"
        results.append({
            "id": item["id"],
            "status": status,
            "returncode": returncode,
            "duration_seconds": round(time.monotonic() - tick, 3),
            "command": item["command"],
            "cwd": item["cwd"].relative_to(ROOT).as_posix() or ".",
            "stdout_tail": _tail(stdout),
            "stderr_tail": _tail(stderr),
        })
    passed = all(row["status"] == "PASS" for row in results)
    report = {
        "report_version": "OVERNIGHT_PIT_SHADOW_REGRESSION_V1",
        "status": "FULL_REGRESSION_PASS" if passed else "FULL_REGRESSION_FAIL",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "commands": results,
        "passed_commands": sum(row["status"] == "PASS" for row in results),
        "command_count": len(results),
        "all_commands_passed": passed,
        "price_outcomes_opened_by_regression": False,
        "operational_action_ratio": 0.0,
    }
    _atomic_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    result = run_all(args.report)
    print(json.dumps(
        {
            "status": result["status"],
            "passed_commands": result["passed_commands"],
            "command_count": result["command_count"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    raise SystemExit(0 if result["all_commands_passed"] else 1)


if __name__ == "__main__":
    main()
