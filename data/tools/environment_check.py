"""비밀값을 읽지 않고 Python 실행 환경의 재현 가능성을 검사한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from importlib import metadata
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = DATA_ROOT / "requirements.lock"
REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)==([^;\\s]+)$")


def normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_locked_versions(path: Path) -> dict[str, tuple[str, str]]:
    """잠금 파일의 exact requirement만 읽는다."""
    locked: dict[str, tuple[str, str]] = {}
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = REQUIREMENT.fullmatch(line)
        if not match:
            raise ValueError(
                f"{path}:{line_number}: exact version requirement가 아닙니다: {line}"
            )
        package, version = match.groups()
        locked[normalize_package_name(package)] = (package, version)
    if not locked:
        raise ValueError(f"{path}: 잠긴 패키지가 없습니다")
    return locked


def inspect_environment(lock_path: Path = DEFAULT_LOCK) -> dict:
    locked = read_locked_versions(lock_path)
    packages = []
    mismatches = []
    for normalized, (package, expected) in sorted(locked.items()):
        try:
            actual = metadata.version(package)
            status = "MATCH" if actual == expected else "VERSION_MISMATCH"
        except metadata.PackageNotFoundError:
            actual = None
            status = "MISSING"
        item = {
            "package": package,
            "expected": expected,
            "actual": actual,
            "status": status,
        }
        packages.append(item)
        if status != "MATCH":
            mismatches.append(item)

    supported_python = sys.version_info[:2] == (3, 12)
    return {
        "status": "PASS" if supported_python and not mismatches else "FAIL",
        "python": {
            "required": "3.12.x",
            "actual": ".".join(map(str, sys.version_info[:3])),
            "status": "MATCH" if supported_python else "VERSION_MISMATCH",
        },
        "lock_file": str(lock_path.resolve()),
        "lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
        "packages": packages,
        "mismatches": mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--json", action="store_true", help="JSON 형식으로 출력")
    args = parser.parse_args()
    report = inspect_environment(args.lock)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"Python {report['python']['actual']} "
            f"({report['python']['status']}) · "
            f"locked packages {len(report['packages'])} · {report['status']}"
        )
        for mismatch in report["mismatches"]:
            print(
                f"- {mismatch['package']}: "
                f"expected={mismatch['expected']} actual={mismatch['actual']}"
            )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
